from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from daydream_workflow_harness.author import author_workflow
from daydream_workflow_harness.compatibility import analyze_workflow_compatibility
from daydream_workflow_harness.repair import repair_workflow_result
from daydream_workflow_harness.runtime import (
    preflight_cloud_runtime,
    record_validate_workflow,
)
from daydream_workflow_harness.source_proof import compare_source_to_recording
from daydream_workflow_harness.templates import (
    build_template_workflow,
    candidate_templates_for_intent,
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _check(
    name: str,
    passed: bool,
    *,
    required: bool = True,
    detail: str = "",
    evidence: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "required": required,
        "detail": detail,
        "evidence": evidence,
    }


def _ffprobe_video(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,nb_frames,duration",
        "-show_entries",
        "format=size,duration,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout or "{}")


def _generate_contact_sheet(video_path: Path, contact_sheet_path: Path) -> None:
    contact_sheet_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "fps=2,scale=288:160,tile=4x3",
        str(contact_sheet_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _safe_video_artifacts(
    video_path: Path, output_dir: Path
) -> tuple[dict[str, Any], list[str]]:
    artifacts: dict[str, Any] = {}
    warnings: list[str] = []

    if not video_path.exists():
        return artifacts, [f"recording path does not exist: {video_path}"]

    try:
        artifacts["ffprobe"] = _ffprobe_video(video_path)
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as exc:
        warnings.append(f"ffprobe failed for {video_path}: {type(exc).__name__}: {exc}")

    contact_sheet_path = output_dir / "contact-sheet.jpg"
    try:
        _generate_contact_sheet(video_path, contact_sheet_path)
        artifacts["contact_sheet"] = str(contact_sheet_path)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        warnings.append(f"contact sheet generation failed: {type(exc).__name__}: {exc}")

    return artifacts, warnings


@dataclass(slots=True)
class WeaveCreateResult:
    ok: bool
    output_dir: str
    workflow_path: str
    authoring_path: str
    report_path: str = ""
    runtime_report_path: str = ""
    recording_path: str = ""
    contact_sheet_path: str = ""
    authoring: dict[str, Any] = field(default_factory=dict)
    compatibility: dict[str, Any] = field(default_factory=dict)
    cloud_preflight: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    runtime: dict[str, Any] = field(default_factory=dict)
    source_proof: dict[str, Any] = field(default_factory=dict)
    video: dict[str, Any] = field(default_factory=dict)
    checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "output_dir": self.output_dir,
            "artifacts": {
                "workflow": self.workflow_path,
                "authoring": self.authoring_path,
                "report": self.report_path,
                "runtime_report": self.runtime_report_path,
                "recording": self.recording_path,
                "contact_sheet": self.contact_sheet_path,
            },
            "authoring": dict(self.authoring),
            "compatibility": dict(self.compatibility),
            "cloud_preflight": dict(self.cloud_preflight),
            "candidates": list(self.candidates),
            "runtime": dict(self.runtime),
            "source_proof": dict(self.source_proof),
            "video": dict(self.video),
            "checks": list(self.checks),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def _candidate_score(candidate: dict[str, Any]) -> float:
    score = float(candidate.get("template_score") or candidate.get("score") or 0)
    compatibility = candidate.get("compatibility") or {}
    if compatibility.get("compatible"):
        score += 10
    runtime = candidate.get("runtime") or {}
    if runtime.get("ok"):
        score += 25
    source_proof = candidate.get("source_proof") or {}
    score += 10 * float(source_proof.get("similarity") or 0)
    return round(score, 4)


def _record_with_optional_repair(
    workflow: Mapping[str, Any],
    *,
    output_dir: Path,
    base_url: str,
    runtime_mode: str,
    input_video_path: str | None,
    record_seconds: float,
    timeout_s: float,
    load_timeout_s: float,
    frame_timeout_s: float,
    poll_interval_s: float,
    attempt_repair: bool,
) -> tuple[Any, list[str], str]:
    recording_path = output_dir / "recording.mp4"
    result = record_validate_workflow(
        dict(workflow),
        base_url=base_url,
        runtime_mode=runtime_mode,
        input_video_path=input_video_path,
        output_recording_path=str(recording_path),
        record_seconds=record_seconds,
        timeout_s=timeout_s,
        load_timeout_s=load_timeout_s,
        frame_timeout_s=frame_timeout_s,
        poll_interval_s=poll_interval_s,
    )
    repair_changes: list[str] = []
    repaired_workflow_path = ""
    if result.ok or not attempt_repair:
        return result, repair_changes, repaired_workflow_path

    repaired = repair_workflow_result(workflow)
    if not repaired.changes:
        return result, repair_changes, repaired_workflow_path

    repaired_workflow_path = str(output_dir / "runtime-repaired-workflow.json")
    _write_json(Path(repaired_workflow_path), repaired.workflow)
    retry_recording_path = output_dir / "recording-retry.mp4"
    retry = record_validate_workflow(
        repaired.workflow,
        base_url=base_url,
        runtime_mode=runtime_mode,
        input_video_path=input_video_path,
        output_recording_path=str(retry_recording_path),
        record_seconds=record_seconds,
        timeout_s=timeout_s,
        load_timeout_s=load_timeout_s,
        frame_timeout_s=frame_timeout_s,
        poll_interval_s=poll_interval_s,
    )
    if retry.ok:
        retry_recording_path.replace(recording_path)
        retry.recording_path = str(recording_path)
        return retry, list(repaired.changes), repaired_workflow_path
    result.errors.extend([f"repair retry failed: {error}" for error in retry.errors])
    return result, list(repaired.changes), repaired_workflow_path


def evaluate_intent_candidates(
    intent: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
    output_dir: str | None = None,
    base_url: str | None = None,
    runtime_mode: str = "local",
    run_runtime: bool = False,
    input_video_path: str | None = None,
    limit: int = 3,
    timeout_s: float = 30.0,
    load_timeout_s: float = 30.0,
    frame_timeout_s: float = 10.0,
    record_seconds: float = 1.0,
    poll_interval_s: float = 0.5,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    root = Path(output_dir) if output_dir else None
    if root is not None:
        root.mkdir(parents=True, exist_ok=True)

    for template in candidate_templates_for_intent(
        intent, catalog=catalog, limit=limit
    ):
        candidate: dict[str, Any] = dict(template)
        candidate["template_score"] = candidate.pop("score", 0)
        try:
            workflow = build_template_workflow(
                template["name"],
                intent,
                catalog=catalog,
            )
        except ValueError as exc:
            candidate["compatible"] = False
            candidate["errors"] = [str(exc)]
            candidate["rank_score"] = _candidate_score(candidate)
            candidates.append(candidate)
            continue

        compatibility = analyze_workflow_compatibility(
            workflow, catalog=catalog
        ).to_dict()
        candidate["compatibility"] = compatibility
        candidate["compatible"] = bool(compatibility.get("compatible"))
        if root is not None:
            candidate_dir = root / f"candidate-{template['name']}"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            workflow_path = candidate_dir / "workflow.json"
            _write_json(workflow_path, workflow)
            candidate["workflow_path"] = str(workflow_path)

        if run_runtime and base_url and candidate["compatible"] and root is not None:
            candidate_dir = root / f"candidate-{template['name']}"
            recording_path = candidate_dir / "recording.mp4"
            runtime_result = record_validate_workflow(
                workflow,
                base_url=base_url,
                runtime_mode=runtime_mode,
                input_video_path=input_video_path,
                output_recording_path=str(recording_path),
                record_seconds=record_seconds,
                timeout_s=timeout_s,
                load_timeout_s=load_timeout_s,
                frame_timeout_s=frame_timeout_s,
                poll_interval_s=poll_interval_s,
            )
            candidate["runtime"] = runtime_result.to_dict()
            if runtime_result.ok and input_video_path:
                candidate["source_proof"] = compare_source_to_recording(
                    input_video_path,
                    str(recording_path),
                ).to_dict()

        candidate["rank_score"] = _candidate_score(candidate)
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (-float(item.get("rank_score") or 0), item["name"])
    )
    return candidates


def create_weave_workflow(
    intent: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
    output_dir: str,
    base_url: str | None = None,
    runtime_mode: str = "local",
    run_runtime: bool = True,
    input_video_path: str | None = None,
    require_input_source: bool = False,
    attempt_repair: bool = True,
    record_seconds: float = 2.0,
    timeout_s: float = 30.0,
    load_timeout_s: float = 30.0,
    frame_timeout_s: float = 10.0,
    poll_interval_s: float = 0.5,
    candidate_limit: int = 4,
) -> WeaveCreateResult:
    """Create, validate, run, and package a Scope workflow from typed intent."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    authoring_result = author_workflow(
        dict(intent),
        catalog=catalog,
        attempt_repair=attempt_repair,
    )
    authoring_payload = authoring_result.to_dict()
    workflow_path = root / "workflow.json"
    authoring_path = root / "authoring-result.json"
    runtime_report_path = root / "runtime-record-report.json"
    report_path = root / "weave-report.json"
    recording_path = root / "recording.mp4"

    _write_json(workflow_path, authoring_result.workflow)
    _write_json(authoring_path, authoring_payload)

    compatibility_payload = analyze_workflow_compatibility(
        authoring_result.workflow,
        catalog=catalog,
    ).to_dict()
    candidates = evaluate_intent_candidates(
        intent,
        catalog=catalog,
        output_dir=str(root / "candidates"),
        limit=candidate_limit,
    )

    checks = [
        _check(
            "authoring_valid",
            authoring_result.valid,
            detail="intent compiled and validated structurally",
            evidence=str(authoring_path),
        ),
        _check(
            "graph_compatible",
            bool(compatibility_payload.get("compatible")),
            detail="node, port, and role wiring is compatible with the catalog",
            evidence=str(workflow_path),
        ),
    ]
    warnings: list[str] = []
    errors: list[str] = []
    runtime_payload: dict[str, Any] = {}
    cloud_preflight_payload: dict[str, Any] = {}
    source_proof_payload: dict[str, Any] = {}
    video_payload: dict[str, Any] = {}
    contact_sheet_path = ""

    if not authoring_result.valid:
        errors.extend(authoring_result.final_errors)
    if not compatibility_payload.get("compatible"):
        errors.extend(
            issue.get("message", "compatibility issue")
            for issue in compatibility_payload.get("issues", [])
        )

    if run_runtime and authoring_result.valid:
        if base_url is None:
            checks.append(
                _check(
                    "runtime_recording",
                    False,
                    detail="base_url is required when runtime validation is enabled",
                )
            )
            errors.append("base_url is required when runtime validation is enabled")
        else:
            if runtime_mode == "cloud":
                preflight = preflight_cloud_runtime(
                    base_url=base_url,
                    pipeline_ids=authoring_result.workflow.get("metadata", {}).get(
                        "pipeline_ids", []
                    ),
                    timeout_s=min(timeout_s, 8.0),
                )
                cloud_preflight_payload = preflight.to_dict()
                checks.append(
                    _check(
                        "cloud_preflight",
                        preflight.ok,
                        detail=f"cloud runtime classification: {preflight.classification}",
                        evidence=str(runtime_report_path),
                    )
                )
                if not preflight.ok:
                    warnings.append(
                        f"cloud preflight failed before runtime: {preflight.classification}"
                    )

            record_result, repair_changes, repaired_workflow_path = (
                _record_with_optional_repair(
                    authoring_result.workflow,
                    output_dir=root,
                    base_url=base_url,
                    runtime_mode=runtime_mode,
                    input_video_path=input_video_path,
                    record_seconds=record_seconds,
                    timeout_s=timeout_s,
                    load_timeout_s=load_timeout_s,
                    frame_timeout_s=frame_timeout_s,
                    poll_interval_s=poll_interval_s,
                    attempt_repair=attempt_repair,
                )
            )
            runtime_payload = record_result.to_dict()
            if repair_changes:
                runtime_payload["repair_retry"] = {
                    "changes": repair_changes,
                    "workflow_path": repaired_workflow_path,
                }
            _write_json(runtime_report_path, runtime_payload)
            checks.append(
                _check(
                    "runtime_recording",
                    record_result.ok,
                    detail="Scope runtime started the graph and returned a non-empty MP4",
                    evidence=str(runtime_report_path),
                )
            )
            if runtime_mode == "cloud":
                checks.append(
                    _check(
                        "cloud_mode",
                        runtime_payload.get("session_start", {}).get("cloud_mode")
                        is True,
                        detail="remote GPU path must report cloud_mode=true",
                        evidence=str(runtime_report_path),
                    )
                )
            if input_video_path or require_input_source:
                input_verified = record_result.input_source_verified is True
                checks.append(
                    _check(
                        "input_source_verified",
                        input_verified,
                        required=require_input_source,
                        detail="session metrics should show input_source_enabled=true",
                        evidence=str(runtime_report_path),
                    )
                )
                if record_result.input_source_verified is not True:
                    warnings.append(
                        "input source was not verified by Scope session metrics; "
                        "inspect the recording/contact sheet before making a strict "
                        "video-to-video source-ingestion claim"
                    )
            if record_result.errors:
                errors.extend(record_result.errors)

            if record_result.ok:
                video_payload, artifact_warnings = _safe_video_artifacts(
                    recording_path,
                    root,
                )
                warnings.extend(artifact_warnings)
                if input_video_path:
                    source_proof_payload = compare_source_to_recording(
                        input_video_path,
                        str(recording_path),
                    ).to_dict()
                    checks.append(
                        _check(
                            "visual_source_similarity",
                            bool(source_proof_payload.get("ok")),
                            required=False,
                            detail=(
                                "ffmpeg thumbnail similarity between input video "
                                "and recorded output"
                            ),
                            evidence=str(recording_path),
                        )
                    )
                contact_sheet_path = str(root / "contact-sheet.jpg")
                checks.append(
                    _check(
                        "video_probe",
                        bool(video_payload.get("ffprobe")),
                        required=False,
                        detail="ffprobe metadata was collected for the MP4",
                        evidence=str(recording_path),
                    )
                )
                checks.append(
                    _check(
                        "contact_sheet",
                        Path(contact_sheet_path).exists(),
                        required=False,
                        detail="contact sheet generated for visual review",
                        evidence=contact_sheet_path,
                    )
                )
    elif not run_runtime:
        checks.append(
            _check(
                "runtime_recording",
                True,
                required=False,
                detail="runtime validation was skipped by caller",
            )
        )

    ok = all(check["passed"] for check in checks if check.get("required", True))
    result = WeaveCreateResult(
        ok=ok,
        output_dir=str(root),
        workflow_path=str(workflow_path),
        authoring_path=str(authoring_path),
        report_path=str(report_path),
        runtime_report_path=str(runtime_report_path) if runtime_payload else "",
        recording_path=str(recording_path) if recording_path.exists() else "",
        contact_sheet_path=contact_sheet_path
        if Path(contact_sheet_path).exists()
        else "",
        authoring=authoring_payload,
        compatibility=compatibility_payload,
        cloud_preflight=cloud_preflight_payload,
        candidates=candidates,
        runtime=runtime_payload,
        source_proof=source_proof_payload,
        video=video_payload,
        checks=checks,
        warnings=warnings,
        errors=errors,
    )
    _write_json(report_path, result.to_dict() | {"created_at": int(time.time())})
    return result


def run_weave_create(
    intent: Mapping[str, Any],
    *,
    output_dir: str,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
    base_url: str = "http://127.0.0.1:8000",
    runtime_mode: str = "local",
    skip_runtime: bool = False,
    input_video_path: str | None = None,
    require_input_source: bool = False,
    record_seconds: float = 2.0,
    timeout_s: float = 30.0,
    load_timeout_s: float = 30.0,
    frame_timeout_s: float = 10.0,
    poll_interval_s: float = 0.5,
    candidate_limit: int = 4,
) -> WeaveCreateResult:
    """Compatibility wrapper for the CLI command name."""

    return create_weave_workflow(
        intent,
        output_dir=output_dir,
        catalog=catalog,
        base_url=base_url,
        runtime_mode=runtime_mode,
        run_runtime=not skip_runtime,
        input_video_path=input_video_path,
        require_input_source=require_input_source,
        record_seconds=record_seconds,
        timeout_s=timeout_s,
        load_timeout_s=load_timeout_s,
        frame_timeout_s=frame_timeout_s,
        poll_interval_s=poll_interval_s,
        candidate_limit=candidate_limit,
    )
