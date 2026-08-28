# M0 Product Contract

## Decision

PulseGrid is an observable streaming-data reliability lab, not a static dashboard and not a claim of production-scale infrastructure.

## Primary user story

As a technical recruiter or engineering reviewer, I can eventually watch deterministic events move through a pipeline, inject a controlled fault, observe its operational impact, and verify quarantine and recovery from visible evidence.

## MVP scope

1. One controlled, replayable event source.
2. An ingestion boundary with stable event identifiers.
3. A versioned JSON data contract.
4. Bronze, Silver, and Gold representations.
5. A quarantine/dead-letter path that preserves rejected payloads and reasons.
6. Two failure scenarios: malformed event and source outage.
7. Idempotent replay for eligible quarantined events.
8. Five metrics: throughput, processing lag, freshness, error rate, and recovery time.
9. A living topology UI with loading, empty, degraded, outage, recovery, and healthy states.
10. Hosted verification through GitHub Actions and a public demo URL in later evidence-gated milestones.

## Explicit non-goals for MVP

- Production readiness.
- Unverified throughput or latency claims.
- A multi-region or high-availability deployment.
- A decorative Kafka, Spark, Databricks, or Kubernetes claim without an executable implementation.
- Autonomous AI remediation.
- More than one real external source before deterministic reliability is proven.

## Failure semantics

### Malformed event

- The contract check fails closed.
- The trusted path receives no invalid record.
- The original payload, event ID, schema version, rejection reason, and timestamp remain inspectable in quarantine.

### Source outage

- The UI enters an explicit degraded state.
- The last successful event time remains visible.
- A deterministic simulation may continue only when visibly labelled `SIMULATION`.
- Recovery records the outage duration and resumes without fabricating external-source events.

## Replay contract

- Replay preserves the original event ID and adds replay metadata.
- Duplicate delivery must not duplicate the trusted Gold result.
- A replay is successful only when contract validation passes and the expected Gold state is verified.
- Failed replays remain quarantined with a new attempt record.

## Visual contract

- Obsidian environment with electric-cyan healthy flow, ultraviolet processing, amber degraded state, and crimson incident state.
- Events are visible as moving particles; motion must communicate state rather than decorate it.
- Selecting a node exposes input/output counts, current status, contract version, and latest evidence.
- The incident timeline can replay the transition: detect -> quarantine -> diagnose -> repair -> replay -> recover.
- Reduced-motion and keyboard-accessible alternatives are required.

## Architecture boundary

[ADR-0001](adr/0001-smallest-honest-architecture.md) defines the smallest planned executable architecture, event lifecycle, persistence boundary, idempotency rule, schema strategy, metric formulas, deployment boundary, and rejected alternatives.

## Acceptance source of truth

The only canonical M0 checklist is [`M0_ACCEPTANCE.md`](M0_ACCEPTANCE.md). This document intentionally does not duplicate that checklist.
