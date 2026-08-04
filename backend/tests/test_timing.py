import pytest

from app.utils.timing import BeatMap, quantize_to_grid


@pytest.fixture
def steady() -> BeatMap:
    """Sixteen beats at 120 BPM, bar one starting on the first beat."""
    return BeatMap(beat_times=[i * 0.5 for i in range(16)], beats_per_bar=4, downbeat_index=0)


def test_seconds_map_to_beats(steady: BeatMap) -> None:
    assert steady.seconds_to_beats(0.0) == pytest.approx(0.0)
    assert steady.seconds_to_beats(0.5) == pytest.approx(1.0)
    assert steady.seconds_to_beats(0.75) == pytest.approx(1.5)


def test_round_trip_is_stable(steady: BeatMap) -> None:
    for t in (0.13, 1.7, 4.25, 7.4):
        assert steady.beats_to_seconds(steady.seconds_to_beats(t)) == pytest.approx(t, abs=1e-6)


def test_extrapolates_past_the_tracked_range(steady: BeatMap) -> None:
    """Notes can sound before the first tracked beat or after the last."""
    assert steady.seconds_to_beats(-0.5) == pytest.approx(-1.0)
    assert steady.seconds_to_beats(8.0) == pytest.approx(16.0)


def test_interpolates_across_a_tempo_change() -> None:
    # Beats slow down: 0.5s spacing, then 1.0s spacing.
    drifting = BeatMap(beat_times=[0.0, 0.5, 1.0, 2.0, 3.0])
    assert drifting.seconds_to_beats(1.5) == pytest.approx(2.5)
    assert drifting.seconds_to_beats(0.25) == pytest.approx(0.5)


def test_bar_and_beat_positions(steady: BeatMap) -> None:
    assert steady.bar_of_beat(0.0) == 0
    assert steady.beat_in_bar(0.0) == 1.0
    assert steady.bar_of_beat(4.0) == 1
    assert steady.beat_in_bar(6.5) == 3.5
    assert steady.bar_count() == 4


def test_downbeat_offset_shifts_the_bar_lines() -> None:
    """When beat one is the third tracked beat, bar numbering has to follow."""
    offset = BeatMap(beat_times=[i * 0.5 for i in range(16)], beats_per_bar=4, downbeat_index=2)
    assert offset.beat_in_bar(2.0) == 1.0
    assert offset.bar_of_beat(2.0) == 0
    assert offset.bar_of_beat(6.0) == 1


def test_quantize_snaps_to_subdivision() -> None:
    assert quantize_to_grid(1.13, 4) == pytest.approx(1.25)
    assert quantize_to_grid(1.13, 2) == pytest.approx(1.0)
    assert quantize_to_grid(0.9, 1) == pytest.approx(1.0)


def test_empty_beat_map_does_not_divide_by_zero() -> None:
    empty = BeatMap(beat_times=[])
    assert empty.seconds_to_beats(1.0) == pytest.approx(2.0)
    assert empty.bar_count() == 0
