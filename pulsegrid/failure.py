"""Deterministic laboratory failure injection."""

from __future__ import annotations


AFTER_BRONZE = "after_bronze"


class InjectedFailure(RuntimeError):
    """Raised only when an explicitly armed laboratory point is reached."""


class FailOnce:
    """Fail exactly once at one named point, then permit retries."""

    def __init__(self, point: str) -> None:
        self.point = point
        self.triggered = False

    def __call__(self, point: str) -> None:
        if point == self.point and not self.triggered:
            self.triggered = True
            raise InjectedFailure(f"deterministic failure at {point}")
