from __future__ import annotations

import copy
import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from daydream_workflow_harness.catalog import catalog_entries_from_payload


def _ensure_trailing_slashless(url: str) -> str:
    return url.rstrip("/")


def _extract_workflow_payload(payload: dict[str, Any]) -> dict[str, Any]:
    workflow = payload.get("workflow")
    if isinstance(workflow, dict):
        return workflow
    return payload


def _copy_workflow_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(payload)


def _pipeline_ids_from_workflow(workflow: dict[str, Any]) -> list[str]:
    graph = workflow.get("graph") or {}
    nodes = graph.get("nodes") or []
    pipeline_ids: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "pipeline":
            continue
        pipeline_id = node.get("pipeline_id")
        if isinstance(pipeline_id, str) and pipeline_id and pipeline_id not in pipeline_ids:
            pipeline_ids.append(pipeline_id)
    return pipeline_ids


def _graph_nodes_and_edges(
    workflow: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    graph = workflow.get("graph") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    return list(nodes), list(edges)


def _sink_node_ids_from_workflow(workflow: dict[str, Any]) -> list[str]:
    nodes, _ = _graph_nodes_and_edges(workflow)
    sink_ids: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "sink":
            continue
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id and node_id not in sink_ids:
            sink_ids.append(node_id)
    return sink_ids


def set_first_source_to_video_file(
    workflow_payload: dict[str, Any],
    *,
    input_video_path: str,
) -> dict[str, Any]:
    """Return a copied workflow payload whose first source node reads a video file."""

    copied = _copy_workflow_payload(workflow_payload)
    workflow = _extract_workflow_payload(copied)
    graph = workflow.get("graph")
    if not isinstance(graph, dict):
        raise ValueError("workflow does not contain a graph")

    nodes = list(graph.get("nodes") or [])
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "source":
            continue
        node["source_mode"] = "video_file"
        node["source_name"] = input_video_path
        graph["nodes"] = nodes
        workflow["graph"] = graph
        return copied
    raise ValueError("workflow graph has no source nodes")


def ensure_record_node_connected(
    workflow_payload: dict[str, Any],
    *,
    record_node_id: str = "record",
    sink_node_id: str | None = None,
) -> dict[str, Any]:
    """Return a copied workflow payload with a record node wired from a sink.

    The input payload is never mutated. When the payload is a wrapper with a
    top-level ``workflow`` key, the same wrapper shape is preserved.
    """

    copied = _copy_workflow_payload(workflow_payload)
    workflow = _extract_workflow_payload(copied)
    graph = workflow.get("graph")
    if not isinstance(graph, dict):
        raise ValueError("workflow does not contain a graph")

    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])

    sink_ids = _sink_node_ids_from_workflow(workflow)
    if not sink_ids:
        raise ValueError("workflow graph has no sink nodes")

    selected_sink_id = sink_node_id or sink_ids[0]
    if selected_sink_id not in sink_ids:
        raise ValueError(f"unknown sink node: {selected_sink_id!r}")

    record_node = None
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("id") == record_node_id:
            record_node = node
            break

    if record_node is not None:
        if record_node.get("type") != "record":
            raise ValueError(
                f"node {record_node_id!r} already exists and is not a record node"
            )
    else:
        nodes.append({"id": record_node_id, "type": "record"})

    required_edge = {
        "from": selected_sink_id,
        "from_port": "out",
        "to_node": record_node_id,
        "to_port": "video",
        "kind": "stream",
    }
    edge_exists = any(
        isinstance(edge, dict)
        and edge.get("from") == required_edge["from"]
        and edge.get("from_port") == required_edge["from_port"]
        and edge.get("to_node") == required_edge["to_node"]
        and edge.get("to_port") == required_edge["to_port"]
        and edge.get("kind", "stream") == required_edge["kind"]
        for edge in edges
    )
    if not edge_exists:
        edges.append(required_edge)

    graph["nodes"] = nodes
    graph["edges"] = edges
    workflow["graph"] = graph
    return copied


