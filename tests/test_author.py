from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.author import author_workflow
from daydream_workflow_harness.catalog import build_catalog_index
from daydream_workflow_harness.ir import WorkflowIR, WorkflowNode, WorkflowSession


def sample_catalog() -> dict[str, dict[str, object]]:
    return build_catalog_index(
        [
            {"pipeline_id": "video-depth-anything", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "longlive", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "rife", "inputs": ["video"], "outputs": ["video"]},
        ]
    )


def test_author_workflow_generates_valid_direct_restyle():
    result = author_workflow(
        {
            "objective": "Create a realtime video restyle",
            "notes": ["restyle"],
        },
        catalog=sample_catalog(),
    )

    assert result.valid is True
    assert result.used_repair is False
    assert result.final_errors == []
    assert result.workflow["metadata"]["plan_name"] == "direct-restyle"


def test_author_workflow_generates_valid_depth_conditioned_restyle():
    result = author_workflow(
        {"objective": "Depth-conditioned realtime restyle"},
        catalog=sample_catalog(),
    )

    assert result.valid is True
    assert result.workflow["metadata"]["plan_name"] == "depth-conditioned"
    assert result.workflow["graph"]["nodes"][1]["pipeline_id"] == "video-depth-anything"


def test_author_workflow_can_repair_compiled_workflow(monkeypatch):
    from daydream_workflow_harness import author as author_module

    def fake_plan_workflow(*args, **kwargs):
        return WorkflowIR(
            session=WorkflowSession(objective="broken"),
            nodes=[
                WorkflowNode(node_id="input", kind="source"),
                WorkflowNode(node_id="main", kind="pipeline", pipeline_id="longlive"),
                WorkflowNode(node_id="output", kind="sink"),
            ],
            edges=[],
        )

    def fake_compile_workflow(ir, catalog=None):
        return {
            "name": "broken",
            "nodes": [
                {"node_id": "input", "kind": "source"},
                {"node_id": "main", "kind": "pipeline", "pipeline_id": "longlive"},
                {"node_id": "output", "kind": "sink"},
            ],
            "edges": [
                {
                    "from_node": "input",
                    "source_port": "video",
                    "to_node": "main",
                    "target_port": "video",
                },
                {
                    "from_node": "main",
                    "source_port": "video",
                    "to_node": "output",
                    "target_port": "video",
                },
            ],
        }

    def fake_validate_workflow(workflow, catalog=None):
        if "graph" in workflow:
            return []
        return ["graph wrapper missing"]

    monkeypatch.setattr(author_module, "plan_workflow", fake_plan_workflow)
    monkeypatch.setattr(author_module, "compile_workflow", fake_compile_workflow)
    monkeypatch.setattr(author_module, "validate_workflow", fake_validate_workflow)

    result = author_workflow(
        {"objective": "broken"},
        catalog=sample_catalog(),
    )

    assert result.valid is True
    assert result.used_repair is True
    assert "graph" in result.workflow
    assert result.repair_changes
