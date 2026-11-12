# Design decisions

## Durability before throughput

Each event start and completion is committed separately. This makes interrupted
runs inspectable and avoids fabricating success after a process death. The
trade-off is measurable write latency, currently about 8.8 ms per recorded tool
call on the documented benchmark host.

## Explicit replay contracts

Replay is limited to versioned workflows with JSON checkpoint state and
structured tool/model calls. This excludes arbitrary stack-frame replay and
automatic recovery, but makes mismatched call order, arguments, versions, and
missing responses fail closed instead of silently producing a plausible result.

## Redaction is irreversible

Persisted snapshots are redacted before SQLite writes. A redacted run remains
available for inspection but cannot be replayed because the original arguments
or results cannot be recovered. This favors minimizing secret retention over
maximizing replay coverage.

## Local-first storage

SQLite keeps the demo dependency-light and makes the ownership boundary clear.
The package does not claim to provide distributed tracing, encrypted storage,
immutable audit records, or multi-user authorization. Those concerns belong at
the deployment boundary or in optional integrations.

## Comparison is structural

Fork comparison aligns the original and revised event sequences using explicit
fork lineage and reports changed fields. It is not causal inference and does not
attempt to align unrelated runs or prove that one evidence item caused a
decision.
