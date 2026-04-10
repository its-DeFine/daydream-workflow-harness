from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from daydream_workflow_harness.catalog import build_catalog_index
from daydream_workflow_harness.planner import plan_workflow
from daydream_workflow_harness.schemas import IntentSpec


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _prompt_text(workflow_data: dict[str, Any]) -> str:
    prompts = workflow_data.get("prompts") or []
    for item in prompts:
        if isinstance(item, Mapping) and item.get("text"):
            return str(item["text"])

    timeline = _mapping(workflow_data.get("timeline"))
    entries = timeline.get("entries") or []
    for entry in entries:
        for item in _mapping(entry).get("prompts") or []:
            if isinstance(item, Mapping) and item.get("text"):
                return str(item["text"])
    return ""


def _actual_pipeline_ids(payload: dict[str, Any]) -> list[str]:
    workflow_data = _mapping(payload.get("workflowData"))
    pipelines = workflow_data.get("pipelines") or []
    pipeline_ids = [
        str(_mapping(pipeline).get("pipeline_id") or "")
        for pipeline in pipelines
        if _mapping(pipeline).get("pipeline_id")
    ]
    if pipeline_ids:
        return pipeline_ids

    graph = _mapping(workflow_data.get("graph"))
    return [
        str(_mapping(node).get("pipeline_id") or "")
        for node in graph.get("nodes") or []
        if _mapping(node).get("type") == "pipeline" and _mapping(node).get("pipeline_id")
    ]


def _catalog_from_published_workflows(workflows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for workflow in workflows:
        workflow_data = _mapping(workflow.get("workflowData"))
        for pipeline in workflow_data.get("pipelines") or []:
            pipeline_map = _mapping(pipeline)
            pipeline_id = str(pipeline_map.get("pipeline_id") or "")
            if not pipeline_id or pipeline_id in seen:
                continue
            params = _mapping(pipeline_map.get("params"))
            input_mode = str(params.get("input_mode") or "video").lower()
            inputs = ["text"] if input_mode == "text" else ["video"]
            outputs = ["video"]
            if pipeline_id == "transparent":
                inputs = ["video", "mask"]
            entries.append(
                {
                    "pipeline_id": pipeline_id,
                    "inputs": inputs,
                    "outputs": outputs,
                }
            )
            seen.add(pipeline_id)
    return build_catalog_index(entries)


def intent_from_published_workflow(payload: dict[str, Any]) -> IntentSpec:
    workflow_data = _mapping(payload.get("workflowData"))
    pipelines = workflow_data.get("pipelines") or []
    first_pipeline = _mapping(pipelines[0]) if pipelines else {}
    first_params = _mapping(first_pipeline.get("params"))
    source = str(first_params.get("input_mode") or "video").lower()

    parts = [
        str(payload.get("name") or ""),
        str(payload.get("description") or ""),
        _prompt_text(workflow_data),
    ]
    objective = " ".join(part.strip() for part in parts if part and part.strip())
    return IntentSpec(
        objective=objective or str(payload.get("name") or "Untitled Workflow"),
        source=source,
        target="video",
        realtime=True,
    )


@dataclass(slots=True)
class CorpusBenchmarkEntry:
    slug: str
    plan_name: str
    source: str
    predicted_pipeline_ids: list[str]
    actual_pipeline_ids: list[str]
    exact_match: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "plan_name": self.plan_name,
            "source": self.source,
            "predicted_pipeline_ids": list(self.predicted_pipeline_ids),
            "actual_pipeline_ids": list(self.actual_pipeline_ids),
            "exact_match": self.exact_match,
        }


@dataclass(slots=True)
class CorpusBenchmarkResult:
    total: int
    exact_matches: int
    entries: list[CorpusBenchmarkEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "exact_matches": self.exact_matches,
            "exact_match_rate": self.exact_matches / self.total if self.total else 0.0,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def benchmark_published_workflows(payload: dict[str, Any]) -> CorpusBenchmarkResult:
    workflows = [
        _mapping(workflow)
        for workflow in payload.get("workflows") or []
        if isinstance(workflow, Mapping)
    ]
    catalog = _catalog_from_published_workflows(workflows)
    entries: list[CorpusBenchmarkEntry] = []

    for workflow in workflows:
        intent = intent_from_published_workflow(workflow)
        ir = plan_workflow(intent, catalog=catalog)
        predicted = [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"]
        actual = _actual_pipeline_ids(workflow)
        entries.append(
            CorpusBenchmarkEntry(
                slug=str(workflow.get("slug") or workflow.get("name") or ""),
                plan_name=str(ir.metadata.get("plan_name") or ""),
                source=intent.source,
                predicted_pipeline_ids=[pipeline_id for pipeline_id in predicted if pipeline_id],
                actual_pipeline_ids=list(actual),
                exact_match=predicted == actual,
            )
        )

    exact_matches = sum(1 for entry in entries if entry.exact_match)
    return CorpusBenchmarkResult(total=len(entries), exact_matches=exact_matches, entries=entries)
