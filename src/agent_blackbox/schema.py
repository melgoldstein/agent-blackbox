from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

SCHEMA_VERSION = 1


class BlackboxError(ValueError):
    """An actionable trace or execution-policy error."""


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seq: int = Field(ge=1)
    parent: int | None = None
    kind: Literal["tool", "model", "span", "checkpoint", "decision"]
    name: str
    arguments: JsonValue = None
    result: JsonValue = None
    status: Literal["running", "ok", "error", "cancelled"] = "running"
    error: str | None = None
    start_ns: int
    duration_ns: int = Field(default=0, ge=0)
    origin: Literal["recorded", "replayed", "replaced", "executed"] = "recorded"
    adapter_version: str = "1"
    usage: dict[str, int] | None = None


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = SCHEMA_VERSION
    id: str
    name: str
    parent_run: str | None = None
    fork_checkpoint: int | None = None
    workflow: str | None = None
    workflow_version: str | None = None
    policy: Literal["record", "offline", "fork"] = "record"
    created_at: str
    status: Literal["running", "ok", "error", "cancelled"] = "running"
    events: list[Event] = Field(default_factory=list)
