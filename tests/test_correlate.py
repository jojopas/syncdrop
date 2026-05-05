"""Test correlation against synthetic signals with known offsets."""
import wave
from pathlib import Path

import numpy as np
import pytest

from syncdrop.correlate import correlate_clip, correlate_envelopes


def write_wav(path: Path, signal: np.ndarray, sr: int = 16000) -> None:
    """Write float32 [-1, 1] signal as 16-bit PCM mono WAV."""
    pcm = (np.clip(signal, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def make_percussive_signal(duration_s: float, sr: int, seed: int = 42) -> np.ndarray:
    """Sparse percussive impulses + low noise — like a drum track."""
    rng = np.random.default_rng(seed)
    n = int(duration_s * sr)
    sig = rng.normal(0, 0.005, n).astype(np.float32)  # noise floor
    n_hits = int(duration_s * 4)  # ~4 hits per second
    for _ in range(n_hits):
        idx = int(rng.integers(0, n - 100))
        decay = np.exp(-np.arange(100) / 30.0)
        sig[idx:idx + 100] += rng.uniform(0.3, 0.9) * decay
    return sig


def test_correlate_synthetic_offset(tmp_path: Path) -> None:
    sr = 16000
    ref = make_percussive_signal(20.0, sr)
    offset_seconds = 5.0
    offset_samples = int(offset_seconds * sr)
    clip = ref[offset_samples:offset_samples + sr * 8]  # 8s window starting 5s in

    ref_path = tmp_path / "ref.wav"
    clip_path = tmp_path / "clip.wav"
    write_wav(ref_path, ref, sr)
    write_wav(clip_path, clip, sr)

    found_offset, conf = correlate_clip(ref_path, clip_path)
    # clip starts 5s into ref → offset_seconds is positive 5.0
    assert abs(found_offset - offset_seconds) < 0.05, f"Expected ~5.0s, got {found_offset}"
    assert conf > 10.0, f"Confidence too low: {conf}"


def test_correlate_negative_offset(tmp_path: Path) -> None:
    """Clip rolling before reference → negative offset."""
    sr = 16000
    full = make_percussive_signal(30.0, sr, seed=7)
    # ref starts 8s into the full signal
    ref = full[8 * sr: 22 * sr]
    # clip starts at the beginning of full, runs 12s
    clip = full[: 12 * sr]

    ref_path = tmp_path / "ref.wav"
    clip_path = tmp_path / "clip.wav"
    write_wav(ref_path, ref, sr)
    write_wav(clip_path, clip, sr)

    found_offset, conf = correlate_clip(ref_path, clip_path)
    assert abs(found_offset - (-8.0)) < 0.05, f"Expected ~-8.0s, got {found_offset}"
    assert conf > 10.0
