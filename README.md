<h1 align="center">PulseGrid</h1>

<p align="center">
  A streaming pipeline you can break on purpose.<br>
  Bad events are quarantined, repaired events are replayed under their original identity,<br>
  and five fail-closed metrics say <b>"unavailable"</b> rather than inventing a number.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/operational%20metrics-5-FF4D4F?style=flat-square" alt="5 metrics">
  <img src="https://img.shields.io/badge/runtime%20dependencies-0-FF4D4F?style=flat-square" alt="0 dependencies">
  <img src="https://img.shields.io/badge/milestones%20closed-M0%20%C2%B7%20M1%20%C2%B7%20M2-FF4D4F?style=flat-square" alt="M0 M1 M2 closed">
</p>

---

## Run the invariant suite

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

The core uses only the **Python 3.12 standard library** — nothing to install.

## What the system does with an event

```text
Controlled source
  -> Event gateway
  -> Contract validation
       |-> valid: Bronze -> Silver -> Gold -> Live API
       `-> invalid: Quarantine / DLQ -> Repair -> Replay
```

One transactional path records every JSON-compatible delivery attempt in Bronze,
then either quarantines rejected input or derives Silver and idempotently projects
Gold. Unknown schema versions and non-finite readings **fail closed**. Replays
retain the original `event_id`, carry a database-enforced reference to their
quarantine record, and return through the same validator and ingest path. Reuse of
an existing identity with different normalized content is quarantined as
`IDENTITY_CONFLICT`.

M2 adds an explicit `after_bronze` fail-once injection point **inside** that
transaction, a persisted one-open-incident-per-source health model, and exactly
five metrics:

| # | Metric | Behaviour when evidence is missing |
|---|---|---|
| 1 | `acceptance_rate` | `status="unavailable"`, `value=None` |
| 2 | `quarantine_rate` | `status="unavailable"`, `value=None` |
| 3 | `duplicate_delivery_rate` | `status="unavailable"`, `value=None` |
| 4 | `replay_success_rate` | `status="unavailable"`, `value=None` |
| 5 | `latest_recovery_seconds` | derived from persisted incident timestamps via an injectable clock |

A metric never guesses: if its denominator or prerequisite evidence does not exist,
it says so.

## Milestones

- **M0** — product contract, visual storyboard, architecture decisions — *complete*
- **M1** — deterministic exact-version validation, atomic SQLite evidence, quarantine, idempotent Gold projection, identity-preserving replay — *complete*
- **M2** — deterministic failure injection, persisted source incidents, exactly five fail-closed operational metrics — *complete*
- **M3** — living topology UI and hosted demo
- **M4** — bounded AI incident investigator and portfolio evidence

M0, M1 and M2 are closed with exact-`main` hosted evidence:
[Product contract](docs/M0_PRODUCT_CONTRACT.md) ·
[Architecture decision record](docs/adr/0001-smallest-honest-architecture.md) ·
[Visual storyboard](docs/VISUAL_STORYBOARD.md) ·
[Canonical acceptance gates](docs/M0_ACCEPTANCE.md)

## Limits

The hosted demo — open one URL, watch the pipeline operate, inject a bounded
failure, verify quarantine and replay — is a **planned M3 outcome, not a current
capability**.

No deployment, scale, live-demo, concurrency, or production-readiness claim is
made. Documentation CI proves the documentation surface; core CI proves the
executable invariant suite on exact GitHub SHAs. Neither workflow establishes
measured throughput, streaming scale, or concurrency behaviour.

---

Reliability is not a feature you add at the end — it is whether the system tells the truth when it is broken.
