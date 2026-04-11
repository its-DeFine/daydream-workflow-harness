from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from daydream_workflow_harness.catalog import catalog_inputs, catalog_outputs


IMPLICIT_PORTS: dict[str, dict[str, set[str]]] = {
    "source": {"outputs": {"video"}, "inputs": set()},
    "sink": {"inputs": {"video"}, "outputs": {"out"}},
    "record": {"inputs": {"video"}, "outputs": set()},
}


@dataclass(slots=True, frozen=True)
class CompatibilityIssue:
    severity: str
    code: str
    message: str
    path: str = ""


@dataclass(slots=True)
class CompatibilityReport:
    compatible: bool
    pipeline_ids: list[str] = field(default_factory=list)
    issues: list[CompatibilityIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    graph_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "pipeline_ids": list(self.pipeline_ids),
            "issues": [asdict(issue) for issue in self.issues],
            "warnings": list(self.warnings),
            "graph_summary": dict(self.graph_summary),
        }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _workflow(workflow_or_wrapper: Mapping[str, Any]) -> Mapping[str, Any]:
    workflow = workflow_or_wrapper.get("workflow")
    if isinstance(workflow, Mapping):
        return workflow
    return workflow_or_wrapper


def _graph(
    workflow_payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    graph = _mapping(workflow_payload.get("graph"))
    return (
        [_mapping(node) for node in list(graph.get("nodes") or [])],
        [_mapping(edge) for edge in list(graph.get("edges") or [])],
    )


def _pipeline_stage_roles(workflow_payload: Mapping[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for stage in list(workflow_payload.get("pipelines") or []):
        stage_map = _mapping(stage)
        pipeline_id = str(stage_map.get("pipeline_id") or "")
        role = str(stage_map.get("role") or "")
        if pipeline_id and role:
            roles[pipeline_id] = role
    return roles


def _node_role(node: Mapping[str, Any], stage_roles: Mapping[str, str]) -> str:
    node_type = str(node.get("type") or "")
    if node_type != "pipeline":
        return node_type
    pipeline_id = str(node.get("pipeline_id") or "")
    metadata = _mapping(node.get("metadata"))
    return str(metadata.get("role") or stage_roles.get(pipeline_id) or "pipeline")


def _node_output_ports(
    node: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None,
) -> set[str]:
    node_type = str(node.get("type") or "")
    if node_type == "pipeline":
        pipeline_id = str(node.get("pipeline_id") or "")
        outputs = set(catalog_outputs(catalog or {}, pipeline_id))
        return outputs or {"video"}
    return set(IMPLICIT_PORTS.get(node_type, {}).get("outputs") or set())


def _node_input_ports(
    node: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None,
) -> set[str]:
    node_type = str(node.get("type") or "")
    if node_type == "pipeline":
        pipeline_id = str(node.get("pipeline_id") or "")
        inputs = set(catalog_inputs(catalog or {}, pipeline_id))
        return inputs or {"video"}
    return set(IMPLICIT_PORTS.get(node_type, {}).get("inputs") or set())


def analyze_workflow_compatibility(
    workflow_or_wrapper: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
) -> CompatibilityReport:
    workflow_payload = _workflow(workflow_or_wrapper)
    nodes, edges = _graph(workflow_payload)
    node_by_id = {str(node.get("id") or ""): node for node in nodes if node.get("id")}
    stage_roles = _pipeline_stage_roles(workflow_payload)
    issues: list[CompatibilityIssue] = []
    warnings: list[str] = []
    pipeline_ids: list[str] = []
    role_sequence: list[str] = []

    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if not node_id:
            issues.append(
                CompatibilityIssue(
                    "error",
                    "missing_node_id",
                    "node is missing id",
                    f"graph.nodes[{index}]",
                )
            )
            continue
        if node_type == "pipeline":
            pipeline_id = str(node.get("pipeline_id") or "")
            if pipeline_id:
                pipeline_ids.append(pipeline_id)
                if catalog is not None and pipeline_id not in catalog:
                    issues.append(
                        CompatibilityIssue(
                            "error",
                            "unknown_pipeline",
                            f"pipeline {pipeline_id!r} is not in the active catalog",
                            f"graph.nodes[{index}]",
                        )
                    )
            role_sequence.append(_node_role(node, stage_roles))
        elif node_type in IMPLICIT_PORTS:
            role_sequence.append(node_type)
        else:
            issues.append(
                CompatibilityIssue(
                    "error",
                    "unknown_node_type",
                    f"node {node_id!r} has unknown type {node_type!r}",
                    f"graph.nodes[{index}]",
                )
            )

    for index, edge in enumerate(edges):
        from_id = str(
            edge.get("from") or edge.get("from_node") or edge.get("source_node") or ""
        )
        to_id = str(
            edge.get("to_node") or edge.get("to") or edge.get("target_node") or ""
        )
        from_port = str(edge.get("from_port") or edge.get("source_port") or "")
        to_port = str(edge.get("to_port") or edge.get("target_port") or "")
        from_node = node_by_id.get(from_id)
        to_node = node_by_id.get(to_id)
        path = f"graph.edges[{index}]"

        if from_node is None or to_node is None:
            issues.append(
                CompatibilityIssue(
                    "error",
                    "unknown_edge_endpoint",
                    f"edge references unknown endpoint {from_id!r}->{to_id!r}",
                    path,
                )
            )
            continue

        if from_port and from_port not in _node_output_ports(
            from_node, catalog=catalog
        ):
            issues.append(
                CompatibilityIssue(
                    "error",
                    "invalid_from_port",
                    f"port {from_port!r} is not an output of node {from_id!r}",
                    path,
                )
            )
        if to_port and to_port not in _node_input_ports(to_node, catalog=catalog):
            issues.append(
                CompatibilityIssue(
                    "error",
                    "invalid_to_port",
                    f"port {to_port!r} is not an input of node {to_id!r}",
                    path,
                )
            )

        if (
            str(to_node.get("type") or "") == "record"
            and str(from_node.get("type") or "") != "sink"
        ):
            warnings.append(
                f"record node {to_id!r} is fed directly from {from_id!r}; current harness record injection prefers sink output"
            )

    if "postprocessor" in role_sequence and "main" in role_sequence:
        if role_sequence.index("postprocessor") < role_sequence.index("main"):
            issues.append(
                CompatibilityIssue(
                    "error",
                    "postprocessor_before_main",
                    "postprocessor role appears before main role",
                    "graph.nodes",
                )
            )
    if "preprocessor" in role_sequence and "main" in role_sequence:
        if role_sequence.index("preprocessor") > role_sequence.index("main"):
            warnings.append("preprocessor role appears after main role")

    return CompatibilityReport(
        compatible=not any(issue.severity == "error" for issue in issues),
        pipeline_ids=pipeline_ids,
        issues=issues,
        warnings=warnings,
        graph_summary={
            "node_count": len(nodes),
            "edge_count": len(edges),
            "role_sequence": role_sequence,
            "sink_count": sum(1 for node in nodes if node.get("type") == "sink"),
            "record_count": sum(1 for node in nodes if node.get("type") == "record"),
        },
    )
