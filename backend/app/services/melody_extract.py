"""Monophonic melody transcription.

pYIN gives a per-frame pitch estimate plus a probability that the frame is
voiced at all. Using that probability is what separates a sung line from the
breaths and room tone around it, and its value becomes the note's reported
confidence instead of a hardcoded number.
"""

from pathlib import Path
from typing import List, Sequence

import librosa
import numpy as np
from scipy.ndimage import median_filter

from app.config import settings
from app.services.classify import profile_for
from app.services.quantize import quantize_notes
from app.utils.audio import is_silent, load_mono
from app.utils.notes import hz_to_midi_float, midi_to_hz, midi_to_note_name
from app.utils.timing import BeatMap

# Roles that can carry the tune, best first.
LEAD_PRIORITY = ["vocals", "backing_vocals", "guitar", "keys", "strings", "brass", "other", "bass"]

# A frame must be at least this likely to be voiced before its pitch is used.
VOICED_THRESHOLD = 0.5

# Pitch is smoothed over this many frames before rounding to a semitone, so
# vibrato does not split one note into several.
SMOOTHING_FRAMES = 7


def pick_lead_stem(stems: dict) -> tuple[str, Path] | None:
    for role in LEAD_PRIORITY:
        entry = stems.get(role)
        if not entry:
            continue
        path = entry[0] if isinstance(entry, list) else entry
        if path is not None:
            return role, path
    return None


def extract_melody_events(
    stem_name: str,
    stem_path: Path,
    beat_reference: BeatMap | dict | Sequence[float],
    division: int | None = None,
) -> List[dict]:
    beat_map = as_beat_map(beat_reference)
    profile = profile_for(stem_name)
    y, sr = load_mono(stem_path)
    if is_silent(y):
        return []

    hop = settings.hop_length
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=max(profile.fmin_hz, 65.0),
        fmax=min(profile.fmax_hz, sr / 2 - 1),
        sr=sr,
        hop_length=hop,
        fill_na=np.nan,
    )
    times = librosa.times_like(f0, sr=sr, hop_length=hop)
    onset_frames = set(
        int(f)
        for f in librosa.onset.onset_detect(y=np.ascontiguousarray(y), sr=sr, hop_length=hop)
    )

    midi_track = _smoothed_midi(f0, voiced_flag, voiced_prob)
    segments = _segment(midi_track, voiced_prob, times, onset_frames)

    notes = [_note_from_segment(seg, stem_name) for seg in segments]
    return quantize_notes(notes, beat_map, division)


def _smoothed_midi(
    f0: np.ndarray, voiced_flag: np.ndarray, voiced_prob: np.ndarray
) -> np.ndarray:
    """Per-frame MIDI number, NaN where unvoiced, smoothed across vibrato."""
    midi = np.full(f0.shape, np.nan, dtype=float)
    usable = np.isfinite(f0) & voiced_flag & (voiced_prob >= VOICED_THRESHOLD)
    if not np.any(usable):
        return midi
    midi[usable] = [hz_to_midi_float(float(v)) for v in f0[usable]]

    # Median-filter the voiced values only, then write them back, so silence
    # is never smeared into pitch.
    idx = np.where(usable)[0]
    filled = np.copy(midi)
    filled[idx] = median_filter(
        midi[idx], size=min(SMOOTHING_FRAMES, max(idx.size, 1)), mode="nearest"
    )
    return filled


def _segment(
    midi_track: np.ndarray,
    voiced_prob: np.ndarray,
    times: np.ndarray,
    onset_frames: set[int],
) -> list[dict]:
    """Group frames of equal rounded pitch into note events.

    A new note also begins at a detected onset even when the pitch has not
    changed — that is how a repeated note is told apart from one long one.
    """
    segments: list[dict] = []
    current: dict | None = None

    for frame, value in enumerate(midi_track):
        if not np.isfinite(value):
            if current:
                segments.append(current)
                current = None
            continue

        rounded = int(round(float(value)))
        restart = (
            current is None
            or rounded != current["midi"]
            or (frame in onset_frames and frame - current["start_frame"] > 2)
        )
        if restart:
            if current:
                segments.append(current)
            current = {
                "midi": rounded,
                "start_frame": frame,
                "start_sec": float(times[frame]),
                "end_sec": float(times[frame]),
                "probs": [float(voiced_prob[frame])],
                "cents": [float((value - rounded) * 100.0)],
            }
        else:
            current["end_sec"] = float(times[frame])
            current["probs"].append(float(voiced_prob[frame]))
            current["cents"].append(float((value - rounded) * 100.0))

    if current:
        segments.append(current)
    return segments


def _note_from_segment(seg: dict, source: str) -> dict:
    midi = int(seg["midi"])
    mean_prob = float(np.mean(seg["probs"])) if seg["probs"] else 0.0
    # Frames sitting far from the tempered pitch usually mean the tracker
    # latched onto something that is not the fundamental, so tuning distance
    # discounts the confidence.
    detune = float(np.mean(np.abs(seg["cents"]))) if seg["cents"] else 0.0
    tuning_penalty = float(np.clip(1.0 - detune / 50.0, 0.0, 1.0))
    return {
        "note_name": midi_to_note_name(midi),
        "midi": midi,
        "frequency_hz": round(midi_to_hz(midi), 4),
        "start_sec": seg["start_sec"],
        "end_sec": max(seg["end_sec"], seg["start_sec"] + 0.01),
        "duration_sec": max(seg["end_sec"] - seg["start_sec"], 0.01),
        "source_stem": source,
        "confidence": round(mean_prob * (0.6 + 0.4 * tuning_penalty), 4),
    }


def as_beat_map(reference) -> BeatMap:
    if isinstance(reference, BeatMap):
        return reference
    if isinstance(reference, dict):
        return BeatMap(
            beat_times=list(reference.get("beat_times", [0.0, 0.5])),
            beats_per_bar=int(reference.get("beats_per_bar", 4)),
            downbeat_index=int(reference.get("downbeat_index", 0)),
        )
    return BeatMap(beat_times=list(reference))


def locate_bar_beat(start_sec: float, beat_grid: dict) -> tuple[int, float]:
    """Bar index and 1-based beat position for a moment in the song."""
    beat_map = as_beat_map(beat_grid)
    beats = beat_map.seconds_to_beats(start_sec)
    return beat_map.bar_of_beat(beats), beat_map.beat_in_bar(beats)
