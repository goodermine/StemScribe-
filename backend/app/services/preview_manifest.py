from pathlib import Path

from app.services.storage import write_json


def build_preview_manifest(job_dir: Path, tempo_info: dict) -> dict:
    scores = [p.as_posix().replace(job_dir.as_posix() + "/", "") for p in job_dir.rglob("*.musicxml")]
    downloads = [p.as_posix().replace(job_dir.as_posix() + "/", "") for p in job_dir.rglob("*.mid")]
    lead = next((s for s in scores if "lead_melody" in s), scores[0] if scores else "")
    manifest = {
        "available_scores": scores,
        "default_score": lead,
        "available_downloads": downloads,
        "lead_melody_path": lead,
        "tempo_summary": {
            "bpm": tempo_info.get("bpm", 120.0),
            "time_signature": tempo_info.get("time_signature_guess", "4/4"),
        },
    }
    write_json(job_dir / "merged" / "preview_manifest.json", manifest)
    return manifest
