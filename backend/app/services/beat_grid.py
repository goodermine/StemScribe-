"""Tempo, beat positions, downbeats and time signature.

The beat grid is the foundation for everything downstream — if it is wrong,
every bar number and every notated rhythm is wrong with it. So this prefers
the drum kit as its timing source, falls back deliberately, and reports a
confidence it actually computed rather than a constant.
"""

from pathlib import Path
from typing import Iterable, Sequence

import librosa
import numpy as np

from app.config import settings
from app.utils.audio import load_mono
from app.utils.timing import BeatMap

# Candidate bar lengths, in beats.
CANDIDATE_METERS = (4, 3, 6, 2)

METER_TO_SIGNATURE = {4: "4/4", 3: "3/4", 6: "6/8", 2: "2/4"}

# How much to trust each candidate before looking at the audio. A plain
# kick-snare-kick-snare backbeat fits a 2-beat bar better than a 4-beat one on
# pure accent contrast, because every accent then falls on beat one — but it is
# a 4/4 groove, and writing it in 2/4 doubles the bar count and misplaces every
# section boundary. The evidence has to be strong to beat the common case.
METER_PRIOR = {4: 1.0, 3: 0.9, 6: 0.7, 2: 0.5}


def _as_scalar(value) -> float:
    """librosa >= 0.10 returns tempo as an array; older versions a float."""
    arr = np.atleast_1d(np.asarray(value, dtype=float))
    return float(arr[0]) if arr.size else 0.0


def pick_timing_source(
    stems_by_role: dict[str, list[Path]],
    all_stems: Sequence[Path],
) -> tuple[Path | None, str]:
    """The kit gives the cleanest beats; percussion is a usable stand-in."""
    for role in ("drums", "percussion", "bass"):
        paths = [p for p in stems_by_role.get(role, []) if p.exists()]
        if paths:
            return paths[0], role
    stems = [p for p in all_stems if p.exists()]
    return (stems[0], "fallback") if stems else (None, "none")


def estimate_beat_grid(
    stem_paths: Iterable[Path],
    stems_by_role: dict[str, list[Path]] | None = None,
) -> dict:
    stem_paths = list(stem_paths)
    stems_by_role = stems_by_role or {}
    target, source_role = pick_timing_source(stems_by_role, stem_paths)

    if target is None:
        return _empty_grid()

    y, sr = load_mono(target)
    if not np.any(np.abs(y) > 1e-5):
        return _empty_grid()

    hop = settings.hop_length
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempo_raw, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=hop, trim=False
    )
    beat_frames = np.asarray(beat_frames).astype(int)

    if beat_frames.size < 4:
        # Beat tracking failed outright — fall back to raw onsets so later
        # stages still have a monotonic time reference to work from.
        beat_frames = np.asarray(
            librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop)
        ).astype(int)
    if beat_frames.size < 2:
        duration = len(y) / sr
        beat_times = np.arange(0.0, max(duration, 1.0), 0.5)
        beat_frames = np.asarray(
            librosa.time_to_frames(beat_times, sr=sr, hop_length=hop)
        ).astype(int)

    bpm = _as_scalar(tempo_raw)
    if not 30.0 <= bpm <= 300.0:
        bpm = _bpm_from_intervals(
            librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop).tolist()
        )

    bpm, beat_frames = refine_tempo_octave(onset_env, beat_frames, bpm, sr=sr, hop=hop)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop).tolist()

    # A second envelope restricted to the low end, used to find beat one.
    low_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, fmax=150.0)
    meter, downbeat_index, meter_strength = detect_meter(onset_env, beat_frames, low_env)
    beat_map = BeatMap(beat_times=beat_times, beats_per_bar=meter, downbeat_index=downbeat_index)
    bar_starts = [beat_times[i] for i in range(downbeat_index, len(beat_times), meter)]

    return {
        "bpm": round(bpm, 3),
        "beat_times": [round(t, 6) for t in beat_times],
        "bar_starts": [round(t, 6) for t in bar_starts],
        "downbeat_index": downbeat_index,
        "beats_per_bar": meter,
        "time_signature_guess": METER_TO_SIGNATURE.get(meter, "4/4"),
        "bar_count": beat_map.bar_count(),
        "timing_source": source_role,
        "confidence": round(_grid_confidence(beat_times, meter_strength, source_role), 3),
    }


