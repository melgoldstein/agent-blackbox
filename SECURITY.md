# Security

This is a local development tool. Trace contents can contain sensitive application inputs. Default redaction is best effort, and database files are not encrypted. Never commit private recordings.

See [the threat model](docs/threat-model.md) for trust boundaries, replay
isolation guidance, browser exposure risks, and the limits of trace integrity.

Report security issues through GitHub's private vulnerability reporting when enabled. If unavailable, open an issue requesting a private contact without including secrets or exploit payloads. Do not publish private traces in an issue.
