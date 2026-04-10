from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from daydream_workflow_harness.ir import WorkflowEdge, WorkflowIR, WorkflowNode, WorkflowSession


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _core_payload(payload: Any) -> dict[str, Any]:
    root = _mapping(payload)
    nested = root.get("workflowData")
    if isinstance(nested, Mapping):
        return dict(nested)
    return root


def _first_text(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    for item in items:
        text = _mapping(item).get("text")
        if text:
            return str(text)
    return ""


def _first_timeline_entry(core: dict[str, Any]) -> dict[str, Any]:
    timeline = _mapping(core.get("timeline"))
    entries = timeline.get("entries")
    if isinstance(entries, list) and entries:
        return _mapping(entries[0])
    return {}


def _infer_dimensions(pipelines: list[dict[str, Any]]) -> tuple[int, int]:
    for pipeline in pipelines:
        params = _mapping(pipeline.get("params"))
        width = params.get("width")
        height = params.get("height")
        if isinstance(width, int) and isinstance(height, int):
            return width, height
    return 512, 512


def _pipeline_name_sequence(pipelines: list[dict[str, Any]]) -> list[str]:
    return [str(_mapping(pipeline).get("pipeline_id") or "") for pipeline in pipelines]


def _build_session(payload: dict[str, Any], core: dict[str, Any], pipelines: list[dict[str, Any]]) -> WorkflowSession:
    metadata = _mapping(core.get("metadata"))
    timeline_entry = _first_timeline_entry(core)
    prompts = core.get("prompts") or timeline_entry.get("prompts", [])
    prompt = _first_text(prompts)
    objective = prompt or str(
        payload.get("name") or metadata.get("name") or payload.get("description") or ""
    )
    width, height = _infer_dimensions(pipelines)
    parameters = {
        key: value
        for key, value in {
            "interpolation_method": core.get("interpolation_method"),
            "transition_steps": core.get("transition_steps"),
            "temporal_interpolation_method": core.get("temporal_interpolation_method"),
        }.items()
        if value is not None
    }
    return WorkflowSession(
        objective=objective,
        prompt=prompt,
        width=width,
        height=height,
        parameters=parameters,
    )


def _stage_chain_nodes_and_edges(core: dict[str, Any]) -> tuple[list[WorkflowNode], list[WorkflowEdge]]:
    pipelines = [_mapping(pipeline) for pipeline in core.get("pipelines") or []]
    nodes: list[WorkflowNode] = [WorkflowNode(node_id="input", kind="source", source_mode="video")]
    edges: list[WorkflowEdge] = []

    previous_node = "input"
    for pipeline in pipelines:
        node_id = str(pipeline.get("pipeline_id") or "")
        role = str(pipeline.get("role") or "pipeline")
        nodes.append(
            WorkflowNode(
                node_id=node_id,
                kind="pipeline",
                pipeline_id=node_id,
                metadata={
                    "role": role,
                    "pipeline_version": pipeline.get("pipeline_version"),
                    "params": _mapping(pipeline.get("params")),
                    "source": _mapping(pipeline.get("source")),
                    "loras": list(pipeline.get("loras") or []),
                },
            )
        )
        edges.append(
            WorkflowEdge(
                source_node=previous_node,
                source_port="video",
                target_node=node_id,
                target_port="video",
            )
        )
        previous_node = node_id

    nodes.append(WorkflowNode(node_id="output", kind="sink", sink_mode="webrtc"))
    edges.append(
        WorkflowEdge(
            source_node=previous_node,
            source_port="video",
            target_node="output",
            target_port="video",
        )
    )
    return nodes, edges


def _graph_nodes_and_edges(core: dict[str, Any]) -> tuple[list[WorkflowNode], list[WorkflowEdge]]:
    graph = _mapping(core.get("graph"))
    nodes: list[WorkflowNode] = []
    for raw_node in graph.get("nodes") or []:
        node = _mapping(raw_node)
        node_id = str(node.get("id") or node.get("node_id") or "")
        kind = str(node.get("type") or node.get("kind") or "pipeline")
        metadata = {
            key: value
            for key, value in node.items()
            if key
            not in {
                "id",
                "node_id",
                "type",
                "kind",
                "pipeline_id",
                "source_mode",
                "source_name",
                "sink_mode",
                "sink_name",
            }
        }
        nodes.append(
            WorkflowNode(
                node_id=node_id,
                kind=kind,  # type: ignore[arg-type]
                pipeline_id=str(node.get("pipeline_id") or "") or None,
                source_mode=node.get("source_mode"),
                sink_mode=node.get("sink_mode"),
                metadata=metadata,
            )
        )

    edges = [
        WorkflowEdge(
            source_node=str(_mapping(raw_edge).get("from") or _mapping(raw_edge).get("from_node") or _mapping(raw_edge).get("source_node") or ""),
            source_port=str(_mapping(raw_edge).get("from_port") or _mapping(raw_edge).get("source_port") or ""),
            target_node=str(_mapping(raw_edge).get("to_node") or _mapping(raw_edge).get("to") or _mapping(raw_edge).get("target_node") or ""),
            target_port=str(_mapping(raw_edge).get("to_port") or _mapping(raw_edge).get("target_port") or ""),
            kind=str(_mapping(raw_edge).get("kind") or "stream"),  # type: ignore[arg-type]
        )
        for raw_edge in graph.get("edges") or []
    ]
    return nodes, edges


def reconstruct_workflow(payload: Any) -> WorkflowIR:
    """Reconstruct a published Scope workflow payload into the shared IR."""

    root = _mapping(payload)
    core = _core_payload(payload)
    pipelines = [_mapping(pipeline) for pipeline in core.get("pipelines") or []]
    session = _build_session(root, core, pipelines)

    if core.get("graph"):
        nodes, edges = _graph_nodes_and_edges(core)
    else:
        nodes, edges = _stage_chain_nodes_and_edges(core)

    metadata = {
        "format": core.get("format") or root.get("format"),
        "format_version": core.get("format_version") or root.get("format_version"),
        "workflow_name": _mapping(core.get("metadata")).get("name") or root.get("name"),
        "source_scope_version": _mapping(core.get("metadata")).get("scope_version"),
        "pipelines": _pipeline_name_sequence(pipelines),
    }
    if root.get("slug"):
        metadata["slug"] = root.get("slug")
    if root.get("workflowUrl"):
        metadata["workflow_url"] = root.get("workflowUrl")
    if core.get("graph"):
        metadata["graph"] = _mapping(core.get("graph"))

    return WorkflowIR(session=session, nodes=nodes, edges=edges, metadata=metadata)
