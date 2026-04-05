# API

- `GET /health`
- `POST /jobs` (multipart `files`)
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/downloads`
- `GET /jobs/{job_id}/preview-manifest`
- `GET /jobs/{job_id}/files/{path}`

`analysis.json` includes job metadata, warnings, confidence, and detected stem types.
`tempo.json` includes bpm, beats, bars, time-signature guess, confidence.
