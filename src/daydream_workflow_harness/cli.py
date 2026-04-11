from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from daydream_workflow_harness.author import author_workflow
from daydream_workflow_harness.benchmark import benchmark_published_workflows
from daydream_workflow_harness.catalog import build_catalog_index_from_payload
from daydream_workflow_harness.equivalence import (
    evaluate_published_workflow_equivalence,
)
from daydream_workflow_harness.evaluate import evaluate_blind_regeneration
from daydream_workflow_harness.extract_scope import extract_scope_catalog
from daydream_workflow_harness.runtime import (
    fetch_live_catalog,
    record_validate_workflow,
    smoke_validate_workflow,
)
from daydream_workflow_harness.validator import validate_workflow
from daydream_workflow_harness.weave import (
    create_weave_workflow,
    evaluate_intent_candidates,
)


def _load_json(path: str | None) -> Any:
    if path is None:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump_json(payload: Any, output: str | None, indent: int = 2) -> None:
    text = json.dumps(payload, indent=indent, sort_keys=True)
    if output is None:
        sys.stdout.write(text)
        sys.stdout.write("\n")
        return
    Path(output).write_text(text + "\n", encoding="utf-8")


def _load_catalog_payload(
    *,
    catalog_path: str | None,
    app_path: str | None,
    base_url: str | None,
) -> Any:
    catalog_payload = _load_json(catalog_path)
    if catalog_payload is not None:
        return catalog_payload
    if base_url:
        return fetch_live_catalog(base_url=base_url)
    if app_path:
        return extract_scope_catalog(app_path=app_path)
    return None


def cmd_extract_catalog(args: argparse.Namespace) -> int:
    if args.base_url:
        catalog = fetch_live_catalog(base_url=args.base_url)
    else:
        catalog = extract_scope_catalog(app_path=args.app_path)
    _dump_json(catalog, args.output)
    return 0


def cmd_validate_workflow(args: argparse.Namespace) -> int:
    workflow = _load_json(args.workflow)
    if workflow is None:
        raise ValueError("workflow path is required")

    catalog_payload = _load_catalog_payload(
        catalog_path=args.catalog,
        app_path=args.app_path,
        base_url=args.base_url,
    )
    catalog = build_catalog_index_from_payload(catalog_payload)
    errors = validate_workflow(workflow, catalog=catalog)
    report = {
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
    }
    _dump_json(report, args.output)
    return 0 if not errors else 1


def cmd_author_workflow(args: argparse.Namespace) -> int:
    intent = _load_json(args.intent)
    if intent is None:
        raise ValueError("intent path is required")

    catalog_payload = _load_catalog_payload(
        catalog_path=args.catalog,
        app_path=args.app_path,
        base_url=args.base_url,
    )
    catalog = (
        build_catalog_index_from_payload(catalog_payload)
        if catalog_payload is not None
        else None
    )

    result = author_workflow(
        intent,
        catalog=catalog,
        attempt_repair=not args.no_repair,
    )
    _dump_json(result.to_dict(), args.output)
    return 0 if result.valid else 1


def cmd_smoke_validate(args: argparse.Namespace) -> int:
    workflow = _load_json(args.workflow)
    if workflow is None:
        raise ValueError("workflow path is required")

    result = smoke_validate_workflow(
        workflow,
        base_url=args.base_url,
        timeout_s=float(args.timeout),
        load_timeout_s=float(args.load_timeout),
        frame_timeout_s=float(args.frame_timeout),
        poll_interval_s=float(args.poll_interval),
        runtime_mode=args.runtime_mode,
    )
    _dump_json(result.to_dict(), args.output)
    return 0 if result.ok else 1


