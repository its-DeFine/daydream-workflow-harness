from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.equivalence import evaluate_published_workflow_equivalence


def test_evaluate_published_workflow_equivalence_scores_multiple_dimensions():
    payload = {
        "workflows": [
            {
                "slug": "pixel-art-man",
                "name": "Pixel Art Man",
                "description": "",
                "workflowData": {
                    "prompts": [{"text": "A pixel art man, background is a pixel art library"}],
                    "timeline": {"entries": [{"prompts": [{"text": "A pixel art man, background is a pixel art library"}]}]},
                    "pipelines": [
                        {
                            "role": "main",
                            "pipeline_id": "longlive",
                            "loras": [{"filename": "pixelart.safetensors"}],
                            "params": {
                                "width": 512,
                                "height": 512,
                                "input_mode": "video",
                                "noise_scale": 0.7,
                                "manage_cache": True,
                                "quantization": None,
                                "noise_controller": True,
                                "kv_cache_attention_bias": 0.3,
                            },
                        }
                    ],
                },
            },
            {
                "slug": "face-swap",
                "name": "Face Swap",
                "description": "",
                "workflowData": {
                    "prompts": [{"text": ""}],
                    "timeline": {"entries": [{"prompts": [{"text": ""}]}]},
                    "pipelines": [
                        {
                            "role": "main",
                            "pipeline_id": "deeplivecam-faceswap",
                            "loras": [],
                            "params": {
                                "width": 512,
                                "height": 512,
                                "input_mode": "video",
                                "manage_cache": True,
                                "quantization": None,
                                "kv_cache_attention_bias": 0.3,
                                "source_face_image": "placeholder-face.png",
                            },
                        },
                        {
                            "role": "postprocessor",
                            "pipeline_id": "rife",
                            "loras": [],
                            "params": {},
                        },
                    ],
                },
            },
        ]
    }

    report = evaluate_published_workflow_equivalence(payload)

    assert report["summary"]["total_cases"] == 2
    assert report["summary"]["chain_exact_matches"] == 2
    assert report["summary"]["role_exact_matches"] == 2
    assert report["summary"]["input_mode_exact_matches"] == 2
    assert report["summary"]["dimension_exact_matches"] == 2
    by_slug = {result["slug"]: result for result in report["results"]}
    assert by_slug["pixel-art-man"]["lora_count_exact"] is True
    assert by_slug["face-swap"]["main_param_keys_exact"] is True
