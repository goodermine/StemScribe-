"""Chord estimation.

Beat-synchronous chroma is matched against chord templates, then smoothed with
Viterbi decoding. The smoothing matters more than the matching: frame-by-frame
guesses flicker between relative chords on every passing note, and a chart that
changes chord twice a beat is useless to a player. A transition penalty makes
the decoder prefer holding a chord unless the evidence to move is strong.
"""

from pathlib import Path
from typing import Sequence

import librosa
import numpy as np

from app.config import settings
from app.services.classify import profile_for
from app.services.key_detect import FLAT_SPELLING, SHARP_SPELLING, roman_numeral
from app.utils.audio import is_silent, load_mono
from app.utils.timing import BeatMap

# Chord templates as semitone offsets from the root, ordered so that simpler
# shapes are preferred when scores tie.
TEMPLATES: list[tuple[str, str, tuple[int, ...]]] = [
    ("maj", "", (0, 4, 7)),
    ("min", "m", (0, 3, 7)),
    ("5", "5", (0, 7)),
    ("sus4", "sus4", (0, 5, 7)),
    ("sus2", "sus2", (0, 2, 7)),
    ("7", "7", (0, 4, 7, 10)),
    ("m7", "m7", (0, 3, 7, 10)),
    ("maj7", "maj7", (0, 4, 7, 11)),
    ("dim", "dim", (0, 3, 6)),
]

# Cost of changing chord from one slot to the next, on the same scale as the
# correlation scores below (-1 to 1). High enough that a vocal run or a cymbal
# crash cannot pull the chord around, low enough that a real move to a chord
# sharing two notes with the current one — C to Am — still wins. Past about
# 0.4 genuine changes start being swallowed.
TRANSITION_PENALTY = 0.30

# Chords shorter than this get absorbed into their neighbours.
MIN_CHORD_BEATS = 2.0

# Weight of each role's contribution to the harmonic picture. The bass names
# the root; guitars and keys name the quality.
ROLE_WEIGHTS = {"guitar": 1.0, "keys": 1.0, "strings": 0.7, "brass": 0.6, "other": 0.6, "bass": 0.9}


def _template_vectors() -> tuple[list[str], list[str], np.ndarray]:
    """Binary chord masks, one state per root and quality."""
    names, suffixes, vectors = [], [], []
    for quality, suffix, offsets in TEMPLATES:
        for root in range(12):
            vec = np.zeros(12, dtype=float)
            for offset in offsets:
                vec[(root + offset) % 12] = 1.0
            names.append(f"{root}:{quality}")
            suffixes.append(suffix)
            vectors.append(vec)
    return names, suffixes, np.stack(vectors)


STATE_NAMES, STATE_SUFFIXES, STATE_VECTORS = _template_vectors()

_CENTRED_TEMPLATES = STATE_VECTORS - STATE_VECTORS.mean(axis=1, keepdims=True)
_TEMPLATE_NORMS = np.linalg.norm(_CENTRED_TEMPLATES, axis=1, keepdims=True)


def score_templates(chroma: np.ndarray) -> np.ndarray:
    """How well each chord explains each beat, independent of chord size.

    Getting this scale-free matters more than it looks. Cosine against an
    L2-normalised binary template rewards bigger chords for free: real chroma
    from a mixed recording is smeared by harmonics and bleed, and against
    flat-ish chroma an n-note template scores sqrt(n/12). That put a seventh
    chord on 371 of 398 beats of this song. Contrasting mean energy inside the
    chord against outside it overcorrects the other way, favouring two-note
    power chords for the mirror-image reason.

    Pearson correlation is neutral. The exact template scores 1.0, while both a
    subset and a superset of the sounding notes score strictly less, so the
    chord that wins is the one that was actually played.
    """
    centred = chroma - chroma.mean(axis=0, keepdims=True)
    norms = np.linalg.norm(centred, axis=0, keepdims=True)
    denominator = _TEMPLATE_NORMS * np.where(norms > 0, norms, 1.0)
    return (_CENTRED_TEMPLATES @ centred) / denominator


def harmonic_chroma(
    stems_by_role: dict[str, list[Path]], beat_times: Sequence[float]
) -> np.ndarray | None:
    """Beat-synchronous chroma built from the stems that carry harmony."""
    accumulated: np.ndarray | None = None
    sr_used = None
    for role, paths in stems_by_role.items():
        if not profile_for(role).informs_harmony:
            continue
        weight = ROLE_WEIGHTS.get(role, 0.5)
        for path in paths:
            y, sr = load_mono(path)
            if is_silent(y):
                continue
            chroma = librosa.feature.chroma_cqt(
                y=np.ascontiguousarray(y), sr=sr, hop_length=settings.hop_length
            )
            sr_used = sr
            if accumulated is None:
                accumulated = weight * chroma
            else:
                width = min(accumulated.shape[1], chroma.shape[1])
                accumulated = accumulated[:, :width] + weight * chroma[:, :width]

    if accumulated is None or sr_used is None:
        return None

    beat_frames = librosa.time_to_frames(
        np.asarray(beat_times, dtype=float), sr=sr_used, hop_length=settings.hop_length
    )
    beat_frames = np.clip(beat_frames, 0, accumulated.shape[1] - 1)
    if beat_frames.size < 2:
        return None
    return librosa.util.sync(accumulated, beat_frames, aggregate=np.median)


