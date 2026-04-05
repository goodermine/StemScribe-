from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class Job:
    job_id: str
    created_at: datetime
    status: str = "queued"
    input_stems: List[str] = field(default_factory=list)
    detected_stem_types: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    confidence_summary: Dict[str, float] = field(default_factory=dict)
