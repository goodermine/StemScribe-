"""Separation pre-stage.

The real backend downloads a few-hundred-MB model and needs a GPU to be quick,
so these tests never touch it: a fake separator writes named files and the
assertions are about the two things this module actually owns — mapping a
separator's outputs onto StemScribe roles, and refusing a non-commercial model
unless the caller opts in.
"""

from pathlib import Path

import pytest

from app.services import separate
from app.services.classify import role_from_separated_stem


class _FakeSeparator:
    """Stands in for audio_separator.separator.Separator.

    Writes a file per requested stem label into the output directory and
    returns their names, which is the shape separate_mix() consumes.
    """

    def __init__(self, out_dir: str, labels: list[str]) -> None:
        self.out_dir = Path(out_dir)
        self._labels = labels
        self.loaded_model: str | None = None

    def load_model(self, model_filename: str | None = None) -> None:
        self.loaded_model = model_filename

    def separate(self, path: str) -> list[str]:
        names = []
        for label in self._labels:
            name = f"mix_({label})_somemodel.wav"
            (self.out_dir / name).write_bytes(b"RIFFfake")
            names.append(name)
        return names


def _factory(labels: list[str]):
    return lambda out_dir: _FakeSeparator(out_dir, labels)


# --- role mapping -----------------------------------------------------------

@pytest.mark.parametrize(
    "label,role",
    [
        ("Vocals", "vocals"),
        ("Instrumental", "other"),
        ("No Vocals", "other"),
        ("Drums", "drums"),
        ("Bass", "bass"),
        ("Guitar", "guitar"),
        ("Piano", "keys"),
        ("Other", "other"),
    ],
)
def test_separator_labels_map_to_roles(label: str, role: str) -> None:
    assert role_from_separated_stem(label) == role


# --- license gate -----------------------------------------------------------

def test_default_model_is_commercial_safe() -> None:
    model = separate.default_model()
    assert model.commercial_ok is True
    assert model.license == "MIT"


def test_noncommercial_model_blocked_by_default() -> None:
    with pytest.raises(separate.SeparationLicenseError):
        separate.resolve_model("htdemucs-6s")


def test_noncommercial_model_allowed_on_opt_in() -> None:
    model = separate.resolve_model("htdemucs-6s", allow_noncommercial=True)
    assert model.stems == ("vocals", "drums", "bass", "guitar", "keys", "other")
    assert model.commercial_ok is False


def test_unknown_model_is_treated_as_unverified() -> None:
    with pytest.raises(separate.SeparationLicenseError):
        separate.resolve_model("some_random_uvr_model.onnx")
    model = separate.resolve_model("some_random_uvr_model.onnx", allow_noncommercial=True)
    assert model.license == "unknown"


# --- separation run ---------------------------------------------------------

def test_six_stem_outputs_become_role_named_files(tmp_path: Path) -> None:
    mix = tmp_path / "mix.wav"
    mix.write_bytes(b"RIFFfake")
    out = tmp_path / "input"

    result = separate.separate_mix(
        mix,
        out,
        model="htdemucs-6s",
        allow_noncommercial=True,
        separator_factory=_factory(["Vocals", "Drums", "Bass", "Guitar", "Piano", "Other"]),
    )

    names = sorted(p.name for p in result.stem_paths)
    assert names == ["Bass.wav", "Drums.wav", "Guitar.wav", "Keys.wav", "Other.wav", "Vocals.wav"]
    assert result.roles.count("keys") == 1  # Piano folded into keys
    assert result.stem_count == 6
    assert result.model == "htdemucs_6s.yaml"
    assert all(p.exists() for p in result.stem_paths)


def test_two_stem_split_folds_instrumental_into_other(tmp_path: Path) -> None:
    mix = tmp_path / "mix.wav"
    mix.write_bytes(b"RIFFfake")
    out = tmp_path / "input"

    result = separate.separate_mix(
        mix, out, separator_factory=_factory(["Vocals", "Instrumental"])
    )

    assert sorted(result.roles) == ["other", "vocals"]
    assert result.commercial is True
    assert {p.name for p in result.stem_paths} == {"Vocals.wav", "Other.wav"}


def test_missing_backend_raises_actionable_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(separate, "available", lambda: False)
    with pytest.raises(separate.SeparationUnavailable):
        separate.separate_mix(tmp_path / "mix.wav", tmp_path / "out")


def test_recovered_warning_is_specific_and_long(tmp_path: Path) -> None:
    mix = tmp_path / "mix.wav"
    mix.write_bytes(b"RIFFfake")
    result = separate.separate_mix(
        mix, tmp_path / "input", separator_factory=_factory(["Vocals", "Instrumental"])
    )
    warning = separate.recovered_stems_warning(result)
    # The pipeline's own test asserts every warning explains itself (>20 chars).
    assert len(warning) > 20
    assert "vocals_mel_band_roformer.ckpt" in warning


# --- orchestration ----------------------------------------------------------

def test_prepare_passes_real_stems_through_untouched(tmp_path: Path) -> None:
    stems = [tmp_path / "1 Drums.wav", tmp_path / "2 Bass.wav"]
    for s in stems:
        s.write_bytes(b"RIFFfake")
    resolved, note = separate.prepare_job_stems(stems, tmp_path, separate=False)
    assert resolved == stems
    assert note is None


def test_prepare_refuses_to_separate_many_files(tmp_path: Path) -> None:
    stems = [tmp_path / "a.wav", tmp_path / "b.wav"]
    for s in stems:
        s.write_bytes(b"RIFFfake")
    with pytest.raises(ValueError):
        separate.prepare_job_stems(stems, tmp_path, separate=True)


def test_prepare_separates_a_single_mix(tmp_path: Path) -> None:
    mix = tmp_path / "song.wav"
    mix.write_bytes(b"RIFFfake")
    out = tmp_path / "input"
    out.mkdir()
    resolved, note = separate.prepare_job_stems(
        [mix],
        out,
        separate=True,
        separator_factory=_factory(["Vocals", "Instrumental"]),
    )
    assert {p.name for p in resolved} == {"Vocals.wav", "Other.wav"}
    assert note is not None and "recovered" in note.lower()
