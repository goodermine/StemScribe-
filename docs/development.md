# Development

## Setup

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

Every dependency ships wheels for Python 3.10–3.13, so no compiler is needed.

Scores are engraved to browser-readable HTML out of the box. For PDF output as
well:

```bash
pip install cairosvg pypdf
```

That needs a system cairo library, which is why it is optional rather than in
`requirements.txt`. Without it, every score still gets an HTML page that prints
to PDF from a browser.

## Running a job without the server

```bash
cd backend
python -m app.cli ../sample_data/carved-from-stone --title "Carved From Stone"
```

Options: `--title`, `--out` (write the job somewhere specific), `--job-id`.

It prints the key, tempo, structure and per-part note counts, plus any
warnings, and tells you where the sheet was written.

## Running the app

```bash
cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev     # http://127.0.0.1:5173
```

The frontend reads `VITE_API_BASE` if you need to point it elsewhere; it
defaults to `http://127.0.0.1:8000`. The backend allows CORS from the Vite dev
server only.

## Tests

```bash
cd backend && pytest -q
```

The suite runs against a synthetic song built in `tests/conftest.py` — four
bars of C–Am–F–G at 120 BPM with drums, bass, keys and a vocal line, generated
as real audio. Because its key, tempo and progression are known in advance, the
assertions are about musical correctness (this key, this tempo, this
progression, a plausible number of notes) rather than about whether files were
written.

When you change an analysis stage, that fixture is the regression guard. If a
tuning change makes the synthetic progression come out wrong, it is wrong.

## Adding an instrument role

1. Add its filename tokens to `ROLE_TOKENS` in `services/classify.py`.
2. Add a `LANE_MAP` entry — `melody`, `harmony`, `bass` or `rhythm`.
3. Add an `InstrumentProfile`: pitch range, MIDI program, clef, whether it is
   polyphonic, and whether it should inform chord detection. A lead vocal
   should not; a rhythm guitar should.
4. Add a case to `test_classify.py`.

## Performance

A seven-stem, three-and-a-half-minute song takes about 90 seconds. Most of that
is pYIN on the vocal and bass stems. Decoded audio is cached across stages
(`utils/audio.py`), since several stages read the same stems.

Analysis runs at 22050 Hz for speed. Drums are the exception and load at 44100 —
telling a hi-hat from a snare depends on energy above 8 kHz, which does not
survive the lower rate.
