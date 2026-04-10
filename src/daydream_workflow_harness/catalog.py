from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

DEFAULT_SCOPE_APP_PATH = "/Applications/Daydream Scope.app"


@dataclass(slots=True)
class PipelineCatalogEntry:
    pipeline_id: str
    name: str = ""
    description: str = ""
    version: str = ""
    plugin_name: str | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    usage: list[str] = field(default_factory=list)
    produces_video: bool = True
    produces_audio: bool = False
    estimated_vram_gb: float | None = None
    config_schema: dict[str, Any] = field(default_factory=dict)
    mode_defaults: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None


def normalize_pipeline_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable catalog record for one pipeline."""

    pipeline_id = str(entry.get("pipeline_id") or entry.get("id") or "")
    normalized = PipelineCatalogEntry(
        pipeline_id=pipeline_id,
        name=str(entry.get("name") or ""),
        description=str(entry.get("description") or ""),
        version=str(entry.get("version") or ""),
        plugin_name=entry.get("plugin_name"),
        inputs=list(entry.get("inputs") or []),
        outputs=list(entry.get("outputs") or []),
        usage=list(entry.get("usage") or []),
        produces_video=bool(entry.get("produces_video", True)),
        produces_audio=bool(entry.get("produces_audio", False)),
        estimated_vram_gb=entry.get("estimated_vram_gb"),
        config_schema=dict(entry.get("config_schema") or {}),
        mode_defaults=dict(entry.get("mode_defaults") or {}),
        source_path=entry.get("source_path"),
    )
    return asdict(normalized)


def catalog_entries_from_payload(payload: Any) -> list[dict[str, Any]]:
    """Return pipeline entries from either bundle extraction or runtime schemas."""

    if isinstance(payload, Mapping):
        pipelines = payload.get("pipelines")
        if isinstance(pipelines, Mapping):
            entries: list[dict[str, Any]] = []
            for pipeline_id, raw_entry in pipelines.items():
                if not isinstance(raw_entry, Mapping):
                    continue
                entry = dict(raw_entry)
                entry["pipeline_id"] = str(
                    entry.get("pipeline_id") or entry.get("id") or pipeline_id
                )
                entries.append(entry)
            return entries
        if isinstance(pipelines, list):
            return [
                {
                    **dict(entry),
                    "pipeline_id": str(
                        entry.get("pipeline_id") or entry.get("id") or ""
                    ),
                }
                for entry in pipelines
                if isinstance(entry, Mapping)
            ]
        return []

    if isinstance(payload, list):
        return [
            {
                **dict(entry),
                "pipeline_id": str(entry.get("pipeline_id") or entry.get("id") or ""),
            }
            for entry in payload
            if isinstance(entry, Mapping)
        ]
    return []


def build_catalog_index(entries: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index pipeline metadata by pipeline id."""

    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        normalized = normalize_pipeline_entry(entry)
        pipeline_id = normalized["pipeline_id"]
        if not pipeline_id:
            continue
        index[pipeline_id] = normalized
    return index


def build_catalog_index_from_payload(payload: Any) -> dict[str, dict[str, Any]]:
    """Build a catalog index from a list payload or a catalog wrapper."""

    return build_catalog_index(catalog_entries_from_payload(payload))


def catalog_inputs(catalog: Mapping[str, Mapping[str, Any]], pipeline_id: str) -> list[str]:
    return list(catalog.get(pipeline_id, {}).get("inputs") or [])


def catalog_outputs(catalog: Mapping[str, Mapping[str, Any]], pipeline_id: str) -> list[str]:
    return list(catalog.get(pipeline_id, {}).get("outputs") or [])
