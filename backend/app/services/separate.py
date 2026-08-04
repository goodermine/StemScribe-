"""Optional pre-stage: recover stems from a single mix so the rest of the
pipeline is unchanged.

StemScribe transcribes stems; it does not, on its own, pull them out of a mix.
When a song only exists as one file this stage runs first —

    mix.(mp3|wav) -> separation -> stem files -> the existing classify/analyse
    pipeline -> sheet

— and everything downstream stays exactly as it was, because the recovered
stems are just files in ``input/`` like any uploaded ones.

Ported from aaroncodex ``voxpolish/stages/separation.py``, which established the
license-safe backend: ``audio-separator`` (MIT) running a commercial-cleared
checkpoint. The hard rule carried over from there is the important part.

**Never silently run a model whose weights are non-commercial.** ``audio-
separator`` downloads models by name from its registry, and several community
checkpoints — including the most common 6-stem one, ``htdemucs_6s`` — are
CC-BY-NC. Those are fine for personal or research use and must never ship as a
default. The registry below records each model's license, and a model that is
not commercially cleared only runs when the caller explicitly opts in.

Target granularity is six stems (vocals / drums / bass / guitar / keys / other),
which maps one-to-one onto the roles ``classify.py`` already treats differently.
No 6-stem checkpoint in the audio-separator registry is confirmed commercial-
cleared today, so the shipping default falls back to the verified MIT 2-stem
model (vocals + everything-else). When a commercial 6-stem RoFormer is
confirmed, add it to ``MODELS`` with ``commercial_ok=True`` and point
``COMMERCIAL_6STEM`` at it — nothing else here has to change.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from app.services.classify import role_from_separated_stem

# audio-separator embeds the stem name in parentheses, e.g.
# ``song_(Vocals)_mel_band_roformer.wav``. The model name can carry underscores
# but not parentheses, so the last parenthesised group is the stem label.
_LABEL_RE = re.compile(r"\(([^)]+)\)")


class SeparationUnavailable(RuntimeError):
    """The audio-separator backend is not installed."""


class SeparationLicenseError(RuntimeError):
    """A non-commercial model was requested without an explicit opt-in."""


@dataclass(frozen=True)
class SeparationModel:
    """One separation checkpoint and the facts we must not lose about it."""

    key: str
    filename: str  # the name audio-separator resolves and downloads
    stems: tuple[str, ...]  # StemScribe roles it is expected to produce
    license: str
    commercial_ok: bool
    note: str = ""


# The registry. Add models here; do not hardcode filenames elsewhere. The
# license field is not documentation — resolve_model() enforces it.
MODELS: dict[str, SeparationModel] = {
    # Verified MIT, 2-stem. The safe default: a lead vocal plus one lumped
    # "instrumental", which classify.py reads as the "other" role. Pinned by
    # aaroncodex docs/models/separation-model.md (Kimberley Jensen Mel-Band
    # RoFormer, relicensed GPL-3.0 -> MIT by the author, April 2026).
    "roformer-vocals": SeparationModel(
        key="roformer-vocals",
        filename="vocals_mel_band_roformer.ckpt",
        stems=("vocals", "other"),
        license="MIT",
        commercial_ok=True,
        note="Mel-Band RoFormer (vocals) by Kimberley Jensen. Commercial use permitted.",
    ),
    # 6-stem and a clean role map, but the Demucs weights are CC-BY-NC. Wired so
    # the code path is exercised and ready; never selected unless the caller
    # passes allow_noncommercial=True, which is a personal/research grant only.
    "htdemucs-6s": SeparationModel(
        key="htdemucs-6s",
        filename="htdemucs_6s.yaml",
        stems=("vocals", "drums", "bass", "guitar", "keys", "other"),
        license="CC-BY-NC-4.0",
        commercial_ok=False,
        note="Demucs 6-source. Maps onto every role, but non-commercial weights.",
    ),
}

# The default model is chosen at call time by default_model(): a commercial
# 6-stem checkpoint when one is confirmed, otherwise the MIT 2-stem fallback.
# Leave this None until a 6-stem model's commercial license is verified on the
# target machine and recorded in the registry above.
COMMERCIAL_6STEM: str | None = None


def default_model() -> SeparationModel:
    """The model used when the caller does not name one.

    Prefers a commercial-cleared 6-stem model if the registry has one; falls
    back to the verified MIT 2-stem model so the default is always something we
    can ship.
    """
    if COMMERCIAL_6STEM is not None:
        candidate = MODELS.get(COMMERCIAL_6STEM)
        if candidate is not None and candidate.commercial_ok:
            return candidate
    return MODELS["roformer-vocals"]


def available() -> bool:
    """True when the separation backend can be imported."""
    try:
        import audio_separator.separator  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_model(name: str | None, allow_noncommercial: bool = False) -> SeparationModel:
    """Pick a model by registry key or raw filename, enforcing the license.

    A name that is not in the registry is treated as license-unknown, which is
    the same as non-commercial for gating: we will not vouch for a checkpoint we
    have not recorded.
    """
    if name is None:
        model = default_model()
    elif name in MODELS:
        model = MODELS[name]
    else:
        by_filename = next((m for m in MODELS.values() if m.filename == name), None)
        model = by_filename or SeparationModel(
            key=name,
            filename=name,
            stems=(),
            license="unknown",
            commercial_ok=False,
            note="Not in the registry; license unverified.",
        )

    if not model.commercial_ok and not allow_noncommercial:
        raise SeparationLicenseError(
            f"Separation model '{model.filename}' is licensed {model.license}, which does "
            "not clear commercial use. Pass allow_noncommercial=True to use it for personal "
            "or research work, or pick a commercial-cleared model such as "
            f"'{MODELS['roformer-vocals'].filename}'."
        )
    return model


@dataclass
class SeparationResult:
    """What a separation run produced, for the caller to analyse and report."""

    stem_paths: list[Path]
    roles: list[str]
    model: str
    license: str
    commercial: bool
    stem_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.stem_count = len(self.stem_paths)


# A factory that returns an object with ``.load_model(model_filename=...)`` and
# ``.separate(path) -> list[str]``. Real backend by default; tests inject a fake.
SeparatorFactory = Callable[[str], object]


def _default_separator_factory(out_dir: str) -> object:
    from audio_separator.separator import Separator

    return Separator(output_dir=out_dir)


def _label_of(output_name: str) -> str:
    """The stem label audio-separator wrote into a filename."""
    groups = _LABEL_RE.findall(Path(output_name).stem)
    return groups[-1] if groups else Path(output_name).stem


def separate_mix(
    mix_path: str | Path,
    out_dir: str | Path,
    *,
    model: str | None = None,
    allow_noncommercial: bool = False,
    separator_factory: SeparatorFactory | None = None,
) -> SeparationResult:
    """Split ``mix_path`` into role-named stem files under ``out_dir``.

    Each recognised output is copied to ``out_dir/<Role>.wav`` (title-cased so
    classify.py reads it back to the same role) and the mix's own copy is left
    untouched. Returns the recovered stem paths and the model provenance.
    """
    chosen = resolve_model(model, allow_noncommercial=allow_noncommercial)
    if separator_factory is None and not available():
        raise SeparationUnavailable(
            "Stem separation needs the audio-separator backend. Install it with "
            "`pip install audio-separator`, or upload stems that are already separated "
            "(Suno exports, or a separation tool's output) and analyse those directly."
        )

    mix_path = Path(mix_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    factory = separator_factory or _default_separator_factory
    separator = factory(str(out_dir))
    separator.load_model(model_filename=chosen.filename)  # type: ignore[attr-defined]
    outputs = separator.separate(str(mix_path))  # type: ignore[attr-defined]

    stem_paths: list[Path] = []
    roles: list[str] = []
    seen: set[str] = set()
    for name in outputs:
        source = out_dir / Path(name).name
        if not source.exists():
            # audio-separator may return a bare name or an absolute path.
            alt = Path(name)
            source = alt if alt.exists() else source
        role = role_from_separated_stem(_label_of(name))
        if role is None:
            continue
        # Two outputs mapping to one role (e.g. two "other"-ish stems) must not
        # collide on disk or overwrite each other's transcription.
        target_role = role if role not in seen else f"{role}_{roles.count(role) + 1}"
        seen.add(role)
        target = out_dir / f"{_title(target_role)}.wav"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        stem_paths.append(target)
        roles.append(role)

    if not stem_paths:
        raise RuntimeError(
            f"Separation with '{chosen.filename}' produced no recognised stems "
            f"(outputs: {[Path(n).name for n in outputs]})."
        )

    return SeparationResult(
        stem_paths=stem_paths,
        roles=roles,
        model=chosen.filename,
        license=chosen.license,
        commercial=chosen.commercial_ok,
    )


def _title(role: str) -> str:
    return role.replace("_", " ").title().replace(" ", "_")


def recovered_stems_warning(result: SeparationResult) -> str:
    """The line the sheet carries when its stems were recovered, not supplied.

    Separated stems carry bleed and artifacts that real (Suno / multitrack)
    stems do not, and the drum classifier in particular is sensitive to it — so
    the reader is told, rather than being left to wonder why a recovered mix
    transcribes worse than a set of clean stems.
    """
    stems = ", ".join(sorted(set(result.roles)))
    return (
        f"These stems were recovered from a single mix by {result.model} "
        f"({stems}), not supplied as separate tracks. Recovered stems carry "
        "bleed and separation artifacts, so treat the drum and bass parts in "
        "particular as more approximate than a clean multitrack would give."
    )


def looks_like_single_mix(saved: Sequence[Path]) -> bool:
    """Heuristic: a lone file is almost certainly a whole song, not a stem."""
    return len(saved) == 1


def prepare_job_stems(
    saved: Sequence[Path],
    input_dir: str | Path,
    *,
    separate: bool,
    model: str | None = None,
    allow_noncommercial: bool = False,
    separator_factory: SeparatorFactory | None = None,
) -> tuple[list[Path], str | None]:
    """Resolve the stems the pipeline should analyse.

    Returns ``(stem_paths, recovered_note)``. With ``separate`` off — the
    default — the supplied files pass straight through and ``recovered_note`` is
    ``None`` (real stems skip separation entirely). With ``separate`` on, the
    single uploaded mix is split first and the note names the model.
    """
    if not separate:
        return list(saved), None
    if not looks_like_single_mix(saved):
        raise ValueError(
            f"Separation expects one mixed file, but {len(saved)} were provided. "
            "Upload a single mix to separate it, or leave separation off to analyse "
            "files that are already stems."
        )
    result = separate_mix(
        saved[0],
        input_dir,
        model=model,
        allow_noncommercial=allow_noncommercial,
        separator_factory=separator_factory,
    )
    return result.stem_paths, recovered_stems_warning(result)
