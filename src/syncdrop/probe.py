"""ffprobe wrapper. Returns clip metadata + patches AAC sample_fmt for pyaaf2."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def ffprobe(path: Path | str) -> dict:
    """Return parsed ffprobe JSON. Patches AAC streams missing sample_fmt/bit_rate
    so pyaaf2's AMA media link doesn't choke."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    meta = json.loads(r.stdout)
    for s in meta.get("streams", []):
        if s.get("codec_type") == "audio":
            s.setdefault("sample_fmt", "s16")
            s.setdefault("bit_rate", "0")
    return meta


def has_audio(meta: dict) -> bool:
    return any(s.get("codec_type") == "audio" for s in meta.get("streams", []))


def duration_seconds(meta: dict) -> float:
    return float(meta["format"]["duration"])
