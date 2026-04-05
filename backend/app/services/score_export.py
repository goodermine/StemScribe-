from pathlib import Path
from typing import List

import pretty_midi
from music21 import clef, meter, note, stream, tempo


def export_midi(notes: List[dict], out_path: Path, program: int = 0) -> None:
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program)
    for n in notes:
        inst.notes.append(
            pretty_midi.Note(
                velocity=90,
                pitch=int(n["midi"]),
                start=float(n["start_sec"]),
                end=float(n["end_sec"]),
            )
        )
    pm.instruments.append(inst)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(out_path.as_posix())


def export_musicxml(
    notes: List[dict],
    out_path: Path,
    bpm: float = 120.0,
    time_signature: str = "4/4",
    use_bass_clef: bool = False,
) -> None:
    score = stream.Score()
    part = stream.Part()
    part.append(tempo.MetronomeMark(number=bpm))
    part.append(meter.TimeSignature(time_signature))
    part.append(clef.BassClef() if use_bass_clef else clef.TrebleClef())
    for n in notes:
        dur_quarter = max(n["duration_sec"] * bpm / 60.0, 0.25)
        m21note = note.Note(int(n["midi"]))
        m21note.quarterLength = dur_quarter
        part.append(m21note)
    score.append(part)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=out_path.as_posix())
