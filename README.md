# suno-stems-to-notes

Local MVP that converts labeled Suno WAV stems into symbolic outputs:
- per-stem note-event JSON
- per-stem MIDI
- per-stem MusicXML
- beat grid / tempo / bar analysis
- keyboard-playable lead melody output
- browser MusicXML preview

## Quick run

1) Start backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

2) Start frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```

3) Upload stems in browser at `http://127.0.0.1:5173`

or run API flow from terminal:
```bash
scripts/run_local_demo.sh /path/to/stems-folder
```

## Expected per-job output tree

```text
jobs/<job_id>/
  analysis.json
  tempo.json
  lead_melody/
    lead_melody.mid
    lead_melody.musicxml
    lead_melody_notes.json
  stems/
    vocals/
      notes.json
      part.mid
      part.musicxml
      metadata.json
    bass/
      notes.json
      part.mid
      part.musicxml
      metadata.json
    drums/
      rhythm.json
      metadata.json
    other/
      notes.json
      part.mid
      part.musicxml
      metadata.json
  merged/
    preview_manifest.json
```

See `docs/development.md` for exact download commands for each output file.
