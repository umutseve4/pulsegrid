from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

from pulsegrid.pipeline import Pipeline, ReplayIdentityError
from pulsegrid.store import EvidenceStore
from pulsegrid.validator import validate

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class M1InvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = EvidenceStore(Path(self.tempdir.name) / "evidence.sqlite3")
        sequence = (f"id-{number:04d}" for number in range(1, 100))
        self.pipeline = Pipeline(
            self.store,
            clock=lambda: datetime(2026, 8, 28, 12, 30, tzinfo=UTC),
            id_factory=lambda: next(sequence),
        )

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def counts(self) -> tuple[int, int, int, int]:
        return tuple(
            self.store.count(table)
            for table in ("bronze_attempts", "quarantine", "silver_events", "gold_events")
        )

    def test_schema_immutability_and_lineage_guards_exist(self) -> None:
        version = self.store.connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()[0]
        objects = {
            (row["type"], row["name"])
            for row in self.store.connection.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'trigger')"
            )
        }
        self.assertEqual("2.0.0", version)
        expected = {
            "bronze_attempts": "immutable_bronze_event_id",
            "quarantine": "immutable_quarantine_event_id",
            "silver_events": "immutable_silver_event_id",
            "gold_events": "immutable_gold_event_id",
        }
        for table, trigger in expected.items():
            self.assertIn(("table", table), objects)
            self.assertIn(("trigger", trigger), objects)
        bronze_foreign_keys = self.store.connection.execute(
            "PRAGMA foreign_key_list(bronze_attempts)"
        ).fetchall()
        self.assertIn(
            ("parent_quarantine_id", "quarantine", "quarantine_id"),
            {(row["from"], row["table"], row["to"]) for row in bronze_foreign_keys},
        )
        quarantine_foreign_keys = self.store.connection.execute(
            "PRAGMA foreign_key_list(quarantine)"
        ).fetchall()
        self.assertIn(
            ("attempt_id", "bronze_attempts", "attempt_id"),
            {(row["from"], row["table"], row["to"]) for row in quarantine_foreign_keys},
        )

    def test_invalid_event_is_quarantined_and_cannot_reach_trusted_layers(self) -> None:
        outcome = self.pipeline.ingest(fixture("invalid_v1.json"))
        self.assertFalse(outcome.accepted)
        self.assertEqual("INVALID", outcome.reason_code)
        self.assertEqual((1, 1, 0, 0), self.counts())

    def test_unknown_version_fails_closed_without_silent_coercion(self) -> None:
        outcome = self.pipeline.ingest(fixture("unknown_v2.json"))
        self.assertEqual(
            "UNKNOWN_VERSION",
            self.store.quarantine_record(outcome.quarantine_id)["reason_code"],
        )
        self.assertEqual((1, 1, 0, 0), self.counts())

    def test_non_finite_reading_fails_closed(self) -> None:
        event = fixture("valid_v1.json")
        event["payload"]["reading"] = float("inf")
        outcome = self.pipeline.ingest(event)
        self.assertFalse(outcome.accepted)
        self.assertEqual("INVALID", outcome.reason_code)
        self.assertEqual((1, 1, 0, 0), self.counts())

    def test_duplicate_delivery_leaves_attempt_evidence_but_one_gold_row(self) -> None:
        event = fixture("valid_v1.json")
        first = self.pipeline.ingest(event)
        second = self.pipeline.ingest(event)
        duplicate_groups = self.store.connection.execute(
            "SELECT event_id FROM gold_events GROUP BY event_id HAVING COUNT(*) > 1"
        ).fetchall()
        self.assertTrue(first.gold_inserted)
        self.assertFalse(second.gold_inserted)
        self.assertEqual((2, 0, 2, 1), self.counts())
        self.assertEqual([], duplicate_groups)

    def test_same_identity_with_different_content_fails_closed(self) -> None:
        first = fixture("valid_v1.json")
        collision = fixture("valid_v1.json")
        collision["payload"]["reading"] = 999
        self.assertTrue(self.pipeline.ingest(first).accepted)
        rejected = self.pipeline.ingest(collision)
        self.assertFalse(rejected.accepted)
        self.assertEqual("IDENTITY_CONFLICT", rejected.reason_code)
        self.assertEqual((2, 1, 1, 1), self.counts())

    def test_replay_preserves_identity_and_uses_normal_validator(self) -> None:
        invalid = fixture("invalid_v1.json")
        validator_spy = Mock(side_effect=validate)
        self.pipeline.validator = validator_spy
        rejected = self.pipeline.ingest(invalid)
        corrected = fixture("valid_v1.json")
        corrected["event_id"] = invalid["event_id"]
        replayed = self.pipeline.replay(rejected.quarantine_id, corrected)
        attempt = self.store.connection.execute(
            "SELECT event_id, delivery_kind, parent_quarantine_id "
            "FROM bronze_attempts WHERE attempt_id = ?",
            (replayed.attempt_id,),
        ).fetchone()
        self.assertEqual(2, validator_spy.call_count)
        self.assertTrue(replayed.accepted)
        self.assertEqual(invalid["event_id"], replayed.event_id)
        self.assertEqual(
            (invalid["event_id"], "replay", rejected.quarantine_id), tuple(attempt)
        )
        self.assertIsNotNone(
            self.store.connection.execute(
                "SELECT 1 FROM gold_events WHERE event_id = ?", (invalid["event_id"],)
            ).fetchone()
        )

    def test_replay_rejects_identity_change_without_writing_evidence(self) -> None:
        rejected = self.pipeline.ingest(fixture("invalid_v1.json"))
        before = self.counts()
        corrected = fixture("valid_v1.json")
        corrected["event_id"] = "evt-replacement-forbidden"
        with self.assertRaises(ReplayIdentityError):
            self.pipeline.replay(rejected.quarantine_id, corrected)
        self.assertEqual(before, self.counts())

    def test_database_rejects_replay_without_quarantine_lineage(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.connection.execute(
                "INSERT INTO bronze_attempts VALUES (?, ?, ?, ?, ?, ?)",
                ("attempt-orphan", "evt-orphan", "{}", "replay", None, "2026-08-28T12:30:00Z"),
            )
        self.assertEqual((0, 0, 0, 0), self.counts())

    def test_transaction_rolls_back_bronze_when_trusted_write_fails(self) -> None:
        self.store.connection.executescript(
            """
            CREATE TEMP TRIGGER inject_silver_failure
            BEFORE INSERT ON silver_events
            BEGIN SELECT RAISE(ABORT, 'injected trusted write failure'); END;
            """
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.pipeline.ingest(fixture("valid_v1.json"))
        self.assertEqual((0, 0, 0, 0), self.counts())

    def test_event_id_update_is_blocked_by_database_trigger(self) -> None:
        outcome = self.pipeline.ingest(fixture("valid_v1.json"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.connection.execute(
                "UPDATE gold_events SET event_id='mutated' WHERE event_id=?",
                (outcome.event_id,),
            )


if __name__ == "__main__":
    unittest.main()
