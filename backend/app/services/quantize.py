"""Snap detected notes onto the musical grid.

Quantization happens in beat space, not seconds. A note lasting 0.31s means
nothing on a page; the same note lasting half a beat is an eighth note, and
stays an eighth note when the tempo drifts.
"""

from typing import List, Sequence

from app.config import settings
from app.utils.notes import midi_to_note_name
from app.utils.timing import BeatMap, quantize_to_grid


def _coerce_beat_map(beat_reference: BeatMap | Sequence[float] | None) -> BeatMap | None:
    if beat_reference is None:
        return None
    if isinstance(beat_reference, BeatMap):
        return beat_reference
    times = list(beat_reference)
    return BeatMap(beat_times=times) if times else None


def quantize_notes(
    notes: List[dict],
    beat_reference: BeatMap | Sequence[float] | None,
    division: int | None = None,
    min_note_beats: float | None = None,
) -> List[dict]:
    """Place notes on the grid, drop jitter, and join repeats of one pitch."""
    beat_map = _coerce_beat_map(beat_reference)
    if beat_map is None:
        return notes

    division = division or settings.quantization_division
    min_beats = settings.min_note_beats if min_note_beats is None else min_note_beats
    grid_step = 1.0 / max(division, 1)

    snapped: List[dict] = []
    for note in notes:
        start_b = quantize_to_grid(beat_map.seconds_to_beats(note["start_sec"]), division)
        end_b = quantize_to_grid(beat_map.seconds_to_beats(note["end_sec"]), division)
        if end_b <= start_b:
            # A note that rounds to zero length still happened; give it the
            # shortest value the grid can express rather than discarding it.
            end_b = start_b + grid_step
        if end_b - start_b < min_beats:
            continue
        out = dict(note)
        out["start_beat"] = round(start_b, 6)
        out["end_beat"] = round(end_b, 6)
        out["duration_beats"] = round(end_b - start_b, 6)
        snapped.append(out)

    snapped.sort(key=lambda n: (n["start_beat"], n["midi"]))
    merged = _merge_repeats(snapped, grid_step)

    for note in merged:
        note["start_sec"] = round(beat_map.beats_to_seconds(note["start_beat"]), 6)
        note["end_sec"] = round(beat_map.beats_to_seconds(note["end_beat"]), 6)
        note["duration_sec"] = round(note["end_sec"] - note["start_sec"], 6)
        note["bar_index"] = beat_map.bar_of_beat(note["start_beat"])
        note["beat_in_bar"] = round(beat_map.beat_in_bar(note["start_beat"]), 4)
        note.setdefault("note_name", midi_to_note_name(int(note["midi"])))
    return merged


def _merge_repeats(notes: List[dict], grid_step: float) -> List[dict]:
    """Join consecutive same-pitch notes separated by less than one grid slot.

    Pitch trackers drop out briefly mid-note on vibrato and breaths; without
    this a single held note is written as a stutter of repeated notes.
    """
    merged: List[dict] = []
    for note in notes:
        prev = next(
            (m for m in reversed(merged) if m["midi"] == note["midi"]),
            None,
        )
        if (
            prev is not None
            and note["start_beat"] - prev["end_beat"] <= grid_step * 0.5
            and note["start_beat"] >= prev["start_beat"]
        ):
            prev["end_beat"] = max(prev["end_beat"], note["end_beat"])
            prev["duration_beats"] = round(prev["end_beat"] - prev["start_beat"], 6)
            prev["confidence"] = max(
                prev.get("confidence", 0.0), note.get("confidence", 0.0)
            )
            continue
        merged.append(note)
    return merged
