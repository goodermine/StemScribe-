from app.services.melody_extract import pick_lead_stem


def test_missing_stems_best_effort_none() -> None:
    assert pick_lead_stem({}) is None
