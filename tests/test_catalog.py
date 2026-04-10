from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness.catalog import build_catalog_index_from_payload


def test_build_catalog_index_from_live_runtime_payload():
    payload = {
        "pipelines": {
            "gray": {"id": "gray", "inputs": ["video"], "outputs": ["video"]},
            "rife": {"id": "rife", "inputs": ["video"], "outputs": ["video"]},
        }
    }

    catalog = build_catalog_index_from_payload(payload)

    assert sorted(catalog) == ["gray", "rife"]
    assert catalog["gray"]["pipeline_id"] == "gray"
