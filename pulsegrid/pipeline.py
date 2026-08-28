"""Single trusted write path for delivery and replay."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Mapping

from .failure import AFTER_BRONZE
from .model import ValidationResult
from .store import EvidenceStore
from .validator import validate


class ReplayIdentityError(ValueError):
    """Raised when a replay attempts to replace the immutable event ID."""


@dataclass(frozen=True)
class IngestOutcome:
    attempt_id: str
    event_id: str
    accepted: bool
    reason_code: str | None = None
    quarantine_id: str | None = None
    gold_inserted: bool = False


class Pipeline:
    def __init__(
        self,
        store: EvidenceStore,
        *,
        validator: Callable[[Mapping[str, Any] | object], ValidationResult] = validate,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        failure_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.validator = validator
        self.clock = clock or (lambda: datetime.now(UTC))
        self.id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self.failure_injector = failure_injector

    def _now(self) -> str:
        return self.clock().isoformat().replace("+00:00", "Z")

    @staticmethod
    def _event_id(envelope: object) -> str:
        if isinstance(envelope, Mapping) and isinstance(envelope.get("event_id"), str):
            return envelope["event_id"]
        return "__invalid_event_id__"

    def ingest(
        self,
        envelope: Mapping[str, Any] | object,
        *,
        delivery_kind: str = "delivery",
        parent_quarantine_id: str | None = None,
    ) -> IngestOutcome:
        if delivery_kind not in {"delivery", "replay"}:
            raise ValueError("delivery_kind must be delivery or replay")
        attempt_id = self.id_factory()
        event_id = self._event_id(envelope)
        envelope_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        created_at = self._now()
        validation = self.validator(envelope)

        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO bronze_attempts VALUES (?, ?, ?, ?, ?, ?)",
                (attempt_id, event_id, envelope_json, delivery_kind, parent_quarantine_id, created_at),
            )
            if self.failure_injector is not None:
                self.failure_injector(AFTER_BRONZE)
            if not validation.accepted:
                quarantine_id = self.id_factory()
                connection.execute(
                    "INSERT INTO quarantine VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (quarantine_id, attempt_id, event_id, validation.status.value, json.dumps(validation.details), envelope_json, created_at),
                )
                return IngestOutcome(attempt_id, event_id, False, validation.status.value, quarantine_id)

            normalized_json = json.dumps(validation.normalized_payload, sort_keys=True, separators=(",", ":"))
            existing_gold = connection.execute(
                "SELECT normalized_json FROM gold_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing_gold is not None and existing_gold["normalized_json"] != normalized_json:
                quarantine_id = self.id_factory()
                connection.execute(
                    "INSERT INTO quarantine VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (quarantine_id, attempt_id, event_id, "IDENTITY_CONFLICT", json.dumps(("event_id already maps to different normalized content",)), envelope_json, created_at),
                )
                return IngestOutcome(attempt_id, event_id, False, "IDENTITY_CONFLICT", quarantine_id)
            connection.execute(
                "INSERT INTO silver_events VALUES (?, ?, ?, ?)",
                (attempt_id, event_id, normalized_json, created_at),
            )
            cursor = connection.execute(
                "INSERT INTO gold_events VALUES (?, ?, ?, ?) ON CONFLICT(event_id) DO NOTHING",
                (event_id, normalized_json, attempt_id, created_at),
            )
            return IngestOutcome(attempt_id, event_id, True, gold_inserted=cursor.rowcount == 1)

    def replay(
        self, quarantine_id: str, corrected_envelope: Mapping[str, Any] | None = None
    ) -> IngestOutcome:
        record = self.store.quarantine_record(quarantine_id)
        original = json.loads(record["envelope_json"])
        original_event_id = record["event_id"]
        candidate = dict(original if corrected_envelope is None else corrected_envelope)
        candidate.setdefault("event_id", original_event_id)
        if candidate["event_id"] != original_event_id:
            raise ReplayIdentityError("replay must preserve the original event_id")
        return self.ingest(
            candidate, delivery_kind="replay", parent_quarantine_id=quarantine_id
        )
