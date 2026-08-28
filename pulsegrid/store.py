"""Transactional SQLite evidence store for the bounded laboratory."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = "2.0.0"
LEGACY_SCHEMA_VERSION = "1.0.0"

METADATA_DDL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

CORE_DDL = """
CREATE TABLE IF NOT EXISTS quarantine (
    quarantine_id TEXT PRIMARY KEY,
    attempt_id TEXT UNIQUE NOT NULL REFERENCES bronze_attempts(attempt_id),
    event_id TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    details TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bronze_attempts (
    attempt_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    delivery_kind TEXT NOT NULL CHECK (delivery_kind IN ('delivery', 'replay')),
    parent_quarantine_id TEXT REFERENCES quarantine(quarantine_id),
    created_at TEXT NOT NULL,
    CHECK (
        (delivery_kind = 'delivery' AND parent_quarantine_id IS NULL)
        OR (delivery_kind = 'replay' AND parent_quarantine_id IS NOT NULL)
    )
);
CREATE TABLE IF NOT EXISTS silver_events (
    attempt_id TEXT PRIMARY KEY REFERENCES bronze_attempts(attempt_id),
    event_id TEXT NOT NULL,
    normalized_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gold_events (
    event_id TEXT PRIMARY KEY,
    normalized_json TEXT NOT NULL,
    first_attempt_id TEXT NOT NULL REFERENCES bronze_attempts(attempt_id),
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS immutable_bronze_event_id
BEFORE UPDATE OF event_id ON bronze_attempts
BEGIN SELECT RAISE(ABORT, 'event_id is immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_quarantine_event_id
BEFORE UPDATE OF event_id ON quarantine
BEGIN SELECT RAISE(ABORT, 'event_id is immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_silver_event_id
BEFORE UPDATE OF event_id ON silver_events
BEGIN SELECT RAISE(ABORT, 'event_id is immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_gold_event_id
BEFORE UPDATE OF event_id ON gold_events
BEGIN SELECT RAISE(ABORT, 'event_id is immutable'); END;
"""

M2_DDL = """
CREATE TABLE IF NOT EXISTS source_incidents (
    incident_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    degraded_at TEXT NOT NULL,
    recovered_at TEXT,
    CHECK (recovered_at IS NULL OR recovered_at >= degraded_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_incident_per_source
ON source_incidents(source_name) WHERE recovered_at IS NULL;
"""


class EvidenceStore:
    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(database), isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(METADATA_DDL)
        row = self.connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        actual = None if row is None else row["value"]
        if actual not in {None, LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
            self.connection.close()
            raise RuntimeError(f"unsupported evidence schema {actual}")
        if actual is None:
            self.connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + CORE_DDL
                + M2_DDL
                + f"INSERT INTO metadata(key, value) VALUES ('schema_version', '{SCHEMA_VERSION}');\n"
                + "COMMIT;"
            )
        elif actual == LEGACY_SCHEMA_VERSION:
            self.connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + M2_DDL
                + f"UPDATE metadata SET value = '{SCHEMA_VERSION}' WHERE key = 'schema_version';\n"
                + "COMMIT;"
            )
        else:
            self.connection.executescript(CORE_DDL + M2_DDL)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except BaseException:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def count(self, table: str) -> int:
        allowed = {
            "bronze_attempts",
            "quarantine",
            "silver_events",
            "gold_events",
            "source_incidents",
        }
        if table not in allowed:
            raise ValueError(f"unsupported evidence table: {table}")
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def quarantine_record(self, quarantine_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM quarantine WHERE quarantine_id = ?", (quarantine_id,)
        ).fetchone()
        if row is None:
            raise KeyError(quarantine_id)
        return row

    def close(self) -> None:
        self.connection.close()
