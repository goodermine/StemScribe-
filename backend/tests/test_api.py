import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.ingest import safe_filename
from app.services.storage import resolve_within

client = TestClient(app)


def test_health() -> None:
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_upload_rejects_unsupported_types() -> None:
    r = client.post(
        "/jobs",
        files=[("files", ("notes.txt", io.BytesIO(b"not audio"), "text/plain"))],
    )
    assert r.status_code == 400
    assert "Unsupported" in r.json()["detail"]


def test_unknown_job_returns_404() -> None:
    assert client.get("/jobs/does-not-exist").status_code == 404
    assert client.get("/jobs/does-not-exist/chart").status_code == 404
    assert client.get("/jobs/does-not-exist/sheet").status_code == 404


def test_uploaded_filenames_cannot_escape_the_job_directory() -> None:
    """The client controls this string and it is used to build a path."""
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("/absolute/evil.wav") == "evil.wav"
    assert safe_filename("") == "stem.wav"


def test_download_paths_cannot_escape_the_job_directory(tmp_path: Path) -> None:
    root = tmp_path / "job"
    (root / "score").mkdir(parents=True)
    (root / "score" / "lead_sheet.musicxml").write_text("x")
    (tmp_path / "secret.txt").write_text("private")

    assert resolve_within(root, "score/lead_sheet.musicxml") is not None
    assert resolve_within(root, "../secret.txt") is None
    assert resolve_within(root, "../../etc/passwd") is None


def test_download_traversal_is_rejected_over_http() -> None:
    r = client.get("/jobs/any-job/files/../../../etc/passwd")
    assert r.status_code == 404


@pytest.mark.parametrize("suffix", [".wav", ".flac", ".mp3"])
def test_supported_suffixes_are_accepted_by_the_validator(suffix: str) -> None:
    from app.services.ingest import SUPPORTED

    assert suffix in SUPPORTED


def test_job_is_accepted_and_reports_a_status(synthetic_song, tmp_path, monkeypatch) -> None:
    """Analysis runs in the background, so the POST must return immediately."""
    monkeypatch.setattr(settings, "jobs_root", tmp_path)
    stems = sorted(synthetic_song.glob("*.wav"))[:1]

    with TestClient(app) as background_client:
        files = [("files", (p.name, p.read_bytes(), "audio/wav")) for p in stems]
        r = background_client.post("/jobs", files=files, data={"title": "Test"})
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        assert r.json()["status"] in {"queued", "processing"}

    status = client.get(f"/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"queued", "processing", "completed", "failed"}
