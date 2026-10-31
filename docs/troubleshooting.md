# Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `blackbox` not found | Activate the environment where you installed the package; `python -m agent_blackbox.cli` is equivalent. |
| Run not found | Use the same working directory or specify `blackbox --db path/to/traces.sqlite ...`. |
| No compatible workflow | Direct traces support playback. Register the exact workflow/version in your Python application before replaying. |
| Replay mismatch | Tool name or arguments changed. Inspect the response event; do not add a live fallback. |
| Missing or unconsumed responses | The workflow took a new branch or changed call order. Record a new compatible execution. |
| Redacted trace | Redaction removed required inputs. Playback remains available; secrets cannot be recovered. |
| Replacement validation error | Match the tool's response contract. Inventory requires sku, nonnegative integer available and age_hours, and no extra keys. |
| Run stays running | The process may have exited before completion. Inspect the last event; interrupted runs cannot replay. |
| Database locked | A writer held a transaction longer than 15 seconds. Close external SQLite editors or use a separate database. |
| Port in use | Run `blackbox serve --port 8766`. |
| Browser returns 403 | Open the loopback URL printed by the server. Cross-origin writes and unrecognized Host headers are rejected. |
| Optional provider request fails | Check your SDK installation, credentials, selected model, and provider account. Offline demo needs none of these. |

The UI uses native focusable controls, visible focus outlines, labelled editors, and status announcements. Keyboard users can Tab between controls and activate buttons with Enter/Space. Searching filters the stored event JSON; no query leaves the local server.
