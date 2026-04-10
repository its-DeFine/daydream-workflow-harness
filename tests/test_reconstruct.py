from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.catalog import build_catalog_index
from daydream_workflow_harness.compiler import compile_workflow
from daydream_workflow_harness.reconstruct import reconstruct_workflow
from daydream_workflow_harness.validator import validate_workflow


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sample_catalog() -> dict[str, dict[str, object]]:
    return build_catalog_index(
        [
            {"pipeline_id": "video-depth-anything", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "longlive", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "rife", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "transparent", "inputs": ["video", "mask"], "outputs": ["video"]},
        ]
    )


def test_reconstruct_stage_chain_workflow_to_ir_and_back():
    workflow = load_fixture("stage_chain_cyborgtd.json")
    ir = reconstruct_workflow(workflow)

    assert ir.session.objective == "Cyborg Man, Dystopian"
    assert [node.node_id for node in ir.nodes] == [
        "input",
        "video-depth-anything",
        "longlive",
        "rife",
        "output",
    ]
    assert [(edge.source_node, edge.target_node) for edge in ir.edges] == [
        ("input", "video-depth-anything"),
        ("video-depth-anything", "longlive"),
        ("longlive", "rife"),
        ("rife", "output"),
    ]

    compiled = compile_workflow(ir)
    errors = validate_workflow(compiled, catalog=sample_catalog())

    assert compiled["graph"]["nodes"][1]["pipeline_id"] == "video-depth-anything"
    assert errors == []


def test_reconstruct_graph_workflow_to_ir_and_back():
    workflow = load_fixture("graph_transparent.json")
    ir = reconstruct_workflow(workflow)

    assert ir.session.objective == "Untitled Workflow"
    assert {node.node_id for node in ir.nodes} == {
        "video_source",
        "mask_source",
        "output",
        "pipeline",
        "pipeline_1",
        "output_1",
    }
    assert ("pipeline", "pipeline_1") in {
        (edge.source_node, edge.target_node) for edge in ir.edges
    }

    compiled = compile_workflow(ir)
    errors = validate_workflow(compiled, catalog=sample_catalog())

    assert compiled["graph"]["nodes"][4]["pipeline_id"] == "transparent"
    assert errors == []

