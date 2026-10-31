import json
import subprocess
import sys
import types

import pytest

from agent_blackbox import Recorder, Store
from agent_blackbox.adapters.openai import respond
from agent_blackbox.schema import BlackboxError
from agent_blackbox.workflow import demo, execute


def test_abrupt_exit_retains_started_event(tmp_path):
    database = tmp_path / "crash.sqlite"
    program = """
import os, sys
from agent_blackbox import Recorder, Store
with Recorder('crash', store=Store(sys.argv[1])) as recorder:
    recorder.call('interrupted', lambda: os._exit(17))
"""
    process = subprocess.run([sys.executable, "-c", program, str(database)])
    assert process.returncode == 17
    store = Store(database)
    run = store.load(store.list_runs()[0]["id"])
    assert run.status == "running"
    assert run.events[0].status == "running"


def test_redacted_replay_rejected(tmp_path):
    store = Store(tmp_path / "trace.sqlite")
    run = demo(store)
    run.events[2].result["sku"] = "[REDACTED]"
    store.save_event(run.id, run.events[2])
    with pytest.raises(BlackboxError, match="Redacted"):
        execute(store, run.id)


def test_adapter_extracts_only_observable_text(monkeypatch, tmp_path):
    captured = {}

    def create(**request):
        captured.update(request)
        return types.SimpleNamespace(
            output_text="Check stock freshness.",
            model="stub-model",
            usage=types.SimpleNamespace(input_tokens=5, output_tokens=4),
            reasoning="must not persist",
        )

    client = types.SimpleNamespace(responses=types.SimpleNamespace(create=create))
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=lambda: client))
    store = Store(tmp_path / "trace.sqlite")
    with Recorder("model", store=store, capture_models=True) as recorder:
        response = recorder.model(
            "openai.responses", respond, model="stub-model", input="Check stock"
        )
    assert captured["store"] is False
    assert response["usage"]["output_tokens"] == 4
    assert "must not persist" not in store.load(recorder.run.id).model_dump_json()


def test_cli_export_and_missing_run(tmp_path):
    prefix = [sys.executable, "-m", "agent_blackbox.cli", "--db", str(tmp_path / "cli.sqlite")]
    original = json.loads(subprocess.check_output([*prefix, "demo"]))
    exported = json.loads(subprocess.check_output([*prefix, "export", original["id"]]))
    assert original == exported
    missing = subprocess.run([*prefix, "inspect", "missing"], capture_output=True, text=True)
    assert missing.returncode == 2
    assert "blackbox list" in missing.stderr
