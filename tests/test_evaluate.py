from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.catalog import build_catalog_index
from daydream_workflow_harness.evaluate import evaluate_blind_regeneration


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def sample_catalog() -> dict[str, dict[str, object]]:
    return build_catalog_index(
        [
            {"pipeline_id": "video-depth-anything", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "longlive", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "rife", "inputs": ["video"], "outputs": ["video"]},
            {"pipeline_id": "deeplivecam-faceswap", "inputs": ["video"], "outputs": ["video"]},
        ]
    )


def test_evaluate_blind_regeneration_scores_held_out_public_cases():
    cases = json.loads(
        (FIXTURES / "blind_regeneration_public_cases.json").read_text(encoding="utf-8")
    )

    report = evaluate_blind_regeneration(cases, catalog=sample_catalog())

    assert report["summary"]["total_cases"] == 5
    assert report["summary"]["exact_matches"] == 5
    by_slug = {result["slug"]: result for result in report["results"]}
    assert by_slug["supersquish-lora"]["exact_match"] is True
    assert by_slug["god-s-face"]["exact_match"] is True
    assert by_slug["pixel-art-man"]["exact_match"] is True
    assert by_slug["adjustable-acid-slime"]["exact_match"] is True
    assert by_slug["face-swap"]["exact_match"] is True


def test_evaluate_blind_regeneration_accepts_published_workflow_corpus_shape():
    corpus = {
        "workflows": [
            {
                "slug": "face-swap",
                "name": "Face Swap",
                "description": "Workflow containing 2 nodes.",
                "workflowUrl": "https://example.com/face-swap.json",
                "workflowData": {
                    "pipelines": [
                        {
                            "pipeline_id": "deeplivecam-faceswap",
                            "params": {"input_mode": "video"},
                        },
                        {
                            "pipeline_id": "rife",
                            "params": {},
                        },
                    ],
                    "prompts": [{"text": ""}],
                },
            }
        ]
    }

    report = evaluate_blind_regeneration(corpus, catalog=sample_catalog())

    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["exact_matches"] == 1
    assert report["results"][0]["slug"] == "face-swap"
    assert report["results"][0]["exact_match"] is True
