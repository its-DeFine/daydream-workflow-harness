from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.validator import (
    assert_valid_workflow,
    is_valid_workflow,
    validate_workflow,
)


def sample_workflow() -> dict[str, object]:
    return {
        "name": "sample",
        "graph": {
            "nodes": [
                {"id": "input", "type": "source"},
                {"id": "main", "type": "pipeline", "pipeline_id": "longlive"},
                {"id": "output", "type": "sink"},
            ],
            "edges": [
                {"from": "input", "from_port": "video", "to_node": "main", "to_port": "video", "kind": "stream"},
                {"from": "main", "from_port": "video", "to_node": "output", "to_port": "video", "kind": "stream"},
            ],
        },
    }


def test_validate_workflow_accepts_a_simple_graph():
    catalog = {"longlive": {"inputs": ["video"], "outputs": ["video"]}}

    errors = validate_workflow(sample_workflow(), catalog=catalog)

    assert errors == []
    assert is_valid_workflow(sample_workflow(), catalog=catalog)
    assert_valid_workflow(sample_workflow(), catalog=catalog)


def test_validate_workflow_reports_port_and_structure_errors():
    workflow = {
        "graph": {
            "nodes": [
                {"id": "input", "type": "source"},
                {"id": "main", "type": "pipeline"},
                {"id": "main", "type": "sink"},
            ],
            "edges": [
                {"from": "input", "from_port": "video", "to_node": "main", "to_port": "video", "kind": "stream"},
                {"from": "main", "from_port": "bad_port", "to_node": "missing", "to_port": "", "kind": "stream"},
            ],
        }
    }
    catalog = {"longlive": {"inputs": ["video"], "outputs": ["video"]}}

    errors = validate_workflow(workflow, catalog=catalog)

    assert any("missing pipeline_id" in error for error in errors)
    assert any("duplicate node id" in error for error in errors)
    assert any("unknown to_node" in error for error in errors)
    assert any("missing to_port" in error for error in errors)

