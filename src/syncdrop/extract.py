"""Extract scratch audio from video files via ffmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path


def extract_scratch(video: Path, out_wav: Path, sample_rate: int = 16000) -> Path | None:
    """Extract mono PCM scratch audio. Returns out_wav, or None if clip has no audio."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video),
            "-vn", "-ac", "1", "-ar", str(sample_rate),
            "-sample_fmt", "s16",
            str(out_wav),
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not out_wav.exists() or out_wav.stat().st_size == 0:
        return None
    return out_wav
