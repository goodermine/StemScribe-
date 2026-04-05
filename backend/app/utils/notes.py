import math

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def hz_to_midi(frequency_hz: float) -> int:
    if frequency_hz <= 0:
        return 0
    return int(round(69 + 12 * math.log2(frequency_hz / 440.0)))


def midi_to_note_name(midi: int) -> str:
    octave = (midi // 12) - 1
    return f"{NOTE_NAMES[midi % 12]}{octave}"


def midi_to_hz(midi: int) -> float:
    return 440.0 * (2 ** ((midi - 69) / 12))
