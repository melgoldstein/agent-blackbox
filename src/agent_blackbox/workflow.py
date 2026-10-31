from copy import deepcopy
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .recorder import Recorder
from .schema import BlackboxError, Event, Run
from .store import Store


class Workflow(Protocol):
    name: str
    version: str

    def initial_state(self) -> dict: ...
    def resume(self, state: dict, io: "RecordedIO", recorder: Recorder) -> None: ...


class Stock(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sku: str
    available: int = Field(ge=0)
    age_hours: int = Field(ge=0)


class RecordedIO:
    """Only recorded responses are accessible. Never invokes a tool callback."""

    def __init__(
        self, recorder: Recorder, events: list[Event], replacement: tuple[int, Any] | None = None
    ) -> None:
        self.recorder = recorder
        self.events = iter(events)
        self.replacement = replacement

    def call(self, name: str, **arguments: Any) -> Any:
        event = next(self.events, None)
        if event is None:
            raise BlackboxError(
                f"Missing recorded response for {name}; no live fallback is allowed"
            )
        if event.name != name or event.arguments != self.recorder.redactor.snapshot(arguments):
            raise BlackboxError(
                f"Replay mismatch at event {event.seq}: tool name or arguments differ; inspect the recorded event"
            )
        if event.status != "ok":
            raise BlackboxError(
                f"Event {event.seq} is {event.status}; only completed responses can be replayed"
            )
        if event.adapter_version != "1":
            raise BlackboxError(f"Unsupported adapter version at event {event.seq}")
        replaced = self.replacement is not None and self.replacement[0] == event.seq
        result = deepcopy(self.replacement[1] if replaced else event.result)
        self.recorder.emit(
            event.kind,
            name,
            result,
            arguments=arguments,
            origin="replaced" if replaced else "replayed",
        )
        return result

    def finish(self) -> None:
        if next(self.events, None) is not None:
            raise BlackboxError(
                "Workflow did not consume all recorded responses; version or branch mismatch"
            )


class InventoryWorkflow:
    name = "inventory-investigation"
    version = "1"

    def initial_state(self) -> dict:
        return {"step": "lookup", "sku": "PUMP-042", "required": 20}

    def resume(self, state: dict, io: Any, recorder: Recorder) -> None:
        if (
            state.get("step") != "lookup"
            or state.get("sku") != "PUMP-042"
            or state.get("required") != 20
        ):
            raise BlackboxError("Invalid inventory checkpoint")
        recorder.emit("checkpoint", "before-inventory", state)
        stock = Stock.model_validate(io.call("inventory.lookup", sku=state["sku"]))
        if stock.sku != state["sku"]:
            raise BlackboxError("Inventory response SKU does not match checkpoint")
        recorder.emit(
            "decision",
            "fulfillment-plan",
            {
                "action": "expedite_purchase"
                if stock.available < state["required"]
                else "allocate_existing_stock",
                "units": max(0, state["required"] - stock.available),
                "evidence_age_hours": stock.age_hours,
                "explanation": f"Reported {stock.available} units for a {state['required']}-unit order.",
            },
        )


class FixtureIO:
    def __init__(self, recorder: Recorder) -> None:
        self.recorder = recorder

    def call(self, name: str, **arguments: Any) -> Any:
        return self.recorder.call(
            name, lambda sku: {"sku": sku, "available": 0, "age_hours": 48}, **arguments
        )


WORKFLOWS: dict[str, Workflow] = {"inventory-investigation": InventoryWorkflow()}


def demo(store: Store) -> Run:
    workflow = InventoryWorkflow()
    with Recorder(
        workflow.name, store=store, workflow=workflow.name, workflow_version=workflow.version
    ) as recorder:
        with recorder.span("investigate-shortage"):
            workflow.resume(workflow.initial_state(), FixtureIO(recorder), recorder)
    return store.load(recorder.run.id)


def execute(store: Store, run_id: str, replacement: tuple[int, Any] | None = None) -> Run:
    source = store.load(run_id)
    workflow = WORKFLOWS.get(source.workflow or "")
    if workflow is None or workflow.version != source.workflow_version:
        raise BlackboxError("No compatible workflow registered; playback is available with inspect")
    if source.status != "ok":
        raise BlackboxError("Incomplete or failed run; inspect it instead of replaying")
    responses = [event for event in source.events if event.kind in ("tool", "model")]
    if any("[REDACTED]" in event.model_dump_json() for event in source.events):
        raise BlackboxError(
            "Redacted traces support playback only; original inputs cannot be recovered"
        )
    state = workflow.initial_state()
    if replacement:
        target = next((event for event in responses if event.seq == replacement[0]), None)
        if target is None:
            raise BlackboxError("Replacement must select a recorded tool/model response")
        checkpoints = [
            event
            for event in source.events
            if event.kind == "checkpoint" and event.seq < target.seq
        ]
        if not checkpoints:
            raise BlackboxError("No checkpoint precedes this response")
        checkpoint = checkpoints[-1]
        state = deepcopy(checkpoint.result)
        responses = [event for event in responses if event.seq > checkpoint.seq]
    with Recorder(
        source.name,
        store=store,
        workflow=workflow.name,
        workflow_version=workflow.version,
        parent_run=source.id,
        policy="fork" if replacement else "offline",
    ) as recorder:
        io = RecordedIO(recorder, responses, replacement)
        workflow.resume(state, io, recorder)
        io.finish()
    return store.load(recorder.run.id)


def compare(left: Run, right: Run) -> dict:
    original = [event for event in left.events if event.kind != "span"]
    revised = [event for event in right.events if event.kind != "span"]
    changes = []
    for index in range(max(len(original), len(revised))):
        before = original[index] if index < len(original) else None
        after = revised[index] if index < len(revised) else None
        fields = {"kind", "name", "arguments", "result", "status", "error"}
        a = before.model_dump(include=fields) if before else None
        b = after.model_dump(include=fields) if after else None
        if a != b:
            changes.append(
                {
                    "position": index + 1,
                    "original_event": before.seq if before else None,
                    "fork_event": after.seq if after else None,
                    "before": a,
                    "after": b,
                }
            )
    return {
        "original": left.id,
        "revised": right.id,
        "first_divergence": changes[0] if changes else None,
        "changes": changes,
    }
