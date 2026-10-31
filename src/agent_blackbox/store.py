import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from .schema import BlackboxError, Event, Run, SCHEMA_VERSION


class Store:
    """Short transactions and independent connections permit concurrent recorders."""

    def __init__(self, path: Path | str = ".blackbox/traces.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise BlackboxError(
                    f"Unsupported database schema {version}; use a compatible release"
                )
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events (run_id TEXT NOT NULL REFERENCES runs(id), seq INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(run_id,seq))"
            )
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save_run(self, run: Run) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs VALUES (?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                (run.id, run.model_dump_json(exclude={"events"})),
            )

    def save_event(self, run_id: str, event: Event) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO events VALUES (?,?,?) ON CONFLICT(run_id,seq) DO UPDATE SET body=excluded.body",
                (run_id, event.seq, event.model_dump_json()),
            )

    def load(self, run_id: str) -> Run:
        with self.connect() as connection:
            row = connection.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise BlackboxError(f"Run {run_id!r} does not exist; use blackbox list")
            payload = json.loads(row[0])
            if payload.get("schema_version") != SCHEMA_VERSION:
                raise BlackboxError(
                    "Incompatible trace schema; use the recording's package version"
                )
            payload["events"] = [
                json.loads(entry[0])
                for entry in connection.execute(
                    "SELECT body FROM events WHERE run_id=? ORDER BY seq", (run_id,)
                )
            ]
        return Run.model_validate(payload)

    def list_runs(self) -> list[dict]:
        with self.connect() as connection:
            return [
                json.loads(row[0])
                for row in connection.execute("SELECT body FROM runs ORDER BY rowid DESC LIMIT 200")
            ]
