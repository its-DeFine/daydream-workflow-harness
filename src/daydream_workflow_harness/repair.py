from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


def _get_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _normalize_node(node: Any) -> dict[str, Any]:
    raw = _get_mapping(node)
    normalized = {
        "id": str(raw.get("id") or raw.get("node_id") or ""),
        "type": str(raw.get("type") or raw.get("kind") or ""),
    }
    for field_name in ("pipeline_id", "source_mode", "source_name", "sink_mode", "sink_name"):
        value = raw.get(field_name)
        if value is not None:
            normalized[field_name] = value
    if "tempo_sync" in raw:
        normalized["tempo_sync"] = bool(raw.get("tempo_sync"))
    if raw.get("x") is not None:
        normalized["x"] = raw.get("x")
    if raw.get("y") is not None:
        normalized["y"] = raw.get("y")
    if raw.get("w") is not None:
        normalized["w"] = raw.get("w")
    if raw.get("h") is not None:
        normalized["h"] = raw.get("h")
    return normalized


def _normalize_edge(edge: Any) -> dict[str, Any]:
    raw = _get_mapping(edge)
    normalized = {
        "from": str(raw.get("from") or raw.get("from_node") or raw.get("source_node") or ""),
        "from_port": str(raw.get("from_port") or raw.get("source_port") or ""),
        "to_node": str(raw.get("to_node") or raw.get("to") or raw.get("target_node") or ""),
        "to_port": str(raw.get("to_port") or raw.get("target_port") or ""),
        "kind": str(raw.get("kind") or "stream"),
    }
    return normalized


def _normalize_graph(graph: Any) -> dict[str, Any]:
    raw = _get_mapping(graph)
    return {
        "nodes": [_normalize_node(node) for node in list(raw.get("nodes") or [])],
        "edges": [_normalize_edge(edge) for edge in list(raw.get("edges") or [])],
    }


@dataclass(slots=True)
class RepairResult:
    workflow: dict[str, Any]
    changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": deepcopy(self.workflow),
            "changes": list(self.changes),
        }


def repair_workflow(workflow: Any) -> dict[str, Any]:
    """Apply only conservative workflow repairs.

    The helper does not invent new graph structure. It only:
    - wraps top-level nodes/edges into a graph when needed
    - normalizes node and edge aliases
    - defaults missing edge kind values to ``stream``
    """

    payload = deepcopy(_get_mapping(workflow))
    changes: list[str] = []

    graph = payload.get("graph")
    if graph is None and ("nodes" in payload or "edges" in payload):
        payload["graph"] = {
            "nodes": list(payload.pop("nodes", []) or []),
            "edges": list(payload.pop("edges", []) or []),
        }
        graph = payload["graph"]
        changes.append("wrapped top-level nodes/edges into graph")

    if graph is None:
        payload["graph"] = {"nodes": [], "edges": []}
        changes.append("created empty graph wrapper")
        graph = payload["graph"]

    normalized_graph = _normalize_graph(graph)

    if normalized_graph != _get_mapping(graph):
        changes.append("normalized node and edge aliases")

    payload["graph"] = normalized_graph

    if "workflow_name" in payload and "name" not in payload:
        payload["name"] = payload.pop("workflow_name")
        changes.append("normalized workflow_name to name")

    if changes:
        payload["repair"] = {"changes": changes}
    return payload


def repair_workflow_result(workflow: Any) -> RepairResult:
    repaired = repair_workflow(workflow)
    changes = list(_get_mapping(repaired).get("repair", {}).get("changes", []))
    return RepairResult(workflow=repaired, changes=changes)