def _prompts_from_workflow(workflow: dict[str, Any]) -> list[dict[str, Any]] | None:
    session = workflow.get("session") or {}
    prompt = session.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return [{"text": prompt, "weight": 1}]

    intent = workflow.get("intent") or {}
    objective = intent.get("objective") or intent.get("goal")
    if isinstance(objective, str) and objective.strip():
        return [{"text": objective, "weight": 1}]
    return None


def _input_mode_from_workflow(workflow: dict[str, Any]) -> str:
    session = workflow.get("session") or {}
    if isinstance(session.get("input_mode"), str):
        return session["input_mode"]

    parameters = session.get("parameters") or {}
    source = parameters.get("source")
    if isinstance(source, str) and source.lower() in {
        "video",
        "camera",
        "ndi",
        "spout",
        "syphon",
        "video_file",
    }:
        return "video"

    graph = workflow.get("graph") or {}
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "source":
            continue
        mode = node.get("source_mode")
        if isinstance(mode, str) and mode.lower() in {
            "video",
            "camera",
            "ndi",
            "spout",
            "syphon",
            "video_file",
        }:
            return "video"
    return "text"


def build_headless_start_request(workflow_payload: dict[str, Any]) -> dict[str, Any]:
    workflow = _extract_workflow_payload(workflow_payload)
    graph = workflow.get("graph")
    prompts = _prompts_from_workflow(workflow)
    input_mode = _input_mode_from_workflow(workflow)

    if isinstance(graph, dict):
        payload: dict[str, Any] = {
            "graph": graph,
            "input_mode": input_mode,
        }
        if prompts is not None:
            payload["prompts"] = prompts
        return payload

    pipeline_ids = _pipeline_ids_from_workflow(workflow)
    if len(pipeline_ids) != 1:
        raise ValueError("workflow has no graph and does not resolve to a single pipeline")

    payload = {
        "pipeline_id": pipeline_ids[0],
        "input_mode": input_mode,
    }
    if prompts is not None:
        payload["prompts"] = prompts
    return payload


class ScopeRuntimeError(RuntimeError):
    pass


@dataclass(slots=True)
class ScopeRuntimeClient:
    base_url: str = "http://127.0.0.1:8000"
    timeout_s: float = 30.0

    def __post_init__(self) -> None:
        self.base_url = _ensure_trailing_slashless(self.base_url)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> tuple[int, dict[str, str], bytes]:
        url = f"{self.base_url}{path}"
        if query:
            encoded = parse.urlencode({k: v for k, v in query.items() if v is not None})
            url = f"{url}?{encoded}"

        headers = {"Accept": accept}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout_s) as resp:
                body = resp.read()
                return resp.status, dict(resp.headers.items()), body
        except error.HTTPError as exc:
            body = exc.read()
            raise ScopeRuntimeError(
                f"{method} {path} failed with HTTP {exc.code}: {body.decode('utf-8', errors='ignore')}"
            ) from exc
        except TimeoutError as exc:
            raise ScopeRuntimeError(f"{method} {path} timed out after {self.timeout_s}s") from exc
        except error.URLError as exc:
            raise ScopeRuntimeError(f"{method} {path} failed: {exc}") from exc

    def get_json(self, path: str, *, query: dict[str, Any] | None = None) -> dict[str, Any]:
        _, _, body = self._request("GET", path, query=query)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _, _, body = self._request("POST", path, payload=payload, query=query)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def get_bytes(self, path: str, *, query: dict[str, Any] | None = None) -> bytes:
        _, _, body = self._request("GET", path, query=query, accept="*/*")
        return body


