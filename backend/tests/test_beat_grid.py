from app.services.beat_grid import guess_time_signature


def test_guess_time_signature_defaults() -> None:
    assert guess_time_signature([0.0, 0.5, 1.0, 1.5]) == '4/4'
