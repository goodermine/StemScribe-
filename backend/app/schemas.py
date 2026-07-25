from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

StemLane = Literal["rhythm", "melody", "harmony", "bass", "unknown"]


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class TempoInfo(BaseModel):
    bpm: float
    beat_times: List[float]
    bar_starts: List[float]
    downbeat_index: int = 0
    beats_per_bar: int = 4
    time_signature_guess: str = "4/4"
    bar_count: int = 0
    timing_source: str = "unknown"
    confidence: float


class KeyInfo(BaseModel):
    tonic: str
    tonic_pitch_class: int
    mode: str
    key_name: str
    fifths: int
    confidence: float


class NoteEvent(BaseModel):
    note_name: str
    midi: int
    frequency_hz: float
    start_sec: float
    end_sec: float
    duration_sec: float
    start_beat: float
    end_beat: float
    duration_beats: float
    bar_index: int
    beat_in_bar: float
    source_stem: str
    confidence: float


class DrumHit(BaseModel):
    instrument: str
    midi: int
    start_sec: float
    start_beat: float
    bar_index: int
    beat_in_bar: float
    velocity: int
    source_stem: str
    confidence: float


class ChordSpan(BaseModel):
    symbol: str
    root: str
    quality: str
    roman: str = ""
    start_sec: float
    end_sec: float
    start_beat: float
    end_beat: float
    duration_beats: float
    bar_index: int
    beat_in_bar: float
    confidence: float


class SectionSpan(BaseModel):
    name: str
    group: str
    start_bar: int
    end_bar: int
    bar_count: int
    start_sec: float
    end_sec: float
    has_vocal: bool
    relative_energy: float


class PartSummary(BaseModel):
    key: str
    name: str
    lane: StemLane
    note_count: int
    range: str
    confidence: float


class JobStatus(BaseModel):
    job_id: str
    status: str
    title: str = "Untitled"
    input_stems: List[str] = Field(default_factory=list)
    detected_stem_types: Dict[str, str] = Field(default_factory=dict)
    duration_sec: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    confidence_summary: Dict[str, float] = Field(default_factory=dict)
    parts: List[PartSummary] = Field(default_factory=list)
    key: Optional[KeyInfo] = None
    created_at: Optional[datetime] = None


class PreviewManifest(BaseModel):
    title: str
    available_scores: List[str]
    default_score: str
    lead_sheet_path: str = ""
    full_score_path: str = ""
    lead_melody_path: str = ""
    available_downloads: List[str] = Field(default_factory=list)
    song_midi_path: str = ""
    player_sheet_html: str = ""
    player_sheet_markdown: str = ""
    summary: Dict[str, float | str | int] = Field(default_factory=dict)
