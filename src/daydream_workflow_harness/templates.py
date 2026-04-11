from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from daydream_workflow_harness.compiler import compile_workflow
from daydream_workflow_harness.ir import (
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
    WorkflowSession,
)


@dataclass(slots=True, frozen=True)
class WorkflowTemplate:
    name: str
    pipeline_ids: tuple[str, ...]
    roles: tuple[str, ...]
    source: str = "video"
    target: str = "video"
    tags: tuple[str, ...] = ()
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pipeline_ids"] = list(self.pipeline_ids)
        payload["roles"] = list(self.roles)
        payload["tags"] = list(self.tags)
        return payload


TEMPLATES: tuple[WorkflowTemplate, ...] = (
    WorkflowTemplate(
        name="passthrough-preview",
        pipeline_ids=("passthrough",),
        roles=("main",),
        tags=("diagnostic", "identity", "smoke"),
        description="Minimal source-to-sink preview used to prove runtime routing.",
    ),
    WorkflowTemplate(
        name="grayscale-preview",
        pipeline_ids=("gray",),
        roles=("main",),
        tags=("gray", "grayscale", "monochrome", "diagnostic"),
        description="Video-to-video grayscale filter for source-ingestion proof.",
    ),
    WorkflowTemplate(
        name="direct-restyle",
        pipeline_ids=("longlive", "rife"),
        roles=("main", "postprocessor"),
        tags=("restyle", "rife", "interpolation", "cyborg", "dystopian"),
        description="Core real-time restyle chain with frame interpolation.",
    ),
    WorkflowTemplate(
        name="depth-conditioned",
        pipeline_ids=("video-depth-anything", "longlive", "rife"),
        roles=("preprocessor", "main", "postprocessor"),
        tags=("depth", "vace", "structure", "cyborg", "dystopian", "ghibli"),
        description="Depth preprocessor feeding LongLive VACE plus RIFE output.",
    ),
    WorkflowTemplate(
        name="scribble-logo-restyle",
        pipeline_ids=("scribble", "longlive", "rife"),
        roles=("preprocessor", "main", "postprocessor"),
        tags=("scribble", "logo", "typography", "text"),
        description="Scribble preprocessor for logo/text restyling.",
    ),
)


def list_workflow_templates() -> list[dict[str, Any]]:
    return [template.to_dict() for template in TEMPLATES]


def get_workflow_template(name: str) -> WorkflowTemplate | None:
    for template in TEMPLATES:
        if template.name == name:
            return template
    return None


def _catalog_supports(
    template: WorkflowTemplate,
    catalog: Mapping[str, Mapping[str, Any]] | None,
) -> bool:
    if catalog is None:
        return True
    return all(pipeline_id in catalog for pipeline_id in template.pipeline_ids)


def _intent_text(intent: Mapping[str, Any]) -> str:
    parts = [
        intent.get("objective"),
        intent.get("goal"),
        intent.get("prompt"),
        intent.get("source"),
        intent.get("target"),
    ]
    parts.extend(list(intent.get("notes") or []))
    parts.extend(list(intent.get("constraints") or []))
    return " ".join(str(part) for part in parts if part).lower()


def candidate_templates_for_intent(
    intent: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    text = _intent_text(intent)
    scored: list[tuple[int, WorkflowTemplate]] = []
    for template in TEMPLATES:
        if not _catalog_supports(template, catalog):
            continue
        score = 0
        for tag in template.tags:
            if tag.lower() in text:
                score += 2
        for pipeline_id in template.pipeline_ids:
            if pipeline_id.lower() in text:
                score += 3
        if template.name in text:
            score += 4
        if template.name == "depth-conditioned" and "depth" in text:
            score += 4
        if template.name == "scribble-logo-restyle" and any(
            term in text for term in ("scribble", "logo", "typography")
        ):
            score += 4
        if template.name == "direct-restyle" and not scored:
            score += 1
        scored.append((score, template))

    scored.sort(key=lambda item: (-item[0], item[1].name))
    candidates: list[dict[str, Any]] = []
    for score, template in scored[:limit]:
        payload = template.to_dict()
        payload["score"] = score
        payload["available"] = True
        candidates.append(payload)
    return candidates


def _node_id_for_template_stage(
    template: WorkflowTemplate,
    *,
    index: int,
    pipeline_id: str,
    role: str,
    used: set[str],
) -> str:
    preferred = "main" if role == "main" else role
    if preferred in {"pipeline", ""}:
        preferred = pipeline_id.replace("-", "_")
    candidate = preferred
    suffix = 2
    while candidate in used:
        candidate = f"{preferred}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def build_template_workflow(
    template_name: str,
    intent: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    template = get_workflow_template(template_name)
    if template is None:
        raise ValueError(f"unknown workflow template: {template_name}")
    if not _catalog_supports(template, catalog):
        missing = [
            pipeline_id
            for pipeline_id in template.pipeline_ids
            if catalog is not None and pipeline_id not in catalog
        ]
        raise ValueError(
            f"template {template_name!r} is missing pipeline(s): {', '.join(missing)}"
        )

    objective = str(
        intent.get("objective")
        or intent.get("goal")
        or intent.get("prompt")
        or template.description
    )
    source = str(intent.get("source") or template.source)
    target = str(intent.get("target") or template.target)
    session = WorkflowSession(
        objective=objective,
        prompt=objective,
        parameters={
            "source": source,
            "target": target,
            "realtime": bool(intent.get("realtime", True)),
            "notes": list(intent.get("notes") or []),
            "constraints": list(intent.get("constraints") or []),
            "plan_name": template.name,
            "template_name": template.name,
            "timeline_entries": 1,
            "uses_vace": "preprocessor" in template.roles,
        },
    )

    nodes: list[WorkflowNode] = [
        WorkflowNode(node_id="input", kind="source", source_mode=source)
    ]
    edges: list[WorkflowEdge] = []
    previous = "input"
    used = {"input", "output"}
    for index, (pipeline_id, role) in enumerate(
        zip(template.pipeline_ids, template.roles, strict=True)
    ):
        node_id = _node_id_for_template_stage(
            template,
            index=index,
            pipeline_id=pipeline_id,
            role=role,
            used=used,
        )
        nodes.append(
            WorkflowNode(
                node_id=node_id,
                kind="pipeline",
                pipeline_id=pipeline_id,
                metadata={
                    "role": role,
                    "catalog_entry": pipeline_id,
                    "template_name": template.name,
                },
            )
        )
        edges.append(WorkflowEdge(previous, "video", node_id, "video"))
        previous = node_id
    nodes.append(WorkflowNode(node_id="output", kind="sink", sink_mode="webrtc"))
    edges.append(WorkflowEdge(previous, "video", "output", "video"))

    ir = WorkflowIR(
        session=session,
        nodes=nodes,
        edges=edges,
        metadata={
            "plan_name": template.name,
            "template_name": template.name,
            "pipeline_ids": list(template.pipeline_ids),
        },
    )
    return compile_workflow(ir, catalog=catalog)
