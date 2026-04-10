from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from daydream_workflow_harness.compiler import compile_workflow
from daydream_workflow_harness.ir import WorkflowIR
from daydream_workflow_harness.planner import plan_workflow
from daydream_workflow_harness.repair import repair_workflow_result
from daydream_workflow_harness.reporting import build_validation_report
from daydream_workflow_harness.schemas import CapabilityCatalog, IntentSpec
from daydream_workflow_harness.validator import validate_workflow


def _normalize_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if item is not None)
    return (str(value),)


def _coerce_intent(intent: IntentSpec | dict[str, Any]) -> IntentSpec:
    if isinstance(intent, IntentSpec):
        return intent

    objective = (
        intent.get("objective")
        or intent.get("goal")
        or intent.get("prompt")
        or intent.get("effect")
        or ""
    )
    if not objective:
        raise ValueError("intent objective is required")

    return IntentSpec(
        objective=str(objective),
        source=str(intent.get("source") or "video"),
        target=str(intent.get("target") or "video"),
        mode=str(intent.get("mode") or "hybrid"),  # type: ignore[arg-type]
        realtime=bool(intent.get("realtime", True)),
        notes=_normalize_str_tuple(intent.get("notes")),
        constraints=_normalize_str_tuple(intent.get("constraints")),
    )


@dataclass(slots=True)
class AuthoringResult:
    intent: IntentSpec
    ir: WorkflowIR
    workflow: dict[str, Any]
    valid: bool
    used_repair: bool
    initial_errors: list[str]
    final_errors: list[str]
    repair_changes: list[str]
    initial_report: dict[str, Any]
    final_report: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": {
                "objective": self.intent.objective,
                "source": self.intent.source,
                "target": self.intent.target,
                "mode": self.intent.mode,
                "realtime": self.intent.realtime,
                "notes": list(self.intent.notes),
                "constraints": list(self.intent.constraints),
            },
            "ir": self.ir.to_dict(),
            "workflow": self.workflow,
            "valid": self.valid,
            "used_repair": self.used_repair,
            "initial_errors": list(self.initial_errors),
            "final_errors": list(self.final_errors),
            "repair_changes": list(self.repair_changes),
            "initial_report": dict(self.initial_report),
            "final_report": dict(self.final_report),
        }


def author_workflow(
    intent: IntentSpec | dict[str, Any],
    *,
    catalog: CapabilityCatalog | dict[str, Any] | None = None,
    attempt_repair: bool = True,
) -> AuthoringResult:
    """Run the first full authoring loop for a typed intent.

    Flow:
    intent -> plan -> compile -> validate -> optional conservative repair -> report
    """

    intent_spec = _coerce_intent(intent)
    ir = plan_workflow(intent_spec, catalog=catalog)
    compiled = compile_workflow(ir, catalog=catalog)

    initial_errors = validate_workflow(compiled, catalog=catalog)
    initial_report = build_validation_report(
        initial_errors,
        workflow_name=compiled.get("name") or intent_spec.objective,
    ).to_dict()

    workflow = compiled
    final_errors = list(initial_errors)
    repair_changes: list[str] = []
    used_repair = False

    if initial_errors and attempt_repair:
        repaired = repair_workflow_result(compiled)
        repaired_errors = validate_workflow(repaired.workflow, catalog=catalog)
        if len(repaired_errors) <= len(initial_errors):
            workflow = repaired.workflow
            final_errors = repaired_errors
            repair_changes = list(repaired.changes)
            used_repair = bool(repair_changes)

    final_report = build_validation_report(
        final_errors,
        workflow_name=workflow.get("name") or intent_spec.objective,
    ).to_dict()

    return AuthoringResult(
        intent=intent_spec,
        ir=ir,
        workflow=workflow,
        valid=not final_errors,
        used_repair=used_repair,
        initial_errors=list(initial_errors),
        final_errors=list(final_errors),
        repair_changes=repair_changes,
        initial_report=initial_report,
        final_report=final_report,
    )