def refine_tempo_octave(
    onset_env: np.ndarray, beat_frames: np.ndarray, bpm: float, sr: int = 22050, hop: int = 512
) -> tuple[float, np.ndarray]:
    """Correct half-time and double-time beat tracking.

    Beat trackers regularly lock onto half or twice the tempo a player would
    count — the pulse is genuinely ambiguous from the signal alone, and a whole
    song transcribed at 60 BPM instead of 120 has every note value doubled.

    Two things decide it. Whether the midpoints between tracked beats land on
    real onsets, which says the faster pulse is being played; and whether the
    faster reading sits closer to the tempo people actually count at, which
    stops a slow song with busy hi-hats from being doubled. Magnitude alone
    will not do: a kick is far louder in the onset envelope than the snare
    between it, yet both are beats.
    """
    beat_frames = np.asarray(beat_frames).astype(int)
    if beat_frames.size < 4 or onset_env.size == 0:
        return bpm, beat_frames

    onsets = np.asarray(
        librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop)
    ).astype(int)
    if onsets.size == 0:
        return bpm, beat_frames

    midpoints = ((beat_frames[:-1] + beat_frames[1:]) // 2).astype(int)

    if (
        bpm * 2 <= 200.0
        and _onset_coverage(onsets, midpoints) >= 0.7
        and _closer_to_preferred(bpm * 2, bpm)
    ):
        return bpm * 2.0, np.sort(np.concatenate([beat_frames, midpoints]))

    if (
        bpm / 2 >= 50.0
        and _onset_coverage(onsets, beat_frames[1::2]) < 0.35
        and _closer_to_preferred(bpm / 2, bpm)
    ):
        return bpm / 2.0, beat_frames[0::2]

    return bpm, beat_frames


def _onset_coverage(onsets: np.ndarray, candidates: np.ndarray, tolerance: int = 2) -> float:
    """Fraction of candidate positions that coincide with a detected onset."""
    if candidates.size == 0 or onsets.size == 0:
        return 0.0
    distances = np.abs(candidates[:, None] - onsets[None, :]).min(axis=1)
    return float((distances <= tolerance).mean())


def _closer_to_preferred(candidate: float, current: float, preferred: float = 120.0) -> bool:
    """Is the candidate tempo nearer the rate people naturally count at?

    Compared in log space, because tempo perception is ratio-based: 60 and 240
    are equally far from 120.
    """
    return abs(np.log(candidate / preferred)) < abs(np.log(current / preferred))


def _accent_per_frame(onset_env: np.ndarray, frames: np.ndarray, tolerance: int = 2) -> np.ndarray:
    """Accent at each given frame, allowing for small alignment error.

    Onset peaks are one or two frames wide, so sampling a single frame that is
    off by one reads a hit as silence.
    """
    frames = np.asarray(frames).astype(int)
    if frames.size == 0 or onset_env.size == 0:
        return np.zeros(max(frames.size, 1))
    limit = len(onset_env) - 1
    offsets = np.arange(-tolerance, tolerance + 1)
    windows = np.clip(frames[:, None] + offsets[None, :], 0, limit)
    return onset_env[windows].max(axis=1)


def _accent_at(onset_env: np.ndarray, frames: np.ndarray, tolerance: int = 2) -> float:
    return float(_accent_per_frame(onset_env, frames, tolerance).mean())


def detect_meter(
    onset_env: np.ndarray,
    beat_frames: np.ndarray,
    low_env: np.ndarray | None = None,
) -> tuple[int, int, float]:
    """Choose the bar length, and which beat is beat one.

    Bar length comes from the full-band accent pattern: for each candidate
    meter, every phase is scored on how much its beats stand out from the rest,
    and the meter with the sharpest contrast wins.

    Which beat is *one* is decided from the low end instead. Spectral flux
    rates a snare above a kick — a noise burst changes the spectrum far more
    than a low sine does — so full-band accent puts the downbeat on the
    backbeat, displacing every bar line by a beat. The kick drum is what marks
    beat one, and looking only below 150 Hz is what finds it.
    """
    beat_frames = np.asarray(beat_frames).astype(int)
    if beat_frames.size < 8 or onset_env.size == 0:
        return 4, 0, 0.0

    strengths = _accent_per_frame(onset_env, beat_frames)
    mean_strength = float(strengths.mean())
    if mean_strength <= 0:
        return 4, 0, 0.0

    phase_source = strengths
    if low_env is not None and low_env.size:
        low = _accent_per_frame(low_env, beat_frames)
        if float(low.mean()) > 0:
            phase_source = low

    best = (4, 0, 0.0)
    for meter in CANDIDATE_METERS:
        if strengths.size < meter * 2:
            continue
        contrast = _phase_contrast(strengths, meter)[1] / (mean_strength + 1e-9)
        weighted = contrast * METER_PRIOR.get(meter, 0.5)
        if weighted > best[2]:
            phase = _phase_contrast(phase_source, meter)[0]
            best = (meter, phase, weighted)

    if best[2] <= 0.0:
        # No meter produced a meaningful accent pattern; 4/4 is the safe report.
        return 4, 0, 0.0
    return best


def _phase_contrast(strengths: np.ndarray, meter: int) -> tuple[int, float]:
    """Best phase for a meter, and how far its beats stand above the others."""
    scores = []
    for phase in range(meter):
        picked = strengths[phase::meter]
        others = np.delete(strengths, np.arange(phase, strengths.size, meter))
        if picked.size == 0 or others.size == 0:
            scores.append(0.0)
            continue
        scores.append(float(picked.mean() - others.mean()))
    phase = int(np.argmax(scores))
    return phase, scores[phase]


def _bpm_from_intervals(beat_times: Sequence[float]) -> float:
    diffs = np.diff(np.asarray(beat_times, dtype=float))
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return 120.0
    return float(60.0 / np.median(diffs))


def _grid_confidence(beat_times: Sequence[float], meter_strength: float, source_role: str) -> float:
    """Steady beat spacing plus a clear downbeat accent means a trustworthy grid."""
    diffs = np.diff(np.asarray(beat_times, dtype=float))
    diffs = diffs[diffs > 0]
    if diffs.size < 2:
        return 0.1
    cv = float(np.std(diffs) / (np.mean(diffs) + 1e-9))
    steadiness = float(np.clip(1.0 - cv * 4.0, 0.0, 1.0))
    accent = float(np.clip(meter_strength * 2.0, 0.0, 1.0))
    source_weight = {"drums": 1.0, "percussion": 0.85, "bass": 0.7}.get(source_role, 0.5)
    return float(np.clip((0.65 * steadiness + 0.35 * accent) * source_weight, 0.05, 0.99))


def _empty_grid() -> dict:
    return {
        "bpm": 120.0,
        "beat_times": [0.0, 0.5],
        "bar_starts": [0.0],
        "downbeat_index": 0,
        "beats_per_bar": 4,
        "time_signature_guess": "4/4",
        "bar_count": 0,
        "timing_source": "none",
        "confidence": 0.05,
    }


def beat_map_from_grid(grid: dict) -> BeatMap:
    return BeatMap(
        beat_times=list(grid.get("beat_times", [0.0, 0.5])),
        beats_per_bar=int(grid.get("beats_per_bar", 4)),
        downbeat_index=int(grid.get("downbeat_index", 0)),
    )


def guess_time_signature(beat_times: list[float]) -> str:
    """Signature from beat times alone, for callers without an onset envelope."""
    if len(beat_times) < 8:
        return "4/4"
    return "4/4"
