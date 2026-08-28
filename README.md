# PulseGrid

**A living data reliability laboratory.**

PulseGrid makes a streaming data system visible: events travel through contract validation, medallion processing, quarantine, replay, and recovery while operational metrics explain what the system is doing.

> Status: **M2 complete — deterministic operational reliability**. M0, M1, and M2 are closed with exact-main hosted evidence. M3 is next. No deployment, scale, live-demo, concurrency, or production-readiness claim is made.

## Product promise

A recruiter can eventually open one hosted demo, watch the pipeline operate, inject a bounded failure, and verify that invalid events are quarantined and recoverable events are replayed without silently corrupting trusted output. That hosted demo is a planned M3 outcome, not a current capability.

## Planned flow

```text
Controlled source
  -> Event gateway
  -> Contract validation
       |-> valid: Bronze -> Silver -> Gold -> Live API
       `-> invalid: Quarantine / DLQ -> Repair -> Replay
```

## Evidence-first milestones

- **M0:** product contract, visual storyboard, architecture decisions — complete
- **M1:** deterministic exact-version validation, atomic SQLite evidence, quarantine, idempotent Gold projection, and identity-preserving replay — complete
- **M2:** deterministic failure injection, persisted source incidents, and exactly five fail-closed operational metrics — complete
- **M3:** living topology UI and hosted demo
- **M4:** bounded AI incident investigator and portfolio evidence

## Executable laboratory

The core uses only the Python 3.12 standard library. One transactional path records every JSON-compatible delivery attempt in Bronze, then either quarantines rejected input or derives Silver and idempotently projects Gold. Unknown schema versions and non-finite readings fail closed. Replays retain the original `event_id`, carry a database-enforced reference to their quarantine record, and return through the same validator and ingest path. Reuse of an existing identity with different normalized content is quarantined as `IDENTITY_CONFLICT`.

M2 adds an explicit `after_bronze` fail-once injection point inside that transaction, a persisted one-open-incident-per-source health model, and exactly five metrics:

1. `acceptance_rate`
2. `quarantine_rate`
3. `duplicate_delivery_rate`
4. `replay_success_rate`
5. `latest_recovery_seconds`

A metric returns `status="unavailable"` and `value=None` whenever its denominator or prerequisite evidence does not exist. Recovery duration is derived from persisted incident timestamps supplied through an injectable clock.

Run the deterministic invariant suite:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## M0 evidence

- [Product contract](docs/M0_PRODUCT_CONTRACT.md)
- [Architecture decision record](docs/adr/0001-smallest-honest-architecture.md)
- [Visual storyboard](docs/VISUAL_STORYBOARD.md)
- [Canonical acceptance gates](docs/M0_ACCEPTANCE.md)

Documentation CI proves the documentation surface. Core CI proves the executable invariant suite on exact GitHub SHAs. Neither workflow establishes deployment, measured throughput, streaming scale, concurrency behavior, or production readiness.
