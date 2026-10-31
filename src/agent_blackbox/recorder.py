import asyncio
import json
import re
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4

from .schema import BlackboxError, Event, Run
from .store import Store

T = TypeVar("T")


class Redactor:
    def __init__(self, secrets: tuple[str, ...] = (), keys: tuple[str, ...] = ()) -> None:
        self.secrets = tuple(secret for secret in secrets if secret)
        self.keys = {"password", "api_key", "authorization", "token", "secret", *keys}

    def clean(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: "[REDACTED]" if key.lower() in self.keys else self.clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return re.sub(r"\b(?:sk-|ghp_)[A-Za-z0-9_-]{12,}", "[REDACTED]", value)
        return value

    def snapshot(self, value: Any) -> Any:
        return self.clean(json.loads(json.dumps(value, allow_nan=False)))


class Recorder:
    def __init__(self, name: str, *, store: Store | None = None, redactor: Redactor | None = None,
                 capture_models: bool = False, workflow: str | None = None,
                 workflow_version: str | None = None, parent_run: str | None = None,
                 policy: str = "record") -> None:
        self.store = store or Store()
        self.redactor = redactor or Redactor()
        self.capture_models = capture_models
        self.run = Run(id=uuid4().hex, name=self.redactor.clean(name), parent_run=parent_run,
                       workflow=workflow, workflow_version=workflow_version, policy=policy,
                       created_at=datetime.now(timezone.utc).isoformat())
        self._parent: ContextVar[int | None] = ContextVar(f"parent-{self.run.id}", default=None)
        self._lock = threading.Lock()
        self._sequence = 0
        self._active = False

    def __enter__(self) -> "Recorder":
        if self._active or self._sequence:
            raise BlackboxError("Recorder instances are single-use")
        self._active = True
        self.store.save_run(self.run)
        return self

    def __exit__(self, kind: Any, error: Any, traceback: Any) -> None:
        self.run.status = "cancelled" if isinstance(error, asyncio.CancelledError) else "error" if error else "ok"
        self.store.save_run(self.run)
        self._active = False

    async def __aenter__(self) -> "Recorder":
        return self.__enter__()

    async def __aexit__(self, kind: Any, error: Any, traceback: Any) -> None:
        self.__exit__(kind, error, traceback)

    def _begin(self, kind: str, name: str, arguments: Any, origin: str = "recorded") -> Event:
        if not self._active:
            raise BlackboxError("Use Recorder inside a with or async with block")
        clean_arguments = self.redactor.snapshot(arguments)
        with self._lock:
            self._sequence += 1
            event = Event(seq=self._sequence, parent=self._parent.get(), kind=kind,
                          name=self.redactor.clean(name), arguments=clean_arguments,
                          start_ns=time.time_ns(), origin=origin)
            self.store.save_event(self.run.id, event)
        return event

    @contextmanager
    def _event(self, kind: str, name: str, arguments: Any = None, origin: str = "recorded") -> Iterator[Event]:
        event = self._begin(kind, name, arguments, origin)
        token = self._parent.set(event.seq)
        started = time.perf_counter_ns()
        try:
            yield event
            event.status = "ok"
        except BaseException as error:
            event.status = "cancelled" if isinstance(error, asyncio.CancelledError) else "error"
            event.error = self.redactor.clean(f"{type(error).__name__}: {error}")
            raise
        finally:
            self._parent.reset(token)
            event.duration_ns = time.perf_counter_ns() - started
            self.store.save_event(self.run.id, event)

    def span(self, name: str) -> Any:
        return self._event("span", name)

    def call(self, name: str, function: Callable[..., T], **arguments: Any) -> T:
        if self.run.policy != "record":
            raise BlackboxError("Live callbacks are blocked in replay/fork; use workflow RecordedIO")
        with self._event("tool", name, arguments) as event:
            result = function(**arguments)
            event.result = self.redactor.snapshot(result)
            return result

    async def acall(self, name: str, function: Callable[..., Awaitable[T]], **arguments: Any) -> T:
        if self.run.policy != "record":
            raise BlackboxError("Live async callbacks are blocked in replay/fork")
        with self._event("tool", name, arguments) as event:
            result = await function(**arguments)
            event.result = self.redactor.snapshot(result)
            return result

    def emit(self, kind: str, name: str, result: Any, *, arguments: Any = None, origin: str = "executed") -> int:
        with self._event(kind, name, arguments, origin) as event:
            event.result = self.redactor.snapshot(result)
            return event.seq

    def model(self, name: str, function: Callable[..., dict], **request: Any) -> dict:
        if not self.capture_models:
            raise BlackboxError("Model recording requires capture_models=True")
        if self.run.policy != "record":
            raise BlackboxError("Live model calls are blocked during replay/fork")
        with self._event("model", name, request) as event:
            response = function(**request)
            event.result = self.redactor.snapshot(response)
            event.usage = response.get("usage")
            return response
