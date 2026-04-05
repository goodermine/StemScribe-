from pathlib import Path

ALIASES = {
    "vocals": ["vocals", "vocal", "vox", "leadvox"],
    "drums": ["drums", "drum", "perc", "percussion"],
    "bass": ["bass", "sub", "low"],
    "keys": ["keys", "piano", "synth", "keyboard"],
    "guitar": ["guitar", "gtr"],
    "other": ["other", "instrumental", "music"],
}

LANE_MAP = {
    "drums": "rhythm",
    "vocals": "melody",
    "bass": "harmony",
    "keys": "harmony",
    "guitar": "harmony",
    "other": "melody",
}


def classify_stem(filename: str) -> str:
    stem = Path(filename).stem.lower()
    for canonical, aliases in ALIASES.items():
        if any(alias in stem for alias in aliases):
            return canonical
    return "other"


def lane_for_stem(stem_type: str) -> str:
    return LANE_MAP.get(stem_type, "unknown")
