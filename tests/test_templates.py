from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.templates import (
    build_template_workflow,
    candidate_templates_for_intent,
    list_workflow_templates,
)


def test_candidate_templates_use_intent_and_catalog():
    candidates = candidate_templates_for_intent(
        {"objective": "make a depth cyborg restyle"},
        catalog={
            "video-depth-anything": {"pipeline_id": "video-depth-anything"},
            "longlive": {"pipeline_id": "longlive"},
            "rife": {"pipeline_id": "rife"},
        },
    )

    assert candidates[0]["name"] == "depth-conditioned"
    assert all(candidate["available"] for candidate in candidates)


def test_build_template_workflow_creates_graph():
    workflow = build_template_workflow(
        "grayscale-preview",
        {"objective": "make grayscale"},
        catalog={
            "gray": {"pipeline_id": "gray", "inputs": ["video"], "outputs": ["video"]}
        },
    )

    assert workflow["metadata"]["template_name"] == "grayscale-preview"
    assert workflow["graph"]["nodes"][1]["pipeline_id"] == "gray"
    assert workflow["pipelines"][0]["role"] == "main"


def test_list_workflow_templates_includes_core_chains():
    names = {template["name"] for template in list_workflow_templates()}

    assert {"direct-restyle", "depth-conditioned", "grayscale-preview"} <= names
