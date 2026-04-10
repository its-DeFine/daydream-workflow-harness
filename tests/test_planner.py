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
            {"pipeline_id": "gray", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "passthrough", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "video-depth-anything", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "transparent", "inputs": ["video", "mask"], "outputs": ["video"]},
            {"pipeline_id": "yolo_mask", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "scribble", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "flux-klein", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "deeplivecam-faceswap", "inputs": ["video"], "outputs": ["video"]},
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


def test_plan_grayscale_workflow_uses_gray_pipeline():
    intent = IntentSpec(objective="Create a grayscale realtime video effect")

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == ["gray"]
    assert compiled["metadata"]["plan_name"] == "grayscale-preview"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []


def test_plan_passthrough_workflow_uses_passthrough_pipeline():
    intent = IntentSpec(objective="Create a passthrough preview workflow for smoke testing")

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == ["passthrough"]
    assert compiled["metadata"]["plan_name"] == "passthrough-preview"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []


def test_plan_face_swap_workflow_uses_faceswap_and_rife():
    intent = IntentSpec(objective="Create a face swap workflow")

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == [
        "deeplivecam-faceswap",
        "rife",
    ]
    assert compiled["metadata"]["plan_name"] == "face-swap"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []


def test_plan_background_removal_workflow_uses_transparent_pipeline():
    intent = IntentSpec(objective="Create a transparent background removal workflow")

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == [
        "video-depth-anything",
        "transparent",
    ]
    assert compiled["metadata"]["plan_name"] == "background-removal"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []


def test_plan_pixel_art_workflow_uses_longlive_without_rife():
    intent = IntentSpec(objective="Create a pixel art character transform")

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == ["longlive"]
    assert compiled["metadata"]["plan_name"] == "pixel-art-restyle"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []


def test_plan_text_logo_workflow_uses_scribble_chain():
    intent = IntentSpec(objective="Create a text logo restyler for typography")

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == [
        "scribble",
        "longlive",
        "rife",
    ]
    assert compiled["metadata"]["plan_name"] == "scribble-logo-restyle"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []


def test_plan_text_generation_without_interpolation_uses_longlive_only():
    intent = IntentSpec(
        objective="Shimmering translucent light ribbons in an iridescent void",
        source="text",
    )

    ir = plan_workflow(intent, catalog=sample_catalog())
    compiled = compile_workflow(ir)

    assert [node.pipeline_id for node in ir.nodes if node.kind == "pipeline"] == ["longlive"]
    assert compiled["metadata"]["plan_name"] == "text-generation"
    assert validate_workflow(compiled, catalog=sample_catalog()) == []
