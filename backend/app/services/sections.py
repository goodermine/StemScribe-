"""Song structure: where the sections are, and what to call them.

Boundaries come from agglomerative clustering over beat-synchronous timbre and
harmony features — the song changes section where those features change
together. Sections that resemble each other are then grouped, because a chorus
is defined by recurring, and named from what the band is doing in them: no
vocal means intro or instrumental, the loudest recurring vocal group is the
chorus, the rest are verses.
"""

from pathlib import Path
from typing import Sequence

import librosa
import numpy as np

from app.config import settings
from app.utils.audio import is_silent, load_mono
from app.utils.timing import BeatMap

# Aim for sections roughly this many bars long when choosing how many to cut.
TARGET_BARS_PER_SECTION = 8
MIN_SECTIONS = 3
MAX_SECTIONS = 14

# Two sections whose features correlate above this are treated as the same part
# of the song returning.
SIMILARITY_THRESHOLD = 0.82


def analyse_sections(
    stems_by_role: dict[str, list[Path]],
    beat_map: BeatMap,
) -> list[dict]:
    features, sr = _beat_features(stems_by_role, beat_map.beat_times)
    if features is None or features.shape[1] < MIN_SECTIONS * 2:
        return []

    n_sections = int(
        np.clip(
            round(beat_map.bar_count() / TARGET_BARS_PER_SECTION),
            MIN_SECTIONS,
            min(MAX_SECTIONS, features.shape[1] // 2),
        )
    )
    boundaries = librosa.segment.agglomerative(features, n_sections)
    boundaries = sorted(set([0, *[int(b) for b in boundaries], features.shape[1]]))

    vocal_energy = _beat_energy(stems_by_role, ("vocals", "backing_vocals"), beat_map)
    total_energy = _beat_energy(stems_by_role, None, beat_map)

    raw = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end - start < 2:
            continue
        raw.append(
            {
                "start_beat": float(start),
                "end_beat": float(end),
                "profile": features[:, start:end].mean(axis=1),
                "vocal": _mean_slice(vocal_energy, start, end),
                "energy": _mean_slice(total_energy, start, end),
            }
        )

    if not raw:
        return []

    groups = _group_similar(raw)
    named = _name_sections(raw, groups)

    out = []
    for section, name, group in zip(raw, named, groups):
        start_bar = beat_map.bar_of_beat(section["start_beat"])
        end_bar = beat_map.bar_of_beat(max(section["end_beat"] - 1, section["start_beat"]))
        out.append(
            {
                "name": name,
                "group": f"section_{group}",
                "start_bar": start_bar,
                "end_bar": end_bar,
                "bar_count": max(end_bar - start_bar + 1, 1),
                "start_beat": round(section["start_beat"], 3),
                "end_beat": round(section["end_beat"], 3),
                "start_sec": round(beat_map.beats_to_seconds(section["start_beat"]), 3),
                "end_sec": round(beat_map.beats_to_seconds(section["end_beat"]), 3),
                "has_vocal": bool(section["vocal"] > 0.12),
                "relative_energy": round(float(section["energy"]), 4),
            }
        )
    return out


def _beat_features(
    stems_by_role: dict[str, list[Path]], beat_times: Sequence[float]
) -> tuple[np.ndarray | None, int | None]:
    """Beat-synchronous chroma stacked with MFCCs, summed over every stem.

    Chroma catches a change of chord progression; MFCCs catch a change of
    instrumentation. A section boundary usually shows up in one or the other.
    """
    mix: np.ndarray | None = None
    sr_used = None
    for paths in stems_by_role.values():
        for path in paths:
            y, sr = load_mono(path)
            if is_silent(y):
                continue
            sr_used = sr
            mix = np.asarray(y, dtype=float) if mix is None else _sum_to_length(mix, y)

    if mix is None or sr_used is None:
        return None, None

    peak = float(np.max(np.abs(mix))) or 1.0
    mix = np.ascontiguousarray(mix / peak)
    hop = settings.hop_length

    chroma = librosa.feature.chroma_cqt(y=mix, sr=sr_used, hop_length=hop)
    mfcc = librosa.feature.mfcc(y=mix, sr=sr_used, hop_length=hop, n_mfcc=13)

    beat_frames = librosa.time_to_frames(
        np.asarray(beat_times, dtype=float), sr=sr_used, hop_length=hop
    )
    width = min(chroma.shape[1], mfcc.shape[1])
    beat_frames = np.clip(beat_frames, 0, width - 1)
    if beat_frames.size < 2:
        return None, None

    chroma_sync = librosa.util.sync(chroma[:, :width], beat_frames, aggregate=np.median)
    mfcc_sync = librosa.util.sync(mfcc[:, :width], beat_frames, aggregate=np.mean)
    stacked = np.vstack([_normalise(chroma_sync), _normalise(mfcc_sync)])
    return stacked, sr_used


def _beat_energy(
    stems_by_role: dict[str, list[Path]],
    roles: tuple[str, ...] | None,
    beat_map: BeatMap,
) -> np.ndarray:
    """Loudness per beat for a subset of roles, scaled to its own maximum."""
    total: np.ndarray | None = None
    sr_used = None
    for role, paths in stems_by_role.items():
        if roles is not None and role not in roles:
            continue
        for path in paths:
            y, sr = load_mono(path)
            if is_silent(y):
                continue
            sr_used = sr
            rms = librosa.feature.rms(
                y=np.ascontiguousarray(y), hop_length=settings.hop_length
            )[0]
            total = rms if total is None else _sum_to_length(total, rms)

    if total is None or sr_used is None:
        return np.zeros(1)

    beat_frames = librosa.time_to_frames(
        np.asarray(beat_map.beat_times, dtype=float), sr=sr_used, hop_length=settings.hop_length
    )
    beat_frames = np.clip(beat_frames, 0, len(total) - 1)
    if beat_frames.size < 2:
        return np.zeros(1)
    synced = librosa.util.sync(total[np.newaxis, :], beat_frames, aggregate=np.mean)[0]
    peak = float(synced.max()) or 1.0
    return synced / peak


def _group_similar(sections: list[dict]) -> list[int]:
    """Assign a group id per section, so recurring parts share one id."""
    groups: list[int] = []
    representatives: list[np.ndarray] = []
    for section in sections:
        profile = section["profile"]
        match = None
        for index, rep in enumerate(representatives):
            if _cosine(profile, rep) >= SIMILARITY_THRESHOLD:
                match = index
                break
        if match is None:
            representatives.append(profile)
            groups.append(len(representatives) - 1)
        else:
            # Average the representative so a group drifts toward its members
            # rather than being pinned to whichever one appeared first.
            representatives[match] = (representatives[match] + profile) / 2.0
            groups.append(match)
    return groups


def _name_sections(sections: list[dict], groups: list[int]) -> list[str]:
    last = len(sections) - 1
    vocal_groups = {g for s, g in zip(sections, groups) if s["vocal"] > 0.12}

    # The recurring vocal group with the most energy behind it is the chorus.
    group_energy: dict[int, list[float]] = {}
    group_counts: dict[int, int] = {}
    for section, group in zip(sections, groups):
        group_energy.setdefault(group, []).append(float(section["energy"]))
        group_counts[group] = group_counts.get(group, 0) + 1

    chorus_group = None
    if vocal_groups:
        chorus_group = max(
            vocal_groups,
            key=lambda g: (np.mean(group_energy[g]), group_counts[g]),
        )

    names: list[str] = []
    counters: dict[str, int] = {}
    for index, (section, group) in enumerate(zip(sections, groups)):
        if section["vocal"] <= 0.12:
            if index == 0:
                base = "Intro"
            elif index == last:
                base = "Outro"
            else:
                base = "Instrumental"
        elif group == chorus_group:
            base = "Chorus"
        elif group_counts[group] == 1 and index > last // 2:
            base = "Bridge"
        else:
            base = "Verse"

        counters[base] = counters.get(base, 0) + 1
        # Only number the parts that come round more than once.
        repeats = sum(
            1
            for s, g in zip(sections, groups)
            if _base_name(s, g, chorus_group, sections, groups) == base
        )
        names.append(f"{base} {counters[base]}" if repeats > 1 else base)
    return names


def _base_name(section, group, chorus_group, sections, groups) -> str:
    index = sections.index(section)
    last = len(sections) - 1
    if section["vocal"] <= 0.12:
        if index == 0:
            return "Intro"
        if index == last:
            return "Outro"
        return "Instrumental"
    if group == chorus_group:
        return "Chorus"
    counts = sum(1 for g in groups if g == group)
    if counts == 1 and index > last // 2:
        return "Bridge"
    return "Verse"


def _sum_to_length(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    width = min(a.shape[-1], b.shape[-1])
    return a[..., :width] + np.asarray(b, dtype=float)[..., :width]


def _mean_slice(values: np.ndarray, start: int, end: int) -> float:
    if values.size == 0:
        return 0.0
    lo = min(start, values.size - 1)
    hi = min(max(end, lo + 1), values.size)
    return float(values[lo:hi].mean())


def _normalise(matrix: np.ndarray) -> np.ndarray:
    centred = matrix - matrix.mean(axis=1, keepdims=True)
    scale = np.std(centred, axis=1, keepdims=True)
    return centred / np.where(scale > 0, scale, 1.0)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0
