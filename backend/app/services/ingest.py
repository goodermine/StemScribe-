import shutil
from pathlib import Path
from typing import List

from fastapi import UploadFile

from app.services.storage import ensure_dir

SUPPORTED = {".wav", ".flac", ".aiff", ".aif", ".ogg", ".mp3", ".m4a"}

# Uploads are streamed rather than read whole: a set of stems for one song is
# routinely hundreds of megabytes.
CHUNK_BYTES = 1024 * 1024


def safe_filename(name: str) -> str:
    """Strip any directory component from an uploaded filename.

    The client controls this string, and it is used to build a path.
    """
    cleaned = Path(name or "stem.wav").name
    return cleaned or "stem.wav"


def save_uploaded_stems(files: List[UploadFile], job_dir: Path) -> list[Path]:
    if not files:
        raise ValueError("No files were uploaded.")

    stems_dir = ensure_dir(job_dir / "input")
    saved: list[Path] = []
    for file in files:
        filename = safe_filename(file.filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED:
            raise ValueError(
                f"Unsupported file type: {filename}. Supported: {', '.join(sorted(SUPPORTED))}"
            )
        out = stems_dir / filename
        file.file.seek(0)
        with out.open("wb") as target:
            shutil.copyfileobj(file.file, target, CHUNK_BYTES)
        if out.stat().st_size == 0:
            out.unlink()
            raise ValueError(f"{filename} is empty.")
        saved.append(out)
    return saved


def collect_local_stems(folder: Path) -> list[Path]:
    """Stems from a directory on disk, for the CLI path that skips HTTP."""
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
