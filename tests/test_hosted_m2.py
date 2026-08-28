from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pulsegrid.failure import AFTER_BRONZE, FailOnce, InjectedFailure
from pulsegrid.pipeline import Pipeline
from pulsegrid.reliability import (
    METRIC_NAMES,
    NoOpenIncidentError,
    OpenIncidentError,
    SourceReliability,
)
from pulsegrid.store import EvidenceStore


def event(event_id: str, reading: float | None = 10.0) -> dict:
    return {
        "event_id": event_id,
        "schema_version": "1.0.0",
        "origin": "SIMULATION",
        "payload": {
            "sensor_id": "sensor-a",
            "reading": reading,
            "source_created_at": "2026-08-28T12:00:00Z",
        },
    }


class M2OperationalReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "evidence.sqlite3"
        self.store = EvidenceStore(self.path)
        ids = (f"m2-id-{number:04d}" for number in range(1, 100))
        self.clock_value = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)
        self.pipeline = Pipeline(
            self.store,
            clock=lambda: self.clock_value,
            id_factory=lambda: next(ids),
        )
        self.reliability = SourceReliability(
            self.store,
            clock=lambda: self.clock_value,
            id_factory=lambda: next(ids),
        )

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_evidence_schema_upgrades_additively_to_2_0_0(self) -> None:
        self.store.connection.execute(
            "INSERT INTO bronze_attempts VALUES (?, ?, ?, ?, ?, ?)",
            ("legacy-attempt", "legacy-event", "{}", "delivery", None, "2026-08-28T12:00:00Z"),
        )
        self.store.connection.execute(
            "UPDATE metadata SET value = '1.0.0' WHERE key = 'schema_version'"
        )
        self.store.close()
        self.store = EvidenceStore(self.path)
        version = self.store.connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()[0]
        self.assertEqual("2.0.0", version)
        self.assertEqual(1, self.store.count("bronze_attempts"))
        self.assertIsNotNone(
            self.store.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_incidents'"
            ).fetchone()
        )

    def test_fail_once_rolls_back_then_permits_retry(self) -> None:
        injector = FailOnce(AFTER_BRONZE)
        self.pipeline.failure_injector = injector
        with self.assertRaises(InjectedFailure):
            self.pipeline.ingest(event("evt-failure"))
        self.assertEqual(0, self.store.count("bronze_attempts"))
        outcome = self.pipeline.ingest(event("evt-failure"))
        self.assertTrue(outcome.accepted)
        self.assertEqual(1, self.store.count("gold_events"))

    def test_empty_snapshot_has_exactly_five_unavailable_metrics(self) -> None:
        snapshot = self.reliability.metrics()
        self.assertEqual(METRIC_NAMES, tuple(snapshot))
        self.assertEqual(5, len(snapshot))
        for reading in snapshot.values():
            self.assertEqual("unavailable", reading.status)
            self.assertIsNone(reading.value)

    def test_metric_formulas_use_persisted_attempt_evidence(self) -> None:
        self.pipeline.ingest(event("evt-a"))
        self.pipeline.ingest(event("evt-a"))
        self.pipeline.ingest(event("evt-b", None))
        rejected = self.pipeline.ingest(event("evt-c", None))
        self.pipeline.replay(rejected.quarantine_id, event("evt-c"))
        snapshot = self.reliability.metrics()
        self.assertEqual(3 / 5, snapshot["acceptance_rate"].value)
        self.assertEqual(2 / 5, snapshot["quarantine_rate"].value)
        self.assertEqual(1 / 3, snapshot["duplicate_delivery_rate"].value)
        self.assertEqual(1.0, snapshot["replay_success_rate"].value)
        self.assertEqual("unavailable", snapshot["latest_recovery_seconds"].status)

    def test_controlled_outage_persists_degraded_state(self) -> None:
        incident_id = self.reliability.inject_outage("sensor-feed", "controlled disconnect")
        row = self.store.connection.execute(
            "SELECT * FROM source_incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        self.assertEqual("degraded", self.reliability.source_state("sensor-feed"))
        self.assertEqual("controlled disconnect", row["reason"])
        self.assertIsNone(row["recovered_at"])

    def test_recovery_time_uses_persisted_deterministic_timestamps(self) -> None:
        incident_id = self.reliability.inject_outage("sensor-feed", "controlled disconnect")
        self.clock_value += timedelta(seconds=37)
        self.assertEqual(incident_id, self.reliability.recover("sensor-feed"))
        self.assertEqual("available", self.reliability.source_state("sensor-feed"))
        reading = self.reliability.metrics()["latest_recovery_seconds"]
        self.assertEqual("available", reading.status)
        self.assertEqual(37.0, reading.value)
        self.assertEqual("seconds", reading.unit)

    def test_second_open_outage_fails_closed(self) -> None:
        self.reliability.inject_outage("sensor-feed", "first")
        with self.assertRaises(OpenIncidentError):
            self.reliability.inject_outage("sensor-feed", "second")
        self.assertEqual(1, self.store.count("source_incidents"))

    def test_recovery_without_open_outage_fails_closed(self) -> None:
        with self.assertRaises(NoOpenIncidentError):
            self.reliability.recover("sensor-feed")
        self.assertEqual(0, self.store.count("source_incidents"))


if __name__ == "__main__":
    unittest.main()