def cmd_record_validate(args: argparse.Namespace) -> int:
    workflow = _load_json(args.workflow)
    if workflow is None:
        raise ValueError("workflow path is required")

    result = record_validate_workflow(
        workflow,
        base_url=args.base_url,
        timeout_s=float(args.timeout),
        load_timeout_s=float(args.load_timeout),
        frame_timeout_s=float(args.frame_timeout),
        record_seconds=float(args.record_seconds),
        poll_interval_s=float(args.poll_interval),
        record_node_id=args.record_node_id,
        sink_node_id=args.sink_node_id,
        output_recording_path=args.output_recording,
        input_video_path=args.input_video,
        runtime_mode=args.runtime_mode,
    )
    _dump_json(result.to_dict(), args.output)
    return 0 if result.ok else 1


def cmd_weave_create(args: argparse.Namespace) -> int:
    intent = _load_json(args.intent)
    if intent is None:
        raise ValueError("intent path is required")

    catalog_payload = _load_catalog_payload(
        catalog_path=args.catalog,
        app_path=args.app_path,
        base_url=args.base_url if args.base_url_catalog else None,
    )
    catalog = (
        build_catalog_index_from_payload(catalog_payload)
        if catalog_payload is not None
        else None
    )

    result = create_weave_workflow(
        intent,
        output_dir=args.output_dir,
        catalog=catalog,
        base_url=args.base_url,
        runtime_mode=args.runtime_mode,
        run_runtime=not args.skip_runtime,
        input_video_path=args.input_video,
        require_input_source=args.require_input_source,
        attempt_repair=not args.no_repair,
        record_seconds=float(args.record_seconds),
        timeout_s=float(args.timeout),
        load_timeout_s=float(args.load_timeout),
        frame_timeout_s=float(args.frame_timeout),
        poll_interval_s=float(args.poll_interval),
        candidate_limit=int(args.candidate_limit),
    )
    _dump_json(result.to_dict(), args.output)
    return 0 if result.ok else 1


def cmd_weave_evaluate_candidates(args: argparse.Namespace) -> int:
    intent = _load_json(args.intent)
    if intent is None:
        raise ValueError("intent path is required")

    catalog_payload = _load_catalog_payload(
        catalog_path=args.catalog,
        app_path=args.app_path,
        base_url=args.base_url if args.base_url_catalog else None,
    )
    catalog = (
        build_catalog_index_from_payload(catalog_payload)
        if catalog_payload is not None
        else None
    )

    result = evaluate_intent_candidates(
        intent,
        catalog=catalog,
        output_dir=args.output_dir,
        base_url=args.base_url,
        runtime_mode=args.runtime_mode,
        run_runtime=args.run_runtime,
        input_video_path=args.input_video,
        limit=int(args.limit),
        timeout_s=float(args.timeout),
        load_timeout_s=float(args.load_timeout),
        frame_timeout_s=float(args.frame_timeout),
        record_seconds=float(args.record_seconds),
        poll_interval_s=float(args.poll_interval),
    )
    payload = {
        "ok": bool(result),
        "candidate_count": len(result),
        "candidates": result,
    }
    _dump_json(payload, args.output)
    return 0 if result else 1


def cmd_evaluate_regeneration(args: argparse.Namespace) -> int:
    cases = _load_json(args.cases)
    if cases is None:
        raise ValueError("cases path is required")

    catalog_payload = _load_catalog_payload(
        catalog_path=args.catalog,
        app_path=args.app_path,
        base_url=args.base_url,
    )
    catalog = (
        build_catalog_index_from_payload(catalog_payload)
        if catalog_payload is not None
        else None
    )
    report = evaluate_blind_regeneration(cases, catalog=catalog)
    _dump_json(report, args.output)
    summary = report.get("summary") or {}
    exact_matches = int(summary.get("exact_matches") or 0)
    total_cases = int(summary.get("total_cases") or 0)
    return 0 if total_cases > 0 and exact_matches == total_cases else 1


def cmd_benchmark_published(args: argparse.Namespace) -> int:
    payload = _load_json(args.payload)
    if payload is None:
        raise ValueError("payload path is required")

    report = benchmark_published_workflows(payload).to_dict()
    _dump_json(report, args.output)
    total = int(report.get("total") or 0)
    exact_matches = int(report.get("exact_matches") or 0)
    return 0 if total > 0 and exact_matches == total else 1


