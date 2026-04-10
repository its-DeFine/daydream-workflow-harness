from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.benchmark import benchmark_published_workflows


def test_benchmark_published_workflows_scores_small_corpus():
    payload = {
        "workflows": [
            {
                "slug": "pixel-art-man",
                "name": "Pixel Art Man",
                "description": "",
                "workflowData": {
                    "pipelines": [
                        {
                            "pipeline_id": "longlive",
                            "params": {"input_mode": "video"},
                        }
                    ],
                    "prompts": [{"text": "A pixel art man, background is a pixel art library"}],
                },
            },
            {
                "slug": "face-swap",
                "name": "Face Swap",
                "description": "",
                "workflowData": {
                    "pipelines": [
                        {
                            "pipeline_id": "deeplivecam-faceswap",
                            "params": {"input_mode": "video"},
                        },
                        {
                            "pipeline_id": "rife",
                            "params": {"input_mode": "video"},
                        },
                    ],
                    "prompts": [],
                },
            },
            {
                "slug": "cinegen",
                "name": "Cinegen",
                "description": "",
                "workflowData": {
                    "pipelines": [
                        {
                            "pipeline_id": "longlive",
                            "params": {"input_mode": "text"},
                        }
                    ],
                    "prompts": [{"text": "Shimmering, translucent light ribbons in a pastel void"}],
                },
            },
        ]
    }

    result = benchmark_published_workflows(payload)

    assert result.total == 3
    assert result.exact_matches == 3
    assert [entry.slug for entry in result.entries] == [
        "pixel-art-man",
        "face-swap",
        "cinegen",
    ]
