from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness import weave


def test_run_weave_create_can_skip_runtime(tmp_path):
    result = weave.run_weave_create(
        {"objective": "Create a realtime grayscale video effect"},
        output_dir=str(tmp_path),
        catalog={
            "gray": {"pipeline_id": "gray", "inputs": ["video"], "outputs": ["video"]}
        },
        skip_runtime=True,
    )

    assert result.ok is True
    assert Path(result.workflow_path).exists()
    assert Path(result.report_path).exists()
    report = json.loads(Path(result.report_path).read_text())
    assert any(
        check["name"] == "authoring_valid" and check["passed"]
        for check in report["checks"]
    )
    assert any(
        check["name"] == "runtime_recording" and check["required"] is False
        for check in report["checks"]
    )


def test_run_weave_create_packages_runtime_artifacts(monkeypatch, tmp_path):
    recording_bytes = b"fake-mp4"

    def fake_record_validate_workflow(*args, **kwargs):
        Path(kwargs["output_recording_path"]).write_bytes(recording_bytes)
        return SimpleNamespace(
            ok=True,
            input_source_verified=True,
            errors=[],
            to_dict=lambda: {
                "ok": True,
                "session_start": {"cloud_mode": True},
                "recording_path": kwargs["output_recording_path"],
                "recording_bytes": len(recording_bytes),
                "input_source_verified": True,
            },
        )

    monkeypatch.setattr(
        weave, "record_validate_workflow", fake_record_validate_workflow
    )
    monkeypatch.setattr(
        weave,
        "preflight_cloud_runtime",
        lambda **kwargs: SimpleNamespace(
            ok=True,
            classification="ready",
            to_dict=lambda: {
                "ok": True,
                "classification": "ready",
                "endpoint_checks": [],
                "errors": [],
            },
        ),
    )
    monkeypatch.setattr(
        weave,
        "compare_source_to_recording",
        lambda *args, **kwargs: SimpleNamespace(
            ok=True,
            to_dict=lambda: {
                "ok": True,
                "similarity": 0.99,
                "proof_level": "strong",
            },
        ),
    )
    monkeypatch.setattr(
        weave,
        "_safe_video_artifacts",
        lambda recording, output_dir: (
            {
                "ffprobe": {"format": {"size": str(len(recording_bytes))}},
                "contact_sheet": str(output_dir / "contact-sheet.jpg"),
            },
            [],
        ),
    )
    (tmp_path / "contact-sheet.jpg").write_bytes(b"fake-jpeg")

    result = weave.run_weave_create(
        {"objective": "Create a realtime cyborg video restyle"},
        output_dir=str(tmp_path),
        catalog={
            "video-depth-anything": {
                "pipeline_id": "video-depth-anything",
                "inputs": ["video"],
                "outputs": ["video"],
            },
            "longlive": {
                "pipeline_id": "longlive",
                "inputs": ["video"],
                "outputs": ["video"],
            },
            "rife": {"pipeline_id": "rife", "inputs": ["video"], "outputs": ["video"]},
        },
        runtime_mode="cloud",
        input_video_path="/tmp/input.mp4",
        require_input_source=True,
    )

    assert result.ok is True
    assert any(
        check["name"] == "cloud_mode" and check["passed"] for check in result.checks
    )
    assert any(
        check["name"] == "cloud_preflight" and check["passed"]
        for check in result.checks
    )
    assert any(
        check["name"] == "input_source_verified" and check["passed"]
        for check in result.checks
    )
    assert any(
        check["name"] == "visual_source_similarity" and check["passed"]
        for check in result.checks
    )
    assert result.recording_path == str(tmp_path / "recording.mp4")
    assert result.contact_sheet_path == str(tmp_path / "contact-sheet.jpg")


def test_evaluate_intent_candidates_ranks_compatible_templates(tmp_path):
    candidates = weave.evaluate_intent_candidates(
        {"objective": "Create a realtime cyborg depth-conditioned restyle"},
        output_dir=str(tmp_path),
        catalog={
            "video-depth-anything": {
                "pipeline_id": "video-depth-anything",
                "inputs": ["video"],
                "outputs": ["video"],
            },
            "longlive": {
                "pipeline_id": "longlive",
                "inputs": ["video"],
                "outputs": ["video"],
            },
            "rife": {"pipeline_id": "rife", "inputs": ["video"], "outputs": ["video"]},
        },
        limit=2,
    )

    assert candidates
    assert candidates[0]["compatible"] is True
    assert candidates[0]["workflow_path"]
    assert Path(candidates[0]["workflow_path"]).exists()
    assert "rank_score" in candidates[0]
