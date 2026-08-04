"""Map stem filenames to instrument roles, and roles to musical facts.

Suno exports names like ``0 Lead Vocals.wav`` / ``5 Percussion.wav``. Matching
is done on word tokens rather than raw substrings so that "slow" does not read
as "low", and drums and percussion stay distinct — collapsing them loses the
kit, which is the stem the beat tracker depends on.
"""

import re
from dataclasses import dataclass
from pathlib import Path

# Ordered most-specific first: the first role with a matching token wins.
ROLE_TOKENS: list[tuple[str, tuple[str, ...]]] = [
    ("vocals", ("vocals", "vocal", "vox", "voice", "lead vocals", "sing")),
    ("backing_vocals", ("backing", "harmonies", "bvs", "choir", "adlib", "adlibs")),
    ("drums", ("drums", "drum", "kit", "beat")),
    ("percussion", ("percussion", "perc", "shaker", "tambourine", "conga", "bongo")),
    ("bass", ("bass", "sub", "808")),
    ("guitar", ("guitar", "gtr", "acoustic", "electric")),
    ("keys", ("keys", "key", "keyboard", "piano", "rhodes", "organ", "synth", "pad")),
    ("strings", ("strings", "string", "violin", "cello", "viola", "orchestra")),
    ("brass", ("brass", "horn", "horns", "trumpet", "sax", "saxophone", "trombone")),
    ("other", ("other", "instrumental", "music", "fx", "misc")),
]

LANE_MAP = {
    "vocals": "melody",
    "backing_vocals": "melody",
    "drums": "rhythm",
    "percussion": "rhythm",
    "bass": "bass",
    "guitar": "harmony",
    "keys": "harmony",
    "strings": "harmony",
    "brass": "harmony",
    "other": "harmony",
}


@dataclass(frozen=True)
class InstrumentProfile:
    """What the transcriber and the exporter each need to know about a role."""

    role: str
    display_name: str
    fmin_hz: float
    fmax_hz: float
    midi_program: int
    bass_clef: bool
    polyphonic: bool
    # Roles that carry the song's harmony feed chord detection; a lead vocal
    # or a shaker should not.
    informs_harmony: bool


PROFILES: dict[str, InstrumentProfile] = {
    "vocals": InstrumentProfile("vocals", "Lead Vocals", 82.0, 1050.0, 52, False, False, False),
    "backing_vocals": InstrumentProfile("backing_vocals", "Backing Vocals", 98.0, 1050.0, 52, False, True, True),
    "bass": InstrumentProfile("bass", "Bass", 31.0, 400.0, 33, True, False, True),
    "guitar": InstrumentProfile("guitar", "Guitar", 78.0, 1320.0, 27, False, True, True),
    "keys": InstrumentProfile("keys", "Keys", 55.0, 2100.0, 0, False, True, True),
    "strings": InstrumentProfile("strings", "Strings", 65.0, 1568.0, 48, False, True, True),
    "brass": InstrumentProfile("brass", "Brass", 87.0, 1175.0, 61, False, True, True),
    "other": InstrumentProfile("other", "Other", 65.0, 1568.0, 0, False, True, True),
    "drums": InstrumentProfile("drums", "Drums", 0.0, 0.0, 0, False, False, False),
    "percussion": InstrumentProfile("percussion", "Percussion", 0.0, 0.0, 0, False, False, False),
}

_SPLIT = re.compile(r"[^a-z0-9]+")


def _tokens(filename: str) -> list[str]:
    stem = Path(filename).stem.lower()
    # Suno prefixes each stem with an index; drop leading digits so "1 Drums"
    # does not tokenise into something that shadows a real name.
    parts = [p for p in _SPLIT.split(stem) if p and not p.isdigit()]
    return parts


def classify_stem(filename: str) -> str:
    tokens = _tokens(filename)
    joined = " ".join(tokens)

    for role, needles in ROLE_TOKENS:
        for needle in needles:
            if (needle in joined) if " " in needle else (needle in tokens):
                return role

    # Nothing matched a whole word. Fall back to substring matching to catch
    # run-together names like "leadvox" or "elecgtr". This is only safe because
    # no alias is a common fragment of an unrelated word — the ambiguous ones
    # ("low" for bass, "key" for keys) are deliberately not in the lists above.
    for role, needles in ROLE_TOKENS:
        for needle in needles:
            if " " not in needle and len(needle) >= 3 and needle in joined:
                return role
    return "other"


# audio-separator labels its outputs with a fixed vocabulary — (Vocals),
# (Drums), (Bass), (Guitar), (Piano), (Other), and (Instrumental) on a 2-stem
# model. These map onto roles the pipeline already treats differently; "piano"
# is the keys role, and a lumped "instrumental" is the catch-all "other".
SEPARATED_STEM_ROLES: dict[str, str] = {
    "vocals": "vocals",
    "vocal": "vocals",
    "instrumental": "other",
    "no vocals": "other",
    "drums": "drums",
    "drum": "drums",
    "bass": "bass",
    "guitar": "guitar",
    "piano": "keys",
    "keys": "keys",
    "other": "other",
}


def role_from_separated_stem(label: str) -> str | None:
    """Map a separator's stem label onto a StemScribe role.

    Falls back to the filename classifier for anything outside the known
    vocabulary, so an unexpected label still lands somewhere sensible rather
    than being dropped.
    """
    key = " ".join(label.strip().lower().split())
    if key in SEPARATED_STEM_ROLES:
        return SEPARATED_STEM_ROLES[key]
    return classify_stem(label)


def lane_for_stem(stem_type: str) -> str:
    return LANE_MAP.get(stem_type, "harmony")


def profile_for(role: str) -> InstrumentProfile:
    return PROFILES.get(role, PROFILES["other"])


def unique_key(role: str, taken: set[str]) -> str:
    """Stable output-directory name when a song has two stems of one role.

    Two guitar stems must not overwrite each other, which is what a plain
    role-keyed dict does.
    """
    if role not in taken:
        return role
    n = 2
    while f"{role}_{n}" in taken:
        n += 1
    return f"{role}_{n}"
