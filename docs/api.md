# API

Base URL (local): `http://127.0.0.1:8000`

## Endpoints
- `GET /health`
- `POST /jobs` (multipart `files`)
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/downloads`
- `GET /jobs/{job_id}/preview-manifest`
- `GET /jobs/{job_id}/files/{path}`

## Minimal example

Create job:
```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -F "files=@/path/to/vocals.wav" \
  -F "files=@/path/to/drums.wav" \
  -F "files=@/path/to/bass.wav"
```

List downloadable artifacts:
```bash
curl http://127.0.0.1:8000/jobs/<job_id>/downloads
```

Fetch one generated file:
```bash
curl -O http://127.0.0.1:8000/jobs/<job_id>/files/lead_melody/lead_melody.musicxml
```

## Data contracts

`analysis.json` includes:
- `job_id`
- `input_stems`
- `detected_stem_types`
- `warnings`
- `confidence_summary`
- `created_at`

`tempo.json` includes:
- `bpm`
- `beat_times`
- `bar_starts`
- `time_signature_guess`
- `confidence`
