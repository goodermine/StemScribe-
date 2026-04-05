from app.services.melody_extract import locate_bar_beat


def test_locate_bar_beat() -> None:
    beat = {"beat_times": [0, 0.5, 1.0, 1.5, 2.0], "bar_starts": [0, 2.0]}
    bar, beat_in_bar = locate_bar_beat(1.0, beat)
    assert bar == 0
    assert beat_in_bar >= 1.0
