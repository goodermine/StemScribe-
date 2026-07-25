import pytest

from app.services.quantize import quantize_notes
from app.utils.timing import BeatMap


def beat_map() -> BeatMap:
    return BeatMap(beat_times=[i * 0.5 for i in range(17)], beats_per_bar=4)


def note(midi: int, start: float, end: float) -> dict:
    return {"midi": midi, "start_sec": start, "end_sec": end, "duration_sec": end - start}


def test_quantize_snaps_onto_the_grid() -> None:
    out = quantize_notes([note(60, 0.11, 0.39)], beat_map(), division=2)
    assert out[0]["start_beat"] == pytest.approx(0.0)
    assert out[0]["start_sec"] == pytest.approx(0.0)
    assert out[0]["duration_beats"] > 0


def test_positions_are_reported_in_bars_and_beats() -> None:
    out = quantize_notes([note(60, 2.0, 2.5)], beat_map(), division=4)
    assert out[0]["bar_index"] == 1
    assert out[0]["beat_in_bar"] == pytest.approx(1.0)


def test_jitter_shorter_than_the_minimum_is_dropped() -> None:
    """A 20ms blip is tracking noise, not a note anyone played."""
    out = quantize_notes([note(60, 1.0, 1.02)], beat_map(), division=4, min_note_beats=0.5)
    assert out == []


def test_repeated_same_pitch_notes_are_joined() -> None:
    """Pitch trackers drop out mid-note; one held note must not become three."""
    notes = [note(60, 0.0, 0.48), note(60, 0.5, 0.98), note(60, 1.0, 1.48)]
    out = quantize_notes(notes, beat_map(), division=4)
    assert len(out) == 1
    assert out[0]["duration_beats"] == pytest.approx(3.0)


def test_different_pitches_are_not_joined() -> None:
    notes = [note(60, 0.0, 0.48), note(62, 0.5, 0.98)]
    out = quantize_notes(notes, beat_map(), division=4)
    assert len(out) == 2
    assert {n["midi"] for n in out} == {60, 62}


def test_simultaneous_notes_are_all_kept() -> None:
    """A chord is several notes at one instant, not a merge conflict."""
    notes = [note(60, 0.0, 1.0), note(64, 0.0, 1.0), note(67, 0.0, 1.0)]
    out = quantize_notes(notes, beat_map(), division=4)
    assert len(out) == 3
    assert all(n["start_beat"] == pytest.approx(0.0) for n in out)


def test_no_beat_reference_returns_input_unchanged() -> None:
    notes = [note(60, 0.0, 1.0)]
    assert quantize_notes(notes, None) == notes


def test_output_carries_both_time_and_beat_positions() -> None:
    out = quantize_notes([note(60, 1.0, 2.0)], beat_map(), division=4)[0]
    for field in ("start_sec", "end_sec", "start_beat", "end_beat", "duration_beats", "note_name"):
        assert field in out
