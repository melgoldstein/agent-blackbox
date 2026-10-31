"""Measure durable recording latency against the exact same uninstrumented callback."""

import json
import platform
import statistics
import tempfile
import time
from pathlib import Path

from agent_blackbox import Recorder, Store

SAMPLES = 500
WARMUP = 50


def lookup(sku: str) -> dict:
    return {"sku": sku, "available": 24, "age_hours": 0}


def summarize(timings: list[float]) -> dict:
    ordered = sorted(timings)
    return {
        "median_us": round(statistics.median(ordered), 3),
        "p95_us": round(ordered[int(0.95 * (len(ordered) - 1))], 3),
    }


def measure(callback) -> dict:
    for _ in range(WARMUP):
        callback()
    timings = []
    for _ in range(SAMPLES):
        started = time.perf_counter_ns()
        callback()
        timings.append((time.perf_counter_ns() - started) / 1000)
    return summarize(timings)


with tempfile.TemporaryDirectory() as directory:
    store = Store(Path(directory) / "benchmark.sqlite")
    plain = measure(lambda: lookup("PUMP-042"))
    with Recorder("benchmark", store=store) as recorder:
        recorded = measure(lambda: recorder.call("inventory.lookup", lookup, sku="PUMP-042"))
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "samples": SAMPLES,
        "warmup": WARMUP,
        "workload": "Synchronous in-memory lookup; recorded path includes two SQLite WAL commits per call; run setup excluded",
        "baseline": plain,
        "recorded": recorded,
        "median_added_us": round(recorded["median_us"] - plain["median_us"], 3),
    }
    print(json.dumps(report, indent=2))
