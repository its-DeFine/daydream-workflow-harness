from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceProofResult:
    ok: bool
    similarity: float = 0.0
    proof_level: str = "unavailable"
    compared_bytes: int = 0
    input_video_path: str = ""
    output_video_path: str = ""
    method: str = "ffmpeg-grayscale-thumbnail-mae"
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _raw_grayscale_contact(
    path: Path,
    *,
    fps: float = 2.0,
    width: int = 64,
    height: int = 36,
) -> bytes:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-vf",
        f"fps={fps},scale={width}:{height},format=gray",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def compare_source_to_recording(
    input_video_path: str | None,
    output_video_path: str | None,
    *,
    strong_threshold: float = 0.68,
    weak_threshold: float = 0.45,
) -> SourceProofResult:
    if not input_video_path or not output_video_path:
        return SourceProofResult(
            ok=False,
            error="input and output video paths are required",
            input_video_path=input_video_path or "",
            output_video_path=output_video_path or "",
        )

    input_path = Path(input_video_path)
    output_path = Path(output_video_path)
    if not input_path.exists():
        return SourceProofResult(
            ok=False,
            error=f"input video does not exist: {input_path}",
            input_video_path=str(input_path),
            output_video_path=str(output_path),
        )
    if not output_path.exists():
        return SourceProofResult(
            ok=False,
            error=f"output video does not exist: {output_path}",
            input_video_path=str(input_path),
            output_video_path=str(output_path),
        )

    try:
        input_bytes = _raw_grayscale_contact(input_path)
        output_bytes = _raw_grayscale_contact(output_path)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        return SourceProofResult(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            input_video_path=str(input_path),
            output_video_path=str(output_path),
        )

    compared = min(len(input_bytes), len(output_bytes))
    if compared <= 0:
        return SourceProofResult(
            ok=False,
            error="ffmpeg produced no comparable bytes",
            input_video_path=str(input_path),
            output_video_path=str(output_path),
        )

    mean_abs_delta = (
        sum(abs(input_bytes[index] - output_bytes[index]) for index in range(compared))
        / compared
    )
    similarity = max(0.0, min(1.0, 1.0 - mean_abs_delta / 255.0))
    if similarity >= strong_threshold:
        proof_level = "strong"
    elif similarity >= weak_threshold:
        proof_level = "weak"
    else:
        proof_level = "low"

    return SourceProofResult(
        ok=similarity >= weak_threshold,
        similarity=round(similarity, 4),
        proof_level=proof_level,
        compared_bytes=compared,
        input_video_path=str(input_path),
        output_video_path=str(output_path),
    )
