import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from agent_blackbox import Recorder, Store
from agent_blackbox.recorder import Redactor
from agent_blackbox.schema import BlackboxError
from agent_blackbox.workflow import RecordedIO, compare, demo, execute


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "traces.sqlite")


def test_vertical_slice_and_isolation(store):
    original = demo(store)
    snapshot = original.model_dump()
    replayed = execute(store, original.id)
    assert compare(original, replayed)["changes"] == []
    forked = execute(store, original.id, (3, {"sku": "PUMP-042", "available": 24, "age_hours": 0}))
    assert forked.parent_run == original.id
    assert forked.events[-1].result["action"] == "allocate_existing_stock"
    assert original.events[-1].result["action"] == "expedite_purchase"
    assert compare(original, forked)["first_divergence"]["original_event"] == 3
    assert store.load(original.id).model_dump() == snapshot


def test_nested_spans(store):
    with Recorder("nested", store=store) as recorder:
        with recorder.span("outer"):
            with recorder.span("inner"):
                recorder.call("leaf", lambda: 7)
    events = store.load(recorder.run.id).events
    assert [event.parent for event in events] == [None, 1, 2]


def test_concurrent_runs(store):
    with ThreadPoolExecutor(max_workers=6) as pool:
        runs = list(pool.map(lambda _: demo(store), range(12)))
    assert len({run.id for run in runs}) == 12
    assert all([event.seq for event in run.events] == [1, 2, 3, 4] for run in runs)


def test_async_tasks_and_cancellation(store):
    async def scenario():
        async with Recorder("async", store=store) as recorder:

            async def worker(index):
                with recorder.span(f"task-{index}"):
                    return await recorder.acall("sleep", asyncio.sleep, delay=0.001, result=index)

            assert await asyncio.gather(*(worker(i) for i in range(8))) == list(range(8))
        events = store.load(recorder.run.id).events
        parents = {event.seq: event.name for event in events if event.kind == "span"}
        assert all(
            parents[event.parent] == f"task-{event.result}"
            for event in events
            if event.kind == "tool"
        )
        cancelled = Recorder("cancelled", store=store)
        with pytest.raises(asyncio.CancelledError):
            async with cancelled:

                async def stop():
                    raise asyncio.CancelledError()

                await cancelled.acall("stop", stop)
        assert store.load(cancelled.run.id).status == "cancelled"
        assert store.load(cancelled.run.id).events[0].status == "cancelled"

    asyncio.run(scenario())


def test_redaction_before_storage_including_exceptions(store):
    recorder = Recorder("private", store=store, redactor=Redactor(secrets=("sensitive-value",)))

    def fail(**arguments):
        raise RuntimeError("sensitive-value")

    with pytest.raises(RuntimeError):
        with recorder:
            recorder.call("fail", fail, api_key="never-store-this", note="sensitive-value")
    raw = store.path.read_bytes()
    assert b"sensitive-value" not in raw and b"never-store-this" not in raw
    event = store.load(recorder.run.id).events[0]
    assert event.status == "error" and "[REDACTED]" in event.error


def test_offline_callback_blocked(store):
    touched = []
    with Recorder("offline", store=store, policy="offline") as recorder:
        with pytest.raises(BlackboxError, match="blocked"):
            recorder.call("write", lambda: touched.append(1))
    assert touched == []


def test_response_matching_and_missing(store):
    original = demo(store)
    with Recorder("offline", store=store, policy="offline") as recorder:
        with pytest.raises(BlackboxError, match="mismatch"):
            RecordedIO(recorder, [original.events[2]]).call("inventory.lookup", sku="WRONG")
        with pytest.raises(BlackboxError, match="Missing"):
            RecordedIO(recorder, []).call("missing")
        with pytest.raises(BlackboxError, match="consume"):
            RecordedIO(recorder, [original.events[2]]).finish()


def test_schema_version_rejected(store):
    run = demo(store)
    with store.connect() as connection:
        payload = json.loads(
            connection.execute("SELECT body FROM runs WHERE id=?", (run.id,)).fetchone()[0]
        )
        payload["schema_version"] = 999
        connection.execute("UPDATE runs SET body=? WHERE id=?", (json.dumps(payload), run.id))
    with pytest.raises(BlackboxError, match="schema"):
        store.load(run.id)


def test_rollback_on_interrupted_write(store):
    run = demo(store)
    before = store.load(run.id)
    with pytest.raises(KeyboardInterrupt):
        with store.connect() as connection:
            connection.execute("DELETE FROM events WHERE run_id=?", (run.id,))
            raise KeyboardInterrupt()
    assert store.load(run.id) == before


def test_unsupported_workflow_and_replacement(store):
    run = demo(store)
    with pytest.raises(BlackboxError, match="select"):
        execute(store, run.id, (2, {}))
    with pytest.raises(ValueError):
        execute(store, run.id, (3, {"sku": "PUMP-042", "available": -4, "age_hours": 0}))
    run.workflow_version = "999"
    store.save_run(run)
    with pytest.raises(BlackboxError, match="compatible"):
        execute(store, run.id)


def test_model_capture_is_opt_in(store):
    with Recorder("model", store=store) as recorder:
        with pytest.raises(BlackboxError, match="capture_models"):
            recorder.model("model", lambda: {})
    with Recorder("model", store=store, capture_models=True) as recorder:
        recorder.model(
            "fake",
            lambda **_: {"text": "ok", "usage": {"input_tokens": 3, "output_tokens": 1}},
            input="hello",
        )
    assert store.load(recorder.run.id).events[0].usage["input_tokens"] == 3
