"""Persisted source health and fail-closed reliability metrics."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from .store import EvidenceStore

METRIC_NAMES = (
    "acceptance_rate",
    "quarantine_rate",
    "duplicate_delivery_rate",
    "replay_success_rate",
    "latest_recovery_seconds",
)


class OpenIncidentError(RuntimeError):
    """Raised when a source already has an open incident."""


class NoOpenIncidentError(RuntimeError):
    """Raised when recovery is requested without an open incident."""


@dataclass(frozen=True)
class MetricReading:
    status: str
    value: float | None
    unit: str


class SourceReliability:
    def __init__(
        self,
        store: EvidenceStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(UTC))
        self.id_factory = id_factory or (lambda: str(uuid.uuid4()))

    def _now(self) -> str:
        return self.clock().isoformat().replace("+00:00", "Z")

    def inject_outage(self, source_name: str, reason: str) -> str:
        if not source_name.strip() or not reason.strip():
            raise ValueError("source_name and reason must be non-empty")
        existing = self.store.connection.execute(
            "SELECT 1 FROM source_incidents WHERE source_name = ? AND recovered_at IS NULL",
            (source_name,),
        ).fetchone()
        if existing is not None:
            raise OpenIncidentError(source_name)
        incident_id = self.id_factory()
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO source_incidents VALUES (?, ?, ?, ?, NULL)",
                (incident_id, source_name, reason, self._now()),
            )
        return incident_id

    def recover(self, source_name: str) -> str:
        row = self.store.connection.execute(
            "SELECT incident_id FROM source_incidents "
            "WHERE source_name = ? AND recovered_at IS NULL",
            (source_name,),
        ).fetchone()
        if row is None:
            raise NoOpenIncidentError(source_name)
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE source_incidents SET recovered_at = ? WHERE incident_id = ?",
                (self._now(), row["incident_id"]),
            )
        return str(row["incident_id"])

    def source_state(self, source_name: str) -> str:
        open_incident = self.store.connection.execute(
            "SELECT 1 FROM source_incidents WHERE source_name = ? AND recovered_at IS NULL",
            (source_name,),
        ).fetchone()
        return "degraded" if open_incident is not None else "available"

    @staticmethod
    def _rate(numerator: int, denominator: int) -> MetricReading:
        if denominator == 0:
            return MetricReading("unavailable", None, "ratio")
        return MetricReading("available", numerator / denominator, "ratio")

    def metrics(self) -> dict[str, MetricReading]:
        connection = self.store.connection
        bronze = int(connection.execute("SELECT COUNT(*) FROM bronze_attempts").fetchone()[0])
        accepted = int(connection.execute("SELECT COUNT(*) FROM silver_events").fetchone()[0])
        quarantined = int(connection.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0])
        distinct_accepted = int(
            connection.execute("SELECT COUNT(DISTINCT event_id) FROM silver_events").fetchone()[0]
        )
        replay_attempts = int(
            connection.execute(
                "SELECT COUNT(*) FROM bronze_attempts WHERE delivery_kind = 'replay'"
            ).fetchone()[0]
        )
        accepted_replays = int(
            connection.execute(
                "SELECT COUNT(*) FROM bronze_attempts b "
                "JOIN silver_events s ON s.attempt_id = b.attempt_id "
                "WHERE b.delivery_kind = 'replay'"
            ).fetchone()[0]
        )
        recovered = connection.execute(
            "SELECT degraded_at, recovered_at FROM source_incidents "
            "WHERE recovered_at IS NOT NULL "
            "ORDER BY recovered_at DESC, incident_id DESC LIMIT 1"
        ).fetchone()
        recovery = MetricReading("unavailable", None, "seconds")
        if recovered is not None:
            start = datetime.fromisoformat(recovered["degraded_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(recovered["recovered_at"].replace("Z", "+00:00"))
            recovery = MetricReading("available", (end - start).total_seconds(), "seconds")

        snapshot = {
            "acceptance_rate": self._rate(accepted, bronze),
            "quarantine_rate": self._rate(quarantined, bronze),
            "duplicate_delivery_rate": self._rate(accepted - distinct_accepted, accepted),
            "replay_success_rate": self._rate(accepted_replays, replay_attempts),
            "latest_recovery_seconds": recovery,
        }
        if tuple(snapshot) != METRIC_NAMES:
            raise AssertionError("metric surface changed")
        return snapshot
