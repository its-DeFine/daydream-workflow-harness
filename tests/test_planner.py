from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness import IntentSpec, plan_workflow
from daydream_workflow_harness.catalog import build_catalog_index
from daydream_workflow_harness.compiler import compile_workflow
from daydream_workflow_harness.validator import validate_workflow


def sample_catalog() -> dict[str, dict[str, object]]:
    return build_catalog_index(
        [
            {"pipeline_id": "video-depth-anything", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "longlive", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "rife", "inputs": ["video"], "outputs": ["video"]},
        ]
    )


def test_plan_direct_restyle_to_longlive_rife():
    intent = IntentSpec(objective="Create a realtime video restyle", notes=("restyle",))

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == [
        "longlive",
        "rife",
    ]
    assert compiled["metadata"]["plan_name"] == "direct-restyle"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []


def test_plan_depth_conditioned_workflow_includes_depth_preprocessor():
    intent = IntentSpec(objective="Depth-conditioned realtime restyle")

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == [
        "video-depth-anything",
        "longlive",
        "rife",
    ]
    assert compiled["metadata"]["plan_name"] == "depth-conditioned"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []
