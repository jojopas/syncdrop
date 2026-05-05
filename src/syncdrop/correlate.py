"""Cross-correlate scratch audio against a reference timeline.

Ported from the Yaleo sync_work/correlate.py — pure functions only, no CLI.
"""
from __future__ import annotations

import wave
from math import gcd
from pathlib import Path

import numpy as np
from scipy.signal import correlate, correlation_lags, resample_poly


def load_envelope(path: Path, target_sr: int = 4000) -> tuple[np.ndarray, int]:
    """Load mono PCM WAV, downsample, and produce a smoothed envelope.

    Pre-emphasis + abs + 50ms smoothing makes percussive transients dominate
    the cross-correlation, which is what makes mixed-source sync robust.
    """
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        if sw != 2:
            raise ValueError(f"{path}: expected 16-bit PCM, got sampwidth={sw}")
        raw = w.readframes(n)
    arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        arr = arr.reshape(-1, ch).mean(axis=1)

    if sr != target_sr:
        if sr % target_sr != 0:
            g = gcd(sr, target_sr)
            arr = resample_poly(arr, target_sr // g, sr // g).astype(np.float32)
        else:
            step = sr // target_sr
            trim = (len(arr) // step) * step
            arr = arr[:trim].reshape(-1, step).mean(axis=1).astype(np.float32)

    arr = np.diff(arr, prepend=arr[0])
    env = np.abs(arr)
    win = max(1, target_sr // 20)
    kernel = np.ones(win, dtype=np.float32) / win
    env = np.convolve(env, kernel, mode="same")
    env = env - env.mean()
    s = env.std()
    if s > 0:
        env = env / s
    return env.astype(np.float32), target_sr


def correlate_envelopes(clip: np.ndarray, ref: np.ndarray, sr: int) -> tuple[float, float]:
    """Return (offset_seconds, confidence).

    offset_seconds: where clip[0] sits on ref's timeline. Negative = clip
    started rolling before ref did.

    confidence: peak / median(|corr|). >10 reliable, 5–10 marginal, <5 likely noise.
    """
    corr = correlate(clip, ref, mode="full", method="fft")
    lags = correlation_lags(len(clip), len(ref), mode="full")
    abs_corr = np.abs(corr)
    peak = int(np.argmax(abs_corr))
    lag_samples = int(lags[peak])
    med = float(np.median(abs_corr))
    confidence = float(abs_corr[peak] / med) if med > 0 else 0.0
    offset_seconds = -lag_samples / sr
    return offset_seconds, confidence


def correlate_clip(ref_wav: Path, clip_wav: Path, sr: int = 4000) -> tuple[float, float]:
    """High-level: load both WAVs, return (offset_seconds, confidence)."""
    ref_env, _ = load_envelope(ref_wav, target_sr=sr)
    clip_env, _ = load_envelope(clip_wav, target_sr=sr)
    return correlate_envelopes(clip_env, ref_env, sr)
