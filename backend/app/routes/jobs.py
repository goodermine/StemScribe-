import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.config import settings
from app.schemas import JobCreateResponse
from app.services.ingest import save_uploaded_stems
from app.services.pipeline import run_analysis
from app.services.preview_manifest import build_preview_manifest
from app.services.separate import (
    SeparationLicenseError,
    SeparationUnavailable,
    prepare_job_stems,
)
from app.services.storage import read_json, resolve_within, write_json

router = APIRouter(prefix="/jobs", tags=["jobs"])

DOWNLOADABLE_SUFFIXES = {".mid", ".musicxml", ".json", ".html", ".md", ".pdf"}


def _status_path(job_dir: Path) -> Path:
    return job_dir / "status.json"


def _set_status(job_dir: Path, status: str, **extra) -> None:
    write_json(
        _status_path(job_dir),
        {"status": status, "updated_at": datetime.now(timezone.utc).isoformat(), **extra},
    )


def _process(job_id: str, job_dir: Path, saved: list[Path], title: str, separate: bool) -> None:
    """Run the analysis, recording the outcome either way.

    Transcribing a full song takes minutes, so this runs in the background and
    the caller polls. A failure has to land in the status file — otherwise the
    job simply never finishes and the client waits forever. Separation, when
    asked for, is a pre-stage: it turns the one uploaded mix into stems, which
    the analysis then treats like any others.
    """
    try:
        if separate:
            _set_status(job_dir, "processing", stage="separating")
            stems, recovered_note = prepare_job_stems(
                saved, job_dir / "input", separate=True
            )
        else:
            stems, recovered_note = saved, None
        _set_status(job_dir, "processing", stage="analysing")
        analysis = run_analysis(job_id, job_dir, stems, title, recovered_note=recovered_note)
        build_preview_manifest(job_dir, analysis)
        _set_status(job_dir, "completed", warnings=analysis.get("warnings", []))
    except (SeparationUnavailable, SeparationLicenseError, ValueError) as exc:
        # Expected, explainable failures — record the message plainly so the UI
        # can show it, without a traceback that reads like a crash.
        _set_status(job_dir, "failed", error=str(exc))
    except Exception as exc:
        _set_status(
            job_dir,
            "failed",
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(limit=8),
        )


@router.post("", response_model=JobCreateResponse)
def create_job(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    title: str = Form(default="Untitled"),
    separate: bool = Form(default=False),
) -> JobCreateResponse:
    job_id = str(uuid4())
    job_dir = settings.jobs_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        saved = save_uploaded_stems(files, job_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _set_status(job_dir, "queued")
    background.add_task(_process, job_id, job_dir, saved, title, separate)
    return JobCreateResponse(job_id=job_id, status="queued")


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job_dir = settings.jobs_root / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    status_file = _status_path(job_dir)
    status = read_json(status_file) if status_file.exists() else {"status": "unknown"}

    analysis_file = job_dir / "analysis.json"
    if not analysis_file.exists():
        return {"job_id": job_id, **status}

    data = read_json(analysis_file)
    data["status"] = status.get("status", "completed")
    tempo_file = job_dir / "tempo.json"
    data["tempo_detail"] = read_json(tempo_file) if tempo_file.exists() else None
    return data


@router.get("/{job_id}/chart")
def get_chart(job_id: str) -> dict:
    chart_file = settings.jobs_root / job_id / "chart.json"
    if not chart_file.exists():
        raise HTTPException(status_code=404, detail="Chart not ready")
    return read_json(chart_file)


@router.get("/{job_id}/sheet", response_class=HTMLResponse)
def get_sheet(job_id: str) -> HTMLResponse:
    """The printable player sheet, served directly for viewing."""
    sheet = settings.jobs_root / job_id / "player_sheet.html"
    if not sheet.exists():
        raise HTTPException(status_code=404, detail="Player sheet not ready")
    return HTMLResponse(sheet.read_text(encoding="utf-8"))


@router.get("/{job_id}/downloads")
def list_downloads(job_id: str) -> dict:
    job_dir = settings.jobs_root / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    files = sorted(
        p.relative_to(job_dir).as_posix()
        for p in job_dir.rglob("*")
        if p.is_file() and p.suffix in DOWNLOADABLE_SUFFIXES
    )
    return {"job_id": job_id, "files": files}


@router.get("/{job_id}/preview-manifest")
def get_preview_manifest(job_id: str) -> dict:
    manifest = settings.jobs_root / job_id / "merged" / "preview_manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    return read_json(manifest)


@router.get("/{job_id}/files/{path:path}")
def get_file(job_id: str, path: str):
    job_dir = settings.jobs_root / job_id
    file_path = resolve_within(job_dir, path)
    if file_path is None or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
