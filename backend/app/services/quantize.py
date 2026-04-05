from typing import List


def quantize_notes(notes: List[dict], beat_times: list[float], division: int = 2) -> List[dict]:
    if not beat_times:
        return notes
    beat_step = _avg_step(beat_times) / division
    out = []
    for note in notes:
        start = round(note["start_sec"] / beat_step) * beat_step
        end = round(note["end_sec"] / beat_step) * beat_step
        if end <= start:
            end = start + beat_step
        duration = end - start
        if duration < beat_step * 0.5:
            continue
        copy = dict(note)
        copy["start_sec"] = round(start, 6)
        copy["end_sec"] = round(end, 6)
        copy["duration_sec"] = round(duration, 6)
        out.append(copy)
    merged: List[dict] = []
    for note in out:
        if merged and merged[-1]["midi"] == note["midi"] and note["start_sec"] - merged[-1]["end_sec"] <= beat_step * 0.25:
            merged[-1]["end_sec"] = note["end_sec"]
            merged[-1]["duration_sec"] = round(merged[-1]["end_sec"] - merged[-1]["start_sec"], 6)
        else:
            merged.append(note)
    return merged


def _avg_step(beat_times: list[float]) -> float:
    if len(beat_times) < 2:
        return 0.5
    diffs = [b - a for a, b in zip(beat_times, beat_times[1:]) if b > a]
    return sum(diffs) / max(len(diffs), 1)
