from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
    source = (intent.source or "").lower()

    if _has_any(
        text,
        ("grayscale", "greyscale", "gray scale", "grey scale", "black and white", "monochrome"),
    ):
        return PlannedPath(name="grayscale-preview", pipeline_ids=("gray",))

    if _has_any(text, ("passthrough", "identity", "preview", "smoke", "diagnostic")):
        return PlannedPath(name="passthrough-preview", pipeline_ids=("passthrough",))

    if _has_any(text, ("face swap", "faceswap", "swap face")):
        return PlannedPath(name="face-swap", pipeline_ids=("deeplivecam-faceswap", "rife"))

    if _has_any(text, ("transparent", "background removal", "remove background", "alpha mask")):
        return PlannedPath(
            name="background-removal",
            pipeline_ids=("video-depth-anything", "transparent"),
        )

    if _has_any(
        text,
        (
            "preserved background",
            "preserve background",
            "background preserved",
            "subject preserving",
            "subject preserve",
        ),
    ):
        return PlannedPath(
            name="masked-subject-preserving-restyle",
            pipeline_ids=("yolo_mask", "longlive"),
        )

    if _has_any(
        text,
        (
            "text logo",
            "logo restyler",
            "text restyling",
            "word daydream",
            "logo",
            "typography",
        ),
    ):
        return PlannedPath(
            name="scribble-logo-restyle",
            pipeline_ids=("scribble", "longlive", "rife"),
        )

    if _has_any(text, ("flux", "klein", "promptswitcher")):
        return PlannedPath(name="flux-experimental", pipeline_ids=("flux-klein",))

    if _has_any(text, ("pixel art", "lucasarts-era", "lucasarts era")):
        return PlannedPath(name="pixel-art-restyle", pipeline_ids=("longlive",))

    if source == "text":
        if _has_any(text, ("butterfly", "dissolve", "slime", "morph", "portal")):
            return PlannedPath(
                name="text-restyle-with-frame-interpolation",
                pipeline_ids=("longlive", "rife"),
            )
        return PlannedPath(name="text-generation", pipeline_ids=("longlive",))

    if _has_any(text, ("depth", "depth-conditioned", "depth conditioned", "depth-guided")):
        return PlannedPath(
            name="depth-conditioned",
            pipeline_ids=("video-depth-anything", "longlive", "rife"),
        )

    if _has_any(
        text,
        (
            "ghibli",
            "cyborg",
            "dystopian",
            "particle emitter",
            "electric",
            "cat",
            "flowers",
            "looking around",
            "grass",
            "adjustable",
        ),
    ):
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


def _pipeline_specs_for_path(path: PlannedPath) -> list[tuple[str, str, dict[str, Any]]]:
    if path.name == "depth-conditioned":
        return [
            ("depth", "video-depth-anything", {"role": "preprocessor"}),
            ("main", "longlive", {"role": "main"}),
            ("post", "rife", {"role": "postprocessor"}),
        ]
    if path.name == "background-removal":
        return [
            ("depth", "video-depth-anything", {"role": "preprocessor"}),
            ("main", "transparent", {"role": "main"}),
        ]
    if path.name == "masked-subject-preserving-restyle":
        return [
            ("mask", "yolo_mask", {"role": "preprocessor"}),
            ("main", "longlive", {"role": "main"}),
        ]
    if path.name == "scribble-logo-restyle":
        return [
            ("scribble", "scribble", {"role": "preprocessor"}),
            ("main", "longlive", {"role": "main"}),
            ("post", "rife", {"role": "postprocessor"}),
        ]
    if path.name == "grayscale-preview":
        return [("main", "gray", {"role": "main"})]
    if path.name == "passthrough-preview":
        return [("main", "passthrough", {"role": "main"})]
    if path.name == "face-swap":
        return [
            ("main", "deeplivecam-faceswap", {"role": "main"}),
            ("post", "rife", {"role": "postprocessor"}),
        ]
    if path.name == "flux-experimental":
        return [("main", "flux-klein", {"role": "main"})]
    if path.name in {"text-generation", "pixel-art-restyle"}:
        return [("main", "longlive", {"role": "main"})]
    return [
        ("main", "longlive", {"role": "main"}),
        ("post", "rife", {"role": "postprocessor"}),
    ]


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

    nodes.append(WorkflowNode(node_id="input", kind="source", source_mode="video"))
    previous_node_id = "input"

    for node_id, pipeline_id, metadata in _pipeline_specs_for_path(path):
        nodes.append(
            _node_for_pipeline(
                pipeline_id,
                node_id=node_id,
                catalog=catalog_map,
                metadata=metadata,
            )
        )
        edges.append(WorkflowEdge(previous_node_id, "video", node_id, "video"))
        previous_node_id = node_id

    nodes.append(WorkflowNode(node_id="output", kind="sink", sink_mode="webrtc"))
    edges.append(WorkflowEdge(previous_node_id, "video", "output", "video"))

    return WorkflowIR(
        session=session,
        nodes=nodes,
        edges=edges,
        metadata={
            "plan_name": path.name,
            "pipeline_ids": list(path.pipeline_ids),
        },
    )
