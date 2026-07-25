"""Drum transcription: where the hits are, and what was hit.

Onset detection finds the hits. Which piece of the kit made each one is
decided from where its energy sits in the spectrum — a kick is almost all low
end, a hi-hat almost all top end, a snare is broadband with a strong midrange
crack. That is enough to write a groove a drummer can read.
"""

from pathlib import Path
from typing import List, Sequence

import librosa
import numpy as np

from app.config import settings
from app.utils.audio import is_silent, load_mono
from app.utils.timing import BeatMap, quantize_to_grid

# General MIDI percussion keys, so exported MIDI plays back on any drum kit.
GM_DRUM_KEYS = {
    "kick": 36,
    "snare": 38,
    "hihat": 42,
    "tom": 45,
    "cymbal": 49,
}

# Notation staff positions, from the standard drum-kit layout.
DRUM_STAFF = {
    "kick": {"step": "F", "octave": 4, "notehead": "normal", "stem": "down"},
    "snare": {"step": "C", "octave": 5, "notehead": "normal", "stem": "up"},
    "hihat": {"step": "G", "octave": 5, "notehead": "x", "stem": "up"},
    "tom": {"step": "E", "octave": 5, "notehead": "normal", "stem": "up"},
    "cymbal": {"step": "A", "octave": 5, "notehead": "x", "stem": "up"},
}

# Frequency bands, in Hz, that separate the pieces of the kit.
BANDS = {
    "low": (20.0, 150.0),
    "low_mid": (150.0, 500.0),
    "mid": (500.0, 2000.0),
    "high": (2000.0, 8000.0),
    "very_high": (8000.0, 16000.0),
}

# How much audio after the onset to analyse. Long enough to capture the body
# of the hit, short enough not to run into the next one.
WINDOW_SEC = 0.06


def transcribe_drums(
    stem_name: str,
    stem_path: Path,
    beat_reference: BeatMap | dict | Sequence[float],
    division: int | None = None,
) -> List[dict]:
    beat_map = _as_beat_map(beat_reference)
    division = division or settings.quantization_division
    y, sr = load_mono(stem_path)
    if is_silent(y):
        return []

    y = np.ascontiguousarray(y)
    hop = settings.hop_length
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=hop, backtrack=True
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop)
    if onset_times.size == 0:
        return []

    strength_peak = float(onset_env.max()) or 1.0
    window = int(WINDOW_SEC * sr)

    hits: List[dict] = []
    for frame, t in zip(onset_frames, onset_times):
        start = int(t * sr)
        segment = y[start : start + window]
        if segment.size < 32:
            continue
        piece, certainty = classify_hit(segment, sr)
        beat_pos = quantize_to_grid(beat_map.seconds_to_beats(float(t)), division)
        strength = float(onset_env[min(int(frame), len(onset_env) - 1)]) / strength_peak
        hits.append(
            {
                "instrument": piece,
                "midi": GM_DRUM_KEYS[piece],
                "start_sec": round(float(t), 6),
                "start_beat": round(beat_pos, 6),
                "bar_index": beat_map.bar_of_beat(beat_pos),
                "beat_in_bar": round(beat_map.beat_in_bar(beat_pos), 4),
                "velocity": int(np.clip(strength * 127, 30, 127)),
                "source_stem": stem_name,
                "confidence": round(float(certainty), 4),
            }
        )

    return _dedupe(hits)


def classify_hit(segment: np.ndarray, sr: int) -> tuple[str, float]:
    """Name the kit piece from the balance of energy across the spectrum."""
    spectrum = np.abs(np.fft.rfft(segment * np.hanning(segment.size)))
    freqs = np.fft.rfftfreq(segment.size, 1.0 / sr)
    total = float(spectrum.sum()) + 1e-12

    share = {}
    for name, (low, high) in BANDS.items():
        mask = (freqs >= low) & (freqs < high)
        share[name] = float(spectrum[mask].sum()) / total

    centroid = float((freqs * spectrum).sum() / total)

    # Scores are deliberately overlapping rather than exclusive: a snare has
    # real low-mid content and a kick has some click, so the piece with the
    # best overall fit wins instead of the first threshold that matches.
    scores = {
        "kick": share["low"] * 2.0 - share["very_high"],
        "snare": share["low_mid"] * 1.2 + share["mid"] * 1.4 - share["low"] * 0.5,
        "hihat": share["very_high"] * 1.8 + share["high"] * 0.6 - share["low"] * 1.5,
        "cymbal": share["very_high"] * 1.2 + share["high"] * 1.0 - share["low"] * 1.0,
    }
    # A cymbal rings much longer than a hi-hat; without a decay measurement the
    # two are hard to separate, so bias toward the hi-hat, which is far more
    # common in a groove.
    scores["cymbal"] -= 0.15
    if centroid < 200.0:
        scores["kick"] += 0.3

    piece = max(scores, key=scores.get)
    ordered = sorted(scores.values(), reverse=True)
    margin = ordered[0] - ordered[1] if len(ordered) > 1 else 0.0
    certainty = float(np.clip(0.45 + margin, 0.1, 0.99))
    return piece, certainty


def _dedupe(hits: List[dict]) -> List[dict]:
    """One hit per instrument per grid slot.

    Onset detection often fires twice on a single loud hit; two kicks written
    on the same sixteenth is unplayable and always wrong.
    """
    seen: dict[tuple[str, float], dict] = {}
    for hit in hits:
        key = (hit["instrument"], hit["start_beat"])
        current = seen.get(key)
        if current is None or hit["velocity"] > current["velocity"]:
            seen[key] = hit
    return sorted(seen.values(), key=lambda h: (h["start_beat"], h["instrument"]))


def summarise_groove(hits: List[dict], beat_map: BeatMap) -> dict:
    """What the drummer is actually doing, in words rather than events."""
    if not hits:
        return {"pattern": "unknown", "kick_beats": [], "snare_beats": [], "hits_per_bar": 0.0}

    def positions(instrument: str) -> list[float]:
        slots = sorted(
            {
                round((h["start_beat"] - beat_map.downbeat_index) % beat_map.beats_per_bar + 1, 2)
                for h in hits
                if h["instrument"] == instrument
            }
        )
        return slots

    kick = positions("kick")
    snare = positions("snare")
    bars = max(beat_map.bar_count(), 1)

    backbeat = {2.0, 4.0}
    pattern = "backbeat" if backbeat.issubset(set(snare)) else "varied"
    return {
        "pattern": pattern,
        "kick_beats": kick,
        "snare_beats": snare,
        "hits_per_bar": round(len(hits) / bars, 2),
    }


def _as_beat_map(reference) -> BeatMap:
    if isinstance(reference, BeatMap):
        return reference
    if isinstance(reference, dict):
        return BeatMap(
            beat_times=list(reference.get("beat_times", [0.0, 0.5])),
            beats_per_bar=int(reference.get("beats_per_bar", 4)),
            downbeat_index=int(reference.get("downbeat_index", 0)),
        )
    return BeatMap(beat_times=list(reference))
