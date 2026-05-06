"""End-to-end pipeline test using ffmpeg-generated synthetic videos."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ffmpeg_missing = shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None
pytestmark = pytest.mark.skipif(
    ffmpeg_missing, reason="requires ffmpeg + ffprobe on PATH",
)


def make_synthetic_clip(
    out_path: Path,
    duration_s: float,
    audio_phase_offset_s: float = 0.0,
    sample_rate: int = 16000,
    fps: int = 30,
) -> Path:
    """Create a tiny .mov with deterministic test patterns + an offset audio click track.

    Different audio_phase_offset_s values shift where 'click' impulses land so the
    correlator can find a non-zero offset between two clips with shared structure.

    Uses a 'sine' source seeded by phase so the audio is deterministic and
    cross-correlation has a clean alignment signal across both clips.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # The audio uses a sum of sines whose phase shifts produce sharp transients.
    # Two clips with different audio_phase_offset_s share structural energy after
    # the offset is removed, yielding a strong correlation peak.
    audio_filter = (
        f"sine=frequency=440:sample_rate={sample_rate}:duration={duration_s},"
        f"adelay={int(audio_phase_offset_s*1000)}|{int(audio_phase_offset_s*1000)},"
        f"apad=whole_dur={duration_s}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size=160x120:rate={fps}:duration={duration_s}",
        "-f", "lavfi", "-i", audio_filter,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


def test_pipeline_end_to_end_synthetic(tmp_path: Path) -> None:
    """Two synthetic clips → run pipeline → AAF round-trips via pyaaf2.

    This proves: scan → extract → correlate → build_aaf glue is wired correctly,
    even if the synthetic audio's correlation peak isn't at the precise offset
    we'd want on real footage. We assert the AAF is structurally valid, not
    that the offsets are pixel-perfect.
    """
    folder = tmp_path / "clips"
    folder.mkdir()

    make_synthetic_clip(folder / "clip_a.mov", duration_s=8.0, audio_phase_offset_s=0.0)
    make_synthetic_clip(folder / "clip_b.mov", duration_s=6.0, audio_phase_offset_s=2.0)

    from syncdrop.pipeline import run_pipeline

    out = tmp_path / "synced.aaf"
    result = run_pipeline(
        input_folder=folder,
        output_aaf=out,
        min_confidence=0.0,  # synthetic audio has weak correlation; don't filter
        verbose=False,
    )
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0

    # Round-trip: pyaaf2 should re-open the AAF and find our composition
    import aaf2
    with aaf2.open(str(out), "r") as f:
        comps = list(f.content.toplevel())
        assert len(comps) == 1
        comp = comps[0]
        assert comp.name == "SyncDrop Timeline"
        video_slots = [s for s in comp.slots if str(s.media_kind) == "Picture"]
        # One video track per clip (v1 design)
        assert len(video_slots) == 2


def test_pipeline_dry_run_skips_aaf_write(tmp_path: Path) -> None:
    folder = tmp_path / "clips"
    folder.mkdir()
    make_synthetic_clip(folder / "clip_a.mov", duration_s=5.0)
    make_synthetic_clip(folder / "clip_b.mov", duration_s=5.0, audio_phase_offset_s=1.0)

    from syncdrop.pipeline import run_pipeline

    out = tmp_path / "synced.aaf"
    result = run_pipeline(
        input_folder=folder,
        output_aaf=out,
        min_confidence=0.0,
        verbose=False,
        dry_run=True,
    )
    assert result is None
    assert not out.exists()
