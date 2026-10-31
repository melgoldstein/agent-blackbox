# Trace export v1

`blackbox export RUN_ID` writes a single JSON object validated by `Run` and `Event` in `schema.py`. It contains no executable code. Import is not currently implemented.

Run fields: `schema_version`, `id`, `name`, `parent_run`, `fork_checkpoint`, `workflow`, `workflow_version`, `policy`, `created_at`, `status`, `events`. The optional `fork_checkpoint` is a sequence number in the parent run, identifying the restored state and comparison suffix.

`schema_version` must be 1. IDs are UUID4 hex strings. `created_at` is timezone-aware UTC ISO 8601. Policy is `record`, `offline`, or `fork`; status is `running`, `ok`, `error`, or `cancelled`. `ok` means the program completed, not that its business decision was correct.

Event fields:

| Field | Meaning |
| --- | --- |
| seq / parent | Start-order integer, optional parent sequence within this run |
| kind | tool, model, span, checkpoint, decision |
| name | Application-defined event name |
| arguments / result | Redacted JSON values; checkpoint state is in result |
| status / error | Completion state and redacted exception type/message |
| start_ns | Unix epoch nanoseconds |
| duration_ns | Monotonic elapsed nanoseconds, excluding own persistence |
| origin | recorded, replayed, replaced, executed |
| adapter_version | Recording contract version, currently 1 |
| usage | Optional provider-reported integer token counts |

No estimated price or cost field is emitted. Replay events get new sequence numbers and timing measurements; they are not original latency measurements. Use `parent_run` to locate the original recording. Unknown database and trace schema versions fail instead of silently migrating. Never edit version fields to bypass compatibility checks.
