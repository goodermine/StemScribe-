from pathlib import Path
from typing import Iterable

import librosa
import numpy as np

from app.utils.audio import load_mono


def estimate_beat_grid(stem_paths: Iterable[Path], preferred_drums: Path | None = None) -> dict:
    target = preferred_drums if preferred_drums and preferred_drums.exists() else None
    if target is None:
        stem_paths = list(stem_paths)
        if not stem_paths:
            return {
                "bpm": 120.0,
                "beat_times": [0.0],
                "bar_starts": [0.0],
                "time_signature_guess": "4/4",
                "confidence": 0.1,
            }
        target = stem_paths[0]

    y, sr = load_mono(target)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr).tolist()
    if not beat_times:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        beats = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
        beat_times = librosa.frames_to_time(beats, sr=sr).tolist()
    if not beat_times:
        beat_times = list(np.arange(0.0, max(len(y) / sr, 1.0), 0.5))

    ts = guess_time_signature(beat_times)
    bar_starts = beat_times[::4] if ts == "4/4" else beat_times[::3]
    return {
        "bpm": float(tempo if tempo else 120.0),
        "beat_times": beat_times,
        "bar_starts": bar_starts,
        "time_signature_guess": ts,
        "confidence": 0.75 if preferred_drums else 0.55,
    }


def guess_time_signature(beat_times: list[float]) -> str:
    if len(beat_times) < 8:
        return "4/4"
    intervals = np.diff(beat_times)
    cv = float(np.std(intervals) / (np.mean(intervals) + 1e-6))
    if cv < 0.05:
        return "4/4"
    return "4/4"