@dataclass(slots=True)
class SmokeValidationResult:
    ok: bool
    base_url: str
    pipeline_ids: list[str] = field(default_factory=list)
    start_payload: dict[str, Any] = field(default_factory=dict)
    health: dict[str, Any] = field(default_factory=dict)
    cloud_status: dict[str, Any] = field(default_factory=dict)
    pipeline_status: dict[str, Any] = field(default_factory=dict)
    session_start: dict[str, Any] = field(default_factory=dict)
    frame_captured: bool = False
    frame_bytes: int = 0
    steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "base_url": self.base_url,
            "pipeline_ids": list(self.pipeline_ids),
            "start_payload": dict(self.start_payload),
            "health": dict(self.health),
            "cloud_status": dict(self.cloud_status),
            "pipeline_status": dict(self.pipeline_status),
            "session_start": dict(self.session_start),
            "frame_captured": self.frame_captured,
            "frame_bytes": self.frame_bytes,
            "steps": list(self.steps),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class RecordValidationResult:
    ok: bool
    base_url: str
    record_node_id: str = "record"
    sink_node_id: str = ""
    pipeline_ids: list[str] = field(default_factory=list)
    start_payload: dict[str, Any] = field(default_factory=dict)
    health: dict[str, Any] = field(default_factory=dict)
    cloud_status: dict[str, Any] = field(default_factory=dict)
    pipeline_status: dict[str, Any] = field(default_factory=dict)
    session_start: dict[str, Any] = field(default_factory=dict)
    frame_captured: bool = False
    frame_bytes: int = 0
    recording_bytes: int = 0
    recording_path: str = ""
    input_video_path: str = ""
    steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "base_url": self.base_url,
            "record_node_id": self.record_node_id,
            "sink_node_id": self.sink_node_id,
            "pipeline_ids": list(self.pipeline_ids),
            "start_payload": dict(self.start_payload),
            "health": dict(self.health),
            "cloud_status": dict(self.cloud_status),
            "pipeline_status": dict(self.pipeline_status),
            "session_start": dict(self.session_start),
            "frame_captured": self.frame_captured,
            "frame_bytes": self.frame_bytes,
            "recording_bytes": self.recording_bytes,
            "recording_path": self.recording_path,
            "input_video_path": self.input_video_path,
            "steps": list(self.steps),
            "errors": list(self.errors),
        }


