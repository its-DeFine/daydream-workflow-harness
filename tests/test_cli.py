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


def test_extract_catalog_can_fetch_from_runtime(monkeypatch, tmp_path):
    output = tmp_path / "catalog.json"
    payload = {
        "source": "runtime",
        "base_url": "http://scope.test",
        "pipelines": [
            {"pipeline_id": "gray", "inputs": ["video"], "outputs": ["video"]}
        ],
    }

    monkeypatch.setattr(cli, "fetch_live_catalog", lambda base_url=None: payload)

    exit_code = cli.main(
        [
            "extract-catalog",
            "--base-url",
            "http://scope.test",
            "--output",
            str(output),
        ]
    )

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


def test_validate_workflow_accepts_runtime_schema_object_catalog(tmp_path):
    workflow = tmp_path / "workflow.json"
    catalog = tmp_path / "catalog.json"
    report = tmp_path / "report.json"

    workflow.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    catalog.write_text(
        json.dumps(
            {
                "pipelines": {
                    "gray": {
                        "id": "gray",
                        "inputs": ["video"],
                        "outputs": ["video"],
                    }
                }
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
                    {
                        "pipeline_id": "longlive",
                        "inputs": ["video"],
                        "outputs": ["video"],
                    },
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


def test_author_workflow_without_catalog_or_app_path_uses_empty_catalog(tmp_path):
    intent = tmp_path / "intent.json"
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

    exit_code = cli.main(
        [
            "author-workflow",
            str(intent),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["valid"] is True
    assert report_data["workflow"]["metadata"]["plan_name"] == "direct-restyle"


def test_author_workflow_can_fetch_runtime_catalog(monkeypatch, tmp_path):
    intent = tmp_path / "intent.json"
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

    monkeypatch.setattr(
        cli,
        "fetch_live_catalog",
        lambda base_url=None: {
            "source": "runtime",
            "base_url": base_url,
            "pipelines": {
                "longlive": {
                    "id": "longlive",
                    "inputs": ["video"],
                    "outputs": ["video"],
                },
                "rife": {"id": "rife", "inputs": ["video"], "outputs": ["video"]},
            },
        },
    )

    exit_code = cli.main(
        [
            "author-workflow",
            str(intent),
            "--base-url",
            "http://scope.test",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["valid"] is True
    assert report_data["workflow"]["metadata"]["plan_name"] == "direct-restyle"


def test_author_workflow_can_generate_live_compatible_grayscale_plan(
    monkeypatch, tmp_path
):
    intent = tmp_path / "intent.json"
    report = tmp_path / "authoring.json"

    intent.write_text(
        json.dumps(
            {
                "objective": "Create a realtime grayscale video effect",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli,
        "fetch_live_catalog",
        lambda base_url=None: {
            "source": "runtime",
            "base_url": base_url,
            "pipelines": {
                "gray": {"id": "gray", "inputs": ["video"], "outputs": ["video"]},
            },
        },
    )

    exit_code = cli.main(
        [
            "author-workflow",
            str(intent),
            "--base-url",
            "http://scope.test",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["valid"] is True
    assert report_data["workflow"]["metadata"]["plan_name"] == "grayscale-preview"


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


def test_record_validate_writes_result(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.json"
    report = tmp_path / "record.json"
    recording = tmp_path / "recording.mp4"

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
        "record_validate_workflow",
        lambda payload, **kwargs: SimpleNamespace(
            ok=True,
            to_dict=lambda: {
                "ok": True,
                "record_node_id": kwargs["record_node_id"],
                "sink_node_id": "output",
                "recording_bytes": 12,
                "recording_path": str(recording),
                "steps": ["health", "session_start", "recording_download"],
            },
        ),
    )

    exit_code = cli.main(
        [
            "record-validate",
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
    assert report_data["record_node_id"] == "record"


def test_cloud_connect_writes_lifecycle_result(monkeypatch, tmp_path):
    report = tmp_path / "cloud-connect.json"

    monkeypatch.setattr(
        cli,
        "connect_cloud_runtime",
        lambda **kwargs: SimpleNamespace(
            ok=True,
            to_dict=lambda: {
                "ok": True,
                "action": "connect",
                "pipeline_ids": kwargs["pipeline_ids"],
                "wait": kwargs["wait"],
            },
        ),
    )

    exit_code = cli.main(
        [
            "cloud-connect",
            "--base-url",
            "http://scope.test",
            "--wait",
            "--pipeline-id",
            "gray",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["ok"] is True
    assert report_data["action"] == "connect"
    assert report_data["pipeline_ids"] == ["gray"]
    assert report_data["wait"] is True


def test_cloud_preflight_writes_nonzero_result(monkeypatch, tmp_path):
    report = tmp_path / "cloud-preflight.json"

    monkeypatch.setattr(
        cli,
        "preflight_cloud_runtime",
        lambda **kwargs: SimpleNamespace(
            ok=False,
            to_dict=lambda: {
                "ok": False,
                "classification": "cloud_proxy_unavailable",
                "pipeline_ids": kwargs["pipeline_ids"],
            },
        ),
    )

    exit_code = cli.main(
        [
            "cloud-preflight",
            "--pipeline-id",
            "gray",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 1
    report_data = json.loads(report.read_text())
    assert report_data["classification"] == "cloud_proxy_unavailable"
    assert report_data["pipeline_ids"] == ["gray"]


def test_cloud_disconnect_writes_lifecycle_result(monkeypatch, tmp_path):
    report = tmp_path / "cloud-disconnect.json"

    monkeypatch.setattr(
        cli,
        "disconnect_cloud_runtime",
        lambda **kwargs: SimpleNamespace(
            ok=True,
            to_dict=lambda: {
                "ok": True,
                "action": "disconnect",
                "base_url": kwargs["base_url"],
            },
        ),
    )

    exit_code = cli.main(
        [
            "cloud-disconnect",
            "--base-url",
            "http://scope.test",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["ok"] is True
    assert report_data["action"] == "disconnect"
    assert report_data["base_url"] == "http://scope.test"


def test_weave_create_writes_packaged_result(monkeypatch, tmp_path):
    intent = tmp_path / "intent.json"
    output_dir = tmp_path / "weave"
    report = tmp_path / "weave-report.json"

    intent.write_text(
        json.dumps({"objective": "Create a realtime video restyle"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli,
        "create_weave_workflow",
        lambda intent, **kwargs: SimpleNamespace(
            ok=True,
            to_dict=lambda: {
                "ok": True,
                "output_dir": kwargs["output_dir"],
                "checks": [
                    {"name": "runtime_enabled", "passed": kwargs["run_runtime"]}
                ],
            },
        ),
    )

    exit_code = cli.main(
        [
            "weave-create",
            str(intent),
            "--output-dir",
            str(output_dir),
            "--skip-runtime",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["ok"] is True
    assert report_data["output_dir"] == str(output_dir)


def test_weave_evaluate_candidates_writes_report(monkeypatch, tmp_path):
    intent = tmp_path / "intent.json"
    report = tmp_path / "candidates.json"
    output_dir = tmp_path / "candidates"

    intent.write_text(
        json.dumps({"objective": "Create a realtime video restyle"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli,
        "evaluate_intent_candidates",
        lambda intent, **kwargs: [
            {
                "name": "direct-restyle",
                "rank_score": 12,
                "output_dir": kwargs["output_dir"],
            }
        ],
    )

    exit_code = cli.main(
        [
            "weave-evaluate-candidates",
            str(intent),
            "--output-dir",
            str(output_dir),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["ok"] is True
    assert report_data["candidate_count"] == 1
    assert report_data["candidates"][0]["name"] == "direct-restyle"


def test_evaluate_regeneration_writes_report(monkeypatch, tmp_path):
    cases = tmp_path / "cases.json"
    report = tmp_path / "evaluation.json"

    cases.write_text(json.dumps({"cases": [{"slug": "demo"}]}), encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "evaluate_blind_regeneration",
        lambda payload, **kwargs: {
            "summary": {
                "total_cases": 1,
                "exact_matches": 0,
                "mismatches": 1,
                "exact_match_rate": 0.0,
            },
            "results": [{"slug": "demo", "exact_match": False}],
        },
    )

    exit_code = cli.main(
        [
            "evaluate-regeneration",
            str(cases),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 1
    report_data = json.loads(report.read_text())
    assert report_data["summary"]["total_cases"] == 1


def test_evaluate_equivalence_writes_report(monkeypatch, tmp_path):
    payload = tmp_path / "published.json"
    report = tmp_path / "equivalence.json"

    payload.write_text(json.dumps({"workflows": [{"slug": "demo"}]}), encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "evaluate_published_workflow_equivalence",
        lambda data: {
            "summary": {"total_cases": 1, "chain_exact_matches": 1},
            "results": [{"slug": "demo", "chain_exact": True}],
        },
    )

    exit_code = cli.main(
        [
            "evaluate-equivalence",
            str(payload),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["summary"]["total_cases"] == 1
    assert report_data["results"][0]["slug"] == "demo"


def test_benchmark_published_writes_report(monkeypatch, tmp_path):
    payload = tmp_path / "published.json"
    report = tmp_path / "benchmark.json"

    payload.write_text(json.dumps({"workflows": []}), encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "benchmark_published_workflows",
        lambda payload: SimpleNamespace(
            to_dict=lambda: {
                "total": 1,
                "exact_matches": 1,
                "exact_match_rate": 1.0,
                "entries": [{"slug": "demo", "exact_match": True}],
            }
        ),
    )

    exit_code = cli.main(
        [
            "benchmark-published",
            str(payload),
            "--output",
            str(report),
        ]
    )

    assert exit_code == 0
    report_data = json.loads(report.read_text())
    assert report_data["total"] == 1
