from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.repair import repair_workflow, repair_workflow_result
from daydream_workflow_harness.validator import validate_workflow


def test_repair_workflow_wraps_top_level_nodes_and_normalizes_aliases():
    workflow = {
        "name": "sample",
        "nodes": [
            {"node_id": "input", "kind": "source"},
            {"node_id": "main", "kind": "pipeline", "pipeline_id": "longlive"},
            {"node_id": "output", "kind": "sink"},
        ],
        "edges": [
            {
                "from_node": "input",
                "source_port": "video",
                "to": "main",
                "target_port": "video",
            },
            {
                "from": "main",
                "from_port": "video",
                "to_node": "output",
                "to_port": "video",
            },
        ],
    }

    repaired = repair_workflow(workflow)

    assert "graph" in repaired
    assert repaired["graph"]["nodes"][0]["id"] == "input"
    assert repaired["graph"]["nodes"][1]["type"] == "pipeline"
    assert repaired["graph"]["edges"][0]["from"] == "input"
    assert repaired["graph"]["edges"][0]["kind"] == "stream"
    assert repaired["graph"]["edges"][1]["to_node"] == "output"


def test_repair_workflow_result_exposes_changes():
    result = repair_workflow_result({"nodes": [], "edges": []})

    assert result.changes
    assert result.to_dict()["workflow"]["graph"]["nodes"] == []


def test_repaired_workflow_stays_validator_compatible():
    workflow = {
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
    catalog = {"longlive": {"inputs": ["video"], "outputs": ["video"]}}

    repaired = repair_workflow(workflow)

    assert validate_workflow(repaired, catalog=catalog) == []
