from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from daydream_workflow_harness.catalog import catalog_inputs, catalog_outputs

ALLOWED_NODE_TYPES = {"source", "pipeline", "sink", "record"}
ALLOWED_EDGE_KINDS = {"stream", "parameter"}


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


def _get_graph(workflow: Any) -> dict[str, Any]:
    if isinstance(workflow, Mapping):
        graph = workflow.get("graph")
        if graph is not None:
            return _get_mapping(graph)
        return {
            "nodes": list(workflow.get("nodes") or []),
            "edges": list(workflow.get("edges") or []),
        }

    graph = getattr(workflow, "graph", None)
    if graph is not None:
        return _get_mapping(graph)
    return {
        "nodes": list(getattr(workflow, "nodes", []) or []),
        "edges": list(getattr(workflow, "edges", []) or []),
    }


def validate_workflow(workflow: Any, catalog: Mapping[str, Mapping[str, Any]] | None = None) -> list[str]:
    """Return a list of structural validation errors for a workflow payload."""

    errors: list[str] = []
    graph = _get_graph(workflow)
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])

    node_ids: set[str] = set()
    pipeline_nodes: dict[str, dict[str, Any]] = {}

    for index, raw_node in enumerate(nodes):
        node = _get_mapping(raw_node)
        node_id = str(node.get("id") or node.get("node_id") or "")
        node_type = str(node.get("type") or node.get("kind") or "")
        if not node_id:
            errors.append(f"node[{index}] is missing id")
            continue
        if node_id in node_ids:
            errors.append(f"duplicate node id: {node_id}")
        node_ids.add(node_id)

        if node_type not in ALLOWED_NODE_TYPES:
            errors.append(f"node {node_id!r} has invalid type {node_type!r}")
        if node_type == "pipeline":
            pipeline_id = str(node.get("pipeline_id") or "")
            if not pipeline_id:
                errors.append(f"pipeline node {node_id!r} is missing pipeline_id")
            else:
                pipeline_nodes[node_id] = node
                if catalog is not None and pipeline_id not in catalog:
                    errors.append(f"pipeline node {node_id!r} references unknown pipeline_id {pipeline_id!r}")

    for index, raw_edge in enumerate(edges):
        edge = _get_mapping(raw_edge)
        from_node = str(edge.get("from") or edge.get("from_node") or edge.get("source_node") or "")
        to_node = str(edge.get("to_node") or edge.get("to") or edge.get("target_node") or "")
        from_port = str(edge.get("from_port") or edge.get("source_port") or "")
        to_port = str(edge.get("to_port") or edge.get("target_port") or "")
        kind = str(edge.get("kind") or "stream")

        if kind not in ALLOWED_EDGE_KINDS:
            errors.append(f"edge[{index}] has invalid kind {kind!r}")
        if from_node and from_node not in node_ids:
            errors.append(f"edge[{index}] references unknown from_node {from_node!r}")
        if to_node and to_node not in node_ids:
            errors.append(f"edge[{index}] references unknown to_node {to_node!r}")
        if not from_port:
            errors.append(f"edge[{index}] is missing from_port")
        if not to_port:
            errors.append(f"edge[{index}] is missing to_port")

        if catalog is not None and kind == "stream":
            if from_node in pipeline_nodes:
                pipeline_id = str(pipeline_nodes[from_node].get("pipeline_id") or "")
                if from_port and from_port not in catalog_outputs(catalog, pipeline_id):
                    errors.append(
                        f"edge[{index}] from_port {from_port!r} is not declared on pipeline {pipeline_id!r}"
                    )
            if to_node in pipeline_nodes:
                pipeline_id = str(pipeline_nodes[to_node].get("pipeline_id") or "")
                if to_port and to_port not in catalog_inputs(catalog, pipeline_id):
                    errors.append(
                        f"edge[{index}] to_port {to_port!r} is not declared on pipeline {pipeline_id!r}"
                    )

    return errors


def is_valid_workflow(workflow: Any, catalog: Mapping[str, Mapping[str, Any]] | None = None) -> bool:
    return not validate_workflow(workflow, catalog=catalog)


def assert_valid_workflow(workflow: Any, catalog: Mapping[str, Mapping[str, Any]] | None = None) -> None:
    errors = validate_workflow(workflow, catalog=catalog)
    if errors:
        raise ValueError("; ".join(errors))
