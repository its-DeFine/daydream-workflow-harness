from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness import cli


def test_extract_catalog_writes_json(monkeypatch, tmp_path):
    output = tmp_path / "catalog.json"
    payload = {"app_path": "/Applications/Daydream Scope.app", "pipelines": []}

    monkeypatch.setattr(cli, "extract_scope_catalog", lambda app_path=None: payload)

    exit_code = cli.main(["extract-catalog", "--output", str(output)])

    assert exit_code == 0
    assert json.loads(output.read_text()) == payload


def test_validate_workflow_reports_valid_workflow(tmp_path):
    workflow = tmp_path / "workflow.json"
    catalog = tmp_path / "catalog.json"
    report = tmp_path / "report.json"

    workflow.write_text(
        json.dumps(
            {
                "graph": {
                    "nodes": [
                        {"id": "input", "type": "source"},
                        {"id": "main", "type": "pipeline", "pipeline_id": "longlive"},
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
        ),
        encoding="utf-8",
    )
    catalog.write_text(
        json.dumps(
            {
                "pipelines": [
                    {
                        "pipeline_id": "longlive",
                        "inputs": ["video"],
                        "outputs": ["video"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "validate-workflow",
            str(workflow),
            "--catalog",
            str(catalog),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["valid"] is True
    assert report_data["error_count"] == 0
    assert report_data["errors"] == []


def test_validate_workflow_exits_nonzero_on_invalid_workflow(tmp_path):
    workflow = tmp_path / "workflow.json"
    catalog = tmp_path / "catalog.json"
    report = tmp_path / "report.json"

    workflow.write_text(
        json.dumps(
            {
                "graph": {
                    "nodes": [
                        {"id": "main", "type": "pipeline"},
                        {"id": "main", "type": "sink"},
                    ],
                    "edges": [],
                }
            }
        ),
        encoding="utf-8",
    )
    catalog.write_text(json.dumps({"pipelines": []}), encoding="utf-8")

    exit_code = cli.main(
        [
            "validate-workflow",
            str(workflow),
            "--catalog",
            str(catalog),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 1
    report_data = json.loads(report.read_text())
    assert report_data["valid"] is False
    assert report_data["error_count"] > 0


def test_author_workflow_writes_authoring_result(tmp_path):
    intent = tmp_path / "intent.json"
    catalog = tmp_path / "catalog.json"
    report = tmp_path / "authoring.json"

    intent.write_text(
        json.dumps(
            {
                "objective": "Create a realtime video restyle",
                "notes": ["restyle"],
            }
        ),
        encoding="utf-8",
    )
    catalog.write_text(
        json.dumps(
            {
                "pipelines": [
                    {"pipeline_id": "longlive", "inputs": ["video"], "outputs": ["video"]},
                    {"pipeline_id": "rife", "inputs": ["video"], "outputs": ["video"]},
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "author-workflow",
            str(intent),
            "--catalog",
            str(catalog),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["valid"] is True
    assert report_data["workflow"]["metadata"]["plan_name"] == "direct-restyle"


def test_smoke_validate_writes_result(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.json"
    report = tmp_path / "smoke.json"

    workflow.write_text(
        json.dumps(
            {
                "workflow": {
                    "graph": {"nodes": [], "edges": []},
                    "session": {"prompt": "test"},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli,
        "smoke_validate_workflow",
        lambda payload, **kwargs: SimpleNamespace(
            ok=True,
            to_dict=lambda: {"ok": True, "steps": ["health", "session_start"]},
        ),
    )

    exit_code = cli.main(
        [
            "smoke-validate",
            str(workflow),
            "--base-url",
            "http://scope.test",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["ok"] is True
