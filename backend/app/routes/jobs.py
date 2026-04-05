from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas import JobCreateResponse
from app.services.arrange import stem_output_dir
from app.services.beat_grid import estimate_beat_grid
from app.services.classify import classify_stem, lane_for_stem
from app.services.ingest import save_uploaded_stems
from app.services.melody_extract import extract_melody_events, pick_lead_stem
from app.services.preview_manifest import build_preview_manifest
from app.services.score_export import export_midi, export_musicxml
from app.services.stem_transcribe import transcribe_pitched_stem
from app.services.storage import write_json

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse)
def create_job(files: list[UploadFile] = File(...)) -> JobCreateResponse:
    job_id = str(uuid4())
    job_dir = settings.jobs_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        saved = save_uploaded_stems(files, job_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stem_map: dict[str, Path] = {}
    detected: dict[str, str] = {}
    for p in saved:
        stem_type = classify_stem(p.name)
        detected[p.name] = stem_type
        stem_map[stem_type] = p

    tempo_info = estimate_beat_grid(saved, stem_map.get("drums"))
    write_json(job_dir / "tempo.json", tempo_info)

    lead_choice = pick_lead_stem(stem_map)
    warnings: list[str] = []
    confidence_summary = {"tempo": tempo_info["confidence"]}

    if lead_choice:
        lead_name, lead_path = lead_choice
        lead_notes = extract_melody_events(lead_name, lead_path, tempo_info, settings.quantization_division)
        lead_dir = job_dir / "lead_melody"
        write_json(lead_dir / "lead_melody_notes.json", lead_notes)
        export_midi(lead_notes, lead_dir / "lead_melody.mid", program=0)
        export_musicxml(lead_notes, lead_dir / "lead_melody.musicxml", bpm=tempo_info["bpm"])
        confidence_summary["lead_melody"] = 0.75
    else:
        warnings.append("No viable lead stem found; lead melody is unavailable.")

    for stem_type, stem_path in stem_map.items():
        lane = lane_for_stem(stem_type)
        out_dir = stem_output_dir(job_dir, stem_type)
        metadata = {
            "stem_name": stem_type,
            "lane": lane,
            "source_filename": stem_path.name,
            "transcription_method": "pyin" if lane == "melody" else "piptrack",
            "quantization_settings": {"division": settings.quantization_division},
            "confidence": 0.6,
            "warnings": [],
        }
        if lane == "rhythm":
            write_json(out_dir / "rhythm.json", {"onsets": tempo_info["beat_times"]})
        else:
            notes = transcribe_pitched_stem(stem_type, stem_path, tempo_info, settings.quantization_division)
            write_json(out_dir / "notes.json", notes)
            export_midi(notes, out_dir / "part.mid", program=32 if stem_type == "bass" else 0)
            export_musicxml(
                notes,
                out_dir / "part.musicxml",
                bpm=tempo_info["bpm"],
                time_signature=tempo_info["time_signature_guess"],
                use_bass_clef=stem_type == "bass",
            )
        write_json(out_dir / "metadata.json", metadata)

    analysis = {
        "job_id": job_id,
        "input_stems": [p.name for p in saved],
        "detected_stem_types": detected,
        "warnings": warnings,
        "confidence_summary": confidence_summary,
        "created_at": datetime.utcnow().isoformat(),
    }
    write_json(job_dir / "analysis.json", analysis)
    build_preview_manifest(job_dir, tempo_info)
    return JobCreateResponse(job_id=job_id, status="completed")


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job_dir = settings.jobs_root / job_id
    analysis = job_dir / "analysis.json"
    tempo = job_dir / "tempo.json"
    if not analysis.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    import json

    data = json.loads(analysis.read_text())
    data["tempo"] = json.loads(tempo.read_text()) if tempo.exists() else None
    data["status"] = "completed"
    return data


@router.get("/{job_id}/downloads")
def list_downloads(job_id: str) -> dict:
    job_dir = settings.jobs_root / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    files = [p.relative_to(job_dir).as_posix() for p in job_dir.rglob("*") if p.is_file() and p.suffix in {".mid", ".musicxml", ".json"}]
    return {"job_id": job_id, "files": files}


@router.get("/{job_id}/preview-manifest")
def get_preview_manifest(job_id: str) -> dict:
    manifest = settings.jobs_root / job_id / "merged" / "preview_manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    import json

    return json.loads(manifest.read_text())


@router.get("/{job_id}/files/{path:path}")
def get_file(job_id: str, path: str):
    file_path = settings.jobs_root / job_id / path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
