# Architecture

## The pipeline

Stages run in this order, and the order matters: each one depends on what came
before it.

1. **Classify** (`services/classify.py`) — map each stem filename to an
   instrument role, and each role to the musical facts the later stages need:
   pitch range, clef, whether it is polyphonic, whether it carries harmony.
2. **Beat grid** (`services/beat_grid.py`) — tempo, beat positions, the
   downbeat and the time signature, measured from the drum kit where there is
   one. Everything rhythmic downstream is expressed against this.
3. **Key** (`services/key_detect.py`) — chroma correlated against the
   Krumhansl-Kessler profiles. Decides how notes and chords are spelled.
4. **Chords** (`services/chords.py`) — chord templates matched against
   half-bar chroma, smoothed with Viterbi decoding.
5. **Sections** (`services/sections.py`) — boundaries from clustered
   beat-synchronous features, snapped to bar lines, then grouped so recurring
   parts share an identity.
6. **Transcription** — melody (`melody_extract.py`), pitched parts
   (`stem_transcribe.py`) and drums (`drum_transcribe.py`).
7. **Quantize** (`services/quantize.py`) — snap everything onto the musical
   grid, in beat space.
8. **Export** (`services/score_export.py`, `services/chart.py`) — notation,
   MIDI and the player sheet.

`services/pipeline.py` runs the sequence. `routes/jobs.py` is a thin HTTP layer
over it, and `app/cli.py` a thin command-line one.

## Why beat space

Every note event carries a position in beats as well as in seconds. Detectors
report seconds; notation needs beats, because a written note value depends on
how much of a bar it occupies rather than how long it lasted. Converting once,
in `utils/timing.py`, is what lets the exporter place notes in real measures
with real rests between them, and what keeps note values stable when the tempo
drifts. `BeatMap` interpolates between measured beats rather than assuming a
constant BPM.

## Decisions worth knowing about

**Tempo octave correction.** Beat trackers regularly lock onto half or twice
the tempo a player would count. `refine_tempo_octave` tests whether the
midpoints between tracked beats land on real onsets, and whether the faster
reading sits closer to the rate people naturally count at.

**Downbeats come from the low end.** Spectral flux rates a snare above a kick,
so full-band accent puts beat one on the backbeat and displaces every bar line.
Phase is chosen from an onset envelope restricted to below 150 Hz.

**Chord scoring is size-neutral.** Cosine against a normalised binary template
rewards bigger chords for free — against smeared real-world chroma an n-note
template scores sqrt(n/12). Pearson correlation is used instead: the exact
template scores 1.0, and both subsets and supersets score less.

**Chords are decided per half-bar.** Deciding per beat lets every vocal run and
cymbal crash pull the chord around.

**Notation is one voice per staff.** Notes starting together become a chord;
where one is still sounding as the next begins, the earlier is cut short. A
single staff cannot show overlapping voices legibly.

**Short gaps are held, not rested.** Pitch trackers release early and drop out
through breaths. Engraving each of those silences turns a singable line into a
thicket of thirty-second rests.

**Pitched parts are quantized to eighths, drums to sixteenths.** Below an
eighth, a detected vocal position is tracker jitter rather than rhythm.

## Dependencies

Backend: fastapi, uvicorn, pydantic, librosa, numpy, scipy, soundfile, mido,
music21. Frontend: react, typescript, vite, opensheetmusicdisplay.

MIDI is written with mido rather than pretty_midi — pretty_midi's `setup.py`
fails to build against modern setuptools, which broke installation outright.
