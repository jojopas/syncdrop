"""Build a Premiere-compatible AAF from synced clips.

V1 design: one video track per clip. Editors group multicam in Premiere.
Audio track only created when the source clip has an audio stream — empty
audio sequence slots crash Premiere on import (Yaleo iPhone bug).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import aaf2
from aaf2 import ama
from aaf2.rational import AAFRational

from .probe import ffprobe, has_audio


@dataclass
class ClipPlacement:
    """A clip and where it sits on the timeline."""
    src: Path                    # absolute path to video file
    offset_frames: int           # start position on the timeline (in edit-rate frames)
    duration_frames: int         # how long the clip plays


def build_aaf(
    clips: list[ClipPlacement],
    output_path: Path,
    edit_rate: tuple[int, int] = (30000, 1001),
    audio_rate: int = 48000,
    composition_name: str = "SyncDrop Timeline",
) -> Path:
    """Write an AAF with each clip on its own video track at its offset.

    edit_rate: (num, den) — defaults to 29.97 fps. Use (24000, 1001) for 23.976,
    (60000, 1001) for 59.94, (25, 1) for PAL, etc.
    """
    if not clips:
        raise ValueError("No clips to build AAF from")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    aaf_edit_rate = AAFRational(*edit_rate)
    aaf_audio_rate = AAFRational(audio_rate, 1)
    rate_frac = Fraction(*edit_rate)

    total_frames = max(c.offset_frames + c.duration_frames for c in clips)
    total_audio_samples = round(total_frames / float(rate_frac) * audio_rate)

    with aaf2.open(str(output_path), "w") as f:
        # 1. Create MasterMobs via AMA
        per_clip_meta: list[tuple[ClipPlacement, object, bool]] = []
        for clip in clips:
            meta = ffprobe(clip.src)
            result = ama.create_media_link(f, str(clip.src), meta)
            if result is None:
                raise RuntimeError(f"ama.create_media_link returned None for {clip.src.name}")
            master_mob = result[0]
            per_clip_meta.append((clip, master_mob, has_audio(meta)))

        # 2. Composition with one video track (and audio track when source has audio)
        comp = f.create.CompositionMob()
        comp.name = composition_name
        comp["UsageCode"].value = "Usage_TopLevel"

        for track_idx, (clip, master_mob, with_audio) in enumerate(per_clip_meta, start=1):
            # ── Video slot ────────────────────────────────────────────────
            v_slot = comp.create_empty_sequence_slot(
                edit_rate=aaf_edit_rate, media_kind="picture",
            )
            v_slot.name = f"V{track_idx}"
            v_slot["PhysicalTrackNumber"].value = track_idx
            v_slot.segment.length = total_frames

            cursor = 0
            if clip.offset_frames > cursor:
                fi = f.create.Filler(media_kind="picture")
                fi.length = clip.offset_frames - cursor
                v_slot.segment.components.append(fi)

            pic_slot = next(s for s in master_mob.slots if str(s.media_kind) == "Picture")
            src = master_mob.create_source_clip(slot_id=pic_slot.slot_id, media_kind="picture")
            src.length = clip.duration_frames
            v_slot.segment.components.append(src)

            tail = total_frames - (clip.offset_frames + clip.duration_frames)
            if tail > 0:
                fi = f.create.Filler(media_kind="picture")
                fi.length = tail
                v_slot.segment.components.append(fi)

            # ── Audio slot — only if source has audio ─────────────────────
            if not with_audio:
                continue

            snd_slots = [s for s in master_mob.slots if str(s.media_kind) == "Sound"]
            if not snd_slots:
                continue

            a_slot = comp.create_empty_sequence_slot(
                edit_rate=aaf_audio_rate, media_kind="sound",
            )
            a_slot.name = f"A{track_idx}"
            a_slot["PhysicalTrackNumber"].value = track_idx
            a_slot.segment.length = total_audio_samples

            offset_samples = round(clip.offset_frames / float(rate_frac) * audio_rate)
            clip_samples = round(clip.duration_frames / float(rate_frac) * audio_rate)

            if offset_samples > 0:
                fi = f.create.Filler(media_kind="sound")
                fi.length = offset_samples
                a_slot.segment.components.append(fi)

            asrc = master_mob.create_source_clip(slot_id=snd_slots[0].slot_id, media_kind="sound")
            asrc.length = clip_samples
            a_slot.segment.components.append(asrc)

            tail_s = total_audio_samples - (offset_samples + clip_samples)
            if tail_s > 0:
                fi = f.create.Filler(media_kind="sound")
                fi.length = tail_s
                a_slot.segment.components.append(fi)

        f.content.mobs.append(comp)

    return output_path
