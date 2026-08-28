"""Domain values shared by validation and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

SUPPORTED_SCHEMA_VERSION = "1.0.0"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN_VERSION = "UNKNOWN_VERSION"


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    details: tuple[str, ...] = ()
    normalized_payload: dict[str, Any] | None = None

    @property
    def accepted(self) -> bool:
        return self.status is ValidationStatus.VALID
