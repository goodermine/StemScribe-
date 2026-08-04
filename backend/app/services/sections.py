"""Song structure: where the sections are, and what to call them.

Boundaries come from agglomerative clustering over beat-synchronous timbre and
harmony features — the song changes section where those features change
together — then get snapped to bar lines, because sections start on downbeats
and a section three and a half bars long is a detection artefact, not a part of
the song.

Sections that resemble each other are grouped, since a chorus is defined by
recurring, and named from what the band is doing: no vocal means intro or
instrumental, the loudest recurring vocal group is the chorus, the rest are
verses.
"""

from pathlib import Path
from typing import Sequence

import librosa
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist

from app.config import settings
from app.utils.audio import is_silent, load_mono
from app.utils.timing import BeatMap

# Aim for sections roughly this many bars long when choosing how many to cut.
TARGET_BARS_PER_SECTION = 8
MIN_SECTIONS = 3
MAX_SECTIONS = 14

# Shorter than this and it is a fill or a turnaround, not a section.
MIN_SECTION_BARS = 4

# The leading dimensions of the feature stack that hold chroma.
CHROMA_DIMS = 12

# A section is treated as sung if its vocal stems reach this share of the
# song's loudest vocal moment.
VOCAL_PRESENCE = 0.12


def analyse_sections(
    stems_by_role: dict[str, list[Path]],
    beat_map: BeatMap,
) -> list[dict]:
    features, _ = _beat_features(stems_by_role, beat_map.beat_times)
    if features is None or features.shape[1] < MIN_SECTIONS * 2:
        return []

    n_sections = int(
        np.clip(
            round(beat_map.bar_count() / TARGET_BARS_PER_SECTION),
            MIN_SECTIONS,
            min(MAX_SECTIONS, features.shape[1] // 2),
        )
    )
    # Ask for roughly twice the boundaries wanted. The segmenter tends to spend
    # part of its budget placing a second boundary a beat or two from a strong
    # one; those pairs collapse into a single bar line when snapped, so
    # oversampling is what lands the final count near the target.
    oversampled = int(min(n_sections * 2, max(features.shape[1] // 4, MIN_SECTIONS)))
    raw_bounds = librosa.segment.agglomerative(features, oversampled)
    bounds = _snap_to_bars(raw_bounds, features.shape[1], beat_map)
    if len(bounds) < 2:
        return []

    vocal_energy = _beat_energy(stems_by_role, ("vocals", "backing_vocals"), beat_map)
    total_energy = _beat_energy(stems_by_role, None, beat_map)

    spans = []
    for start, end in zip(bounds, bounds[1:]):
        spans.append(
            {
                "start_beat": float(start),
                "end_beat": float(end),
                "profile": features[:, start:end].mean(axis=1),
                "vocal": _mean_slice(vocal_energy, start, end),
                "energy": _mean_slice(total_energy, start, end),
            }
        )
    if not spans:
        return []

    groups = _group_similar(spans)
    names = _name_sections(spans, groups)

    out = []
    for span, name, group in zip(spans, names, groups):
        start_bar = beat_map.bar_of_beat(span["start_beat"])
        bar_count = max(int(round((span["end_beat"] - span["start_beat"]) / beat_map.beats_per_bar)), 1)
        out.append(
            {
                "name": name,
                "group": f"section_{group}",
                "start_bar": start_bar,
                # Inclusive, so the last bar of one section is the bar before
                # the next one starts rather than the same bar twice.
                "end_bar": start_bar + bar_count - 1,
                "bar_count": bar_count,
                "start_beat": round(span["start_beat"], 3),
                "end_beat": round(span["end_beat"], 3),
                "start_sec": round(beat_map.beats_to_seconds(span["start_beat"]), 3),
                "end_sec": round(beat_map.beats_to_seconds(span["end_beat"]), 3),
                "has_vocal": bool(span["vocal"] > VOCAL_PRESENCE),
                "relative_energy": round(float(span["energy"]), 4),
            }
        )
    return out


def _snap_to_bars(boundaries: Sequence[int], n_beats: int, beat_map: BeatMap) -> list[int]:
    """Move each boundary to the nearest bar line and drop the short ones.

    Section changes happen on downbeats. Left unsnapped, the detector produces
    sections a bar and a half long that no player would recognise, and bar
    ranges that overlap each other by one.
    """
    per_bar = max(beat_map.beats_per_bar, 1)
    origin = beat_map.downbeat_index % per_bar
    minimum = MIN_SECTION_BARS * per_bar

    snapped = set()
    for boundary in [0, *boundaries, n_beats]:
        bars = round((int(boundary) - origin) / per_bar)
        snapped.add(int(np.clip(origin + bars * per_bar, 0, n_beats)))

    ordered = sorted(snapped)
    kept = [ordered[0]]
    for boundary in ordered[1:-1]:
        if boundary - kept[-1] >= minimum and ordered[-1] - boundary >= minimum:
            kept.append(boundary)
    if ordered[-1] > kept[-1]:
        kept.append(ordered[-1])
    return kept


def _group_similar(sections: list[dict]) -> list[int]:
    """Assign a group id per section so recurring parts share one id.

    Clustering all the profiles at once, rather than comparing each section to
    the first one that looked like it, is what lets a chorus be recognised on
    its third appearance when the arrangement has thickened.
    """
    if len(sections) < 2:
        return [0] * len(sections)

    # Harmony, not timbre. A chorus returns with the same chords but often a
    # thicker arrangement, so the MFCC half of the profile argues against the
    # very repeat being looked for.
    profiles = np.stack([s["profile"][:CHROMA_DIMS] for s in sections])
    spread = profiles.std(axis=1)
    if np.any(spread == 0):
        return list(range(len(sections)))

    distances = pdist(profiles, metric="correlation")
    if not np.all(np.isfinite(distances)):
        return list(range(len(sections)))

    # Cut into a fixed number of groups rather than at a fixed distance.
    # Absolute distances between long averaged spans are not comparable across
    # songs, so a threshold that groups one song's choruses leaves another's
    # ungrouped entirely.
    n_groups = int(np.clip(round(len(sections) / 2), 2, max(len(sections) - 1, 2)))
    labels = fcluster(linkage(distances, method="average"), n_groups, criterion="maxclust")
    return [int(label) - 1 for label in labels]


def _name_sections(sections: list[dict], groups: list[int]) -> list[str]:
    last = len(sections) - 1

    counts: dict[int, int] = {}
    energy: dict[int, list[float]] = {}
    for section, group in zip(sections, groups):
        counts[group] = counts.get(group, 0) + 1
        energy.setdefault(group, []).append(float(section["energy"]))

    sung = {g for s, g in zip(sections, groups) if s["vocal"] > VOCAL_PRESENCE}
    # The sung group with the most energy behind it is the chorus; where two
    # are close, the one that comes round more often wins.
    chorus = max(sung, key=lambda g: (np.mean(energy[g]), counts[g])) if sung else None

    bases = [
        _base_name(section, group, index, last, chorus, counts)
        for index, (section, group) in enumerate(zip(sections, groups))
    ]

    totals: dict[str, int] = {}
    for base in bases:
        totals[base] = totals.get(base, 0) + 1

    seen: dict[str, int] = {}
    names = []
    for base in bases:
        seen[base] = seen.get(base, 0) + 1
        # Only number the parts that come round more than once.
        names.append(f"{base} {seen[base]}" if totals[base] > 1 else base)
    return names


def _base_name(
    section: dict,
    group: int,
    index: int,
    last: int,
    chorus: int | None,
    counts: dict[int, int],
) -> str:
    if section["vocal"] <= VOCAL_PRESENCE:
        if index == 0:
            return "Intro"
        if index == last:
            return "Outro"
        return "Instrumental"
    if group == chorus:
        return "Chorus"
    if counts[group] == 1 and index > last // 2:
        return "Bridge"
    return "Verse"
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
