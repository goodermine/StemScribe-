from pathlib import Path

from app.services.score_export import export_musicxml


def test_musicxml_export(tmp_path: Path) -> None:
    notes = [{"midi": 60, "duration_sec": 0.5}]
    out = tmp_path / 'part.musicxml'
    export_musicxml(notes, out)
    assert out.exists()
