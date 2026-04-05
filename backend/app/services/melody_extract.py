from pathlib import Path
from typing import List

import librosa
import numpy as np

from app.services.quantize import quantize_notes
from app.utils.audio import load_mono
from app.utils.notes import hz_to_midi, midi_to_hz, midi_to_note_name


LEAD_PRIORITY = ["vocals", "keys", "guitar", "other", "bass"]


def pick_lead_stem(stems: dict[str, Path]) -> tuple[str, Path] | None:
    for name in LEAD_PRIORITY:
        if name in stems:
            return name, stems[name]
    return None


def extract_melody_events(stem_name: str, stem_path: Path, beat_grid: dict, division: int = 2) -> List[dict]:
    y, sr = load_mono(stem_path)
    f0, _, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )
    hop_length = 512
    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)
    notes: List[dict] = []
    active = None
    for t, f in zip(times, f0):
        if np.isnan(f):
            if active:
                notes.append(active)
                active = None
            continue
        midi = hz_to_midi(float(f))
        if not active:
            active = _new_note(t, midi, stem_name)
        elif abs(midi - active["midi"]) <= 1:
            active["midi"] = int(round((active["midi"] + midi) / 2))
            active["end_sec"] = float(t)
        else:
            notes.append(active)
            active = _new_note(t, midi, stem_name)
    if active:
        notes.append(active)

    for n in notes:
        n["note_name"] = midi_to_note_name(n["midi"])
        n["frequency_hz"] = round(midi_to_hz(n["midi"]), 4)
        n["duration_sec"] = round(max(n["end_sec"] - n["start_sec"], 0.01), 6)
        n["bar_index"], n["beat_in_bar"] = locate_bar_beat(n["start_sec"], beat_grid)

    return quantize_notes(notes, beat_grid.get("beat_times", []), division=division)


def _new_note(t: float, midi: int, source: str) -> dict:
    return {
        "note_name": "",
        "midi": midi,
        "frequency_hz": 0.0,
        "start_sec": float(t),
        "end_sec": float(t) + 0.05,
        "duration_sec": 0.05,
        "bar_index": 0,
        "beat_in_bar": 0.0,
        "source_stem": source,
        "confidence": 0.75,
    }


def locate_bar_beat(start_sec: float, beat_grid: dict) -> tuple[int, float]:
    beats = beat_grid.get("beat_times", [0.0])
    bars = beat_grid.get("bar_starts", [0.0])
    nearest_beat = min(range(len(beats)), key=lambda i: abs(beats[i] - start_sec))
    bar_idx = max([i for i, b in enumerate(bars) if b <= start_sec], default=0)
    beat_in_bar = float(nearest_beat - (bar_idx * 4)) + 1.0
    return bar_idx, beat_in_bar
