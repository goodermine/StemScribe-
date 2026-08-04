from pathlib import Path

from app.services.storage import write_json


def build_preview_manifest(job_dir: Path, analysis: dict) -> dict:
    """Index of everything the job produced, for the UI to offer.

    The lead sheet is the default view: it is the one file that answers "how
    do I play this song" on its own.
    """
    scores = sorted(p.relative_to(job_dir).as_posix() for p in job_dir.rglob("*.musicxml"))
    midis = sorted(p.relative_to(job_dir).as_posix() for p in job_dir.rglob("*.mid"))

    lead_sheet = next((s for s in scores if s.endswith("score/lead_sheet.musicxml")), "")
    full_score = next((s for s in scores if s.endswith("score/full_score.musicxml")), "")
    lead_melody = next((s for s in scores if "lead_melody" in s), "")
    default_score = lead_sheet or full_score or lead_melody or (scores[0] if scores else "")

    engraved_html = sorted(
        p.relative_to(job_dir).as_posix()
        for p in job_dir.rglob("*.html")
        if p.name != "player_sheet.html"
    )
    engraved_pdf = sorted(p.relative_to(job_dir).as_posix() for p in job_dir.rglob("*.pdf"))

    tempo = analysis.get("tempo", {})
    manifest = {
        "title": analysis.get("title", "Untitled"),
        "available_scores": scores,
        "default_score": default_score,
        "lead_sheet_path": lead_sheet,
        "full_score_path": full_score,
        "lead_melody_path": lead_melody,
        "available_downloads": midis,
        "song_midi_path": next((m for m in midis if m.endswith("score/song.mid")), ""),
        "player_sheet_html": "player_sheet.html" if (job_dir / "player_sheet.html").exists() else "",
        "engraved_html": engraved_html,
        "engraved_pdf": engraved_pdf,
        "lead_sheet_readable": _swap_suffix(lead_sheet, engraved_html, engraved_pdf),
        "full_score_readable": _swap_suffix(full_score, engraved_html, engraved_pdf),
        "player_sheet_markdown": "player_sheet.md" if (job_dir / "player_sheet.md").exists() else "",
        "summary": {
            "key": analysis.get("key", {}).get("key_name", "unknown"),
            "bpm": tempo.get("bpm", 120.0),
            "time_signature": tempo.get("time_signature", "4/4"),
            "bar_count": tempo.get("bar_count", 0),
            "sections": len(analysis.get("sections", [])),
        },
    }
    write_json(job_dir / "merged" / "preview_manifest.json", manifest)
    return manifest


def _swap_suffix(musicxml_path: str, html: list[str], pdf: list[str]) -> str:
    """The readable twin of a MusicXML file, preferring PDF where it exists."""
    if not musicxml_path:
        return ""
    stem = musicxml_path.rsplit(".", 1)[0]
    for candidates in (pdf, html):
        for candidate in candidates:
            if candidate.rsplit(".", 1)[0] == stem:
                return candidate
    return ""
