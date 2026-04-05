from app.services.quantize import quantize_notes


def test_quantize_deterministic() -> None:
    notes = [{"midi": 60, "start_sec": 0.11, "end_sec": 0.39, "duration_sec": 0.28}]
    out = quantize_notes(notes, [0.0, 0.5, 1.0], division=2)
    assert out[0]['start_sec'] == 0.0
    assert out[0]['end_sec'] >= out[0]['start_sec']
