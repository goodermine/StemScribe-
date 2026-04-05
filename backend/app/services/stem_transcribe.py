from pathlib import Path
from typing import List

import librosa
import numpy as np

from app.services.quantize import quantize_notes
from app.utils.audio import load_mono
from app.utils.notes import hz_to_midi, midi_to_hz, midi_to_note_name


def transcribe_pitched_stem(stem_name: str, stem_path: Path, beat_grid: dict, division: int = 2) -> List[dict]:
    y, sr = load_mono(stem_path)
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    notes = []
    for frame in range(pitches.shape[1]):
        idx = int(np.argmax(magnitudes[:, frame]))
        hz = float(pitches[idx, frame])
        if hz <= 0:
            continue
        midi = hz_to_midi(hz)
        t = librosa.frames_to_time(frame, sr=sr)
        notes.append(
            {
                "note_name": midi_to_note_name(midi),
                "midi": midi,
                "frequency_hz": round(midi_to_hz(midi), 4),
                "start_sec": float(t),
                "end_sec": float(t + 0.1),
                "duration_sec": 0.1,
                "bar_index": 0,
                "beat_in_bar": 1.0,
                "source_stem": stem_name,
                "confidence": 0.55,
            }
        )
    return quantize_notes(notes, beat_grid.get("beat_times", []), division=division)
