from app.services.classify import classify_stem, lane_for_stem


def test_classification_aliases() -> None:
    assert classify_stem('leadvox.wav') == 'vocals'
    assert classify_stem('perc_loop.wav') == 'drums'
    assert lane_for_stem('drums') == 'rhythm'
