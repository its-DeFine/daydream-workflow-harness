from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.runtime import (
    ScopeRuntimeClient,
    ScopeRuntimeError,
    build_headless_start_request,
    fetch_live_catalog,
    smoke_validate_workflow,
)


def sample_graph_workflow() -> dict[str, object]:
    return {
        "intent": {"objective": "Create a realtime video restyle"},
        "session": {"prompt": "Create a realtime video restyle", "parameters": {"source": "video"}},
        "graph": {
            "nodes": [
                {"id": "input", "type": "source", "source_mode": "video"},
                {"id": "main", "type": "pipeline", "pipeline_id": "longlive"},
                {"id": "post", "type": "pipeline", "pipeline_id": "rife"},
                {"id": "output", "type": "sink"},
            ],
            "edges": [
                {"from": "input", "from_port": "video", "to_node": "main", "to_port": "video", "kind": "stream"},
                {"from": "main", "from_port": "video", "to_node": "post", "to_port": "video", "kind": "stream"},
                {"from": "post", "from_port": "video", "to_node": "output", "to_port": "video", "kind": "stream"},
            ],
        },
    }


def test_build_headless_start_request_uses_graph_mode():
    payload = build_headless_start_request(sample_graph_workflow())

    assert payload["input_mode"] == "video"
    assert "graph" in payload
    assert payload["prompts"][0]["text"] == "Create a realtime video restyle"


def test_build_headless_start_request_accepts_authoring_result_wrapper():
    wrapped = {"workflow": sample_graph_workflow()}

    payload = build_headless_start_request(wrapped)

    assert "graph" in payload
    assert payload["input_mode"] == "video"


def test_smoke_validate_workflow_runs_happy_path(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            calls.append(("GET", path))
            if path == "/health":
                return {"status": "healthy"}
            if path == "/api/v1/pipeline/status":
                return {"status": "loaded"}
            raise AssertionError(path)

        def post_json(self, path: str, payload: dict[str, object]):
            calls.append(("POST", path))
            if path == "/api/v1/pipeline/load":
                return {"message": "ok"}
            if path == "/api/v1/session/start":
                return {"status": "ok", "graph": True}
            if path == "/api/v1/session/stop":
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            calls.append(("GET", path))
            if path == "/api/v1/session/frame":
                return b"\xff\xd8fakejpeg"
            raise AssertionError(path)

    monkeypatch.setattr("daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient)

    result = smoke_validate_workflow(sample_graph_workflow(), base_url="http://scope.test")

    assert result.ok is True
    assert result.frame_captured is True
    assert result.frame_bytes > 0
    assert ("POST", "/api/v1/session/start") in calls
    assert ("POST", "/api/v1/session/stop") in calls


def test_smoke_validate_workflow_reports_failure(monkeypatch):
    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            if path == "/health":
                return {"status": "healthy"}
            if path == "/api/v1/pipeline/status":
                return {"status": "loaded"}
            raise AssertionError(path)

        def post_json(self, path: str, payload: dict[str, object]):
            if path in {"/api/v1/pipeline/load", "/api/v1/session/stop"}:
                return {"status": "ok"}
            if path == "/api/v1/session/start":
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            raise ScopeRuntimeError("GET /api/v1/session/frame failed with HTTP 404: no frame")

    monkeypatch.setattr("daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient)

    result = smoke_validate_workflow(
        sample_graph_workflow(),
        base_url="http://scope.test",
        frame_timeout_s=0.01,
        poll_interval_s=0.0,
    )

    assert result.ok is False
    assert result.errors


def test_fetch_live_catalog_normalizes_runtime_schema_map(monkeypatch):
    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url.rstrip("/")
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            assert path == "/api/v1/pipelines/schemas"
            return {
                "pipelines": {
                    "gray": {
                        "id": "gray",
                        "name": "Grayscale",
                        "inputs": ["video"],
                        "outputs": ["video"],
                    },
                    "rife": {
                        "id": "rife",
                        "name": "RIFE",
                        "inputs": ["video"],
                        "outputs": ["video"],
                    },
                }
            }

    monkeypatch.setattr("daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient)

    catalog = fetch_live_catalog(base_url="http://scope.test/")

    assert catalog["source"] == "runtime"
    assert catalog["base_url"] == "http://scope.test"
    assert [entry["pipeline_id"] for entry in catalog["pipelines"]] == ["gray", "rife"]
