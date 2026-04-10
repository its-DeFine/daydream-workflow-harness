from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from daydream_workflow_harness.catalog import build_catalog_index
from daydream_workflow_harness.extract_scope import extract_scope_catalog
from daydream_workflow_harness.validator import validate_workflow


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


def cmd_extract_catalog(args: argparse.Namespace) -> int:
    catalog = extract_scope_catalog(app_path=args.app_path)
    _dump_json(catalog, args.output)
    return 0


def cmd_validate_workflow(args: argparse.Namespace) -> int:
    workflow = _load_json(args.workflow)
    if workflow is None:
        raise ValueError("workflow path is required")

    catalog_payload = _load_json(args.catalog)
    if catalog_payload is None:
        catalog_payload = extract_scope_catalog(app_path=args.app_path)

    entries = catalog_payload.get("pipelines") if isinstance(catalog_payload, dict) else []
    catalog = build_catalog_index(entries or [])
    errors = validate_workflow(workflow, catalog=catalog)
    report = {
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
    }
    _dump_json(report, args.output)
    return 0 if not errors else 1


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
        "--output",
        default=None,
        help="Write validation report JSON to a file instead of stdout",
    )
    validate.set_defaults(func=cmd_validate_workflow)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
