# Integrating a workflow

Direct `Recorder.call` integration gives playback immediately. Replay requires explicitly moving external reads behind an IO object and expressing continuation state as JSON.

Implement the `Workflow` protocol from `agent_blackbox.workflow`:

1. Choose a stable `name` and `version`; bump the version when state, call order, or decision semantics change.
2. Return a fresh dictionary from `initial_state()`.
3. In `resume(state, io, recorder)`, validate the state before executing.
4. Before an external response, emit `recorder.emit("checkpoint", "checkpoint-name", state)`.
5. Request external evidence with `io.call("tool.name", **arguments)`.
6. Emit observable decisions using `recorder.emit("decision", "decision-name", result)`.

The built-in `InventoryWorkflow` in `src/agent_blackbox/workflow.py` is a complete example. Its `FixtureIO` records initial tool calls. During replay the engine substitutes `RecordedIO`, which accepts no callback and can only consume stored responses.

For another workflow, register its instance in `WORKFLOWS[workflow.name]` before calling `execute(store, run_id)` in the same Python process. Record its initial execution using a Recorder with matching `workflow` and `workflow_version` fields. The CLI does not import arbitrary plugin modules; embed the engine in your own application for custom workflows.

Tools must take keyword arguments and return JSON-serializable values. Do not put filesystem or network effects directly in `resume`. Do not persist API credentials in checkpoint state. A resumed workflow should copy mutable state before changing it; the engine already deep-copies the selected checkpoint and replayed results.

For model calls, opt in with `capture_models=True`. The bundled OpenAI adapter uses the [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create), requests `store=False`, and extracts text and usage only. `Recorder.model` is a generic explicit recording boundary; only pass observable request/response fields to it, never hidden reasoning.

For sensitive domains:

```python
from agent_blackbox import Recorder
from agent_blackbox.recorder import Redactor

with Recorder(
    "private-tool",
    redactor=Redactor(keys=("customer_email",), secrets=("application-specific-secret",)),
) as recorder:
    recorder.call(
        "lookup", lambda customer_email: {"found": True}, customer_email="person@example.com"
    )
```

The original argument still reaches the tool. The saved argument is `[REDACTED]`; this run supports playback only.
