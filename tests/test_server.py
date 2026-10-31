import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from agent_blackbox import Store
from agent_blackbox.server import make_server


@pytest.fixture
def server(tmp_path):
    instance = make_server(Store(tmp_path / "traces.sqlite"), 0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{instance.server_port}"
    instance.shutdown()
    instance.server_close()
    thread.join()


def request(server, path, payload):
    with urlopen(
        Request(
            server + path,
            json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Origin": server},
        )
    ) as response:
        return json.load(response)


def test_browser_api_roundtrip(server):
    with urlopen(server) as response:
        assert b"Execution waterfall" in response.read()
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    original = request(server, "/api/demo", {})
    fork = request(
        server,
        "/api/fork",
        {
            "run_id": original["id"],
            "event": 3,
            "response": {"sku": "PUMP-042", "available": 24, "age_hours": 0},
        },
    )
    assert fork["parent_run"] == original["id"]
    assert fork["events"][-1]["result"]["action"] == "allocate_existing_stock"
    with urlopen(server + f"/api/compare?left={original['id']}&right={fork['id']}") as response:
        assert len(json.load(response)["changes"]) == 2


def test_cross_origin_write_blocked(server):
    with pytest.raises(HTTPError) as caught:
        urlopen(
            Request(
                server + "/api/demo",
                b"{}",
                headers={"Content-Type": "application/json", "Origin": "https://example.com"},
            )
        )
    assert caught.value.code == 403


def test_invalid_json_has_actionable_error(server):
    with pytest.raises(HTTPError) as caught:
        request(server, "/api/fork", {})
    assert caught.value.code == 400
    assert "run_id" in json.load(caught.value)["error"]
