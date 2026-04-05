# Development

## 1) Install dependencies

### Backend
```bash
cd backend
pip install -r requirements.txt
```

### Frontend
```bash
cd frontend
npm install
```

## 2) Start the backend API

From repo root:
```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:
```bash
curl http://127.0.0.1:8000/health
```

## 3) Start the frontend UI

In a separate terminal:
```bash
cd frontend
npm run dev
```

Open: `http://127.0.0.1:5173`

## 4) Run a full job from labeled stem files

You can use either the UI upload flow or CLI curl.

### Option A: UI
1. Open the frontend.
2. Upload WAV stems (any subset):
   - `vocals.wav`
   - `drums.wav`
   - `bass.wav`
   - `keys.wav`
   - `guitar.wav`
   - `other.wav`
3. Click **Process Stems**.
4. The job page will show tempo, lead melody path, downloadable files, and MusicXML preview.

### Option B: CLI helper script
From repo root:
```bash
scripts/run_local_demo.sh /path/to/folder/containing/stems
```

If omitted, the script defaults to `sample_data/`.

## 5) How to fetch every requested output file

Assume `JOB_ID=<your_job_id>`.

### Core analysis outputs
```bash
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/analysis.json
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/tempo.json
```

### Lead melody outputs (always attempted)
```bash
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/lead_melody/lead_melody_notes.json
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/lead_melody/lead_melody.mid
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/lead_melody/lead_melody.musicxml
```

### Per-stem outputs
For each available stem folder under `stems/<stem_name>/`:
- pitched stems (`vocals`, `bass`, `keys`, `guitar`, `other`) expose:
  - `notes.json`
  - `part.mid`
  - `part.musicxml`
  - `metadata.json`
- rhythm stems (`drums`) expose:
  - `rhythm.json`
  - `metadata.json`

Example fetches:
```bash
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/stems/vocals/notes.json
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/stems/vocals/part.mid
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/stems/vocals/part.musicxml
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/stems/vocals/metadata.json
```

### Browser preview manifest
```bash
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/merged/preview_manifest.json
```

## 6) Run tests
```bash
cd backend
pytest -q
```