def fetch_live_catalog(
    *,
    base_url: str = "http://127.0.0.1:8000",
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Fetch pipeline schemas from a running Scope server and normalize them."""

    client = ScopeRuntimeClient(base_url=base_url, timeout_s=timeout_s)
    payload = client.get_json("/api/v1/pipelines/schemas")
    entries = sorted(
        catalog_entries_from_payload(payload),
        key=lambda entry: str(entry.get("pipeline_id") or entry.get("id") or ""),
    )
    return {
        "source": "runtime",
        "base_url": client.base_url,
        "pipelines": entries,
    }


def smoke_validate_workflow(
    workflow_payload: dict[str, Any],
    *,
    base_url: str = "http://127.0.0.1:8000",
    timeout_s: float = 30.0,
    load_timeout_s: float = 30.0,
    frame_timeout_s: float = 10.0,
    poll_interval_s: float = 0.5,
    runtime_mode: str = "local",
) -> SmokeValidationResult:
    workflow = _extract_workflow_payload(workflow_payload)
    client = ScopeRuntimeClient(base_url=base_url, timeout_s=timeout_s)
    result = SmokeValidationResult(ok=False, base_url=base_url)

    session_started = False
    try:
        if runtime_mode == "cloud":
            result.cloud_status = client.get_json("/api/v1/cloud/status")
            result.steps.append("cloud_status")
            if not result.cloud_status.get("connected"):
                raise ScopeRuntimeError("cloud runtime is not connected")
        else:
            result.health = client.get_json("/health")
            result.steps.append("health")

        pipeline_ids = _pipeline_ids_from_workflow(workflow)
        result.pipeline_ids = list(pipeline_ids)
        if pipeline_ids:
            client.post_json("/api/v1/pipeline/load", {"pipeline_ids": pipeline_ids})
            result.steps.append("pipeline_load")

            deadline = time.time() + load_timeout_s
            last_status: dict[str, Any] = {}
            while time.time() < deadline:
                last_status = client.get_json("/api/v1/pipeline/status")
                status = last_status.get("status")
                if status == "loaded":
                    result.pipeline_status = last_status
                    result.steps.append("pipeline_loaded")
                    break
                time.sleep(poll_interval_s)
            else:
                result.pipeline_status = last_status
                raise ScopeRuntimeError(
                    f"pipeline did not reach loaded state within {load_timeout_s}s"
                )

        start_payload = build_headless_start_request(workflow)
        result.start_payload = start_payload
        result.session_start = client.post_json("/api/v1/session/start", start_payload)
        result.steps.append("session_start")
        session_started = True
        if runtime_mode == "cloud" and result.session_start.get("cloud_mode") is not True:
            raise ScopeRuntimeError("session did not start in cloud_mode=true")

        deadline = time.time() + frame_timeout_s
        last_frame_error = ""
        while time.time() < deadline:
            try:
                frame = client.get_bytes("/api/v1/session/frame", query={"quality": 85})
                if frame:
                    result.frame_captured = True
                    result.frame_bytes = len(frame)
                    result.steps.append("frame_capture")
                    result.ok = True
                    return result
            except ScopeRuntimeError as exc:
                last_frame_error = str(exc)
            time.sleep(poll_interval_s)

        raise ScopeRuntimeError(
            last_frame_error or f"no frame available within {frame_timeout_s}s"
        )
    except ScopeRuntimeError as exc:
        result.errors.append(str(exc))
        return result
    finally:
        if session_started:
            try:
                client.post_json("/api/v1/session/stop", {})
                result.steps.append("session_stop")
            except ScopeRuntimeError as exc:
                result.errors.append(f"failed to stop headless session: {exc}")


def record_validate_workflow(
    workflow_payload: dict[str, Any],
    *,
    base_url: str = "http://127.0.0.1:8000",
    timeout_s: float = 30.0,
    load_timeout_s: float = 30.0,
    frame_timeout_s: float = 10.0,
    record_seconds: float = 2.0,
    poll_interval_s: float = 0.5,
    record_node_id: str = "record",
    sink_node_id: str | None = None,
    output_recording_path: str | None = None,
    input_video_path: str | None = None,
    runtime_mode: str = "local",
) -> RecordValidationResult:
    client = ScopeRuntimeClient(base_url=base_url, timeout_s=timeout_s)
    result = RecordValidationResult(
        ok=False,
        base_url=base_url,
        record_node_id=record_node_id,
        input_video_path=input_video_path or "",
    )

    session_started = False
    recording_started = False
    recording_finalized = False
    try:
        prepared_workflow = ensure_record_node_connected(
            workflow_payload,
            record_node_id=record_node_id,
            sink_node_id=sink_node_id,
        )
        if input_video_path is not None:
            prepared_workflow = set_first_source_to_video_file(
                prepared_workflow,
                input_video_path=input_video_path,
            )
        prepared_workflow_inner = _extract_workflow_payload(prepared_workflow)
        sink_ids = _sink_node_ids_from_workflow(prepared_workflow_inner)
        result.sink_node_id = sink_node_id or sink_ids[0]

        if runtime_mode == "cloud":
            result.cloud_status = client.get_json("/api/v1/cloud/status")
            result.steps.append("cloud_status")
            if not result.cloud_status.get("connected"):
                raise ScopeRuntimeError("cloud runtime is not connected")
        else:
            result.health = client.get_json("/health")
            result.steps.append("health")

        pipeline_ids = _pipeline_ids_from_workflow(prepared_workflow_inner)
        result.pipeline_ids = list(pipeline_ids)
        if pipeline_ids:
            client.post_json("/api/v1/pipeline/load", {"pipeline_ids": pipeline_ids})
            result.steps.append("pipeline_load")

            deadline = time.time() + load_timeout_s
            last_status: dict[str, Any] = {}
            while time.time() < deadline:
                last_status = client.get_json("/api/v1/pipeline/status")
                status = last_status.get("status")
                if status == "loaded":
                    result.pipeline_status = last_status
                    result.steps.append("pipeline_loaded")
                    break
                time.sleep(poll_interval_s)
            else:
                result.pipeline_status = last_status
                raise ScopeRuntimeError(
                    f"pipeline did not reach loaded state within {load_timeout_s}s"
                )

        result.start_payload = build_headless_start_request(prepared_workflow)
        result.session_start = client.post_json(
            "/api/v1/session/start",
            result.start_payload,
        )
        result.steps.append("session_start")
        session_started = True
        if runtime_mode == "cloud" and result.session_start.get("cloud_mode") is not True:
            raise ScopeRuntimeError("session did not start in cloud_mode=true")

        client.post_json(
            "/api/v1/recordings/headless/start",
            {},
            query={"node_id": record_node_id},
        )
        result.steps.append("recording_start")
        recording_started = True

        deadline = time.time() + frame_timeout_s
        last_frame_error = ""
        while time.time() < deadline:
            try:
                frame = client.get_bytes(
                    "/api/v1/session/frame",
                    query={"quality": 85, "sink_node_id": result.sink_node_id},
                )
                if frame:
                    result.frame_captured = True
                    result.frame_bytes = len(frame)
                    result.steps.append("frame_capture")
                    break
            except ScopeRuntimeError as exc:
                last_frame_error = str(exc)
            time.sleep(poll_interval_s)

        if not result.frame_captured:
            try:
                frame = client.get_bytes(
                    "/api/v1/session/frame",
                    query={"quality": 85, "sink_node_id": result.sink_node_id},
                )
                if frame:
                    result.frame_captured = True
                    result.frame_bytes = len(frame)
                    result.steps.append("frame_capture")
            except ScopeRuntimeError as exc:
                last_frame_error = str(exc)

        if not result.frame_captured:
            raise ScopeRuntimeError(
                last_frame_error or f"no frame available within {frame_timeout_s}s"
            )

        if record_seconds > 0:
            time.sleep(record_seconds)

        client.post_json(
            "/api/v1/recordings/headless/stop",
            {},
            query={"node_id": record_node_id},
        )
        result.steps.append("recording_stop")

        recording_bytes = client.get_bytes(
            "/api/v1/recordings/headless",
            query={"node_id": record_node_id},
        )
        result.recording_bytes = len(recording_bytes)
        result.steps.append("recording_download")
        recording_finalized = True
        if not recording_bytes:
            raise ScopeRuntimeError("recording download returned 0 bytes")

        if output_recording_path:
            output_path = Path(output_recording_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(recording_bytes)
            result.recording_path = str(output_path)
        else:
            with tempfile.NamedTemporaryFile(
                suffix=".mp4", prefix="scope_recording_", delete=False
            ) as tmp:
                tmp.write(recording_bytes)
                result.recording_path = tmp.name

        result.ok = True
        return result
    except (ScopeRuntimeError, ValueError) as exc:
        result.errors.append(str(exc))
        return result
    finally:
        if recording_started and not recording_finalized:
            try:
                client.post_json(
                    "/api/v1/recordings/headless/stop",
                    {},
                    query={"node_id": record_node_id},
                )
                result.steps.append("recording_stop")
            except ScopeRuntimeError as exc:
                result.errors.append(f"failed to stop recording: {exc}")
        if session_started:
            try:
                client.post_json("/api/v1/session/stop", {})
                result.steps.append("session_stop")
            except ScopeRuntimeError as exc:
                result.errors.append(f"failed to stop headless session: {exc}")
