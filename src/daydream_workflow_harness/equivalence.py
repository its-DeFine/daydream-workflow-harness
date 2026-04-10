from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from daydream_workflow_harness.author import author_workflow
from daydream_workflow_harness.catalog import build_catalog_index


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _string(value: Any) -> str:
    return str(value or "").strip()


def _first_prompt_text(workflow: Mapping[str, Any]) -> str:
    prompts = workflow.get("prompts") or []
    for item in prompts:
        if isinstance(item, Mapping) and item.get("text"):
            return _string(item.get("text"))

    timeline = _mapping(workflow.get("timeline"))
    for entry in timeline.get("entries") or []:
        for item in _mapping(entry).get("prompts") or []:
            if isinstance(item, Mapping) and item.get("text"):
                return _string(item.get("text"))
    return ""


def _timeline_entry_count(workflow: Mapping[str, Any]) -> int:
    timeline = _mapping(workflow.get("timeline"))
    return len(timeline.get("entries") or [])


def _pipeline_list(workflow: Mapping[str, Any]) -> list[dict[str, Any]]:
    pipelines = workflow.get("pipelines")
    if isinstance(pipelines, list):
        return [_mapping(pipeline) for pipeline in pipelines if isinstance(pipeline, Mapping)]

    graph = _mapping(workflow.get("graph"))
    return [
        _mapping(node)
        for node in graph.get("nodes") or []
        if _mapping(node).get("type") == "pipeline"
    ]


def _pipeline_ids(workflow: Mapping[str, Any]) -> list[str]:
    return [
        _string(pipeline.get("pipeline_id"))
        for pipeline in _pipeline_list(workflow)
        if _string(pipeline.get("pipeline_id"))
    ]


def _pipeline_roles(workflow: Mapping[str, Any]) -> list[str]:
    roles: list[str] = []
    for pipeline in _pipeline_list(workflow):
        role = _string(pipeline.get("role"))
        if not role:
            role = "pipeline"
        roles.append(role)
    return roles


def _main_pipeline(workflow: Mapping[str, Any]) -> dict[str, Any]:
    for pipeline in _pipeline_list(workflow):
        if _string(pipeline.get("role")) == "main":
            return pipeline
    pipelines = _pipeline_list(workflow)
    return pipelines[0] if pipelines else {}


def _main_dimensions(workflow: Mapping[str, Any]) -> tuple[int | None, int | None]:
    params = _mapping(_main_pipeline(workflow).get("params"))
    width = params.get("width")
    height = params.get("height")
    return (
        int(width) if isinstance(width, (int, float)) else None,
        int(height) if isinstance(height, (int, float)) else None,
    )


def _main_input_mode(workflow: Mapping[str, Any]) -> str:
    params = _mapping(_main_pipeline(workflow).get("params"))
    return _string(params.get("input_mode") or "video")


def _total_lora_count(workflow: Mapping[str, Any]) -> int:
    return sum(len(_mapping(pipeline).get("loras") or []) for pipeline in _pipeline_list(workflow))


def _param_key_set(workflow: Mapping[str, Any]) -> list[str]:
    params = _mapping(_main_pipeline(workflow).get("params"))
    return sorted(str(key) for key in params)


