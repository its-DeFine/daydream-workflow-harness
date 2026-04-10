"""Workflow intermediate representation for Daydream Scope authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .schemas import ExecutionMode


NodeKind = Literal["source", "pipeline", "sink", "record"]


@dataclass(slots=True, frozen=True)
class WorkflowNode:
    """A node in the workflow IR."""

    node_id: str
    kind: NodeKind
    pipeline_id: str | None = None
    source_mode: str | None = None
    sink_mode: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class WorkflowEdge:
    """A directed edge between workflow nodes."""

    source_node: str
    source_port: str
    target_node: str
    target_port: str
    kind: Literal["stream", "parameter"] = "stream"


@dataclass(slots=True, frozen=True)
class WorkflowSession:
    """Session-level parameters for an authored workflow."""

    objective: str
    mode: ExecutionMode = "hybrid"
    prompt: str = ""
    width: int = 512
    height: int = 512
    fps: int = 30
    seed: int = 42
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowIR:
    """A normalized workflow plan produced by an intent-to-workflow compiler."""

    session: WorkflowSession
    nodes: list[WorkflowNode] = field(default_factory=list)
    edges: list[WorkflowEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: WorkflowEdge) -> None:
        self.edges.append(edge)

    def node_ids(self) -> set[str]:
        return {node.node_id for node in self.nodes}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the IR into a plain dictionary."""
        return {
            "session": {
                "objective": self.session.objective,
                "mode": self.session.mode,
                "prompt": self.session.prompt,
                "width": self.session.width,
                "height": self.session.height,
                "fps": self.session.fps,
                "seed": self.session.seed,
                "parameters": dict(self.session.parameters),
            },
            "nodes": [
                {
                    "node_id": node.node_id,
                    "kind": node.kind,
                    "pipeline_id": node.pipeline_id,
                    "source_mode": node.source_mode,
                    "sink_mode": node.sink_mode,
                    "metadata": dict(node.metadata),
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "source_node": edge.source_node,
                    "source_port": edge.source_port,
                    "target_node": edge.target_node,
                    "target_port": edge.target_port,
                    "kind": edge.kind,
                }
                for edge in self.edges
            ],
            "metadata": dict(self.metadata),
        }

