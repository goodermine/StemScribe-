"""Key detection by chroma profile correlation.

The Krumhansl-Kessler profiles describe how strongly each scale degree is
weighted in major and minor. Correlating a song's average chroma against all
24 rotations of those profiles gives the key, and the gap between the best and
second-best fit gives an honest confidence.
"""

from pathlib import Path
from typing import Sequence

import librosa
import numpy as np

from app.config import settings
from app.utils.audio import is_silent, load_mono
from app.utils.notes import PITCH_CLASSES

# Krumhansl-Kessler key profiles.
MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

# Sharps (positive) or flats (negative) in each major key's signature, by tonic
# pitch class. Minor keys borrow their relative major's signature.
MAJOR_FIFTHS = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3, 10: -2, 5: -1}

# Tonic spelling per signature, so a key with flats is not written with sharps.
SHARP_SPELLING = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_SPELLING = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def average_chroma(stem_paths: Sequence[Path]) -> np.ndarray:
    """Chroma summed across the stems that carry harmony."""
    total = np.zeros(12, dtype=float)
    for path in stem_paths:
        y, sr = load_mono(path)
        if is_silent(y):
            continue
        chroma = librosa.feature.chroma_cqt(
            y=np.ascontiguousarray(y), sr=sr, hop_length=settings.hop_length
        )
        total += chroma.mean(axis=1)
    return total


def detect_key(stem_paths: Sequence[Path]) -> dict:
    chroma = average_chroma(stem_paths)
    if chroma.sum() <= 0:
        return _unknown_key()

    chroma = chroma / chroma.sum()
    scores: list[tuple[float, int, str]] = []
    for tonic in range(12):
        rotated = np.roll(chroma, -tonic)
        scores.append((_correlate(rotated, MAJOR_PROFILE), tonic, "major"))
        scores.append((_correlate(rotated, MINOR_PROFILE), tonic, "minor"))

    scores.sort(reverse=True)
    best_score, tonic, mode = scores[0]
    runner_up = scores[1][0] if len(scores) > 1 else 0.0

    fifths = key_signature_fifths(tonic, mode)
    name = spell_tonic(tonic, fifths)
    # A clear winner means a confident key; two near-equal fits usually means
    # the song is modal or moves between relative keys.
    margin = float(np.clip((best_score - runner_up) * 4.0, 0.0, 1.0))

    return {
        "tonic": name,
        "tonic_pitch_class": tonic,
        "mode": mode,
        "key_name": f"{name} {mode}",
        "fifths": fifths,
        "confidence": round(float(np.clip(0.35 + 0.65 * margin, 0.05, 0.99)), 3),
        "chroma": [round(float(v), 5) for v in chroma],
    }


def key_signature_fifths(tonic_pc: int, mode: str) -> int:
    """Position on the circle of fifths for the written key signature."""
    relative_major = tonic_pc if mode == "major" else (tonic_pc + 3) % 12
    return MAJOR_FIFTHS.get(relative_major, 0)


def spell_tonic(tonic_pc: int, fifths: int) -> str:
    return FLAT_SPELLING[tonic_pc % 12] if fifths < 0 else SHARP_SPELLING[tonic_pc % 12]


def _correlate(observed: np.ndarray, profile: np.ndarray) -> float:
    a = observed - observed.mean()
    b = profile - profile.mean()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _unknown_key() -> dict:
    return {
        "tonic": "C",
        "tonic_pitch_class": 0,
        "mode": "major",
        "key_name": "C major",
        "fifths": 0,
        "confidence": 0.05,
        "chroma": [0.0] * 12,
    }


def scale_degrees(tonic_pc: int, mode: str) -> list[int]:
    steps = [0, 2, 4, 5, 7, 9, 11] if mode == "major" else [0, 2, 3, 5, 7, 8, 10]
    return [(tonic_pc + s) % 12 for s in steps]


def roman_numeral(chord_root_pc: int, chord_quality: str, tonic_pc: int, mode: str) -> str:
    """Where a chord sits relative to the key, for players who think in numbers."""
    degrees = scale_degrees(tonic_pc, mode)
    if chord_root_pc not in degrees:
        return ""
    index = degrees.index(chord_root_pc)
    numerals = ["I", "II", "III", "IV", "V", "VI", "VII"]
    numeral = numerals[index]
    if chord_quality in {"min", "m7", "dim"}:
        numeral = numeral.lower()
    if chord_quality == "dim":
        numeral += "°"
    if chord_quality in {"7", "m7", "maj7"}:
        numeral += "7"
    return numeral


PITCH_CLASS_NAMES = PITCH_CLASSES
