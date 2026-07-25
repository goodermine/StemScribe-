"""Conversion between wall-clock seconds and musical beat position.

Every transcription stage works in beat space. Detectors report seconds, but
notation needs beats: a note's written value depends on how much of a bar it
occupies, not on how long it lasted. Doing the conversion once, here, is what
lets the exporter place notes in real measures with real rests between them.
"""

from bisect import bisect_right
from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class BeatMap:
    """Maps seconds to beats using the detected beat positions.

    Tempo is rarely perfectly constant, so this interpolates between measured
    beats rather than assuming a single BPM. Outside the tracked range it
    extrapolates at the mean beat period.
    """

    beat_times: List[float]
    beats_per_bar: int = 4
    downbeat_index: int = 0

    @property
    def mean_period(self) -> float:
        if len(self.beat_times) < 2:
            return 0.5
        span = self.beat_times[-1] - self.beat_times[0]
        return span / max(len(self.beat_times) - 1, 1) if span > 0 else 0.5

    @property
    def bpm(self) -> float:
        return 60.0 / self.mean_period if self.mean_period > 0 else 120.0

    def seconds_to_beats(self, t: float) -> float:
        beats = self.beat_times
        if not beats:
            return t * 2.0
        if t <= beats[0]:
            return (t - beats[0]) / self.mean_period
        if t >= beats[-1]:
            return (len(beats) - 1) + (t - beats[-1]) / self.mean_period
        i = bisect_right(beats, t) - 1
        i = min(max(i, 0), len(beats) - 2)
        span = beats[i + 1] - beats[i]
        frac = (t - beats[i]) / span if span > 0 else 0.0
        return i + frac

    def beats_to_seconds(self, b: float) -> float:
        beats = self.beat_times
        if not beats:
            return b * 0.5
        if b <= 0:
            return beats[0] + b * self.mean_period
        if b >= len(beats) - 1:
            return beats[-1] + (b - (len(beats) - 1)) * self.mean_period
        i = int(b)
        frac = b - i
        return beats[i] + frac * (beats[i + 1] - beats[i])

    def bar_of_beat(self, b: float) -> int:
        """Bar number (0-based) containing a beat position."""
        return int((b - self.downbeat_index) // self.beats_per_bar)

    def beat_in_bar(self, b: float) -> float:
        """Position within the bar, 1-based, the way a musician counts."""
        offset = (b - self.downbeat_index) % self.beats_per_bar
        return offset + 1.0

    def bar_count(self) -> int:
        if not self.beat_times:
            return 0
        total = len(self.beat_times) - self.downbeat_index
        return max(int(-(-total // self.beats_per_bar)), 0)


def quantize_to_grid(value_beats: float, division: int) -> float:
    """Snap a beat position to the nearest subdivision of a beat."""
    step = 1.0 / max(division, 1)
    return round(value_beats / step) * step


def mean_interval(times: Sequence[float]) -> float:
    diffs = [b - a for a, b in zip(times, times[1:]) if b > a]
    return sum(diffs) / len(diffs) if diffs else 0.5
