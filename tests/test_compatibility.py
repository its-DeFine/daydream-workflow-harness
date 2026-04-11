from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.compatibility import analyze_workflow_compatibility


def test_analyze_workflow_compatibility_accepts_source_pipeline_sink():
    workflow = {
        "graph": {
            "nodes": [
                {"id": "input", "type": "source"},
                {"id": "main", "type": "pipeline", "pipeline_id": "gray"},
                {"id": "output", "type": "sink"},
            ],
            "edges": [
                {
                    "from": "input",
                    "from_port": "video",
                    "to_node": "main",
                    "to_port": "video",
                },
                {
                    "from": "main",
                    "from_port": "video",
                    "to_node": "output",
                    "to_port": "video",
                },
            ],
        }
    }

    report = analyze_workflow_compatibility(
        workflow,
        catalog={
            "gray": {"pipeline_id": "gray", "inputs": ["video"], "outputs": ["video"]}
        },
    )

    assert report.compatible is True
    assert report.pipeline_ids == ["gray"]
    assert report.graph_summary["role_sequence"] == ["source", "pipeline", "sink"]


def test_analyze_workflow_compatibility_rejects_bad_pipeline_port():
    workflow = {
        "graph": {
            "nodes": [
                {"id": "input", "type": "source"},
                {"id": "main", "type": "pipeline", "pipeline_id": "gray"},
            ],
            "edges": [
                {
                    "from": "input",
                    "from_port": "video",
                    "to_node": "main",
                    "to_port": "mask",
                }
            ],
        }
    }

    report = analyze_workflow_compatibility(
        workflow,
        catalog={
            "gray": {"pipeline_id": "gray", "inputs": ["video"], "outputs": ["video"]}
        },
    )

    assert report.compatible is False
    assert any(issue.code == "invalid_to_port" for issue in report.issues)
