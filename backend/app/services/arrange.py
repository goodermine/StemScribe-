from pathlib import Path


def stem_output_dir(job_dir: Path, stem_name: str) -> Path:
    out = job_dir / "stems" / stem_name
    out.mkdir(parents=True, exist_ok=True)
    return out
