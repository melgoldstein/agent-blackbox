"""Reproducible CLI demonstration; writes real trace artifacts to the selected directory."""
import json
import subprocess
import sys
from pathlib import Path

destination = Path(sys.argv[1] if len(sys.argv) > 1 else ".blackbox/demo")
destination.mkdir(parents=True, exist_ok=True)


def command(*arguments: str) -> dict:
    response = subprocess.check_output([sys.executable, "-m", "agent_blackbox.cli", "--db",
                                       str(destination / "traces.sqlite"), *arguments], text=True)
    return json.loads(response)


original = command("demo")
replayed = command("replay", original["id"], "--offline")
target = next(event["seq"] for event in original["events"] if event["kind"] == "tool")
corrected = Path(__file__).with_name("corrected-stock.json")
forked = command("fork", original["id"], "--replace-event", str(target), "--response", str(corrected))
comparison = command("compare", original["id"], forked["id"])
for name, artifact in (("original", original), ("replay", replayed), ("fork", forked), ("comparison", comparison)):
    (destination / f"{name}.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
print(json.dumps({"original": original["id"], "replay": replayed["id"], "fork": forked["id"],
                  "changed_events": len(comparison["changes"])}, indent=2))
