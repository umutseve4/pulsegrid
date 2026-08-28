# PulseGrid

**A living data reliability laboratory.**

PulseGrid makes a streaming data system visible: events travel through contract validation, medallion processing, quarantine, replay, and recovery while operational metrics explain what the system is doing.

> Status: **M1 candidate — executable reliability core**. Local Python 3.12 tests cover the bounded core; hosted CI and merge evidence are required before M1 closes. No deployment, scale, live-demo, or production claim is made.

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
- **M1:** deterministic exact-version validation, atomic SQLite evidence, quarantine, idempotent Gold projection, and identity-preserving replay — candidate
- **M2:** failure injection and operational metrics
- **M3:** living topology UI and hosted demo
- **M4:** bounded AI incident investigator and portfolio evidence

## M1 executable core

The candidate core uses only the Python 3.12 standard library. One transactional path records every delivery attempt in Bronze, then either quarantines rejected input or derives Silver and idempotently projects Gold. Unknown schema versions fail closed. Replays retain the original `event_id`, reference their quarantine record, and return through the same validator and ingest path. Reuse of an existing identity with different normalized content is quarantined as `IDENTITY_CONFLICT`.

Run the deterministic invariant suite:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## M0 evidence

- [Product contract](docs/M0_PRODUCT_CONTRACT.md)
- [Architecture decision record](docs/adr/0001-smallest-honest-architecture.md)
- [Visual storyboard](docs/VISUAL_STORYBOARD.md)
- [Canonical acceptance gates](docs/M0_ACCEPTANCE.md)

Documentation CI proves the M0 documentation surface. M1 Core CI must prove the executable invariant suite on exact GitHub SHAs. Neither workflow establishes deployment, measured throughput, or production readiness.
