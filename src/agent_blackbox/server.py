import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlparse, parse_qs

from .store import Store
from .workflow import compare, demo, execute

LOGGER = logging.getLogger(__name__)


def make_server(store: Store, port: int = 8765) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *arguments: object) -> None:
            LOGGER.debug(format, *arguments)

        def send(self, status: int, payload: bytes, content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def dispatch(self, write: bool = False) -> None:
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") not in (expected, f"localhost:{self.server.server_port}"):
                self.send(403, b'{"error":"Invalid local host"}')
                return
            if write and (
                self.headers.get("Origin")
                not in (f"http://{expected}", f"http://localhost:{self.server.server_port}")
                or self.headers.get("Content-Type") != "application/json"
            ):
                self.send(403, b'{"error":"Same-origin JSON requests required"}')
                return
            try:
                route = urlparse(self.path)
                if write:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 65536:
                        raise ValueError("Request must be between 1 and 65536 bytes")
                    payload = json.loads(self.rfile.read(length))
                    if route.path == "/api/demo":
                        result = demo(store).model_dump()
                    elif route.path == "/api/fork":
                        result = execute(
                            store, payload["run_id"], (int(payload["event"]), payload["response"])
                        ).model_dump()
                    elif route.path == "/api/replay":
                        result = execute(store, payload["run_id"]).model_dump()
                    else:
                        self.send(404, b'{"error":"Unknown endpoint"}')
                        return
                elif route.path == "/api/runs":
                    result = store.list_runs()
                elif route.path.startswith("/api/runs/"):
                    result = store.load(route.path.rsplit("/", 1)[1]).model_dump()
                elif route.path == "/api/compare":
                    query = parse_qs(route.query)
                    result = compare(store.load(query["left"][0]), store.load(query["right"][0]))
                elif route.path in ("/", "/app.js", "/style.css"):
                    name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[
                        route.path
                    ]
                    mime = {
                        "/": "text/html; charset=utf-8",
                        "/app.js": "text/javascript",
                        "/style.css": "text/css",
                    }[route.path]
                    self.send(200, files("agent_blackbox").joinpath("web", name).read_bytes(), mime)
                    return
                else:
                    self.send(404, b'{"error":"Unknown endpoint"}')
                    return
                self.send(200, json.dumps(result).encode())
            except (ValueError, KeyError, TypeError) as error:
                self.send(400, json.dumps({"error": str(error)}).encode())
            except Exception:
                LOGGER.exception("Debugger request failed")
                self.send(500, b'{"error":"Internal failure; inspect the server log"}')

        def do_GET(self) -> None:
            self.dispatch()

        def do_POST(self) -> None:
            self.dispatch(write=True)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(store: Store, port: int) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with make_server(store, port) as server:
        LOGGER.info("Debugger ready at http://127.0.0.1:%s (Ctrl+C to stop)", server.server_port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
