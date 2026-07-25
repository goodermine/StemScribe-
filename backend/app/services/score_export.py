"""Turn note events into notation.

The important work here is placement. Events carry a beat position, so they go
into the stream at that offset and music21 fills the gaps with real rests and
splits the result into real measures. Writing notes back to back in the order
they were detected — ignoring when they happened — produces a file that opens
fine and matches nothing.
"""

from pathlib import Path
from typing import Iterable, List, Sequence

from music21 import (
    chord,
    clef,
    expressions,
    harmony,
    instrument,
    key,
    layout,
    meter,
    note,
    percussion,
    stream,
    tempo,
)

from app.services.classify import profile_for
from app.services.drum_transcribe import DRUM_STAFF
from app.utils.midi_io import MidiTrackSpec, write_midi
from app.utils.timing import BeatMap

# How many quarter notes one detected beat is worth. Beat trackers report the
# felt pulse, which is a quarter in simple metres and an eighth in 6/8.
BEAT_UNIT_QUARTERS = {"4/4": 1.0, "3/4": 1.0, "2/4": 1.0, "6/8": 0.5}

# Written durations are rounded to this fraction of a quarter note. Anything
# finer cannot be engraved, and music21 rejects the file outright.
NOTATION_GRID = 0.25

# Gaps up to this many beats between one note and the next are closed by
# holding the earlier note. Pitch trackers release a note early and drop out
# through breaths and consonants, and every one of those silences would
# otherwise be engraved as a rest — turning a singable line into a thicket of
# thirty-second rests that no one can read.
GAP_FILL_BEATS = 1.0


def beat_unit(time_signature: str) -> float:
    return BEAT_UNIT_QUARTERS.get(time_signature, 1.0)


def to_music21_figure(symbol: str) -> str:
    """music21 spells flats with '-', so 'Ebmaj7' has to become 'E-maj7'."""
    if len(symbol) > 1 and symbol[1] == "b":
        return symbol[0] + "-" + symbol[2:]
    return symbol


def snap_quarters(value: float) -> float:
    snapped = round(value / NOTATION_GRID) * NOTATION_GRID
    return max(snapped, NOTATION_GRID)


def score_offset(beat: float, origin_beat: float, quarters_per_beat: float) -> float:
    """Where a beat position sits in the written score, in quarter notes.

    Bar one of the score is the first downbeat, so positions are measured from
    there. Anything the detectors placed earlier — a pickup, or a note the beat
    tracker started behind — is pulled to the top of bar one: notation has no
    bar zero, and music21 refuses to place a negative offset at all.
    """
    return max((beat - origin_beat) * quarters_per_beat, 0.0)


def _events_from_notes(
    notes: Sequence[dict],
    quarters_per_beat: float,
    origin_beat: float = 0.0,
    gap_fill_beats: float = GAP_FILL_BEATS,
) -> list[dict]:
    """Collapse note events into a single readable voice.

    Notes that begin together become one chord. Where a chord is still
    sounding when the next one starts, the earlier one is cut short: a single
    staff cannot show overlapping voices without becoming unreadable, and a
    player reading a guitar part wants the shapes and when they change.
    """
    grouped: dict[float, dict] = {}
    for n in notes:
        start = round(max(float(n.get("start_beat", 0.0)) - origin_beat, 0.0), 4)
        duration = float(n.get("duration_beats", 0.0))
        entry = grouped.setdefault(start, {"start": start, "duration": duration, "midis": []})
        entry["midis"].append(int(n["midi"]))
        entry["duration"] = max(entry["duration"], duration)

    events = sorted(grouped.values(), key=lambda e: e["start"])
    for current, following in zip(events, events[1:]):
        span_to_next = following["start"] - current["start"]
        overhang = current["duration"] - span_to_next
        if overhang > 0 or -overhang <= gap_fill_beats:
            # Either the note ran into the next one and has to be cut, or it
            # stopped just short and is held until the next one begins.
            current["duration"] = max(span_to_next, 0.0)

    out = []
    for event in events:
        quarters = snap_quarters(event["duration"] * quarters_per_beat)
        if quarters <= 0:
            continue
        out.append(
            {
                "offset": round(event["start"] * quarters_per_beat, 4),
                "quarters": quarters,
                "midis": sorted(set(event["midis"])),
            }
        )
    return out


