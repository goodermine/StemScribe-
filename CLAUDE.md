# StemScribe — working notes

Turns a song's stems into a sheet a musician can play from. Give it labelled
stems, it works out tempo, key, structure and chords, transcribes each part, and
produces a player sheet plus engraved notation.

**It does not separate stems.** It takes stems that are already separated (Suno
exports, or the output of a separation tool). Adding separation is the main open
piece of work — see `docs/handoff.md`.

## Layout

```
backend/app/
  cli.py                  run a job without the server
  config.py               tuning constants live here
  routes/jobs.py          HTTP layer, thin
  services/
    pipeline.py           runs the whole sequence — start here
    classify.py           filename → instrument role → musical facts
    beat_grid.py          tempo, beats, downbeat, meter
    key_detect.py         key from chroma profiles
    chords.py             chord estimation
    sections.py           song structure
    melody_extract.py     monophonic transcription (pYIN)
    stem_transcribe.py    polyphonic transcription (CQT)
    drum_transcribe.py    onsets → kick/snare/hi-hat
    quantize.py           snap to the musical grid, in beat space
    score_export.py       MusicXML + MIDI
    engrave.py            MusicXML → browser-readable pages
    chart.py              the player sheet
  utils/timing.py         BeatMap — seconds ↔ beats
frontend/                 React + Vite, polls the background job
sample_data/carved-from-stone/   seven real stems, the worked example
```

## Running things

```bash
cd backend && pip install -r requirements.txt
python -m app.cli ../sample_data/carved-from-stone --title "Carved From Stone"
pytest -q
```

A seven-stem, 3.5-minute song takes about two minutes. The server path
(`uvicorn app.main:app`) runs the same pipeline in the background and polls.

## Conventions

**Work in beat space, not seconds.** Every note event carries `start_beat` /
`duration_beats` alongside the wall-clock times. Notation depends on how much of
a bar a note occupies, not how long it lasted. `utils/timing.py` does the
conversion once; do not reintroduce second-based rhythm logic.

**Comments explain why, not what.** The non-obvious decisions in this codebase
are all consequences of something that broke. Those comments are load-bearing —
several encode a fix that is not obvious from the code alone.

**Confidence values must be computed.** The original code returned hardcoded
literals (0.75, 0.6, 0.55) presented as measurements. A test now asserts they
are not all identical.

**Warnings must explain themselves.** A test asserts every warning is over 20
characters. "Low confidence" is not a warning; saying what was uncertain and
what the reader should therefore double-check is.

## Gotchas worth knowing before you change something

**`pretty_midi` is banned.** Its `setup.py` does not build against modern
setuptools and made `pip install -r requirements.txt` fail outright. MIDI is
written with `mido` in `utils/midi_io.py`. Do not add it back.

**Drums load at 44100 Hz, everything else at 22050.** Telling a hi-hat from a
snare depends on energy above 8 kHz, which is above Nyquist at the lower rate.
See `DRUM_SAMPLE_RATE` in `drum_transcribe.py`.

**music21 spells flats with `-`, not `b`.** `harmony.ChordSymbol("Ebmaj7")`
raises; it has to be `E-maj7`. `to_music21_figure()` handles this.

**music21 refuses negative offsets.** Notes detected before the first downbeat
have to be clamped into bar one — `score_offset()` does it.

**Durations must be snapped before export.** Raw detected durations are
arbitrary floats and music21 rejects them with "Cannot convert inexpressible
durations". This killed every export in the original code.

**librosa returns tempo as an array** in ≥0.10. `_as_scalar()` in
`beat_grid.py`.

## Tuning constants — judgement calls, change with evidence

These were tuned against one real song plus the synthetic fixture. They are the
most likely things to be wrong on other material.

| Constant | Where | Why this value |
| --- | --- | --- |
| `TRANSITION_PENALTY = 0.30` | `chords.py` | Below ~0.05 chords flicker; above ~0.4 real changes get swallowed. Stable across a wide band on the fixture. |
| `METER_PRIOR` | `beat_grid.py` | A plain backbeat fits 2/4 better than 4/4 on accent contrast alone. The prior stops that. |
| `GROOVE_CORE / GROOVE_OCCASIONAL` | `chart.py` | 0.60 / 0.20 share of bars. Below 0.20 fills start appearing as groove. |
| `MIN_SECTION_BARS = 4` | `sections.py` | Shorter than this is a fill, not a section. |
| `melodic_division = 2` | `config.py` | Eighths. Below an eighth, a detected vocal position is tracker jitter, not rhythm. |
| `GAP_FILL_BEATS = 1.0` | `score_export.py` | Holds notes over tracker dropouts. Without it the melody engraves as a thicket of 32nd rests. |

**Chord scoring is size-neutral on purpose.** `score_templates()` uses Pearson
correlation. Cosine against an L2-normalised binary template rewards bigger
chords for free (an n-note template scores `sqrt(n/12)` against flat chroma) —
that put a seventh chord on 371 of 398 beats. Contrasting inside-vs-outside mean
overcorrects toward power chords. Do not "simplify" this back to a dot product.

## Testing

`tests/conftest.py` generates a synthetic song as real audio — C–Am–F–G at
120 BPM, four stems, known key and progression. **That fixture is the regression
guard.** If a tuning change makes its progression come out wrong, the change is
wrong. Assertions are about musical correctness, not about whether files were
written.

The old suite asserted nothing musical: its MusicXML test passed only because
the exporter ignored start times.

## Honesty about output

Machine transcription of a mixed recording is never note-perfect, and the sheet
says so. Section *boundaries* are detected; section *names* (verse/chorus) are
inferred from loudness and vocal presence and are labelled as a guide. Keep that
distinction — do not present inferred labels as measured facts.
