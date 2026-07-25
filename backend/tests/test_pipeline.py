"""End-to-end: stems in, playable sheet out."""

import json
from pathlib import Path

import pytest

from app.services.ingest import collect_local_stems
from app.services.pipeline import run_analysis
from app.services.preview_manifest import build_preview_manifest


@pytest.fixture(scope="module")
def job(synthetic_song, tmp_path_factory) -> tuple[Path, dict]:
    job_dir = tmp_path_factory.mktemp("job")
    input_dir = job_dir / "input"
    input_dir.mkdir()
    for stem in collect_local_stems(synthetic_song):
        (input_dir / stem.name).write_bytes(stem.read_bytes())

    stems = collect_local_stems(input_dir)
    analysis = run_analysis("test-job", job_dir, stems, "Test Song")
    build_preview_manifest(job_dir, analysis)
    return job_dir, analysis


def test_every_promised_output_exists(job) -> None:
    job_dir, _ = job
    for relative in [
        "analysis.json",
        "tempo.json",
        "key.json",
        "chords.json",
        "sections.json",
        "chart.json",
        "player_sheet.html",
        "player_sheet.md",
        "score/lead_sheet.musicxml",
        "score/full_score.musicxml",
        "score/song.mid",
        "lead_melody/lead_melody.musicxml",
        "lead_melody/lead_melody.mid",
        "lead_melody/lead_melody_notes.json",
        "merged/preview_manifest.json",
    ]:
        path = job_dir / relative
        assert path.exists(), f"missing {relative}"
        assert path.stat().st_size > 0, f"empty {relative}"


def test_notation_is_engraved_for_reading_without_an_app(job) -> None:
    """MusicXML needs software to open; these pages need only a browser."""
    job_dir, analysis = job
    for relative in ["score/lead_sheet.html", "score/full_score.html"]:
        page = job_dir / relative
        assert page.exists(), f"missing {relative}"
        assert "<svg" in page.read_text()

    assert analysis["engraved_pages"], "nothing was engraved"
    assert all(pages > 0 for pages in analysis["engraved_pages"].values())


def test_manifest_offers_a_readable_lead_sheet(job) -> None:
    job_dir, _ = job
    manifest = json.loads((job_dir / "merged" / "preview_manifest.json").read_text())
    readable = manifest["lead_sheet_readable"]
    assert readable, "no readable lead sheet offered"
    assert readable.endswith((".html", ".pdf"))
    assert (job_dir / readable).exists()


def test_each_stem_gets_its_own_output_directory(job) -> None:
    job_dir, _ = job
    stems = {p.name for p in (job_dir / "stems").iterdir()}
    assert {"drums", "bass", "keys", "vocals"}.issubset(stems)


def test_drums_and_pitched_stems_produce_different_files(job) -> None:
    job_dir, _ = job
    assert (job_dir / "stems" / "drums" / "rhythm.json").exists()
    assert (job_dir / "stems" / "bass" / "notes.json").exists()
    assert not (job_dir / "stems" / "drums" / "notes.json").exists()


def test_analysis_reports_the_musical_facts(job, expected) -> None:
    _, analysis = job
    assert analysis["key"]["key_name"] == expected["key"]
    assert analysis["tempo"]["bpm"] == pytest.approx(expected["bpm"], rel=0.05)
    assert analysis["tempo"]["time_signature"] == "4/4"
    assert analysis["chord_count"] > 0
    assert analysis["duration_sec"] == pytest.approx(expected["duration"], rel=0.05)


def test_confidences_are_real_numbers_not_placeholders(job) -> None:
    """Every confidence in the old code was a hardcoded literal."""
    _, analysis = job
    values = list(analysis["confidence_summary"].values())
    assert values
    assert all(0.0 <= v <= 1.0 for v in values)
    assert len(set(values)) > 1, "all confidences identical; likely hardcoded"


def test_part_note_counts_are_musically_plausible(job) -> None:
    """Sixteen seconds of music, not one note per analysis frame."""
    _, analysis = job
    for part in analysis["parts"]:
        assert part["note_count"] < 400, (
            f"{part['name']} has {part['note_count']} events in 16s — that is frame noise"
        )


def test_bass_notes_stay_in_the_bass_register(job) -> None:
    job_dir, _ = job
    notes = json.loads((job_dir / "stems" / "bass" / "notes.json").read_text())
    assert notes, "no bass notes"
    assert all(n["midi"] <= 60 for n in notes), "bass transcribed above middle C"


def test_input_audio_is_cleaned_up(job) -> None:
    """Stems are hundreds of megabytes; the finished job only needs symbols."""
    job_dir, _ = job
    assert not (job_dir / "input").exists()


def test_player_sheet_is_self_contained(job) -> None:
    job_dir, _ = job
    html = (job_dir / "player_sheet.html").read_text()
    assert "<style>" in html
    assert "src=\"http" not in html and "href=\"http" not in html


def test_player_sheet_shows_key_tempo_and_structure(job, expected) -> None:
    job_dir, _ = job
    html = (job_dir / "player_sheet.html").read_text()
    assert expected["key"] in html
    assert "BPM" in html
    assert "Chord chart" in html


def test_chart_json_matches_the_analysis(job) -> None:
    job_dir, analysis = job
    chart = json.loads((job_dir / "chart.json").read_text())
    assert chart["key"] == analysis["key"]["key_name"]
    assert chart["bpm"] == round(analysis["tempo"]["bpm"])
    assert chart["bar_count"] == analysis["tempo"]["bar_count"]


def test_manifest_points_at_the_lead_sheet(job) -> None:
    job_dir, _ = job
    manifest = json.loads((job_dir / "merged" / "preview_manifest.json").read_text())
    assert manifest["default_score"].endswith("lead_sheet.musicxml")
    assert (job_dir / manifest["default_score"]).exists()


def test_warnings_are_specific_when_present(job) -> None:
    _, analysis = job
    assert all(len(w) > 20 for w in analysis["warnings"]), "warnings should explain themselves"
