from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "stemscribe"
    jobs_root: Path = Field(default=Path("jobs"))
    sample_rate: int = 22050

    # Notes are quantized in beat space rather than seconds, so these are
    # musical subdivisions: 4 means sixteenth notes in 4/4, 2 means eighths.
    #
    # Drums genuinely play sixteenths and their onsets are sharp enough to
    # place there. Sung and played pitches are not: below an eighth note the
    # detected position is pitch-tracker jitter rather than rhythm, and writing
    # it down turns a singable line into unreadable syncopation.
    quantization_division: int = 4
    melodic_division: int = 2
    hop_length: int = 512

    # Frames whose normalised salience falls below this are treated as silence
    # rather than as a pitch. Without a gate, pitch trackers emit a note for
    # every frame of a stem, including its noise floor.
    pitch_salience_floor: float = 0.10

    # Notes shorter than this fraction of a beat are dropped as tracking jitter.
    min_note_beats: float = 0.20

    # Stems are large and the finished job only needs the symbolic output.
    discard_input_audio: bool = True


settings = Settings()
settings.jobs_root.mkdir(parents=True, exist_ok=True)
