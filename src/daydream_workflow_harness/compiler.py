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


def compile_workflow(ir: Any, catalog: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Compile a workflow IR object into a normalized workflow dictionary."""

    graph = _get_value(ir, "graph")
    if graph is None:
        graph = {
            "nodes": list(_get_value(ir, "nodes", []) or []),
            "edges": list(_get_value(ir, "edges", []) or []),
        }

    normalized_graph = {
        "nodes": [_normalize_node(node) for node in list(_get_value(graph, "nodes", []) or [])],
        "edges": [_normalize_edge(edge) for edge in list(_get_value(graph, "edges", []) or [])],
    }

    session = _normalize_mapping(_get_value(ir, "session", {}))
    intent = _normalize_mapping(_get_value(ir, "intent", {}))

    workflow = {
        "name": _get_value(ir, "name", "") or _get_value(ir, "workflow_name", "") or "",
        "description": _get_value(ir, "description", "") or "",
        "intent": intent,
        "graph": normalized_graph,
        "session": session,
    }

    metadata = _normalize_mapping(_get_value(ir, "metadata", {}))
    if catalog is not None:
        metadata["catalog_size"] = len(catalog)
    if metadata:
        workflow["metadata"] = metadata

    return workflow
