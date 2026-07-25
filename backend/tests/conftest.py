"""Synthetic stems with known musical content.

The pipeline's job is to recover facts about a song, so the tests need a song
whose facts are known in advance. Generating one here means the assertions can
be about musical correctness — this key, this tempo, this progression — rather
than about whether a file happened to be written.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

SR = 22050
BPM = 120.0
BEATS_PER_BAR = 4
BARS = 8

SECONDS_PER_BEAT = 60.0 / BPM
BAR_SECONDS = SECONDS_PER_BEAT * BEATS_PER_BAR
TOTAL_SECONDS = BAR_SECONDS * BARS

# C major: C - Am - F - G, repeated. Root pitch class and triad intervals.
PROGRESSION = [
    ("C", 60, (0, 4, 7)),
    ("Am", 57, (0, 3, 7)),
    ("F", 53, (0, 4, 7)),
    ("G", 55, (0, 4, 7)),
] * (BARS // 4)

# A melody that stays inside C major, one note per beat.
MELODY_MIDI = [
    72, 71, 69, 67, 69, 67, 65, 64,
    65, 64, 62, 60, 62, 64, 65, 67,
] * (BARS // 4)


def _midi_to_hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def _tone(midi: float, duration: float, amplitude: float = 0.3, harmonics: int = 3) -> np.ndarray:
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    wave = np.zeros_like(t)
    for h in range(1, harmonics + 1):
        wave += (amplitude / h) * np.sin(2 * np.pi * _midi_to_hz(midi) * h * t)
    # A short fade at each end keeps clicks out of the onset detector.
    envelope = np.ones_like(t)
    edge = max(int(SR * 0.01), 1)
    envelope[:edge] = np.linspace(0, 1, edge)
    envelope[-edge:] = np.linspace(1, 0, edge)
    return wave * envelope


def _noise_burst(duration: float, low: float, high: float, amplitude: float = 0.5) -> np.ndarray:
    n = int(SR * duration)
    rng = np.random.default_rng(int(low))
    noise = rng.standard_normal(n)
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    spectrum[(freqs < low) | (freqs > high)] = 0
    filtered = np.fft.irfft(spectrum, n)
    decay = np.exp(-np.linspace(0, 9, n))
    peak = np.max(np.abs(filtered)) or 1.0
    return (filtered / peak) * decay * amplitude


def _place(canvas: np.ndarray, sound: np.ndarray, at_sec: float) -> None:
    start = int(at_sec * SR)
    end = min(start + len(sound), len(canvas))
    if start >= len(canvas):
        return
    canvas[start:end] += sound[: end - start]


def _blank() -> np.ndarray:
    return np.zeros(int(TOTAL_SECONDS * SR), dtype=float)


def _drums() -> np.ndarray:
    canvas = _blank()
    for bar in range(BARS):
        bar_start = bar * BAR_SECONDS
        for beat in range(BEATS_PER_BAR):
            at = bar_start + beat * SECONDS_PER_BEAT
            if beat in (0, 2):
                _place(canvas, _tone(28, 0.18, amplitude=0.9, harmonics=1) * np.exp(
                    -np.linspace(0, 7, int(SR * 0.18))
                ), at)
            if beat in (1, 3):
                _place(canvas, _noise_burst(0.14, 180, 4000, amplitude=0.7), at)
            # Eighth-note hi-hat.
            _place(canvas, _noise_burst(0.04, 9000, 11000, amplitude=0.28), at)
            _place(canvas, _noise_burst(0.04, 9000, 11000, amplitude=0.22),
                   at + SECONDS_PER_BEAT / 2)
    return canvas


def _bass() -> np.ndarray:
    canvas = _blank()
    for bar, (_, root, _) in enumerate(PROGRESSION):
        for beat in range(BEATS_PER_BAR):
            at = bar * BAR_SECONDS + beat * SECONDS_PER_BEAT
            _place(canvas, _tone(root - 24, SECONDS_PER_BEAT * 0.9, amplitude=0.5, harmonics=2), at)
    return canvas


def _keys() -> np.ndarray:
    canvas = _blank()
    for bar, (_, root, intervals) in enumerate(PROGRESSION):
        at = bar * BAR_SECONDS
        for interval in intervals:
            _place(canvas, _tone(root + interval, BAR_SECONDS * 0.95, amplitude=0.22), at)
    return canvas


def _vocals() -> np.ndarray:
    canvas = _blank()
    for index, midi in enumerate(MELODY_MIDI[: BARS * BEATS_PER_BAR // 2]):
        at = index * SECONDS_PER_BEAT * 2
        if at >= TOTAL_SECONDS:
            break
        _place(canvas, _tone(midi, SECONDS_PER_BEAT * 1.7, amplitude=0.35, harmonics=4), at)
    return canvas


def _write(path: Path, samples: np.ndarray) -> Path:
    peak = np.max(np.abs(samples)) or 1.0
    sf.write(path, (samples / peak * 0.9).astype(np.float32), SR)
    return path


@pytest.fixture(scope="session")
def synthetic_song(tmp_path_factory) -> Path:
    """A four-chord song in C major at 120 BPM, as four labelled stems."""
    folder = tmp_path_factory.mktemp("synthetic_song")
    _write(folder / "1 Drums.wav", _drums())
    _write(folder / "2 Bass.wav", _bass())
    _write(folder / "4 Keyboard.wav", _keys())
    _write(folder / "0 Lead Vocals.wav", _vocals())
    return folder


@pytest.fixture(scope="session")
def expected():
    return {
        "bpm": BPM,
        "bars": BARS,
        "beats_per_bar": BEATS_PER_BAR,
        "key": "C major",
        "chords": ["C", "Am", "F", "G"],
        "duration": TOTAL_SECONDS,
    }
