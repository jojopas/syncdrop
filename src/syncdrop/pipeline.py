"""End-to-end pipeline: scan → extract → correlate → build AAF."""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .aaf_builder import ClipPlacement, build_aaf
from .correlate import correlate_clip, load_envelope
from .extract import extract_scratch
from .probe import duration_seconds, ffprobe, video_frame_rate
from .scan import scan_folder


@dataclass
class CorrelatedClip:
    video: Path
    duration_seconds: float
    offset_seconds: float
    confidence: float


def pick_reference(clips: list[Path], scratch_dir: Path) -> tuple[Path, Path]:
    """Return (reference video, reference scratch wav) — longest clip wins."""
    longest_video, longest_wav, longest_dur = None, None, -1.0
    for video in clips:
        wav = scratch_dir / f"{video.stem}.wav"
        if not wav.exists():
            continue
        # Use scratch WAV duration (ffmpeg gave us mono PCM) — simplest and correct
        import wave
        with wave.open(str(wav), "rb") as w:
            dur = w.getnframes() / w.getframerate()
        if dur > longest_dur:
            longest_video, longest_wav, longest_dur = video, wav, dur
    if longest_video is None:
        raise RuntimeError("No clips with extractable audio — cannot pick reference")
    return longest_video, longest_wav


def run_pipeline(
    input_folder: Path,
    output_aaf: Path | None = None,
    reference_video: Path | None = None,
    min_confidence: float = 5.0,
    edit_rate: tuple[int, int] | None = None,
    verbose: bool = True,
    dry_run: bool = False,
) -> Path | None:
    """Sync all videos in input_folder and write an AAF.

    Returns the path of the written AAF, or None if dry_run was True.
    """
    input_folder = Path(input_folder)
    output_aaf = Path(output_aaf) if output_aaf else input_folder / "synced.aaf"

    videos = scan_folder(input_folder)
    if not videos:
        raise RuntimeError(f"No video files found in {input_folder}")

    if verbose:
        print(f"Found {len(videos)} video clips in {input_folder}")

    # Extract scratch audio for each clip
    scratch_dir = Path(tempfile.mkdtemp(prefix="syncdrop_"))
    try:
        scratch_map: dict[Path, Path] = {}
        skipped: list[Path] = []
        for video in videos:
            wav = scratch_dir / f"{video.stem}.wav"
            if verbose:
                print(f"  extract: {video.name}")
            result = extract_scratch(video, wav)
            if result is None:
                skipped.append(video)
                if verbose:
                    print(f"    skipped (no audio)")
            else:
                scratch_map[video] = result

        if not scratch_map:
            raise RuntimeError("None of the clips have audio — cannot sync")

        # Pick or load reference
        if reference_video is not None:
            reference_video = Path(reference_video)
            if reference_video not in scratch_map:
                raise RuntimeError(f"Reference {reference_video} not in scratch map")
            ref_wav = scratch_map[reference_video]
        else:
            reference_video, ref_wav = pick_reference(list(scratch_map.keys()), scratch_dir)

        if verbose:
            print(f"\nReference: {reference_video.name}")

        auto_detected = edit_rate is None
        if auto_detected:
            edit_rate = video_frame_rate(ffprobe(reference_video))
            if edit_rate is None:
                raise RuntimeError(
                    f"Could not detect frame rate from {reference_video.name}; pass --fps explicitly"
                )
        if verbose:
            tag = " (auto-detected from reference)" if auto_detected else ""
            print(f"Edit rate: {edit_rate[0]}/{edit_rate[1]} "
                  f"({float(Fraction(*edit_rate)):.3f} fps){tag}")

        # Correlate every clip against reference
        rate_frac = Fraction(*edit_rate)
        results: list[CorrelatedClip] = []
        if verbose:
            print(f"\n{'clip':<55} {'offset_s':>12} {'conf':>8} {'len_s':>10}")
            print("-" * 90)
        for video, wav in scratch_map.items():
            if video == reference_video:
                offset, conf = 0.0, float("inf")
            else:
                offset, conf = correlate_clip(ref_wav, wav)
            # Duration from scratch wav
            import wave
            with wave.open(str(wav), "rb") as w:
                dur = w.getnframes() / w.getframerate()
            results.append(CorrelatedClip(video, dur, offset, conf))
            if verbose:
                conf_str = "REF" if conf == float("inf") else f"{conf:.1f}"
                print(f"{video.name:<55} {offset:>12.3f} {conf_str:>8} {dur:>10.1f}")

        # Filter by confidence
        kept = [r for r in results if r.confidence >= min_confidence or r.confidence == float("inf")]
        dropped = [r for r in results if r.confidence < min_confidence and r.confidence != float("inf")]
        if dropped and verbose:
            print(f"\nDropped {len(dropped)} clip(s) below confidence {min_confidence}:")
            for r in dropped:
                print(f"  {r.video.name} (conf={r.confidence:.1f})")

        if not kept:
            raise RuntimeError("No clips passed confidence threshold")

        # Normalize to t=0
        min_off = min(r.offset_seconds for r in kept)
        shift = -min_off

        def to_frames(seconds: float) -> int:
            return round(seconds * rate_frac)

        placements: list[ClipPlacement] = [
            ClipPlacement(
                src=r.video,
                offset_frames=to_frames(r.offset_seconds + shift),
                duration_frames=to_frames(r.duration_seconds),
            )
            for r in kept
        ]

        # Resolve overlaps: same track only — but we put each clip on its own track,
        # so no overlap resolution is needed in v1.

        if verbose:
            total = max(p.offset_frames + p.duration_frames for p in placements)
            print(f"\nTimeline: {total} frames @ {edit_rate[0]}/{edit_rate[1]} = "
                  f"{float(total / rate_frac) / 60:.1f} min")

        if dry_run:
            if verbose:
                print("\n--dry-run: skipping AAF write")
            return None

        build_aaf(placements, output_aaf, edit_rate=edit_rate)

        if verbose:
            print(f"\nWrote {output_aaf} ({output_aaf.stat().st_size // 1024} KB)")
            print(f"Import in Premiere: File > Import > {output_aaf.name}")

        return output_aaf

    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)
