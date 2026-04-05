from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


StemLane = Literal["rhythm", "melody", "harmony", "unknown"]


class StemInfo(BaseModel):
    stem_name: str
    source_filename: str
    lane: StemLane
    confidence: float = 0.0


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class TempoInfo(BaseModel):
    bpm: float
    beat_times: List[float]
    bar_starts: List[float]
    time_signature_guess: str = "4/4"
    confidence: float


class NoteEvent(BaseModel):
    note_name: str
    midi: int
    frequency_hz: float
    start_sec: float
    end_sec: float
    duration_sec: float
    bar_index: int
    beat_in_bar: float
    source_stem: str
    confidence: float


class JobStatus(BaseModel):
    job_id: str
    status: str
    input_stems: List[str] = Field(default_factory=list)
    detected_stem_types: Dict[str, str] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    confidence_summary: Dict[str, float] = Field(default_factory=dict)
    created_at: datetime
    tempo: Optional[TempoInfo] = None


class DownloadEntry(BaseModel):
    name: str
    path: str


class PreviewManifest(BaseModel):
    available_scores: List[str]
    default_score: str
    available_downloads: List[str]
    lead_melody_path: str
    tempo_summary: Dict[str, float | str]
