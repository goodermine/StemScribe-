from pathlib import Path
from typing import List

from fastapi import UploadFile

from app.services.storage import ensure_dir


SUPPORTED = {".wav"}


def save_uploaded_stems(files: List[UploadFile], job_dir: Path) -> list[Path]:
    stems_dir = ensure_dir(job_dir / "input")
    saved: list[Path] = []
    for file in files:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in SUPPORTED:
            raise ValueError(f"Unsupported file type: {file.filename}")
        out = stems_dir / file.filename
        content = file.file.read()
        out.write_bytes(content)
        saved.append(out)
    return saved
