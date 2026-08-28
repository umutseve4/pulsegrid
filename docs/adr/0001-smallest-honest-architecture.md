# ADR-0001: Smallest Honest Architecture

- Status: Accepted for staged implementation
- Date: 2026-08-28
- Scope: PulseGrid M1-M3

## Context

PulseGrid must prove reliability behavior before it earns distributed-system or production claims. The first executable architecture therefore optimizes for deterministic evidence, low operational complexity, and a clear upgrade path rather than infrastructure breadth.

## Decision

Build the first verified system as one Python 3.12 service with a framework-independent domain core, a SQLite evidence store, and static HTML/CSS/JavaScript assets served by the same process. GitHub Actions will execute contract, replay, state-transition, and documentation checks. A hosted service is deferred until its deployment and live behavior can be verified in M3.

The single process is a bounded laboratory architecture. It is not presented as a production topology.

## Component boundaries

1. **Deterministic source** emits a fixed-seed sequence of valid events and explicitly selected fault fixtures.
2. **Gateway** assigns ingestion metadata and rejects missing envelope fields before domain processing.
3. **Contract validator** selects the declared schema version and returns structured validation outcomes.
4. **Pipeline core** writes append-only Bronze evidence, derives Silver records, and upserts Gold state.
5. **Quarantine service** preserves rejected payloads, reasons, attempts, and repair metadata.
6. **Replay service** re-enters repaired records through the same validator and trusted path.
7. **Metrics projector** derives operational measurements from persisted timestamps and outcomes.
8. **Read API and static UI** expose topology state, evidence, metrics, and bounded fault controls without mutating trusted state directly.

Domain code must not import the HTTP or persistence adapter. Adapters call the domain core through explicit interfaces so later storage or transport substitutions do not rewrite reliability rules.

## Event lifecycle

```text
created -> received -> bronze-recorded -> validated
  |-> accepted -> silver-derived -> gold-upserted
  `-> rejected -> quarantined -> repaired -> replayed -> validated
```

Every transition appends an evidence record. Invalid events cannot skip validation or enter Silver or Gold. Replayed events return to validation rather than receiving a privileged path.

## Persistence

SQLite is the initial evidence store because it is transactional, inspectable, deterministic in CI, and requires no unverified external infrastructure. Separate tables will represent Bronze events, Silver records, Gold state, quarantine attempts, incident transitions, and metric evidence.

The repository will never imply that Bronze/Silver/Gold table names alone provide a distributed lakehouse. They represent transformation trust levels inside this bounded laboratory.

## Deterministic source and simulation

The default source uses a committed seed and fixture set, making runs reproducible. The two permitted initial faults are one malformed event and one bounded source outage. Simulation output carries `origin=SIMULATION` in data and UI. An outage never causes fabricated external-source events.

## Identity and idempotency

The canonical idempotency key is the immutable `event_id`. Bronze may record multiple delivery attempts, but Gold uses `event_id` as its uniqueness key. A duplicate or replay can update attempt evidence but must not create a second Gold row for the same `event_id`.

## Schema-version strategy

The envelope carries `schema_version` as an explicit string. M1 begins with `1.0.0`. Validators are registered by exact version; an unknown version fails closed into quarantine. Contract changes require a committed schema and compatibility fixture. Silent coercion between versions is forbidden.

## Metric definitions

All windows use UTC timestamps and state their boundaries.

- **Throughput:** accepted events divided by elapsed processing seconds within the selected window.
- **Processing lag:** `gold_committed_at - source_created_at` for an accepted event, reported in milliseconds.
- **Freshness:** `observed_at - latest_gold_source_created_at`, reported in seconds.
- **Error rate:** rejected validation attempts divided by total validation attempts in the selected window.
- **Recovery time:** `recovered_at - detected_at` for one incident, reported in seconds.

A metric is unavailable when its denominator or required timestamp does not exist; the UI must not substitute zero.

## Deployment boundary

M0 proves documentation only. M1 and M2 will prove deterministic behavior in GitHub Actions. M3 may deploy the single service and living UI only after CI is green. A live claim requires a public URL, HTTP success, expected content, and deployed-revision evidence matching the verified commit.

## Rejected alternatives

- **Kafka in M1:** rejected because a broker would add operational surface before the event and replay contracts are proven.
- **Spark or Databricks in M1:** rejected because the bounded data volume does not justify them and their names would overstate the implementation.
- **Kubernetes or multi-service deployment:** rejected because orchestration would not improve the first reliability proof.
- **In-memory-only state:** rejected because restart, replay, and incident evidence must remain inspectable.
- **Browser-only simulation:** rejected because trusted-path invariants need independently executable tests.
- **Autonomous AI remediation:** deferred until logs, metrics, and incident evidence exist; later AI output must remain advisory and evidence-cited.

## Consequences

The first implementation will be easy to run and verify but will not demonstrate broker partitioning, distributed compute, horizontal scaling, or high availability. Those capabilities can be introduced only through later ADRs with executable need and hosted evidence.
