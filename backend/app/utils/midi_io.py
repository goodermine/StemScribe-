"""Minimal MIDI writing.

Times arrive in seconds. Writing them against a fixed tempo means the ticks
convert back to exactly those seconds on playback, so the MIDI lines up with
the original audio rather than with the quantized notation.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import mido

TICKS_PER_BEAT = 480

# General MIDI puts the drum kit on channel 10 (index 9).
DRUM_CHANNEL = 9


@dataclass
class MidiTrackSpec:
    name: str
    notes: Sequence[dict]
    program: int = 0
    is_drums: bool = False


def _seconds_to_ticks(seconds: float, bpm: float) -> int:
    return max(int(round(seconds * (TICKS_PER_BEAT * bpm / 60.0))), 0)


def _channel_for(index: int, is_drums: bool) -> int:
    if is_drums:
        return DRUM_CHANNEL
    # Skip the drum channel when handing out channels to pitched parts.
    channel = index % 15
    return channel + 1 if channel >= DRUM_CHANNEL else channel


def write_midi(tracks: Sequence[MidiTrackSpec], out_path: Path, bpm: float = 120.0) -> None:
    bpm = float(bpm) if 20.0 < float(bpm) < 400.0 else 120.0
    midi = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)

    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    midi.tracks.append(meta)

    for index, spec in enumerate(tracks):
        if not spec.notes:
            continue
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=spec.name[:32], time=0))
        channel = _channel_for(index, spec.is_drums)
        if not spec.is_drums:
            track.append(
                mido.Message("program_change", program=int(spec.program) & 0x7F, channel=channel, time=0)
            )

        events: list[tuple[int, int, int, int]] = []
        for note in spec.notes:
            pitch = int(note["midi"]) & 0x7F
            start = float(note.get("start_sec", 0.0))
            end = float(note.get("end_sec", start + 0.12))
            if end <= start:
                end = start + 0.12
            velocity = int(min(max(int(note.get("velocity", 90)), 1), 127))
            # note-off sorts before note-on at the same tick so a repeated
            # pitch retriggers instead of being cut by its own predecessor.
            events.append((_seconds_to_ticks(start, bpm), 1, pitch, velocity))
            events.append((_seconds_to_ticks(end, bpm), 0, pitch, 0))

        events.sort(key=lambda e: (e[0], e[1]))
        previous = 0
        for tick, is_on, pitch, velocity in events:
            delta = max(tick - previous, 0)
            previous = tick
            track.append(
                mido.Message(
                    "note_on" if is_on else "note_off",
                    note=pitch,
                    velocity=velocity,
                    channel=channel,
                    time=delta,
                )
            )
        midi.tracks.append(track)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(out_path.as_posix())
