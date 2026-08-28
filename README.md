# PulseGrid

**A living data reliability laboratory.**

PulseGrid makes a streaming data system visible: events travel through contract validation, medallion processing, quarantine, replay, and recovery while operational metrics explain what the system is doing.

> Status: **M0 — product contract**. No production-readiness or scale claim is made.

## Product promise

A recruiter can open one live URL, watch the pipeline operate, inject a bounded failure, and verify that invalid events are quarantined and recoverable events are replayed without silently corrupting the trusted output.

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

The acceptance contract for M0 is in [`docs/M0_PRODUCT_CONTRACT.md`](docs/M0_PRODUCT_CONTRACT.md).
