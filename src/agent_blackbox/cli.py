import argparse
import json
import sys
from pathlib import Path

from .schema import BlackboxError
from .store import Store
from .workflow import compare, demo, execute


def main() -> None:
    parser = argparse.ArgumentParser(description="Record, replay, and fork local agent workflows")
    parser.add_argument("--db", type=Path, default=Path(".blackbox/traces.sqlite"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo")
    commands.add_parser("list")
    for verb in ("inspect", "export", "replay", "fork"):
        command = commands.add_parser(verb)
        command.add_argument("run_id")
        if verb == "replay":
            command.add_argument("--offline", action="store_true", required=True)
        if verb == "fork":
            command.add_argument("--replace-event", type=int, required=True)
            command.add_argument("--response", type=Path, required=True)
    command = commands.add_parser("compare")
    command.add_argument("original")
    command.add_argument("revised")
    command = commands.add_parser("serve")
    command.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    try:
        store = Store(arguments.db)
        if arguments.command == "serve":
            from .server import serve
            serve(store, arguments.port)
            return
        if arguments.command == "demo":
            result = demo(store).model_dump()
        elif arguments.command == "list":
            result = store.list_runs()
        elif arguments.command in ("inspect", "export"):
            result = store.load(arguments.run_id).model_dump()
        elif arguments.command == "replay":
            result = execute(store, arguments.run_id).model_dump()
        elif arguments.command == "fork":
            response = json.loads(arguments.response.read_text(encoding="utf-8"))
            result = execute(store, arguments.run_id, (arguments.replace_event, response)).model_dump()
        else:
            result = compare(store.load(arguments.original), store.load(arguments.revised))
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except (BlackboxError, ValueError, OSError) as error:
        print(f"blackbox: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