def _catalog_from_workflow_corpus(workflows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for workflow in workflows:
        for pipeline in _pipeline_list(_mapping(workflow.get("workflowData"))):
            pipeline_id = _string(pipeline.get("pipeline_id"))
            if not pipeline_id or pipeline_id in seen:
                continue
            input_mode = _main_input_mode({"pipelines": [pipeline]})
            inputs = ["text"] if input_mode == "text" else ["video"]
            if pipeline_id == "transparent":
                inputs = ["video", "mask"]
            entries.append(
                {
                    "pipeline_id": pipeline_id,
                    "inputs": inputs,
                    "outputs": ["video"],
                }
            )
            seen.add(pipeline_id)
    return build_catalog_index(entries)


def _intent_from_workflow_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    workflow_data = _mapping(payload.get("workflowData"))
    description = _string(payload.get("description"))
    prompt = _first_prompt_text(workflow_data)
    objective = prompt or _string(payload.get("name")) or "Untitled Workflow"
    notes = []
    name = _string(payload.get("name"))
    if name and name != objective:
        notes.append(name)
    if description:
        notes.append(description)
    return {
        "objective": objective,
        "source": _main_input_mode(workflow_data),
        "target": "video",
        "notes": notes,
    }


def evaluate_published_workflow_equivalence(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    workflows = [
        _mapping(workflow)
        for workflow in payload.get("workflows") or []
        if isinstance(workflow, Mapping)
    ]
    catalog = _catalog_from_workflow_corpus(workflows)

    results: list[dict[str, Any]] = []
    chain_matches = 0
    role_matches = 0
    prompt_matches = 0
    timeline_matches = 0
    dimension_matches = 0
    input_mode_matches = 0
    lora_count_matches = 0
    param_key_matches = 0

    for workflow in workflows:
        actual = _mapping(workflow.get("workflowData"))
        authored = author_workflow(
            _intent_from_workflow_payload(workflow),
            catalog=catalog,
            attempt_repair=False,
        ).to_dict()["workflow"]

        chain_exact = _pipeline_ids(authored) == _pipeline_ids(actual)
        role_exact = _pipeline_roles(authored) == _pipeline_roles(actual)
        prompt_exact = _first_prompt_text(authored) == _first_prompt_text(actual)
        timeline_exact = _timeline_entry_count(authored) == _timeline_entry_count(actual)
        dimension_exact = _main_dimensions(authored) == _main_dimensions(actual)
        input_mode_exact = _main_input_mode(authored) == _main_input_mode(actual)
        lora_count_exact = _total_lora_count(authored) == _total_lora_count(actual)
        param_key_exact = _param_key_set(authored) == _param_key_set(actual)

        chain_matches += int(chain_exact)
        role_matches += int(role_exact)
        prompt_matches += int(prompt_exact)
        timeline_matches += int(timeline_exact)
        dimension_matches += int(dimension_exact)
        input_mode_matches += int(input_mode_exact)
        lora_count_matches += int(lora_count_exact)
        param_key_matches += int(param_key_exact)

        results.append(
            {
                "slug": _string(workflow.get("slug") or workflow.get("name")),
                "chain_exact": chain_exact,
                "role_exact": role_exact,
                "prompt_exact": prompt_exact,
                "timeline_entry_count_exact": timeline_exact,
                "dimension_exact": dimension_exact,
                "input_mode_exact": input_mode_exact,
                "lora_count_exact": lora_count_exact,
                "main_param_keys_exact": param_key_exact,
                "actual": {
                    "pipeline_ids": _pipeline_ids(actual),
                    "roles": _pipeline_roles(actual),
                    "prompt": _first_prompt_text(actual),
                    "timeline_entry_count": _timeline_entry_count(actual),
                    "dimensions": _main_dimensions(actual),
                    "input_mode": _main_input_mode(actual),
                    "lora_count": _total_lora_count(actual),
                    "main_param_keys": _param_key_set(actual),
                },
                "predicted": {
                    "pipeline_ids": _pipeline_ids(authored),
                    "roles": _pipeline_roles(authored),
                    "prompt": _first_prompt_text(authored),
                    "timeline_entry_count": _timeline_entry_count(authored),
                    "dimensions": _main_dimensions(authored),
                    "input_mode": _main_input_mode(authored),
                    "lora_count": _total_lora_count(authored),
                    "main_param_keys": _param_key_set(authored),
                },
            }
        )

    total = len(results)
    return {
        "summary": {
            "total_cases": total,
            "chain_exact_matches": chain_matches,
            "role_exact_matches": role_matches,
            "prompt_exact_matches": prompt_matches,
            "timeline_entry_count_exact_matches": timeline_matches,
            "dimension_exact_matches": dimension_matches,
            "input_mode_exact_matches": input_mode_matches,
            "lora_count_exact_matches": lora_count_matches,
            "main_param_keys_exact_matches": param_key_matches,
        },
        "results": results,
    }
