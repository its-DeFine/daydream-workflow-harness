from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from daydream_workflow_harness.catalog import DEFAULT_SCOPE_APP_PATH


def _resources_src_path(app_path: str) -> Path:
    return Path(app_path) / "Contents" / "Resources" / "src"


def extract_pipeline_metadata(app_path: str = DEFAULT_SCOPE_APP_PATH) -> list[dict[str, Any]]:
    """Extract pipeline schemas from the installed Daydream Scope app."""

    resources_src = _resources_src_path(app_path)
    if not resources_src.exists():
        return []

    inserted = False
    if str(resources_src) not in sys.path:
        sys.path.insert(0, str(resources_src))
        inserted = True

    try:
        from scope.core.pipelines.registry import PipelineRegistry
        from scope.core.plugins import get_plugin_manager

        plugin_manager = get_plugin_manager()
        records: list[dict[str, Any]] = []

        for pipeline_id in PipelineRegistry.list_pipelines():
            config_class = PipelineRegistry.get_config_class(pipeline_id)
            if config_class is None:
                continue
            schema = config_class.get_schema_with_metadata()
            schema["pipeline_id"] = pipeline_id
            with suppress(Exception):
                schema["plugin_name"] = plugin_manager.get_plugin_for_pipeline(
                    pipeline_id
                )
            records.append(schema)

        return records
    except Exception:
        return []
    finally:
        if inserted:
            with suppress(ValueError):
                sys.path.remove(str(resources_src))


def extract_scope_catalog(app_path: str = DEFAULT_SCOPE_APP_PATH) -> dict[str, Any]:
    return {
        "app_path": app_path,
        "resources_src": str(_resources_src_path(app_path)),
        "pipelines": extract_pipeline_metadata(app_path=app_path),
    }