def cmd_evaluate_equivalence(args: argparse.Namespace) -> int:
    payload = _load_json(args.payload)
    if payload is None:
        raise ValueError("payload path is required")

    report = evaluate_published_workflow_equivalence(payload)
    _dump_json(report, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daydream-workflow-harness",
        description="Authoring harness for Daydream Scope workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser(
        "extract-catalog", help="Extract Scope pipeline metadata as JSON."
    )
    extract.add_argument("--app-path", default=None, help="Path to Daydream Scope.app")
    extract.add_argument(
        "--base-url",
        default=None,
        help="Fetch the catalog from a running Scope server instead of the app bundle",
    )
    extract.add_argument(
        "--output",
        default=None,
        help="Write JSON to a file instead of stdout",
    )
    extract.set_defaults(func=cmd_extract_catalog)

    validate = subparsers.add_parser(
        "validate-workflow", help="Validate a workflow JSON file against a catalog."
    )
    validate.add_argument("workflow", help="Path to workflow JSON")
    validate.add_argument(
        "--catalog",
        default=None,
        help="Path to a catalog JSON file produced by extract-catalog",
    )
    validate.add_argument(
        "--app-path",
        default=None,
        help="Path to Daydream Scope.app when catalog is not supplied",
    )
    validate.add_argument(
        "--base-url",
        default=None,
        help="Use a running Scope server as the catalog source when catalog is not supplied",
    )
    validate.add_argument(
        "--output",
        default=None,
        help="Write validation report JSON to a file instead of stdout",
    )
    validate.set_defaults(func=cmd_validate_workflow)

    author = subparsers.add_parser(
        "author-workflow",
        help="Generate a workflow from typed intent, then validate and report.",
    )
    author.add_argument("intent", help="Path to typed intent JSON")
    author.add_argument(
        "--catalog",
        default=None,
        help="Path to a catalog JSON file produced by extract-catalog",
    )
    author.add_argument(
        "--app-path",
        default=None,
        help="Path to Daydream Scope.app when catalog is not supplied",
    )
    author.add_argument(
        "--base-url",
        default=None,
        help="Use a running Scope server as the catalog source when catalog is not supplied",
    )
    author.add_argument(
        "--no-repair",
        action="store_true",
        help="Disable conservative repair before the final validation report",
    )
    author.add_argument(
        "--output",
        default=None,
        help="Write authoring result JSON to a file instead of stdout",
    )
    author.set_defaults(func=cmd_author_workflow)

    smoke = subparsers.add_parser(
        "smoke-validate",
        help="Validate a workflow against a running Scope instance.",
    )
    smoke.add_argument(
        "workflow", help="Path to workflow JSON or authoring result JSON"
    )
    smoke.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the Scope server",
    )
    smoke.add_argument(
        "--timeout",
        default="30",
        help="HTTP request timeout in seconds",
    )
    smoke.add_argument(
        "--load-timeout",
        default="30",
        help="Time to wait for pipeline load status",
    )
    smoke.add_argument(
        "--frame-timeout",
        default="10",
        help="Time to wait for a captured frame after session start",
    )
    smoke.add_argument(
        "--poll-interval",
        default="0.5",
        help="Polling interval while waiting for load/frame readiness",
    )
    smoke.add_argument(
        "--runtime-mode",
        choices=("local", "cloud"),
        default="local",
        help=(
            "Validation runtime. Use cloud to preflight /api/v1/cloud/status "
            "and require session_start.cloud_mode=true."
        ),
    )
    smoke.add_argument(
        "--output",
        default=None,
        help="Write smoke validation report JSON to a file instead of stdout",
    )
    smoke.set_defaults(func=cmd_smoke_validate)

    record = subparsers.add_parser(
        "record-validate",
        help=(
            "Validate a workflow and save a recorded MP4 from the active "
            "headless session."
        ),
    )
    record.add_argument(
        "workflow",
        help="Path to workflow JSON or authoring result JSON",
    )
    record.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the Scope server",
    )
    record.add_argument(
        "--timeout",
        default="30",
        help="HTTP request timeout in seconds",
    )
    record.add_argument(
        "--load-timeout",
        default="30",
        help="Time to wait for pipeline load status",
    )
    record.add_argument(
        "--frame-timeout",
        default="10",
        help="Time to wait for a captured frame after session start",
    )
    record.add_argument(
        "--record-seconds",
        default="2",
        help="Time to keep recording before downloading",
    )
    record.add_argument(
        "--poll-interval",
        default="0.5",
        help="Polling interval while waiting for load/frame readiness",
    )
    record.add_argument(
        "--record-node-id",
        default="record",
        help="Record node id to inject or target",
    )
    record.add_argument(
        "--sink-node-id",
        default=None,
        help="Optional sink node id to wire into the record node",
    )
    record.add_argument(
        "--output-recording",
        default=None,
        help="Optional path to write the downloaded MP4 recording",
    )
    record.add_argument(
        "--input-video",
        default=None,
        help=(
            "Optional local video file to assign to the first source node as "
            "source_mode=video_file for deterministic local validation"
        ),
    )
    record.add_argument(
        "--runtime-mode",
        choices=("local", "cloud"),
        default="local",
        help=(
            "Validation runtime. Use cloud to preflight /api/v1/cloud/status "
            "and require session_start.cloud_mode=true."
        ),
    )
    record.add_argument(
        "--output",
        default=None,
        help="Write validation report JSON to a file instead of stdout",
    )
    record.set_defaults(func=cmd_record_validate)

    weave = subparsers.add_parser(
        "weave-create",
        help=(
            "Author a Scope workflow from intent, then package workflow, "
            "runtime report, recording, and contact sheet artifacts."
        ),
    )
    weave.add_argument("intent", help="Path to typed intent JSON")
    weave.add_argument(
        "--output-dir",
        default="weave-artifacts",
        help="Directory for workflow/report/recording artifacts",
    )
    weave.add_argument(
        "--catalog",
        default=None,
        help="Path to a catalog JSON file produced by extract-catalog",
    )
    weave.add_argument(
        "--app-path",
        default=None,
        help="Path to Daydream Scope.app when catalog is not supplied",
    )
    weave.add_argument(
        "--base-url-catalog",
        action="store_true",
        help="Use --base-url as a live catalog source before authoring",
    )
    weave.add_argument(
        "--base-url",
        default="http://127.0.0.1:52178",
        help="Base URL for the Scope server used by runtime validation",
    )
    weave.add_argument(
        "--runtime-mode",
        choices=("local", "cloud"),
        default="cloud",
        help="Runtime validation mode",
    )
    weave.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Only author and structurally validate; do not start Scope",
    )
    weave.add_argument(
        "--input-video",
        default=None,
        help="Optional local video file assigned to the first source node",
    )
    weave.add_argument(
        "--require-input-source",
        action="store_true",
        help="Fail if runtime metrics do not verify input_source_enabled=true",
    )
    weave.add_argument(
        "--no-repair",
        action="store_true",
        help="Disable conservative repair before final structural validation",
    )
    weave.add_argument(
        "--timeout",
        default="30",
        help="HTTP request timeout in seconds",
    )
    weave.add_argument(
        "--load-timeout",
        default="30",
        help="Time to wait for pipeline load status",
    )
    weave.add_argument(
        "--frame-timeout",
        default="10",
        help="Time to wait for a captured frame after session start",
    )
    weave.add_argument(
        "--record-seconds",
        default="2",
        help="Time to keep recording before downloading",
    )
    weave.add_argument(
        "--poll-interval",
        default="0.5",
        help="Polling interval while waiting for load/frame readiness",
    )
    weave.add_argument(
        "--output",
        default=None,
        help="Write Weave report JSON to a file instead of stdout",
    )
    weave.add_argument(
        "--candidate-limit",
        default="4",
        help="Number of compatible template candidates to include in the report",
    )
    weave.set_defaults(func=cmd_weave_create)

    weave_candidates = subparsers.add_parser(
        "weave-evaluate-candidates",
        help="Rank template workflow candidates for an intent.",
    )
    weave_candidates.add_argument("intent", help="Path to typed intent JSON")
    weave_candidates.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for candidate workflow/runtime artifacts",
    )
    weave_candidates.add_argument(
        "--catalog",
        default=None,
        help="Path to a catalog JSON file produced by extract-catalog",
    )
    weave_candidates.add_argument(
        "--app-path",
        default=None,
        help="Path to Daydream Scope.app when catalog is not supplied",
    )
    weave_candidates.add_argument(
        "--base-url-catalog",
        action="store_true",
        help="Use --base-url as a live catalog source before evaluation",
    )
    weave_candidates.add_argument(
        "--base-url",
        default="http://127.0.0.1:52178",
        help="Base URL for optional runtime validation",
    )
    weave_candidates.add_argument(
        "--runtime-mode",
        choices=("local", "cloud"),
        default="local",
        help="Runtime validation mode when --run-runtime is set",
    )
    weave_candidates.add_argument(
        "--run-runtime",
        action="store_true",
        help="Run each compatible candidate and record MP4 artifacts",
    )
    weave_candidates.add_argument(
        "--input-video",
        default=None,
        help="Optional local video file assigned to the first source node",
    )
    weave_candidates.add_argument(
        "--limit",
        default="3",
        help="Number of candidates to evaluate",
    )
    weave_candidates.add_argument(
        "--timeout",
        default="30",
        help="HTTP request timeout in seconds",
    )
    weave_candidates.add_argument(
        "--load-timeout",
        default="30",
        help="Time to wait for pipeline load status",
    )
    weave_candidates.add_argument(
        "--frame-timeout",
        default="10",
        help="Time to wait for a captured frame after session start",
    )
    weave_candidates.add_argument(
        "--record-seconds",
        default="1",
        help="Time to keep recording before downloading",
    )
    weave_candidates.add_argument(
        "--poll-interval",
        default="0.5",
        help="Polling interval while waiting for load/frame readiness",
    )
    weave_candidates.add_argument(
        "--output",
        default=None,
        help="Write candidate report JSON to a file instead of stdout",
    )
    weave_candidates.set_defaults(func=cmd_weave_evaluate_candidates)

    evaluate = subparsers.add_parser(
        "evaluate-regeneration",
        help="Score blind-regeneration matches on a held-out workflow set.",
    )
    evaluate.add_argument(
        "cases", help="Path to a JSON fixture of held-out workflow cases"
    )
    evaluate.add_argument(
        "--catalog",
        default=None,
        help="Path to a catalog JSON file produced by extract-catalog",
    )
    evaluate.add_argument(
        "--app-path",
        default=None,
        help="Path to Daydream Scope.app when catalog is not supplied",
    )
    evaluate.add_argument(
        "--base-url",
        default=None,
        help="Use a running Scope server as the catalog source when catalog is not supplied",
    )
    evaluate.add_argument(
        "--output",
        default=None,
        help="Write evaluation report JSON to a file instead of stdout",
    )
    evaluate.set_defaults(func=cmd_evaluate_regeneration)

    benchmark = subparsers.add_parser(
        "benchmark-published",
        help="Benchmark the planner against a published workflow corpus snapshot.",
    )
    benchmark.add_argument(
        "payload", help="Path to a published workflow corpus JSON file"
    )
    benchmark.add_argument(
        "--output",
        default=None,
        help="Write benchmark report JSON to a file instead of stdout",
    )
    benchmark.set_defaults(func=cmd_benchmark_published)

    equivalence = subparsers.add_parser(
        "evaluate-equivalence",
        help="Score parameter/timeline equivalence against a published workflow corpus.",
    )
    equivalence.add_argument(
        "payload", help="Path to a published workflow corpus JSON payload"
    )
    equivalence.add_argument(
        "--output",
        default=None,
        help="Write equivalence report JSON to a file instead of stdout",
    )
    equivalence.set_defaults(func=cmd_evaluate_equivalence)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
