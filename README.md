# PulseGrid

**A living data reliability laboratory.**

PulseGrid makes a streaming data system visible: events travel through contract validation, medallion processing, quarantine, replay, and recovery while operational metrics explain what the system is doing.

> Status: **M0 — product contract**. No production-readiness, deployment, scale, or live-demo claim is made.

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

- **M0:** product contract, visual storyboard, architecture decisions
- **M1:** deterministic event flow and contract validation
- **M2:** quarantine, failure injection, replay, and operational metrics
- **M3:** living topology UI and hosted demo
- **M4:** bounded AI incident investigator and portfolio evidence

## M0 evidence

- [Product contract](docs/M0_PRODUCT_CONTRACT.md)
- [Architecture decision record](docs/adr/0001-smallest-honest-architecture.md)
- [Visual storyboard](docs/VISUAL_STORYBOARD.md)
- [Canonical acceptance gates](docs/M0_ACCEPTANCE.md)

Hosted CI validates the documentation surface; it does not prove runtime, deployment, or production readiness.
