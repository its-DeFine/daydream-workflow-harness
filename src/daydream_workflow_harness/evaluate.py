from __future__ import annotations

from typing import Any, Mapping

from daydream_workflow_harness.author import author_workflow


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _first_prompt_text(workflow_data: Mapping[str, Any]) -> str:
    prompts = workflow_data.get("prompts") or []
    for item in prompts:
        if isinstance(item, Mapping) and item.get("text"):
            return str(item["text"])

    timeline = _mapping(workflow_data.get("timeline"))
    for entry in timeline.get("entries") or []:
        prompts = _mapping(entry).get("prompts") or []
        for item in prompts:
            if isinstance(item, Mapping) and item.get("text"):
                return str(item["text"])
    return ""


def _expected_pipeline_ids_from_workflow_payload(workflow: Mapping[str, Any]) -> list[str]:
    workflow_data = _mapping(workflow.get("workflowData"))
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


def _cases_from_workflow_corpus(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    workflows = payload.get("workflows")
    if not isinstance(workflows, list):
        return []

    cases: list[dict[str, Any]] = []
    for workflow in workflows:
        if not isinstance(workflow, Mapping):
            continue
        workflow_data = _mapping(workflow.get("workflowData"))
        first_pipeline = _mapping((workflow_data.get("pipelines") or [{}])[0])
        first_params = _mapping(first_pipeline.get("params"))
        description = str(workflow.get("description") or "").strip()
        prompt = _first_prompt_text(workflow_data)
        notes = [description] if description else []
        cases.append(
            {
                "slug": workflow.get("slug"),
                "name": workflow.get("name"),
                "prompt": prompt,
                "source": str(first_params.get("input_mode") or "video"),
                "notes": notes,
                "expected_pipeline_ids": _expected_pipeline_ids_from_workflow_payload(workflow),
                "source_url": workflow.get("workflowUrl"),
            }
        )
    return cases


def _cases_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        cases = payload.get("cases")
        if isinstance(cases, list):
            return [dict(item) for item in cases if isinstance(item, Mapping)]
        corpus_cases = _cases_from_workflow_corpus(payload)
        if corpus_cases:
            return corpus_cases
    return []


def _intent_for_case(case: Mapping[str, Any]) -> dict[str, Any]:
    objective = str(case.get("prompt") or case.get("objective") or case.get("name") or "").strip()
    if not objective:
        raise ValueError("case is missing prompt/objective/name")

    notes: list[str] = []
    name = str(case.get("name") or "").strip()
    if name and name != objective:
        notes.append(name)
    notes.extend(_string_list(case.get("notes")))

    return {
        "objective": objective,
        "source": str(case.get("source") or "video"),
        "target": str(case.get("target") or "video"),
        "notes": notes,
    }


def _expected_pipeline_ids(case: Mapping[str, Any]) -> list[str]:
    return _string_list(case.get("expected_pipeline_ids"))


def _actual_pipeline_ids(result: Mapping[str, Any]) -> list[str]:
    workflow = result.get("workflow")
    if not isinstance(workflow, Mapping):
        return []
    metadata = workflow.get("metadata")
    if isinstance(metadata, Mapping):
        pipeline_ids = metadata.get("pipeline_ids")
        if isinstance(pipeline_ids, list):
            return [str(item) for item in pipeline_ids if item is not None]
    return []


def evaluate_blind_regeneration(
    payload: Any,
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    cases = _cases_from_payload(payload)
    results: list[dict[str, Any]] = []

    matched = 0
    for case in cases:
        slug = str(case.get("slug") or case.get("name") or f"case-{len(results)}")
        expected = _expected_pipeline_ids(case)
        try:
            authored = author_workflow(
                _intent_for_case(case),
                catalog=catalog,
                attempt_repair=False,
            ).to_dict()
            actual = _actual_pipeline_ids(authored)
            exact_match = actual == expected
            if exact_match:
                matched += 1
            results.append(
                {
                    "slug": slug,
                    "name": case.get("name"),
                    "objective": _intent_for_case(case)["objective"],
                    "expected_pipeline_ids": expected,
                    "actual_pipeline_ids": actual,
                    "exact_match": exact_match,
                    "valid": bool(authored.get("valid")),
                    "source_url": case.get("source_url"),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "slug": slug,
                    "name": case.get("name"),
                    "objective": str(case.get("prompt") or case.get("objective") or case.get("name") or ""),
                    "expected_pipeline_ids": expected,
                    "actual_pipeline_ids": [],
                    "exact_match": False,
                    "valid": False,
                    "error": str(exc),
                    "source_url": case.get("source_url"),
                }
            )

    total = len(results)
    return {
        "summary": {
            "total_cases": total,
            "exact_matches": matched,
            "mismatches": total - matched,
            "exact_match_rate": (matched / total) if total else 0.0,
        },
        "results": results,
    }
