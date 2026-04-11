from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daydream_workflow_harness import source_proof


def test_compare_source_to_recording_reports_strong_similarity(monkeypatch, tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")
    output_path.write_bytes(b"fake")

    monkeypatch.setattr(
        source_proof,
        "_raw_grayscale_contact",
        lambda path: bytes([0, 64, 128, 255]),
    )

    result = source_proof.compare_source_to_recording(str(input_path), str(output_path))

    assert result.ok is True
    assert result.proof_level == "strong"
    assert result.similarity == 1.0


def test_compare_source_to_recording_reports_low_similarity(monkeypatch, tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")
    output_path.write_bytes(b"fake")

    def fake_raw(path):
        if path == input_path:
            return bytes([0, 0, 0, 0])
        return bytes([255, 255, 255, 255])

    monkeypatch.setattr(source_proof, "_raw_grayscale_contact", fake_raw)

    result = source_proof.compare_source_to_recording(str(input_path), str(output_path))

    assert result.ok is False
    assert result.proof_level == "low"
    assert result.similarity == 0.0
