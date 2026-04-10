from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _normalize_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _normalize_node(node: Any) -> dict[str, Any]:
    raw = _normalize_mapping(node)
    normalized = {
        "id": str(raw.get("id") or raw.get("node_id") or ""),
        "type": str(raw.get("type") or raw.get("kind") or "pipeline"),
    }
    for field in ("pipeline_id", "source_mode", "source_name", "sink_mode", "sink_name"):
        value = raw.get(field)
        if value is not None:
            normalized[field] = value
    if "tempo_sync" in raw:
        normalized["tempo_sync"] = bool(raw.get("tempo_sync"))
    return normalized


def _normalize_edge(edge: Any) -> dict[str, Any]:
    raw = _normalize_mapping(edge)
    return {
        "from": str(raw.get("from") or raw.get("from_node") or raw.get("source_node") or ""),
        "from_port": str(raw.get("from_port") or raw.get("source_port") or ""),
        "to_node": str(raw.get("to_node") or raw.get("to") or raw.get("target_node") or ""),
        "to_port": str(raw.get("to_port") or raw.get("target_port") or ""),
        "kind": str(raw.get("kind") or "stream"),
    }


def _prompt_items_from_session(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    prompt = str(session.get("prompt") or "").strip()
    if not prompt:
        return []
    return [{"text": prompt, "weight": 100}]


def _timeline_from_session(session: Mapping[str, Any]) -> dict[str, Any] | None:
    prompts = _prompt_items_from_session(session)
    parameters = _normalize_mapping(session.get("parameters"))
    timeline_entries = int(parameters.get("timeline_entries") or 0)
    if not prompts:
        if timeline_entries <= 0:
            return None
        return {
            "entries": [
                {
                    "prompts": [],
                    "start_time": 0,
                    "end_time": 0,
                    "transition_steps": int(parameters.get("transition_steps") or 0),
                    "temporal_interpolation_method": str(
                        parameters.get("temporal_interpolation_method") or "slerp"
                    ),
                }
                for _ in range(timeline_entries)
            ]
        }
    return {
        "entries": [
            {
                "prompts": prompts,
                "start_time": 0,
                "end_time": 0,
                "transition_steps": int(parameters.get("transition_steps") or 0),
                "temporal_interpolation_method": str(
                    parameters.get("temporal_interpolation_method") or "slerp"
                ),
            }
            for _ in range(max(timeline_entries, 1))
        ]
    }


def _default_main_pipeline_params(
    pipeline_id: str,
    *,
    session: Mapping[str, Any],
) -> dict[str, Any]:
    parameters = _normalize_mapping(session.get("parameters"))
    source = str(parameters.get("source") or "video")
    width = int(session.get("width") or 512)
    height = int(session.get("height") or 512)
    uses_vace = bool(parameters.get("uses_vace"))
    if pipeline_id == "longlive":
        defaults = {
            "width": width,
            "height": height,
            "input_mode": source,
            "noise_scale": 0.7,
            "manage_cache": True,
            "quantization": None,
            "noise_controller": True,
            "kv_cache_attention_bias": 0.3,
            "denoising_step_list": [1000, 858, 748, 550],
        }
        if source == "text":
            defaults["prompt_interpolation_method"] = "linear"
        if uses_vace:
            defaults["vace_enabled"] = True
            defaults["vace_use_input_video"] = True
            defaults["vace_context_scale"] = 1.0
        return defaults
    if pipeline_id == "deeplivecam-faceswap":
        return {
            "width": width,
            "height": height,
            "input_mode": source,
            "manage_cache": True,
            "quantization": None,
            "kv_cache_attention_bias": 0.3,
            "source_face_image": "placeholder-face.png",
        }
    if pipeline_id == "flux-klein":
        return {
            "width": width,
            "height": height,
            "input_mode": source,
            "noise_scale": 0.7,
            "manage_cache": True,
            "quantization": None,
            "noise_controller": True,
            "kv_cache_attention_bias": 0.3,
            "denoising_step_list": [1000, 858, 748, 550],
            "guidance_scale": 1.0,
            "feedback_strength": 0.0,
            "num_inference_steps": 4,
            "seed": 42,
            "vace_enabled": True,
            "vace_use_input_video": True,
            "vace_context_scale": 1.0,
        }
    return {}


def _pipeline_stage_from_node(node: Any, *, session: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = _normalize_mapping(node)
    node_type = str(raw.get("type") or raw.get("kind") or "")
    if node_type != "pipeline":
        return None

    pipeline_id = str(raw.get("pipeline_id") or "")
    if not pipeline_id:
        return None

    node_metadata = _normalize_mapping(raw.get("metadata"))
    role = str(node_metadata.get("role") or raw.get("role") or "pipeline")
    params = _normalize_mapping(node_metadata.get("params"))
    loras = list(node_metadata.get("loras") or [])
    source = _normalize_mapping(node_metadata.get("source"))

    if role == "main":
        default_params = _default_main_pipeline_params(pipeline_id, session=session)
        params = {**default_params, **params}

    stage = {
        "role": role,
        "loras": loras,
        "params": params,
        "source": source or {"type": "builtin"},
        "pipeline_id": pipeline_id,
        "pipeline_version": str(node_metadata.get("pipeline_version") or "1.0.0"),
    }
    return stage


def compile_workflow(ir: Any, catalog: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Compile a workflow IR object into a normalized workflow dictionary."""

    graph = _get_value(ir, "graph")
    if graph is None:
        graph = {
            "nodes": list(_get_value(ir, "nodes", []) or []),
            "edges": list(_get_value(ir, "edges", []) or []),
        }

    raw_nodes = list(_get_value(graph, "nodes", []) or [])
    normalized_graph = {
        "nodes": [_normalize_node(node) for node in raw_nodes],
        "edges": [_normalize_edge(edge) for edge in list(_get_value(graph, "edges", []) or [])],
    }

    session = _normalize_mapping(_get_value(ir, "session", {}))
    intent = _normalize_mapping(_get_value(ir, "intent", {}))
    prompts = _prompt_items_from_session(session)
    timeline = _timeline_from_session(session)
    pipelines = [
        stage
        for stage in (
            _pipeline_stage_from_node(node, session=session) for node in raw_nodes
        )
        if stage is not None
    ]

    workflow = {
        "name": _get_value(ir, "name", "") or _get_value(ir, "workflow_name", "") or "",
        "description": _get_value(ir, "description", "") or "",
        "format": "scope-workflow",
        "format_version": "1.0",
        "intent": intent,
        "graph": normalized_graph,
        "session": session,
    }
    if prompts:
        workflow["prompts"] = prompts
    if timeline is not None:
        workflow["timeline"] = timeline
    if pipelines:
        workflow["pipelines"] = pipelines

    metadata = _normalize_mapping(_get_value(ir, "metadata", {}))
    if catalog is not None:
        metadata["catalog_size"] = len(catalog)
    if metadata:
        workflow["metadata"] = metadata

    return workflow
