"""Transcription for pitched stems.

Two strategies, chosen by instrument. A bass line is one note at a time, so it
gets the same pitch tracker the melody uses, constrained to the bass register.
Guitars and keys play chords, so they get a constant-Q analysis segmented at
note onsets: between two onsets the sounding pitches are stable, and the peaks
of the median spectrum over that span are the notes being held.
"""

from pathlib import Path
from typing import List, Sequence

import librosa
import numpy as np

from app.config import settings
from app.services.classify import profile_for
from app.services.melody_extract import as_beat_map, extract_melody_events
from app.services.quantize import quantize_notes
from app.utils.audio import is_silent, load_mono
from app.utils.notes import midi_to_hz, midi_to_note_name
from app.utils.timing import BeatMap

BINS_PER_OCTAVE = 12

# A CQT peak this far below the loudest pitch in its segment is background
# bleed or reverb tail rather than a note someone played.
PEAK_FLOOR = 0.22

# Overtones land 12, 19 and 24 semitones above the fundamental. A peak at one
# of those offsets that is weaker than this share of its parent is treated as
# that parent's harmonic, not as a separate note.
HARMONIC_OFFSETS = (12, 19, 24, 28)
HARMONIC_RATIO = 0.62

# Even a dense keyboard part rarely sounds more than this many notes at once;
# the cap keeps reverb wash out of the score.
MAX_VOICES = 6


def transcribe_pitched_stem(
    stem_name: str,
    stem_path: Path,
    beat_reference: BeatMap | dict | Sequence[float],
    division: int | None = None,
) -> List[dict]:
    profile = profile_for(stem_name)
    if not profile.polyphonic:
        return extract_melody_events(stem_name, stem_path, beat_reference, division)

    beat_map = as_beat_map(beat_reference)
    y, sr = load_mono(stem_path)
    if is_silent(y):
        return []

    hop = settings.hop_length
    y = np.ascontiguousarray(y)
    min_midi = max(int(round(librosa.hz_to_midi(profile.fmin_hz))), 12)
    max_midi = min(int(round(librosa.hz_to_midi(profile.fmax_hz))), 108)
    n_bins = max(max_midi - min_midi + 1, BINS_PER_OCTAVE)

    cqt = np.abs(
        librosa.cqt(
            y,
            sr=sr,
            hop_length=hop,
            fmin=midi_to_hz(min_midi),
            n_bins=n_bins,
            bins_per_octave=BINS_PER_OCTAVE,
        )
    )
    times = librosa.times_like(cqt, sr=sr, hop_length=hop)
    boundaries = _segment_boundaries(y, sr, hop, cqt.shape[1])

    notes: List[dict] = []
    for start_frame, end_frame in zip(boundaries, boundaries[1:]):
        if end_frame - start_frame < 2:
            continue
        spectrum = np.median(cqt[:, start_frame:end_frame], axis=1)
        for midi, strength in _pitches_in_segment(spectrum, min_midi):
            notes.append(
                {
                    "note_name": midi_to_note_name(midi),
                    "midi": midi,
                    "frequency_hz": round(midi_to_hz(midi), 4),
                    "start_sec": float(times[start_frame]),
                    "end_sec": float(times[min(end_frame, len(times) - 1)]),
                    "duration_sec": float(
                        times[min(end_frame, len(times) - 1)] - times[start_frame]
                    ),
                    "source_stem": stem_name,
                    "confidence": round(float(strength), 4),
                }
            )

    return quantize_notes(notes, beat_map, division)


def _segment_boundaries(y: np.ndarray, sr: int, hop: int, n_frames: int) -> list[int]:
    """Frames where the sounding harmony may have changed.

    Onsets mark where something new was struck; the start and end of the stem
    close the first and last segments.
    """
    onsets = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop, backtrack=True)
    frames = sorted({0, *(int(f) for f in onsets if 0 < int(f) < n_frames), n_frames})
    return frames


def _pitches_in_segment(spectrum: np.ndarray, min_midi: int) -> list[tuple[int, float]]:
    """Peak pitches of one segment, with overtones of stronger pitches removed."""
    peak = float(spectrum.max()) if spectrum.size else 0.0
    if peak <= 0:
        return []
    normalised = spectrum / peak

    candidates: list[tuple[int, float]] = []
    for bin_index in range(1, len(normalised) - 1):
        value = normalised[bin_index]
        if value < PEAK_FLOOR:
            continue
        if value < normalised[bin_index - 1] or value < normalised[bin_index + 1]:
            continue
        candidates.append((min_midi + bin_index, float(value)))

    # Also allow the very strongest bin through even if it sits at an edge of
    # the range, where the local-maximum test cannot apply.
    strongest_bin = int(np.argmax(normalised))
    if strongest_bin in (0, len(normalised) - 1):
        candidates.append((min_midi + strongest_bin, float(normalised[strongest_bin])))

    candidates.sort(key=lambda c: c[1], reverse=True)
    kept: list[tuple[int, float]] = []
    for midi, strength in candidates:
        if any(
            midi - parent_midi in HARMONIC_OFFSETS and strength < parent_strength * HARMONIC_RATIO
            for parent_midi, parent_strength in kept
        ):
            continue
        kept.append((midi, strength))
        if len(kept) >= MAX_VOICES:
            break
    return sorted(kept)


def transcribe_bass_stem(
    stem_name: str,
    stem_path: Path,
    beat_reference: BeatMap | dict | Sequence[float],
    division: int | None = None,
) -> List[dict]:
    """Bass is monophonic by nature; the melody tracker handles it best."""
    return extract_melody_events(stem_name, stem_path, beat_reference, division)
