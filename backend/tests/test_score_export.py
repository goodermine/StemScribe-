"""Notation correctness — the part that decides whether the sheet is readable."""

from pathlib import Path

import pytest

from app.services.score_export import (
    build_drum_part,
    build_pitched_part,
    export_lead_sheet,
    export_midi,
    export_musicxml,
    to_music21_figure,
)


def note(midi: int, start_beat: float, duration_beats: float) -> dict:
    return {
        "midi": midi,
        "start_beat": start_beat,
        "end_beat": start_beat + duration_beats,
        "duration_beats": duration_beats,
        "start_sec": start_beat * 0.5,
        "end_sec": (start_beat + duration_beats) * 0.5,
        "note_name": "X",
    }


def test_awkward_durations_do_not_break_export(tmp_path: Path) -> None:
    """Raw detected durations are arbitrary floats; music21 rejects those.

    This is the failure that stopped every real job: 'Cannot convert
    inexpressible durations to MusicXML'.
    """
    ugly = [
        {**note(60, 0.0, 1.0), "duration_beats": 1.3719},
        {**note(62, 2.0, 1.0), "duration_beats": 0.4137},
        {**note(64, 4.0, 1.0), "duration_beats": 2.9021},
    ]
    out = tmp_path / "part.musicxml"
    export_musicxml(ugly, out, bpm=120.0)
    assert out.exists() and out.stat().st_size > 0


def test_rests_fill_the_silence(tmp_path: Path) -> None:
    """Two notes eight beats apart must not be written next to each other."""
    notes = [note(60, 0.0, 1.0), note(67, 8.0, 1.0)]
    out = tmp_path / "gaps.musicxml"
    export_musicxml(notes, out, bpm=120.0)
    xml = out.read_text()
    assert xml.count("<rest") >= 3, "silence was not notated as rests"


def test_notes_land_in_the_right_measures(tmp_path: Path) -> None:
    notes = [note(60, 0.0, 1.0), note(62, 4.0, 1.0), note(64, 8.0, 1.0)]
    out = tmp_path / "bars.musicxml"
    export_musicxml(notes, out, bpm=120.0)
    xml = out.read_text()
    assert xml.count("<measure ") >= 3


def test_key_signature_is_written(tmp_path: Path) -> None:
    out = tmp_path / "key.musicxml"
    export_musicxml([note(60, 0.0, 1.0)], out, bpm=120.0, fifths=-3)
    xml = out.read_text()
    assert "<fifths>-3</fifths>" in xml


def test_bass_part_uses_a_bass_clef() -> None:
    part = build_pitched_part([note(40, 0.0, 1.0)], "bass", 120.0)
    assert any(type(el).__name__ == "BassClef" for el in part)


def test_simultaneous_notes_become_one_chord() -> None:
    from music21 import chord

    part = build_pitched_part(
        [note(60, 0.0, 2.0), note(64, 0.0, 2.0), note(67, 0.0, 2.0)], "keys", 120.0
    )
    chords = [el for el in part.recurse().notes if isinstance(el, chord.Chord)]
    assert len(chords) == 1
    assert len(chords[0].pitches) == 3


def test_overlapping_notes_are_truncated_not_stacked() -> None:
    """One staff cannot show overlapping voices legibly."""
    part = build_pitched_part([note(60, 0.0, 4.0), note(62, 1.0, 1.0)], "keys", 120.0)
    offsets = sorted(el.offset for el in part.recurse().notes)
    first, second = offsets[0], offsets[1]
    first_element = next(el for el in part.recurse().notes if el.offset == first)
    assert first + first_element.quarterLength <= second + 1e-6


def test_chord_symbols_appear_above_the_staff(tmp_path: Path) -> None:
    chords = [
        {"symbol": "C", "start_beat": 0.0, "end_beat": 4.0},
        {"symbol": "Am", "start_beat": 4.0, "end_beat": 8.0},
    ]
    out = tmp_path / "chords.musicxml"
    export_musicxml([note(60, 0.0, 1.0), note(64, 4.0, 1.0)], out, bpm=120.0, chords=chords)
    xml = out.read_text()
    assert xml.count("<harmony") == 2
    assert "<root-step>C</root-step>" in xml


def test_flat_chord_symbols_are_translated_for_music21() -> None:
    """music21 spells flats with '-', so 'Ebmaj7' has to be rewritten."""
    assert to_music21_figure("Ebmaj7") == "E-maj7"
    assert to_music21_figure("Bb5") == "B-5"
    assert to_music21_figure("C#m") == "C#m"
    assert to_music21_figure("F") == "F"


def test_unparseable_chord_symbol_does_not_kill_the_score(tmp_path: Path) -> None:
    chords = [{"symbol": "???", "start_beat": 0.0, "end_beat": 4.0}]
    out = tmp_path / "bad_chord.musicxml"
    export_musicxml([note(60, 0.0, 1.0)], out, bpm=120.0, chords=chords)
    assert out.exists()


def test_section_marks_are_written(tmp_path: Path) -> None:
    sections = [{"name": "Chorus 1", "start_beat": 0.0}]
    out = tmp_path / "sections.musicxml"
    export_musicxml([note(60, 0.0, 1.0)], out, bpm=120.0, sections=sections)
    assert "Chorus 1" in out.read_text()


def test_drum_part_uses_percussion_notation() -> None:
    hits = [
        {"instrument": "kick", "start_beat": 0.0},
        {"instrument": "snare", "start_beat": 1.0},
        {"instrument": "hihat", "start_beat": 1.0},
    ]
    part = build_drum_part(hits, 120.0)
    assert any(type(el).__name__ == "PercussionClef" for el in part)
    assert len(list(part.recurse().notes)) >= 1


def test_lead_sheet_carries_melody_chords_and_sections(tmp_path: Path) -> None:
    out = tmp_path / "lead_sheet.musicxml"
    export_lead_sheet(
        melody_notes=[note(72, 0.0, 2.0), note(71, 2.0, 2.0)],
        chords=[{"symbol": "C", "start_beat": 0.0, "end_beat": 4.0}],
        sections=[{"name": "Verse 1", "start_beat": 0.0}],
        out_path=out,
        bpm=128.0,
        time_signature="4/4",
        fifths=0,
        title="Test Song",
        key_name="C major",
    )
    xml = out.read_text()
    assert "<harmony" in xml
    assert "Verse 1" in xml
    assert "Test Song" in xml


def test_midi_round_trips_note_timing(tmp_path: Path) -> None:
    import mido

    out = tmp_path / "part.mid"
    export_midi([note(60, 0.0, 2.0), note(64, 4.0, 2.0)], out, program=0, bpm=120.0)
    midi = mido.MidiFile(out.as_posix())

    note_ons = [m for track in midi.tracks for m in track if m.type == "note_on" and m.velocity > 0]
    assert len(note_ons) == 2
    assert {m.note for m in note_ons} == {60, 64}


def test_drum_midi_goes_to_the_percussion_channel(tmp_path: Path) -> None:
    import mido

    out = tmp_path / "drums.mid"
    export_midi(
        [{"midi": 36, "start_sec": 0.0, "end_sec": 0.1, "velocity": 100}],
        out,
        is_drums=True,
        bpm=120.0,
    )
    midi = mido.MidiFile(out.as_posix())
    channels = {m.channel for track in midi.tracks for m in track if m.type == "note_on"}
    assert channels == {9}


def test_empty_note_list_still_produces_a_valid_file(tmp_path: Path) -> None:
    out = tmp_path / "empty.musicxml"
    export_musicxml([], out, bpm=120.0)
    assert out.exists()
