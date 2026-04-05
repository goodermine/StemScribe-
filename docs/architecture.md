# Architecture

## Phase 0 plan
- Build a local-first FastAPI backend with file-based job storage.
- Add three transcription lanes: rhythm (beat grid), melody (pYIN-first lead extraction), harmony (basic pitched transcription).
- Export JSON + MIDI + MusicXML via pretty_midi/music21.
- Build a React + Vite frontend for upload, result summary, downloads, and MusicXML preview with OpenSheetMusicDisplay.

## Dependencies
- Backend: fastapi, uvicorn, pydantic, librosa, numpy, scipy, soundfile, pretty_midi, music21.
- Frontend: react, typescript, vite, opensheetmusicdisplay.

## Assumptions
- Inputs are labeled WAV stems.
- Stems are short enough for synchronous MVP processing.
- 4/4 is default time signature for MVP.

## Risks
- Monophonic pitch detection may fail on noisy/polyphonic stems.
- Basic harmony transcription quality is limited in MVP.
- Browser score rendering depends on valid MusicXML generation.

## Milestones
1. Backend scaffold + health + jobs.
2. Stem ingestion/classification.
3. Beat-grid inference.
4. Lead melody extraction + exports.
5. Per-stem transcription + exports.
6. Frontend upload/results/preview.
7. Tests + docs + limitations.
