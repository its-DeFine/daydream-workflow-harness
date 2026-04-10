from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.reporting import build_validation_report


def test_build_validation_report_groups_errors_and_suggests_fixes():
    errors = [
        "pipeline node 'main' is missing pipeline_id",
        "pipeline node 'main' references unknown pipeline_id 'longlive'",
        "edge[0] is missing to_port",
        "edge[0] has invalid kind 'bogus'",
        "edge[1] references unknown to_node 'missing'",
    ]

    report = build_validation_report(errors, workflow_name="cyborgtd")
    report_dict = report.to_dict()

    assert report_dict["counts"]["total"] == 5
    assert report_dict["categories"]["structure"] == 2
    assert report_dict["categories"]["catalog"] == 1
    assert report_dict["categories"]["ports"] == 2
    assert report_dict["suggestions"][0] == "Review workflow 'cyborgtd' after applying the fixes."
    assert any(
        "Refresh the catalog or install the missing plugin/pipeline." in suggestion
        for suggestion in report_dict["suggestions"]
    )
    assert any(
        finding["category"] == "ports" and finding["code"] == "port_wiring"
        for finding in report_dict["findings"]
    )
