from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _normalize_message(error: str) -> str:
    return str(error).strip()


def _category_for_error(error: str) -> tuple[str, str, str]:
    text = error.lower()

    if "pipeline_id" in text:
        if "unknown pipeline_id" in text:
            return (
                "catalog",
                "unknown_pipeline_id",
                "Refresh the catalog or install the missing plugin/pipeline.",
            )
        return (
            "structure",
            "missing_pipeline_id",
            "Add a pipeline_id to every pipeline node.",
        )

    if "port" in text or "edge" in text:
        if "invalid kind" in text or "missing from_port" in text or "missing to_port" in text:
            return (
                "ports",
                "port_wiring",
                "Check edge port names and default missing edge kinds to stream.",
            )
        if "unknown from_node" in text or "unknown to_node" in text:
            return (
                "structure",
                "unknown_node_reference",
                "Check node ids and graph wiring.",
            )
        if "not declared on pipeline" in text:
            return (
                "ports",
                "undeclared_port",
                "Align the edge with the pipeline's declared inputs and outputs.",
            )

    if "duplicate node id" in text or "missing id" in text or "invalid type" in text:
        return (
            "structure",
            "node_structure",
            "Fix node ids and node types before retrying.",
        )

    if "graph" in text:
        return (
            "structure",
            "graph_structure",
            "Wrap nodes and edges in a graph object.",
        )

    return (
        "general",
        "unspecified",
        "Inspect the workflow structure and rerun validation after a targeted fix.",
    )


@dataclass(slots=True, frozen=True)
class ValidationFinding:
    category: str
    code: str
    message: str
    suggestion: str


@dataclass(slots=True)
class ValidationReport:
    total_errors: int
    categories: dict[str, int] = field(default_factory=dict)
    findings: list[ValidationFinding] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": {
                "total": self.total_errors,
                "by_category": dict(self.categories),
            },
            "categories": dict(self.categories),
            "findings": [asdict(finding) for finding in self.findings],
            "suggestions": list(self.suggestions),
            "errors": list(self.errors),
        }


def build_validation_report(
    errors: list[str],
    *,
    workflow_name: str | None = None,
) -> ValidationReport:
    findings: list[ValidationFinding] = []
    categories: dict[str, int] = {}
    suggestions: list[str] = []

    for raw_error in errors:
        error = _normalize_message(raw_error)
        category, code, suggestion = _category_for_error(error)
        findings.append(
            ValidationFinding(
                category=category,
                code=code,
                message=error,
                suggestion=suggestion,
            )
        )
        categories[category] = categories.get(category, 0) + 1
        if suggestion not in suggestions:
            suggestions.append(suggestion)

    if workflow_name and workflow_name not in suggestions:
        suggestions.insert(0, f"Review workflow {workflow_name!r} after applying the fixes.")

    return ValidationReport(
        total_errors=len(errors),
        categories=categories,
        findings=findings,
        suggestions=suggestions,
        errors=[_normalize_message(error) for error in errors],
    )


def validation_report_to_dict(
    errors: list[str],
    *,
    workflow_name: str | None = None,
) -> dict[str, Any]:
    return build_validation_report(errors, workflow_name=workflow_name).to_dict()
