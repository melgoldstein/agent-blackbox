# Security and threat model

Blackbox is a local development and evaluation tool. It records application
inputs and outputs, so trace data must be treated as sensitive. The project
makes conservative claims: it is not a DLP product, sandbox, encrypted vault,
tamper-proof audit store, or multi-user service.

## Trust boundaries

| Boundary | Trusted by Blackbox | Required operator control |
| --- | --- | --- |
| Recorder callback | The host application and its tool code | Do not pass untrusted callbacks |
| Workflow replay | Registered workflow implementation | Isolate untrusted code in a process/container |
| SQLite database | The local database owner | Protect filesystem permissions and backups |
| Browser server | A local operator on the host | Keep loopback-only; do not expose through a proxy |
| Trace contents | Structured data, not executable code | Treat exports as sensitive untrusted input |

## Primary threats and mitigations

### Secret persistence

Arguments, results, and exceptions are snapshotted through the configured
redactor before SQLite writes. Default rules are best effort and cannot detect
all secrets, encoded credentials, or sensitive prose. Configure application
specific keys and literals, avoid recording unnecessary fields, and do not
commit private traces.

### Unsafe replay

Replay does not execute recorded callbacks, but registered workflow code is
trusted Python and can still access the network or filesystem if it chooses to
do so. Run workflows you do not control in a separate process or container with
restricted credentials and network access.

### Local web exposure

The browser server is intended for loopback use. Host and write-origin checks,
same-origin JSON writes, a restrictive CSP, and text rendering reduce common
browser exposure risks, but there is no remote authentication. Do not bind it
to a public interface or place it behind a public proxy.

### Trace tampering

SQLite files are editable by their owner. Compatibility checks prevent silently
accepting unsupported schemas, but they do not prove historical integrity. Use
filesystem access control and separately managed immutable storage when an
audit-grade record is required.

### Malicious trace content

Exported traces contain data, not executable code, and the browser renders
payloads as text. Consumers importing or transforming traces remain
responsible for validating size, shape, and content before further processing.

## Reporting

Do not include credentials, private traces, or exploit payloads in public issues.
Use GitHub private vulnerability reporting when available; otherwise open an
issue requesting a private contact without sensitive details.
