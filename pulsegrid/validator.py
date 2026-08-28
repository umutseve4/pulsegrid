"""Exact-version, fail-closed event contract validation."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

from .model import SUPPORTED_SCHEMA_VERSION, ValidationResult, ValidationStatus

REQUIRED_ENVELOPE_FIELDS = ("event_id", "schema_version", "origin", "payload")
REQUIRED_PAYLOAD_FIELDS = ("sensor_id", "reading", "source_created_at")


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return False
    return True


def validate(envelope: Mapping[str, Any] | object) -> ValidationResult:
    if not isinstance(envelope, Mapping):
        return ValidationResult(ValidationStatus.INVALID, ("envelope must be an object",))

    missing = tuple(field for field in REQUIRED_ENVELOPE_FIELDS if field not in envelope)
    if missing:
        return ValidationResult(
            ValidationStatus.INVALID,
            (f"missing envelope fields: {', '.join(missing)}",),
        )

    event_id = envelope["event_id"]
    version = envelope["schema_version"]
    origin = envelope["origin"]
    payload = envelope["payload"]

    envelope_errors: list[str] = []
    if not _nonempty_string(event_id):
        envelope_errors.append("event_id must be a non-empty string")
    if not _nonempty_string(version):
        envelope_errors.append("schema_version must be a non-empty string")
    if origin != "SIMULATION":
        envelope_errors.append("origin must equal SIMULATION")
    if envelope_errors:
        return ValidationResult(ValidationStatus.INVALID, tuple(envelope_errors))

    if version != SUPPORTED_SCHEMA_VERSION:
        return ValidationResult(
            ValidationStatus.UNKNOWN_VERSION,
            (f"no validator registered for schema_version {version}",),
        )

    if not isinstance(payload, Mapping):
        return ValidationResult(ValidationStatus.INVALID, ("payload must be an object",))

    errors: list[str] = []
    missing_payload = [field for field in REQUIRED_PAYLOAD_FIELDS if field not in payload]
    if missing_payload:
        errors.append(f"missing payload fields: {', '.join(missing_payload)}")
    if "sensor_id" in payload and not _nonempty_string(payload["sensor_id"]):
        errors.append("sensor_id must be a non-empty string")
    if "reading" in payload:
        reading = payload["reading"]
        if (
            isinstance(reading, bool)
            or not isinstance(reading, (int, float))
            or not math.isfinite(reading)
        ):
            errors.append("reading must be a finite number")
    if "source_created_at" in payload and not _valid_utc_timestamp(payload["source_created_at"]):
        errors.append("source_created_at must be an ISO 8601 UTC timestamp ending in Z")
    if errors:
        return ValidationResult(ValidationStatus.INVALID, tuple(errors))

    normalized = {
        "sensor_id": payload["sensor_id"].strip(),
        "reading": payload["reading"],
        "source_created_at": payload["source_created_at"],
    }
    return ValidationResult(ValidationStatus.VALID, normalized_payload=normalized)
