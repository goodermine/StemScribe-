# StemScribe

Turns a song's stems into a sheet a musician can play from.

Give it labelled stems — the kind Suno and most separation tools export — and it
works out the tempo, key, structure and chords, transcribes each part, and
produces a player sheet: the chord chart bar by bar, the drum groove, and
notation for anyone who reads it.

## What comes out

Nothing here needs notation software. Every score is engraved to an HTML page
that opens in any browser and prints straight to PDF — and to a PDF directly,
where the optional PDF dependencies are installed.

| File | What it's for |
| --- | --- |
| `player_sheet.html` | **The thing to hand a musician.** Key, tempo, structure, bar-by-bar chord chart, drum groove. Prints to A4. |
| `score/lead_sheet.html` / `.pdf` | Engraved notation: melody staff with chord symbols and section marks — the singer's page. |
| `score/full_score.html` / `.pdf` | Every part on its own staff, bracketed together. |
| `stems/<part>/part.html` / `.pdf` | One part on its own, for the player of that instrument. |
| `score/song.mid` | The whole arrangement as multi-track MIDI. |
| `*.musicxml` | The same notation as data, for importing into a notation program. |
| `chart.json`, `chords.json`, `sections.json`, `key.json`, `tempo.json` | The analysis as data. |

Every `.musicxml` has an `.html` twin next to it. Open the HTML; keep the
MusicXML for when you want to edit the notation somewhere else. Free programs
that import MusicXML include MuseScore Studio (musescore.org — the desktop app
is GPL, unlike the musescore.com subscription), Frescobaldi and Denemo, and the
browser editors Flat.io and Noteflight have free tiers.

## Quick run

Everything below assumes Python 3.10+ and Node 18+.

### From the command line

```bash
cd backend
pip install -r requirements.txt
python -m app.cli ../sample_data/carved-from-stone --title "Carved From Stone"
```

It prints a summary and writes the job to `backend/jobs/<id>/`. Open
`player_sheet.html` in a browser.

### As a web app

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# terminal 2
cd frontend && npm install && npm run dev
```

Then open `http://127.0.0.1:5173`, upload the stems, and give the song a title.
Transcribing a full song takes a couple of minutes, so the job runs in the
background and the page polls until it is done.

## Naming stems

Each stem is analysed according to what it holds, so the filename matters. The
instrument name anywhere in the name is enough — `1 Drums.wav`,
`0 Lead Vocals.wav`, `gtr_L.wav` all work. Recognised: vocals, backing vocals,
drums, percussion, bass, guitar, keys, strings, brass. Anything unrecognised is
treated as a general harmony part.

Drums and percussion are kept separate on purpose: the kit is what the beat
grid is measured from.

## How much to trust it

Machine transcription of a mixed recording is never note-perfect, so every job
reports what it was confident about and warns about what it was not. Roughly:

- **Tempo, beat grid and bar lines** — reliable when a drum stem is present.
- **Chords** — good on the roots, less certain about extensions. Read the chart,
  not the seventh.
- **Key** — usually right; relative major and minor are easy to confuse, and the
  job says so when the fit was close.
- **Drum groove** — kick, snare and hi-hat separate well. Cymbal types do not.
- **Section boundaries** — detected from the audio and snapped to bar lines.
  The *names* (verse, chorus) are a guess from loudness and vocal presence.
- **Melody and part notation** — approximate. Useful as a guide to the shape of
  a line; not a substitute for a transcriber's ear.

There are no lyrics: nothing here does speech recognition.

## Docs

- `CLAUDE.md` — working notes: conventions, gotchas, and the tuning constants
  that are judgement calls.
- `docs/handoff.md` — where the work stands and what comes next.
- `docs/api.md` — endpoints and the on-disk job layout.
- `docs/architecture.md` — the pipeline, and why it makes the choices it does.
- `docs/development.md` — setup, tests, adding an instrument role.
- `docs/known-limitations.md` — what is reliable, approximate, and not attempted.
