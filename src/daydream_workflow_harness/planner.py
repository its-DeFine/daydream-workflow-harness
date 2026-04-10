from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from daydream_workflow_harness.catalog import catalog_inputs, catalog_outputs
from daydream_workflow_harness.ir import WorkflowEdge, WorkflowIR, WorkflowNode, WorkflowSession
from daydream_workflow_harness.schemas import CapabilityCatalog, IntentSpec


@dataclass(slots=True, frozen=True)
class PlannedPath:
    """A narrow rule-based plan choice."""

    name: str
    pipeline_ids: tuple[str, ...]


def _catalog_map(catalog: CapabilityCatalog | Mapping[str, Any] | None) -> Mapping[str, Any]:
    if catalog is None:
        return {}
    if isinstance(catalog, CapabilityCatalog):
        return catalog.entries
    return catalog


def _text_for_intent(intent: IntentSpec) -> str:
    parts = [intent.objective, intent.source, intent.target]
    parts.extend(intent.notes)
    parts.extend(intent.constraints)
    return " ".join(part for part in parts if part).lower()


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _plan_for_intent(intent: IntentSpec) -> PlannedPath:
    text = _text_for_intent(intent)

    if _has_any(text, ("transparent", "mask", "alpha", "remove background", "background removal")):
        return PlannedPath(
            name="transparent",
            pipeline_ids=("video-depth-anything", "transparent"),
        )

    if _has_any(text, ("depth", "depth-conditioned", "depth conditioned", "depth-guided")):
        return PlannedPath(
            name="depth-conditioned",
            pipeline_ids=("video-depth-anything", "longlive", "rife"),
        )

    return PlannedPath(name="direct-restyle", pipeline_ids=("longlive", "rife"))


def _catalog_entry(catalog: Mapping[str, Any], pipeline_id: str) -> Mapping[str, Any]:
    entry = catalog.get(pipeline_id)
    if isinstance(entry, Mapping):
        return entry
    return {}


def _ports_for(catalog: Mapping[str, Any], pipeline_id: str) -> tuple[list[str], list[str]]:
    entry = _catalog_entry(catalog, pipeline_id)
    inputs = list(catalog_inputs(catalog, pipeline_id) or list(entry.get("inputs") or []))
    outputs = list(catalog_outputs(catalog, pipeline_id) or list(entry.get("outputs") or []))
    return inputs, outputs


def _node_for_pipeline(
    pipeline_id: str,
    *,
    node_id: str | None = None,
    catalog: Mapping[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkflowNode:
    entry = _catalog_entry(catalog or {}, pipeline_id)
    node_metadata = {
        "catalog_entry": pipeline_id,
        "pipeline_name": entry.get("name"),
        "plugin_name": entry.get("plugin_name"),
    }
    if metadata:
        node_metadata.update(metadata)
    return WorkflowNode(
        node_id=node_id or pipeline_id,
        kind="pipeline",
        pipeline_id=pipeline_id,
        metadata={key: value for key, value in node_metadata.items() if value is not None},
    )


def _validate_catalog_support(catalog: Mapping[str, Any], pipeline_ids: tuple[str, ...]) -> None:
    missing = [pipeline_id for pipeline_id in pipeline_ids if pipeline_id not in catalog]
    if missing:
        raise ValueError(f"catalog is missing required pipeline(s): {', '.join(missing)}")


def plan_workflow(
    intent: IntentSpec,
    catalog: CapabilityCatalog | Mapping[str, Any] | None = None,
) -> WorkflowIR:
    """Turn a typed intent into a small valid workflow IR.

    The planner is deliberately rule-based. It recognizes a small set of
    workflow families and emits a deterministic workflow graph.
    """

    catalog_map = _catalog_map(catalog)
    path = _plan_for_intent(intent)

    if catalog_map:
        _validate_catalog_support(catalog_map, path.pipeline_ids)

    session = WorkflowSession(
        objective=intent.objective,
        mode=intent.mode,
        prompt=intent.objective,
        parameters={
            "source": intent.source,
            "target": intent.target,
            "realtime": intent.realtime,
            "notes": list(intent.notes),
            "constraints": list(intent.constraints),
        },
    )

    nodes: list[WorkflowNode] = []
    edges: list[WorkflowEdge] = []

    if path.name == "transparent":
        nodes.append(WorkflowNode(node_id="video_source", kind="source", source_mode="video"))
        nodes.append(WorkflowNode(node_id="mask_source", kind="source", source_mode="camera"))
        nodes.append(
            _node_for_pipeline(
                "video-depth-anything",
                node_id="depth",
                catalog=catalog_map,
                metadata={"role": "preprocessor"},
            )
        )
        nodes.append(
            _node_for_pipeline(
                "transparent",
                node_id="transparent",
                catalog=catalog_map,
                metadata={"role": "main"},
            )
        )
        nodes.append(WorkflowNode(node_id="output", kind="sink", sink_mode="webrtc"))

        edges.extend(
            [
                WorkflowEdge("video_source", "video", "transparent", "video"),
                WorkflowEdge("mask_source", "video", "depth", "video"),
                WorkflowEdge("depth", "video", "transparent", "mask"),
                WorkflowEdge("transparent", "video", "output", "video"),
            ]
        )
    elif path.name == "depth-conditioned":
        nodes.append(WorkflowNode(node_id="input", kind="source", source_mode="video"))
        nodes.append(
            _node_for_pipeline(
                "video-depth-anything",
                node_id="depth",
                catalog=catalog_map,
                metadata={"role": "preprocessor"},
            )
        )
        nodes.append(
            _node_for_pipeline(
                "longlive",
                node_id="main",
                catalog=catalog_map,
                metadata={"role": "main"},
            )
        )
        nodes.append(
            _node_for_pipeline(
                "rife",
                node_id="post",
                catalog=catalog_map,
                metadata={"role": "postprocessor"},
            )
        )
        nodes.append(WorkflowNode(node_id="output", kind="sink", sink_mode="webrtc"))

        edges.extend(
            [
                WorkflowEdge("input", "video", "depth", "video"),
                WorkflowEdge("depth", "video", "main", "video"),
                WorkflowEdge("main", "video", "post", "video"),
                WorkflowEdge("post", "video", "output", "video"),
            ]
        )
    else:
        nodes.append(WorkflowNode(node_id="input", kind="source", source_mode="video"))
        nodes.append(
            _node_for_pipeline(
                "longlive",
                node_id="main",
                catalog=catalog_map,
                metadata={"role": "main"},
            )
        )
        nodes.append(
            _node_for_pipeline(
                "rife",
                node_id="post",
                catalog=catalog_map,
                metadata={"role": "postprocessor"},
            )
        )
        nodes.append(WorkflowNode(node_id="output", kind="sink", sink_mode="webrtc"))

        edges.extend(
            [
                WorkflowEdge("input", "video", "main", "video"),
                WorkflowEdge("main", "video", "post", "video"),
                WorkflowEdge("post", "video", "output", "video"),
            ]
        )

    return WorkflowIR(
        session=session,
        nodes=nodes,
        edges=edges,
        metadata={
            "plan_name": path.name,
            "pipeline_ids": list(path.pipeline_ids),
        },
    )

