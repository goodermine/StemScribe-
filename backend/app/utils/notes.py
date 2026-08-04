"""Pitch helpers.

Note *names* here are for human-readable JSON output. Notation spelling is
decided later, in score export, where the detected key is known.
"""

import math

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

PITCH_CLASSES = SHARP_NAMES

# Keys whose signature is written with flats. Used to pick an enharmonic
# spelling that a reader expects to see on the page.
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"}


def hz_to_midi_float(frequency_hz: float) -> float:
    """Continuous MIDI number, so callers can average before rounding."""
    if frequency_hz <= 0:
        return 0.0
    return 69.0 + 12.0 * math.log2(frequency_hz / 440.0)


def hz_to_midi(frequency_hz: float) -> int:
    return int(round(hz_to_midi_float(frequency_hz)))


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2 ** ((midi - 69) / 12))


def midi_to_note_name(midi: int, prefer_flats: bool = False) -> str:
    names = FLAT_NAMES if prefer_flats else SHARP_NAMES
    octave = (int(midi) // 12) - 1
    return f"{names[int(midi) % 12]}{octave}"


def pitch_class_name(pitch_class: int, prefer_flats: bool = False) -> str:
    names = FLAT_NAMES if prefer_flats else SHARP_NAMES
    return names[pitch_class % 12]


def key_prefers_flats(tonic: str) -> bool:
    return tonic in FLAT_KEYS


def cents_off(frequency_hz: float, midi: int) -> float:
    """How far a detected frequency sits from the note it was rounded to.

    Small deviations are normal; consistently large ones mean the tracker
    latched onto a harmonic rather than the fundamental.
    """
    if frequency_hz <= 0:
        return 0.0
    return 100.0 * (hz_to_midi_float(frequency_hz) - midi)