def build_pitched_part(
    notes: Sequence[dict],
    role: str,
    bpm: float,
    time_signature: str = "4/4",
    fifths: int = 0,
    part_name: str | None = None,
    origin_beat: float = 0.0,
    gap_fill_beats: float = GAP_FILL_BEATS,
) -> stream.Part:
    profile = profile_for(role)
    part = stream.Part()
    part.id = role
    part.partName = part_name or profile.display_name

    part.insert(0, instrument.instrumentFromMidiProgram(profile.midi_program))
    part.insert(0, clef.BassClef() if profile.bass_clef else clef.TrebleClef())
    part.insert(0, key.KeySignature(fifths))
    part.insert(0, meter.TimeSignature(time_signature))
    part.insert(0, tempo.MetronomeMark(number=round(bpm)))

    quarters_per_beat = beat_unit(time_signature)
    for event in _events_from_notes(notes, quarters_per_beat, origin_beat, gap_fill_beats):
        element = (
            chord.Chord(event["midis"])
            if len(event["midis"]) > 1
            else note.Note(event["midis"][0])
        )
        element.quarterLength = event["quarters"]
        part.insert(event["offset"], element)
    return part


def build_drum_part(
    hits: Sequence[dict],
    bpm: float,
    time_signature: str = "4/4",
    default_quarters: float = 0.25,
    origin_beat: float = 0.0,
) -> stream.Part:
    """A drum staff: hits on the standard kit positions, x-noteheads on cymbals."""
    part = stream.Part()
    part.id = "drums"
    part.partName = "Drums"
    part.insert(0, instrument.Percussion())
    part.insert(0, clef.PercussionClef())
    part.insert(0, meter.TimeSignature(time_signature))
    part.insert(0, tempo.MetronomeMark(number=round(bpm)))

    quarters_per_beat = beat_unit(time_signature)
    by_offset: dict[float, list[str]] = {}
    for hit in hits:
        offset = round(
            score_offset(float(hit.get("start_beat", 0.0)), origin_beat, quarters_per_beat), 4
        )
        by_offset.setdefault(offset, []).append(hit["instrument"])

    for offset, pieces in sorted(by_offset.items()):
        unpitched = []
        for piece in sorted(set(pieces)):
            spec = DRUM_STAFF.get(piece, DRUM_STAFF["snare"])
            u = note.Unpitched(displayName=f"{spec['step']}{spec['octave']}")
            u.notehead = spec["notehead"]
            u.stemDirection = spec["stem"]
            unpitched.append(u)
        if not unpitched:
            continue
        element = percussion.PercussionChord(unpitched) if len(unpitched) > 1 else unpitched[0]
        element.quarterLength = default_quarters
        part.insert(offset, element)
    return part


def add_chord_symbols(
    part: stream.Part,
    chords: Sequence[dict],
    time_signature: str = "4/4",
    origin_beat: float = 0.0,
) -> None:
    quarters_per_beat = beat_unit(time_signature)
    for entry in chords:
        try:
            symbol = harmony.ChordSymbol(to_music21_figure(entry["symbol"]))
        except Exception:
            # An unparseable figure should not cost the whole score; the chord
            # still appears in the JSON and in the chart.
            continue
        symbol.writeAsChord = False
        part.insert(
            round(score_offset(float(entry["start_beat"]), origin_beat, quarters_per_beat), 4),
            symbol,
        )


