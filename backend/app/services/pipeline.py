"""End-to-end analysis for one job.

Order matters here: the beat grid underpins every rhythmic decision, the key
decides how chords and notes are spelled, and the chords and sections are what
turn a pile of note events into something a player can read.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import librosa
import numpy as np

from app.config import settings
from app.services import chart as chart_builder
from app.services.arrange import stem_output_dir
from app.services.beat_grid import beat_map_from_grid, estimate_beat_grid
from app.services.chords import estimate_chords
from app.services.classify import classify_stem, lane_for_stem, profile_for, unique_key
from app.services.drum_transcribe import summarise_groove, transcribe_drums
from app.services.engrave import engrave_to_html, engrave_to_pdf
from app.services.key_detect import detect_key
from app.services.melody_extract import extract_melody_events, pick_lead_stem
from app.services.score_export import (
    add_chord_symbols,
    add_section_marks,
    build_drum_part,
    build_pitched_part,
    export_full_score,
    export_lead_sheet,
    export_midi,
    export_musicxml,
    export_song_midi,
)
from app.services.sections import analyse_sections
from app.services.stem_transcribe import transcribe_pitched_stem
from app.services.storage import write_json, write_text
from app.utils.audio import clear_audio_cache, load_mono
from app.utils.notes import midi_to_note_name


def run_analysis(job_id: str, job_dir: Path, saved: Sequence[Path], title: str) -> dict:
    warnings: list[str] = []

    stems_by_role, detected, output_keys = _organise_stems(saved)
    duration = _duration_of(saved)

    tempo_info = estimate_beat_grid(saved, stems_by_role)
    beat_map = beat_map_from_grid(tempo_info)
    # Bar one of every written score is the first detected downbeat.
    origin_beat = float(tempo_info["downbeat_index"])
    write_json(job_dir / "tempo.json", tempo_info)

    if tempo_info["timing_source"] not in {"drums", "percussion"}:
        warnings.append(
            "No drum stem was available, so tempo and bar positions were inferred "
            "from a pitched stem and are less reliable."
        )
    if tempo_info["confidence"] < 0.5:
        warnings.append(
            f"Beat tracking confidence is low ({tempo_info['confidence']:.2f}); "
            "check the tempo and downbeat before relying on bar numbers."
        )

    harmony_paths = [
        path
        for role, paths in stems_by_role.items()
        if profile_for(role).informs_harmony
        for path in paths
    ]
    key_info = detect_key(harmony_paths or list(saved))
    write_json(job_dir / "key.json", key_info)
    if key_info["confidence"] < 0.5:
        warnings.append(
            f"Key detection was ambiguous; {key_info['key_name']} is the best fit but the "
            "song may be modal or change key."
        )

    chords = estimate_chords(stems_by_role, beat_map, key_info)
    write_json(job_dir / "chords.json", chords)
    if not chords:
        warnings.append("No chord-bearing stem was found, so the chart has no chord symbols.")

    sections = analyse_sections(stems_by_role, beat_map)
    write_json(job_dir / "sections.json", sections)
    if sections:
        warnings.append(
            "Section boundaries are detected from the audio and land on bar lines, but the "
            "names (verse, chorus, bridge) are inferred from loudness and whether vocals are "
            "present — treat them as a guide, not a transcript of the arrangement."
        )

    lead_choice = pick_lead_stem(stems_by_role)
    lead_notes: list[dict] = []
    lead_role = "vocals"
    if lead_choice:
        lead_role, lead_path = lead_choice
        lead_notes = extract_melody_events(
            lead_role, lead_path, beat_map, settings.melodic_division
        )
        lead_dir = job_dir / "lead_melody"
        write_json(lead_dir / "lead_melody_notes.json", lead_notes)
        export_midi(
            lead_notes,
            lead_dir / "lead_melody.mid",
            program=profile_for(lead_role).midi_program,
            bpm=tempo_info["bpm"],
            name="lead melody",
        )
        export_musicxml(
            lead_notes,
            lead_dir / "lead_melody.musicxml",
            bpm=tempo_info["bpm"],
            time_signature=tempo_info["time_signature_guess"],
            fifths=key_info["fifths"],
            role=lead_role,
            chords=chords,
            sections=sections,
            title=f"{title} — lead melody",
            origin_beat=origin_beat,
        )
    else:
        warnings.append("No viable lead stem was found; the melody staff is empty.")

    parts, part_summaries, midi_tracks, transcripts = _transcribe_stems(
        job_dir, stems_by_role, output_keys, beat_map, tempo_info, key_info, warnings, origin_beat
    )

    _write_scores(
        job_dir,
        title,
        tempo_info,
        key_info,
        sections,
        chords,
        lead_notes,
        lead_role,
        parts,
        midi_tracks,
        origin_beat,
    )

    engraved = _engrave_all(job_dir, title, key_info, tempo_info)
    if not engraved:
        warnings.append(
            "Notation could not be engraved for viewing; the MusicXML files are still valid "
            "and open in any notation program."
        )

    chart = chart_builder.build_chart(
        title=title,
        tempo_info=tempo_info,
        key_info=key_info,
        sections=sections,
        chords=chords,
        drum_hits=transcripts.get("drums", []),
        parts_summary=part_summaries,
        duration_sec=duration,
        warnings=warnings,
    )
    write_json(job_dir / "chart.json", chart)
    write_text(job_dir / "player_sheet.html", chart_builder.render_html(chart))
    write_text(job_dir / "player_sheet.md", chart_builder.render_markdown(chart))

    analysis = {
        "job_id": job_id,
        "title": title,
        "input_stems": [p.name for p in saved],
        "detected_stem_types": detected,
        "duration_sec": round(duration, 2),
        "key": key_info,
        "tempo": {
            "bpm": tempo_info["bpm"],
            "time_signature": tempo_info["time_signature_guess"],
            "bar_count": tempo_info["bar_count"],
            "confidence": tempo_info["confidence"],
            "timing_source": tempo_info["timing_source"],
        },
        "sections": [{"name": s["name"], "start_bar": s["start_bar"] + 1, "end_bar": s["end_bar"] + 1} for s in sections],
        "chord_count": len(chords),
        "engraved_pages": engraved,
        "parts": part_summaries,
        "warnings": warnings,
        "confidence_summary": {
            "tempo": tempo_info["confidence"],
            "key": key_info["confidence"],
            "chords": round(float(np.mean([c["confidence"] for c in chords])), 3) if chords else 0.0,
            **{f"part_{p['key']}": p["confidence"] for p in part_summaries},
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(job_dir / "analysis.json", analysis)

    if settings.discard_input_audio:
        _remove_input_audio(job_dir)
    clear_audio_cache()
    return analysis


def _organise_stems(saved: Sequence[Path]) -> tuple[dict[str, list[Path]], dict[str, str], dict[Path, str]]:
    """Group stems by role, keeping every stem even when roles repeat."""
    stems_by_role: dict[str, list[Path]] = {}
    detected: dict[str, str] = {}
    output_keys: dict[Path, str] = {}
    taken: set[str] = set()

    for path in saved:
        role = classify_stem(path.name)
        detected[path.name] = role
        stems_by_role.setdefault(role, []).append(path)
        key = unique_key(role, taken)
        taken.add(key)
        output_keys[path] = key
    return stems_by_role, detected, output_keys


def _transcribe_stems(
    job_dir: Path,
    stems_by_role: dict[str, list[Path]],
    output_keys: dict[Path, str],
    beat_map,
    tempo_info: dict,
    key_info: dict,
    warnings: list[str],
    origin_beat: float,
):
    parts = []
    part_summaries: list[dict] = []
    midi_tracks: list[tuple[str, list[dict], int, bool]] = []
    transcripts: dict[str, list[dict]] = {}

    for role, paths in stems_by_role.items():
        profile = profile_for(role)
        lane = lane_for_stem(role)
        for path in paths:
            out_key = output_keys[path]
            out_dir = stem_output_dir(job_dir, out_key)

            if lane == "rhythm":
                hits = transcribe_drums(role, path, beat_map)
                transcripts.setdefault(role, []).extend(hits)
                groove = summarise_groove(hits, beat_map)
                write_json(out_dir / "rhythm.json", {"hits": hits, "groove": groove})
                if hits:
                    part = build_drum_part(
                        hits,
                        tempo_info["bpm"],
                        tempo_info["time_signature_guess"],
                        origin_beat=origin_beat,
                    )
                    parts.append(part)
                    midi_tracks.append((out_key, hits, 0, True))
                    export_midi(
                        hits, out_dir / "part.mid", is_drums=True, bpm=tempo_info["bpm"], name=out_key
                    )
                    _write_part(
                        part,
                        out_dir / "part.musicxml",
                        title=profile.display_name,
                        subtitle=f"{round(tempo_info['bpm'])} BPM · {tempo_info['time_signature_guess']}",
                    )
                summary = _summarise(out_key, profile.display_name, hits, lane)
            else:
                notes = transcribe_pitched_stem(role, path, beat_map, settings.melodic_division)
                transcripts.setdefault(role, []).extend(notes)
                write_json(out_dir / "notes.json", notes)
                if notes:
                    export_midi(
                        notes,
                        out_dir / "part.mid",
                        program=profile.midi_program,
                        bpm=tempo_info["bpm"],
                        name=out_key,
                    )
                    export_musicxml(
                        notes,
                        out_dir / "part.musicxml",
                        bpm=tempo_info["bpm"],
                        time_signature=tempo_info["time_signature_guess"],
                        fifths=key_info["fifths"],
                        role=role,
                        title=f"{profile.display_name}",
                        origin_beat=origin_beat,
                    )
                    parts.append(
                        build_pitched_part(
                            notes,
                            role,
                            tempo_info["bpm"],
                            tempo_info["time_signature_guess"],
                            key_info["fifths"],
                            part_name=profile.display_name,
                            origin_beat=origin_beat,
                        )
                    )
                    midi_tracks.append((out_key, notes, profile.midi_program, False))
                else:
                    warnings.append(f"No notes were detected in the {profile.display_name} stem.")
                summary = _summarise(out_key, profile.display_name, notes, lane)

            write_json(
                out_dir / "metadata.json",
                {
                    "stem_name": out_key,
                    "role": role,
                    "lane": lane,
                    "source_filename": path.name,
                    "transcription_method": _method_for(role, lane),
                    "quantization": {
                        "division": (
                            settings.quantization_division
                            if lane == "rhythm"
                            else settings.melodic_division
                        ),
                        "min_note_beats": settings.min_note_beats,
                    },
                    "confidence": summary["confidence"],
                    "note_count": summary["note_count"],
                },
            )
            part_summaries.append(summary)

    return parts, part_summaries, midi_tracks, transcripts


def _write_scores(
    job_dir: Path,
    title: str,
    tempo_info: dict,
    key_info: dict,
    sections: list[dict],
    chords: list[dict],
    lead_notes: list[dict],
    lead_role: str,
    parts,
    midi_tracks,
    origin_beat: float,
) -> None:
    time_signature = tempo_info["time_signature_guess"]
    bpm = tempo_info["bpm"]

    export_lead_sheet(
        lead_notes,
        chords,
        sections,
        job_dir / "score" / "lead_sheet.musicxml",
        bpm=bpm,
        time_signature=time_signature,
        fifths=key_info["fifths"],
        title=title,
        key_name=key_info["key_name"],
        melody_role=lead_role,
        origin_beat=origin_beat,
    )

    if parts:
        # Chord symbols and section marks ride on the top staff so they appear
        # once above the system rather than repeated on every part.
        annotated = list(parts)
        add_chord_symbols(annotated[0], chords, time_signature, origin_beat)
        add_section_marks(annotated[0], sections, time_signature, origin_beat)
        export_full_score(
            annotated,
            job_dir / "score" / "full_score.musicxml",
            title=title,
            subtitle=f"{key_info['key_name']} · {round(bpm)} BPM · {time_signature}",
        )

    if midi_tracks:
        export_song_midi(midi_tracks, job_dir / "score" / "song.mid", bpm=bpm)


def _engrave_all(job_dir: Path, title: str, key_info: dict, tempo_info: dict) -> dict[str, int]:
    """Turn every MusicXML file into a page a musician can just open.

    Handing someone a .musicxml means handing them a prerequisite. These are
    browser pages that print straight to PDF, so the part is readable with
    nothing installed.
    """
    subtitle = (
        f"{key_info['key_name']} · {round(tempo_info['bpm'])} BPM · "
        f"{tempo_info['time_signature_guess']}"
    )
    engraved: dict[str, int] = {}
    for source in sorted(job_dir.rglob("*.musicxml")):
        relative = source.relative_to(job_dir).as_posix()
        label = _score_label(relative, title)
        try:
            pages = engrave_to_html(source, source.with_suffix(".html"), label, subtitle)
            if pages:
                engrave_to_pdf(source, source.with_suffix(".pdf"))
        except Exception:
            # One unreadable score should not cost the rest of the job.
            pages = 0
        engraved[relative] = pages
    return engraved


def _score_label(relative_path: str, title: str) -> str:
    if relative_path.endswith("lead_sheet.musicxml"):
        return f"{title} — lead sheet"
    if relative_path.endswith("full_score.musicxml"):
        return f"{title} — full score"
    parts = relative_path.split("/")
    if len(parts) >= 2 and parts[0] == "stems":
        return f"{title} — {parts[1].replace('_', ' ')}"
    if "lead_melody" in relative_path:
        return f"{title} — lead melody"
    return title


def _write_part(part, out_path: Path, title: str | None = None, subtitle: str | None = None) -> None:
    from music21 import stream as m21stream

    from app.services.score_export import finalise, write_score

    score = m21stream.Score()
    score.insert(0, part)
    # Without a title music21 stamps the file "Music21 Fragment", which is what
    # a player then sees at the top of their part.
    write_score(finalise(score, title or "Part", subtitle), out_path)


def _summarise(key: str, name: str, events: Sequence[dict], lane: str) -> dict:
    if not events:
        return {"key": key, "name": name, "lane": lane, "note_count": 0, "range": "—", "confidence": 0.0}
    confidences = [float(e.get("confidence", 0.0)) for e in events]
    if lane == "rhythm":
        pieces = sorted({e["instrument"] for e in events})
        span = ", ".join(pieces)
    else:
        midis = [int(e["midi"]) for e in events]
        span = f"{midi_to_note_name(min(midis))}–{midi_to_note_name(max(midis))}"
    return {
        "key": key,
        "name": name,
        "lane": lane,
        "note_count": len(events),
        "range": span,
        "confidence": round(float(np.mean(confidences)), 3),
    }


def _method_for(role: str, lane: str) -> str:
    if lane == "rhythm":
        return "onset detection + spectral band classification"
    return "pyin" if not profile_for(role).polyphonic else "cqt peak picking between onsets"


def _duration_of(saved: Sequence[Path]) -> float:
    for path in saved:
        try:
            y, sr = load_mono(path)
            return float(librosa.get_duration(y=np.asarray(y), sr=sr))
        except Exception:
            continue
    return 0.0


def _remove_input_audio(job_dir: Path) -> None:
    input_dir = job_dir / "input"
    if not input_dir.exists():
        return
    for path in input_dir.iterdir():
        if path.is_file():
            path.unlink()
    input_dir.rmdir()
