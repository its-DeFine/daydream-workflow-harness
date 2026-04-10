"""Typed schemas for catalog, intent, and validation primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


PortKind = Literal["stream", "parameter"]
NodeRole = Literal["source", "pipeline", "sink", "record"]
Severity = Literal["info", "warning", "error"]
ExecutionMode = Literal["local", "remote", "hybrid"]


@dataclass(slots=True, frozen=True)
class PortSpec:
    """A declared port on a Scope pipeline."""

    name: str
    kind: PortKind = "stream"
    description: str = ""
    data_type: str = "video"


@dataclass(slots=True, frozen=True)
class CatalogEntry:
    """A normalized capability catalog entry for a pipeline or plugin-backed unit."""

    pipeline_id: str
    name: str
    role: NodeRole = "pipeline"
    plugin_name: str | None = None
    inputs: tuple[PortSpec, ...] = field(default_factory=tuple)
    outputs: tuple[PortSpec, ...] = field(default_factory=tuple)
    produces_video: bool = True
    produces_audio: bool = False
    supports_remote: bool = True
    description: str = ""


@dataclass(slots=True)
class CapabilityCatalog:
    """In-memory registry of known Scope capabilities."""

    entries: dict[str, CatalogEntry] = field(default_factory=dict)

    def add(self, entry: CatalogEntry) -> None:
        self.entries[entry.pipeline_id] = entry

    def get(self, pipeline_id: str) -> CatalogEntry | None:
        return self.entries.get(pipeline_id)


@dataclass(slots=True, frozen=True)
class IntentSpec:
    """Typed intent for workflow generation."""

    objective: str
    source: str = "video"
    target: str = "video"
    mode: ExecutionMode = "hybrid"
    realtime: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    """A single validation finding."""

    severity: Severity
    code: str
    message: str
    path: str = ""

