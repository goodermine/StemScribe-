from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "suno-stems-to-notes"
    jobs_root: Path = Field(default=Path("jobs"))
    quantization_division: int = 2  # 1=quarter,2=eighth
    sample_rate: int = 44100


settings = Settings()
settings.jobs_root.mkdir(parents=True, exist_ok=True)
