from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.runtime import (
    ScopeRuntimeError,
    build_headless_start_request,
    ensure_record_node_connected,
    fetch_live_catalog,
    preflight_cloud_runtime,
    record_validate_workflow,
    set_first_source_to_video_file,
    smoke_validate_workflow,
)


def sample_graph_workflow() -> dict[str, object]:
    return {
        "intent": {"objective": "Create a realtime video restyle"},
        "session": {
            "prompt": "Create a realtime video restyle",
            "parameters": {"source": "video"},
        },
        "graph": {
            "nodes": [
                {"id": "input", "type": "source", "source_mode": "video"},
                {"id": "main", "type": "pipeline", "pipeline_id": "longlive"},
                {"id": "post", "type": "pipeline", "pipeline_id": "rife"},
                {"id": "output", "type": "sink"},
            ],
            "edges": [
                {
                    "from": "input",
                    "from_port": "video",
                    "to_node": "main",
                    "to_port": "video",
                    "kind": "stream",
                },
                {
                    "from": "main",
                    "from_port": "video",
                    "to_node": "post",
                    "to_port": "video",
                    "kind": "stream",
                },
                {
                    "from": "post",
                    "from_port": "video",
                    "to_node": "output",
                    "to_port": "video",
                    "kind": "stream",
                },
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


def test_ensure_record_node_connected_adds_record_node_without_mutating():
    workflow = sample_graph_workflow()

    result = ensure_record_node_connected(workflow)

    assert workflow["graph"]["nodes"][-1]["id"] == "output"
    assert all(node.get("type") != "record" for node in workflow["graph"]["nodes"])
    assert any(
        node["id"] == "record" and node["type"] == "record"
        for node in result["graph"]["nodes"]
    )
    assert any(
        edge["from"] == "output"
        and edge["from_port"] == "out"
        and edge["to_node"] == "record"
        and edge["to_port"] == "video"
        and edge["kind"] == "stream"
        for edge in result["graph"]["edges"]
    )


def test_set_first_source_to_video_file_preserves_wrapper_without_mutating():
    wrapped = {"workflow": sample_graph_workflow()}

    result = set_first_source_to_video_file(
        wrapped,
        input_video_path="/tmp/input.mp4",
    )

    first_source = result["workflow"]["graph"]["nodes"][0]
    assert first_source["source_mode"] == "video_file"
    assert first_source["source_name"] == "/tmp/input.mp4"
    assert wrapped["workflow"]["graph"]["nodes"][0]["source_mode"] == "video"


def test_record_validate_workflow_runs_happy_path(monkeypatch, tmp_path):
    calls: list[tuple[str, str, tuple[tuple[str, object], ...] | None]] = []
    recording_path = tmp_path / "recording.mp4"

    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            calls.append(
                ("GET", path, tuple(sorted((query or {}).items())) if query else None)
            )
            if path == "/health":
                return {"status": "healthy"}
            if path == "/api/v1/pipeline/status":
                return {"status": "loaded"}
            raise AssertionError(path)

        def post_json(self, path: str, payload: dict[str, object], *, query=None):
            calls.append(
                ("POST", path, tuple(sorted((query or {}).items())) if query else None)
            )
            if path == "/api/v1/pipeline/load":
                return {"message": "ok"}
            if path == "/api/v1/session/start":
                graph = payload["graph"]
                assert graph["nodes"][0]["source_mode"] == "video_file"
                assert graph["nodes"][0]["source_name"] == "/tmp/input.mp4"
                return {
                    "status": "ok",
                    "graph": True,
                    "sink_node_ids": ["output"],
                    "source_node_ids": ["input"],
                }
            if path == "/api/v1/recordings/headless/start":
                return {"status": "started"}
            if path == "/api/v1/recordings/headless/stop":
                return {"status": "stopped"}
            if path == "/api/v1/session/stop":
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            calls.append(
                ("GET", path, tuple(sorted((query or {}).items())) if query else None)
            )
            if path == "/api/v1/session/frame":
                return b"\xff\xd8fakejpeg"
            if path == "/api/v1/recordings/headless":
                return b"fake-mp4"
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = record_validate_workflow(
        sample_graph_workflow(),
        base_url="http://scope.test",
        input_video_path="/tmp/input.mp4",
        record_seconds=0.01,
        frame_timeout_s=0.01,
        poll_interval_s=0.0,
        output_recording_path=str(recording_path),
    )

    assert result.ok is True
    assert result.recording_bytes == len(b"fake-mp4")
    assert recording_path.read_bytes() == b"fake-mp4"
    assert result.sink_node_id == "output"
    assert result.frame_captured is True
    assert (
        "POST",
        "/api/v1/recordings/headless/start",
        (("node_id", "record"),),
    ) in calls
    assert (
        "POST",
        "/api/v1/recordings/headless/stop",
        (("node_id", "record"),),
    ) in calls
    assert ("GET", "/api/v1/recordings/headless", (("node_id", "record"),)) in calls
    assert any(step == "recording_download" for step in result.steps)


def test_record_validate_workflow_cloud_mode_uses_cloud_status(monkeypatch, tmp_path):
    calls: list[tuple[str, str, tuple[tuple[str, object], ...] | None]] = []
    recording_path = tmp_path / "remote-recording.mp4"

    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            calls.append(
                ("GET", path, tuple(sorted((query or {}).items())) if query else None)
            )
            if path == "/api/v1/cloud/status":
                return {"connected": True}
            if path == "/api/v1/pipeline/status":
                return {"status": "loaded"}
            raise AssertionError(path)

        def post_json(self, path: str, payload: dict[str, object], *, query=None):
            calls.append(
                ("POST", path, tuple(sorted((query or {}).items())) if query else None)
            )
            if path == "/api/v1/pipeline/load":
                return {"message": "ok"}
            if path == "/api/v1/session/start":
                return {"status": "ok", "cloud_mode": True, "sink_node_ids": ["output"]}
            if path == "/api/v1/recordings/headless/start":
                return {"status": "started"}
            if path == "/api/v1/recordings/headless/stop":
                return {"status": "stopped"}
            if path == "/api/v1/session/stop":
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            calls.append(
                ("GET", path, tuple(sorted((query or {}).items())) if query else None)
            )
            if path == "/api/v1/session/frame":
                return b"\xff\xd8fakejpeg"
            if path == "/api/v1/recordings/headless":
                return b"fake-remote-mp4"
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = record_validate_workflow(
        sample_graph_workflow(),
        base_url="http://scope.test",
        record_seconds=0.01,
        frame_timeout_s=0.01,
        poll_interval_s=0.0,
        output_recording_path=str(recording_path),
        runtime_mode="cloud",
    )

    assert result.ok is True
    assert result.cloud_status == {"connected": True}
    assert result.session_start["cloud_mode"] is True
    assert "cloud_status" in result.steps
    assert ("GET", "/health", None) not in calls
    assert ("POST", "/api/v1/pipeline/load", None) in calls
    assert recording_path.read_bytes() == b"fake-remote-mp4"


def test_record_validate_workflow_reports_input_source_metric(monkeypatch, tmp_path):
    recording_path = tmp_path / "remote-recording.mp4"

    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            if path == "/api/v1/cloud/status":
                return {"connected": True}
            if path == "/api/v1/pipeline/status":
                return {"status": "loaded"}
            if path == "/api/v1/session/metrics":
                return {"sessions": {"demo": {"input_source_enabled": False}}}
            raise AssertionError(path)

        def post_json(self, path: str, payload: dict[str, object], *, query=None):
            if path == "/api/v1/pipeline/load":
                return {"message": "ok"}
            if path == "/api/v1/session/start":
                return {"status": "ok", "cloud_mode": True, "sink_node_ids": ["output"]}
            if path == "/api/v1/recordings/headless/start":
                return {"status": "started"}
            if path == "/api/v1/recordings/headless/stop":
                return {"status": "stopped"}
            if path == "/api/v1/session/stop":
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            if path == "/api/v1/session/frame":
                return b"\xff\xd8fakejpeg"
            if path == "/api/v1/recordings/headless":
                return b"fake-remote-mp4"
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = record_validate_workflow(
        sample_graph_workflow(),
        base_url="http://scope.test",
        record_seconds=0.01,
        frame_timeout_s=0.01,
        poll_interval_s=0.0,
        output_recording_path=str(recording_path),
        input_video_path="/tmp/input.mp4",
        runtime_mode="cloud",
    )

    assert result.ok is True
    assert result.input_source_verified is False
    assert result.source_diagnostics["input_video_requested"] is True
    assert result.source_diagnostics["source_nodes"][0]["source_mode"] == "video_file"


def test_record_validate_workflow_cloud_mode_requires_cloud_session(monkeypatch):
    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            if path == "/api/v1/cloud/status":
                return {"connected": True}
            if path == "/api/v1/pipeline/status":
                return {"status": "loaded"}
            raise AssertionError(path)

        def post_json(self, path: str, payload: dict[str, object], *, query=None):
            if path == "/api/v1/pipeline/load":
                return {"message": "ok"}
            if path == "/api/v1/session/start":
                return {"status": "ok", "cloud_mode": False}
            if path == "/api/v1/session/stop":
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = record_validate_workflow(
        sample_graph_workflow(),
        base_url="http://scope.test",
        runtime_mode="cloud",
    )

    assert result.ok is False
    assert "session did not start in cloud_mode=true" in result.errors


def test_record_validate_workflow_reports_failure(monkeypatch):
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

        def post_json(self, path: str, payload: dict[str, object], *, query=None):
            if path == "/api/v1/pipeline/load":
                return {"message": "ok"}
            if path == "/api/v1/session/start":
                return {"status": "ok", "graph": True, "sink_node_ids": ["output"]}
            if path == "/api/v1/recordings/headless/start":
                return {"status": "started"}
            if path == "/api/v1/recordings/headless/stop":
                return {"status": "stopped"}
            if path == "/api/v1/session/stop":
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            if path == "/api/v1/session/frame":
                raise ScopeRuntimeError(
                    "GET /api/v1/session/frame failed with HTTP 404: no frame"
                )
            if path == "/api/v1/recordings/headless":
                raise AssertionError("should not download when frame capture fails")
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = record_validate_workflow(
        sample_graph_workflow(),
        base_url="http://scope.test",
        record_seconds=0.01,
        frame_timeout_s=0.01,
        poll_interval_s=0.0,
    )

    assert result.ok is False
    assert result.errors


def test_record_validate_workflow_rejects_zero_byte_recording(monkeypatch):
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

        def post_json(self, path: str, payload: dict[str, object], *, query=None):
            if path in {
                "/api/v1/pipeline/load",
                "/api/v1/session/start",
                "/api/v1/recordings/headless/start",
                "/api/v1/recordings/headless/stop",
                "/api/v1/session/stop",
            }:
                return {"status": "ok"}
            raise AssertionError(path)

        def get_bytes(self, path: str, *, query=None):
            if path == "/api/v1/session/frame":
                return b"\xff\xd8fakejpeg"
            if path == "/api/v1/recordings/headless":
                return b""
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = record_validate_workflow(
        sample_graph_workflow(),
        base_url="http://scope.test",
        record_seconds=0,
    )

    assert result.ok is False
    assert "recording download returned 0 bytes" in result.errors


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

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = smoke_validate_workflow(
        sample_graph_workflow(), base_url="http://scope.test"
    )

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
            raise ScopeRuntimeError(
                "GET /api/v1/session/frame failed with HTTP 404: no frame"
            )

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

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

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    catalog = fetch_live_catalog(base_url="http://scope.test/")

    assert catalog["source"] == "runtime"
    assert catalog["base_url"] == "http://scope.test"
    assert [entry["pipeline_id"] for entry in catalog["pipelines"]] == ["gray", "rife"]


def test_preflight_cloud_runtime_classifies_ready(monkeypatch):
    calls: list[tuple[str, tuple[tuple[str, object], ...] | None]] = []

    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url.rstrip("/")
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            calls.append(
                (path, tuple(sorted((query or {}).items())) if query else None)
            )
            if path == "/api/v1/cloud/status":
                return {"connected": True, "credentials_configured": True}
            if path == "/api/v1/webrtc/ice-servers":
                return {"iceServers": []}
            if path == "/api/v1/models/status":
                return {"downloaded": True}
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = preflight_cloud_runtime(
        base_url="http://scope.test/",
        pipeline_ids=("gray",),
    )

    assert result.ok is True
    assert result.classification == "ready"
    assert ("/api/v1/models/status", (("pipeline_id", "gray"),)) in calls


def test_preflight_cloud_runtime_classifies_disconnected(monkeypatch):
    class FakeClient:
        def __init__(self, base_url: str, timeout_s: float):
            self.base_url = base_url.rstrip("/")
            self.timeout_s = timeout_s

        def get_json(self, path: str, *, query=None):
            if path == "/api/v1/cloud/status":
                return {"connected": False, "credentials_configured": True}
            raise AssertionError(path)

    monkeypatch.setattr(
        "daydream_workflow_harness.runtime.ScopeRuntimeClient", FakeClient
    )

    result = preflight_cloud_runtime(base_url="http://scope.test/")

    assert result.ok is False
    assert result.classification == "cloud_disconnected"