def add_section_marks(
    part: stream.Part,
    sections: Sequence[dict],
    time_signature: str = "4/4",
    origin_beat: float = 0.0,
) -> None:
    quarters_per_beat = beat_unit(time_signature)
    for section in sections:
        text = expressions.TextExpression(section["name"])
        text.style.fontWeight = "bold"
        text.style.absoluteY = 30
        part.insert(
            round(score_offset(float(section["start_beat"]), origin_beat, quarters_per_beat), 4),
            text,
        )


def finalise(score: stream.Score, title: str | None = None, subtitle: str | None = None) -> stream.Score:
    """Bar the score, add rests, and label it."""
    if title:
        score.insert(0, _metadata(title, subtitle))
    score.makeNotation(inPlace=True)
    return score


def _metadata(title: str, subtitle: str | None):
    from music21 import metadata as m21metadata

    md = m21metadata.Metadata()
    md.title = title
    if subtitle:
        md.movementName = subtitle
    return md


def write_score(score: stream.Score, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=out_path.as_posix())


def export_musicxml(
    notes: Sequence[dict],
    out_path: Path,
    bpm: float = 120.0,
    time_signature: str = "4/4",
    use_bass_clef: bool = False,
    fifths: int = 0,
    role: str | None = None,
    chords: Sequence[dict] | None = None,
    sections: Sequence[dict] | None = None,
    title: str | None = None,
    origin_beat: float = 0.0,
) -> None:
    """Write a single part to MusicXML, optionally with chords and sections."""
    resolved_role = role or ("bass" if use_bass_clef else "other")
    part = build_pitched_part(
        notes, resolved_role, bpm, time_signature, fifths, origin_beat=origin_beat
    )
    if chords:
        add_chord_symbols(part, chords, time_signature, origin_beat)
    if sections:
        add_section_marks(part, sections, time_signature, origin_beat)
    score = stream.Score()
    score.insert(0, part)
    write_score(finalise(score, title), out_path)


def export_lead_sheet(
    melody_notes: Sequence[dict],
    chords: Sequence[dict],
    sections: Sequence[dict],
    out_path: Path,
    bpm: float,
    time_signature: str,
    fifths: int,
    title: str,
    key_name: str,
    melody_role: str = "vocals",
    origin_beat: float = 0.0,
) -> None:
    """The singer's page: one melody staff with chord symbols and section marks."""
    part = build_pitched_part(
        melody_notes,
        melody_role,
        bpm,
        time_signature,
        fifths,
        part_name="Melody",
        origin_beat=origin_beat,
    )
    add_chord_symbols(part, chords, time_signature, origin_beat)
    add_section_marks(part, sections, time_signature, origin_beat)
    score = stream.Score()
    score.insert(0, part)
    write_score(finalise(score, title, f"{key_name} · {round(bpm)} BPM · {time_signature}"), out_path)


def export_full_score(
    parts: Iterable[stream.Part],
    out_path: Path,
    title: str,
    subtitle: str | None = None,
) -> None:
    score = stream.Score()
    score.insert(0, layout.StaffGroup(list(parts), symbol="bracket"))
    for part in parts:
        score.insert(0, part)
    write_score(finalise(score, title, subtitle), out_path)


def export_midi(
    notes: Sequence[dict],
    out_path: Path,
    program: int = 0,
    is_drums: bool = False,
    bpm: float = 120.0,
    name: str = "part",
) -> None:
    write_midi([MidiTrackSpec(name=name, notes=notes, program=program, is_drums=is_drums)], out_path, bpm)


def export_song_midi(
    tracks: Sequence[tuple[str, Sequence[dict], int, bool]],
    out_path: Path,
    bpm: float = 120.0,
) -> None:
    """Every part in one multi-track MIDI file, for playing the arrangement back."""
    specs = [
        MidiTrackSpec(name=name, notes=notes, program=program, is_drums=is_drums)
        for name, notes, program, is_drums in tracks
        if notes
    ]
    write_midi(specs, out_path, bpm)


def beat_map_quarters(beat_map: BeatMap, time_signature: str) -> float:
    return beat_unit(time_signature)