def slot_size_for(beats_per_bar: int) -> int:
    """How many beats one chord slot spans.

    Chords change on bar lines and half-bar lines far more often than on
    arbitrary beats, so deciding at that resolution both smooths the estimate
    and puts the changes where a player expects to read them. Deciding per beat
    lets every vocal run and cymbal crash pull the chord around.
    """
    return max(beats_per_bar // 2, 1) if beats_per_bar % 2 == 0 else beats_per_bar


def estimate_chords(
    stems_by_role: dict[str, list[Path]],
    beat_map: BeatMap,
    key_info: dict,
) -> list[dict]:
    chroma = harmonic_chroma(stems_by_role, beat_map.beat_times)
    if chroma is None or chroma.shape[1] == 0:
        return []

    slot_beats = slot_size_for(beat_map.beats_per_bar)
    slotted, origin = _to_slots(chroma, beat_map.downbeat_index, slot_beats)
    if slotted.shape[1] == 0:
        return []

    scores = score_templates(slotted)
    path = _viterbi(scores)
    spans = _collapse(path, scores, beat_map, slot_beats, origin)
    return _label(spans, key_info)


def _to_slots(
    chroma: np.ndarray, downbeat_index: int, slot_beats: int
) -> tuple[np.ndarray, int]:
    """Average beat-synchronous chroma into chord slots aligned to the downbeat."""
    start = downbeat_index % slot_beats
    usable = chroma[:, start:]
    n_slots = usable.shape[1] // slot_beats
    if n_slots == 0:
        return chroma[:, :0], start
    trimmed = usable[:, : n_slots * slot_beats]
    return trimmed.reshape(12, n_slots, slot_beats).mean(axis=2), start


def _viterbi(scores: np.ndarray) -> list[int]:
    """Best chord sequence, trading fit against how often the chord changes."""
    n_states, n_beats = scores.shape
    best = scores[:, 0].copy()
    back = np.zeros((n_states, n_beats), dtype=int)

    for t in range(1, n_beats):
        stay = best
        switch = best.max() - TRANSITION_PENALTY
        switch_from = int(np.argmax(best))
        take_stay = stay >= switch
        best = np.where(take_stay, stay, switch) + scores[:, t]
        back[:, t] = np.where(take_stay, np.arange(n_states), switch_from)

    path = [int(np.argmax(best))]
    for t in range(n_beats - 1, 0, -1):
        path.append(int(back[path[-1], t]))
    return path[::-1]


def _collapse(
    path: list[int],
    scores: np.ndarray,
    beat_map: BeatMap,
    slot_beats: int = 1,
    origin: int = 0,
) -> list[dict]:
    """Turn a per-slot state sequence into chord spans, dropping flickers."""
    spans: list[dict] = []
    for slot_index, state in enumerate(path):
        start_beat = origin + slot_index * slot_beats
        if spans and spans[-1]["state"] == state:
            spans[-1]["end_beat"] = float(start_beat + slot_beats)
            spans[-1]["fit"].append(float(scores[state, slot_index]))
        else:
            spans.append(
                {
                    "state": state,
                    "start_beat": float(start_beat),
                    "end_beat": float(start_beat + slot_beats),
                    "fit": [float(scores[state, slot_index])],
                }
            )

    merged: list[dict] = []
    for span in spans:
        length = span["end_beat"] - span["start_beat"]
        if merged and length < MIN_CHORD_BEATS:
            # Too short to be a real chord change — extend the previous one
            # over it rather than writing a chord nobody played.
            merged[-1]["end_beat"] = span["end_beat"]
            continue
        merged.append(span)

    for span in merged:
        span["start_sec"] = round(beat_map.beats_to_seconds(span["start_beat"]), 4)
        span["end_sec"] = round(beat_map.beats_to_seconds(span["end_beat"]), 4)
        span["bar_index"] = beat_map.bar_of_beat(span["start_beat"])
        span["beat_in_bar"] = round(beat_map.beat_in_bar(span["start_beat"]), 3)
        span["duration_beats"] = round(span["end_beat"] - span["start_beat"], 3)
    return merged


def _label(spans: list[dict], key_info: dict) -> list[dict]:
    prefer_flats = int(key_info.get("fifths", 0)) < 0
    spelling = FLAT_SPELLING if prefer_flats else SHARP_SPELLING
    tonic_pc = int(key_info.get("tonic_pitch_class", 0))
    mode = key_info.get("mode", "major")

    out: list[dict] = []
    for span in spans:
        root_str, quality = STATE_NAMES[span["state"]].split(":")
        root_pc = int(root_str)
        suffix = STATE_SUFFIXES[span["state"]]
        fit = float(np.mean(span["fit"])) if span["fit"] else 0.0
        out.append(
            {
                "symbol": f"{spelling[root_pc]}{suffix}",
                "root": spelling[root_pc],
                "root_pitch_class": root_pc,
                "quality": quality,
                "roman": roman_numeral(root_pc, quality, tonic_pc, mode),
                "start_sec": span["start_sec"],
                "end_sec": span["end_sec"],
                "start_beat": round(span["start_beat"], 3),
                "end_beat": round(span["end_beat"], 3),
                "duration_beats": span["duration_beats"],
                "bar_index": span["bar_index"],
                "beat_in_bar": span["beat_in_bar"],
                "confidence": round(float(np.clip(fit, 0.0, 1.0)), 4),
            }
        )
    return out


def chords_by_bar(chords: list[dict], bar_count: int) -> list[list[dict]]:
    """Group chords under the bar they start in, for chart layout."""
    grouped: list[list[dict]] = [[] for _ in range(max(bar_count, 0))]
    for chord in chords:
        bar = chord["bar_index"]
        if 0 <= bar < len(grouped):
            grouped[bar].append(chord)
    return grouped
