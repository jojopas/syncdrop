"""Discover video clips in a folder."""
from __future__ import annotations

from pathlib import Path

VIDEO_EXTENSIONS = {".mov", ".mp4", ".mts", ".m4v", ".mxf", ".avi"}


def scan_folder(folder: Path) -> list[Path]:
    """Return sorted list of video files in folder (non-recursive)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    clips = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    return clips
