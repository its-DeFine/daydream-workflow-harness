from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.compiler import compile_workflow
from daydream_workflow_harness.ir import WorkflowEdge, WorkflowIR, WorkflowNode, WorkflowSession


def test_compile_workflow_normalizes_ir_into_canonical_dict():
    ir = SimpleNamespace(
        name="forest-seasons",
        description="A realtime transformation harness.",
        intent={"goal": "turn forest into seasons"},
        graph=SimpleNamespace(
            nodes=[
                SimpleNamespace(id="input", type="source"),
                {"id": "main", "type": "pipeline", "pipeline_id": "longlive", "tempo_sync": True},
                {"id": "output", "type": "sink", "sink_mode": "webrtc"},
            ],
            edges=[
                {"from": "input", "from_port": "video", "to_node": "main", "to_port": "video"},
                {"from_node": "main", "from_port": "video", "to_node": "output", "to_port": "video", "kind": "stream"},
            ],
        ),
        session={"input_mode": "video", "prompts": ["forest in summer"]},
        metadata={"author": "codex"},
    )

    compiled = compile_workflow(ir, catalog={"longlive": {}})

    assert compiled["name"] == "forest-seasons"
    assert compiled["intent"]["goal"] == "turn forest into seasons"
    assert compiled["graph"]["nodes"][1]["pipeline_id"] == "longlive"
    assert compiled["graph"]["nodes"][1]["tempo_sync"] is True
    assert compiled["graph"]["edges"][1]["from"] == "main"
    assert compiled["session"]["input_mode"] == "video"
    assert compiled["metadata"]["catalog_size"] == 1


def test_compile_workflow_accepts_the_shared_irl_dataclasses():
    ir = WorkflowIR(
        session=WorkflowSession(objective="turn forest into seasons", prompt="forest"),
        nodes=[
            WorkflowNode(node_id="input", kind="source"),
            WorkflowNode(node_id="main", kind="pipeline", pipeline_id="longlive"),
            WorkflowNode(node_id="output", kind="sink"),
        ],
        edges=[
            WorkflowEdge(
                source_node="input",
                source_port="video",
                target_node="main",
                target_port="video",
            ),
            WorkflowEdge(
                source_node="main",
                source_port="video",
                target_node="output",
                target_port="video",
            ),
        ],
    )

    compiled = compile_workflow(ir)

    assert compiled["graph"]["nodes"][1]["id"] == "main"
    assert compiled["graph"]["edges"][0]["from"] == "input"
    assert compiled["graph"]["edges"][1]["to_node"] == "output"


def test_compile_workflow_emits_stage_chain_and_prompt_helpers():
    ir = WorkflowIR(
        session=WorkflowSession(
            objective="Create a realtime video restyle",
            prompt="Cyborg Man, Dystopian",
            parameters={"source": "video"},
        ),
        nodes=[
            WorkflowNode(node_id="input", kind="source", source_mode="video"),
            WorkflowNode(
                node_id="main",
                kind="pipeline",
                pipeline_id="longlive",
                metadata={"role": "main"},
            ),
            WorkflowNode(
                node_id="post",
                kind="pipeline",
                pipeline_id="rife",
                metadata={"role": "postprocessor"},
            ),
            WorkflowNode(node_id="output", kind="sink", sink_mode="webrtc"),
        ],
        edges=[
            WorkflowEdge("input", "video", "main", "video"),
            WorkflowEdge("main", "video", "post", "video"),
            WorkflowEdge("post", "video", "output", "video"),
        ],
    )

    compiled = compile_workflow(ir)

    assert compiled["format"] == "scope-workflow"
    assert compiled["prompts"][0]["text"] == "Cyborg Man, Dystopian"
    assert compiled["timeline"]["entries"][0]["prompts"][0]["text"] == "Cyborg Man, Dystopian"
    assert [stage["pipeline_id"] for stage in compiled["pipelines"]] == ["longlive", "rife"]
    assert compiled["pipelines"][0]["role"] == "main"
    assert compiled["pipelines"][0]["params"]["input_mode"] == "video"
    assert compiled["pipelines"][0]["params"]["width"] == 512
