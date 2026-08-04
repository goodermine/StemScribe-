"""Engraved output — the part that means a musician needs no notation software."""

from pathlib import Path

import pytest

from app.services.engrave import engrave_to_html, render_pages
from app.services.score_export import export_lead_sheet, export_musicxml


def note(midi: int, start_beat: float, duration_beats: float) -> dict:
    return {
        "midi": midi,
        "start_beat": start_beat,
        "end_beat": start_beat + duration_beats,
        "duration_beats": duration_beats,
        "start_sec": start_beat * 0.5,
        "end_sec": (start_beat + duration_beats) * 0.5,
    }


@pytest.fixture
def score(tmp_path: Path) -> Path:
    out = tmp_path / "lead_sheet.musicxml"
    export_lead_sheet(
        melody_notes=[note(72, 0.0, 2.0), note(71, 2.0, 2.0), note(69, 4.0, 4.0)],
        chords=[
            {"symbol": "C", "start_beat": 0.0, "end_beat": 4.0},
            {"symbol": "Am", "start_beat": 4.0, "end_beat": 8.0},
        ],
        sections=[{"name": "Verse 1", "start_beat": 0.0}],
        out_path=out,
        bpm=120.0,
        time_signature="4/4",
        fifths=0,
        title="Test Song",
        key_name="C major",
    )
    return out


def test_score_renders_to_pages(score: Path) -> None:
    pages = render_pages(score)
    assert pages
    assert all(page.lstrip().startswith("<") for page in pages)


def test_html_is_written_and_reports_its_page_count(score: Path, tmp_path: Path) -> None:
    out = tmp_path / "lead_sheet.html"
    pages = engrave_to_html(score, out, "Test Song", "C major · 120 BPM")
    assert pages >= 1
    assert out.exists()


def test_html_is_self_contained(score: Path, tmp_path: Path) -> None:
    """The point is that it opens anywhere; a remote asset would defeat that."""
    out = tmp_path / "lead_sheet.html"
    engrave_to_html(score, out, "Test Song")
    html = out.read_text()
    assert "<svg" in html
    assert "<style>" in html
    assert 'src="http' not in html
    assert 'href="http' not in html


def test_html_carries_the_title_and_prints_one_page_per_page(score: Path, tmp_path: Path) -> None:
    out = tmp_path / "lead_sheet.html"
    pages = engrave_to_html(score, out, "Carved From Stone", "F minor")
    html = out.read_text()
    assert "Carved From Stone" in html
    assert "F minor" in html
    assert html.count('class="page"') == pages
    assert "@media print" in html


def test_notation_survives_the_round_trip(score: Path, tmp_path: Path) -> None:
    """Chord symbols and section marks have to reach the engraved page."""
    out = tmp_path / "lead_sheet.html"
    engrave_to_html(score, out, "Test Song")
    html = out.read_text()
    assert "Verse 1" in html
    assert "Am" in html


def test_unreadable_input_reports_zero_rather_than_raising(tmp_path: Path) -> None:
    broken = tmp_path / "broken.musicxml"
    broken.write_text("<not-musicxml/>")
    assert engrave_to_html(broken, tmp_path / "out.html", "Broken") == 0
    assert not (tmp_path / "out.html").exists()


def test_empty_score_does_not_crash_the_engraver(tmp_path: Path) -> None:
    empty = tmp_path / "empty.musicxml"
    export_musicxml([], empty, bpm=120.0)
    engrave_to_html(empty, tmp_path / "empty.html", "Empty")
