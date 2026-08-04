# Handoff

State of the work as of the branch `claude/song-notes-player-sheet-1pwry3`,
open as draft PR [#3](https://github.com/goodermine/StemScribe-/pull/3).

## Where things stand

The repository started as a scaffold that could not complete a job on real
audio. It now runs end to end on the sample song and produces a sheet a
guitarist or drummer can play from.

Three commits on the branch:

1. `c694f82` — made it run, rebuilt the transcription core, added key, chord
   and structure analysis.
2. `dad54e1` — tuned the analysis against the real 3.5-minute song, rebuilt the
   frontend and the docs.
3. `f437789` — engraved every score so reading a part needs no notation
   software.

88 tests pass. A seven-stem song takes about two minutes.

### Output on the sample song

```
F minor · 117 BPM · 4/4 · 100 bars · 3:28

Intro        1–4     F5  Dbmaj7
Verse 1      9–16    F5  Ab  Dbmaj7  C
Chorus       73–87   C5  F7  Bbm7  Dbmaj7  C  Fm7
Outro        88–100  Dbmaj7  C  Fm7  Bbm7  Fm  Gb5

        1...2...3...4...
hihat   x---X---x-X-X-X-
snare   ----x-------x---
kick    x-X---X-x-------
```

Every chord is diatonic to F minor; the groove is a plain backbeat. Both are
consistent with the audio, which is the main evidence the analysis is sound.

## What was actually wrong, in case it matters later

Three things stopped the original code dead: `pip install` failed on
`pretty_midi`, `POST /jobs` crashed on librosa's tempo array, and MusicXML
export threw on unnotatable durations. Behind those, the transcription was
placeholder-grade — one note emitted per analysis frame including silence, the
drum stem silently discarded by a role-key collision, and start times thrown
away at export so nothing lined up with the audio.

Full detail is in the commit messages and in the PR description. `CLAUDE.md`
carries the parts that are still live constraints.

## Stem separation — implemented as an optional pre-stage

**Status: built and unit-tested; not yet run end to end against a real model.**
This was the main gap — StemScribe could only read stems that were already
separated. It now has a `--separate` path that recovers stems from a single mix
first, following the aaroncodex implementation the previous handoff pointed at.

### What landed

- `services/separate.py` — the pre-stage. A license-gated model registry, an
  `available()` backend check, `resolve_model()` that refuses a non-commercial
  model unless the caller opts in, `separate_mix()` that runs `audio-separator`
  and renames its outputs to role-named stem files, and `prepare_job_stems()`
  that both callers share.
- `classify.py` — `role_from_separated_stem()` maps the separator's labels
  (Vocals / Drums / Bass / Guitar / Piano / Other / Instrumental) onto roles.
- `routes/jobs.py` — a `separate` form flag; the pre-stage runs in the
  background job before analysis. `cli.py` — `--separate`, `--model`,
  `--allow-noncommercial-model`, and it now accepts a single file, not just a
  folder.
- `pipeline.run_analysis` takes a `recovered_note`; when stems were recovered
  the sheet carries a warning saying so and why it matters.
- `tests/test_separate.py` — a fake separator exercises the role map, the
  license gate and the orchestration without downloading a model.

### The licensing decision, carried over from aaroncodex

aaroncodex deliberately rejected Demucs and the UVR defaults because their
weights are **CC-BY-NC (non-commercial)**, and standardised on the MIT Mel-Band
RoFormer via `audio-separator`. `separate.py` keeps that rule as code: the
default model is commercial-cleared, and `htdemucs_6s` (the obvious 6-stem
option) is wired but gated behind `allow_noncommercial=True`.

### What is left — the one real open question

The **target is 6 commercial-safe stems**, but no 6-stem checkpoint in the
audio-separator registry is *confirmed* commercial-cleared, so the shipping
default falls back to the verified MIT **2-stem** model (vocals + everything
else). That is legally safe but only partly useful: a lumped "instrumental"
stem does not give the pipeline separate drums or bass. Closing this needs
someone to confirm a 6-stem RoFormer's license on the target machine, then set
`COMMERCIAL_6STEM` in `separate.py` — the code path is already there.

Also still to do, all needing the real backend a headless session can't run:
run one mix end to end, record the model SHA-256 (as aaroncodex's
`docs/models/separation-model.md` prescribes), and measure CPU wall-clock.

### What was established (background)

- **Demucs** (Meta) splits a mix into vocals / drums / bass / other, and
  `htdemucs_6s` adds guitar and piano — but its weights are **CC-BY-NC**.
- **RoFormer** is better and is the current state of the art. `BS-RoFormer` and
  `Mel-Band RoFormer` beat Demucs on quality. A `BS-RoFormer SW` variant does
  six stems — vocals, drums, bass, guitar, piano, other — which maps directly
  onto roles `classify.py` already treats differently.
- Mel-band projection improves vocals, drums and "other" over plain band-split,
  but is **worse for bass**, where band-split handles low frequencies better.
  The strongest setups ensemble different models per stem.
- [`python-audio-separator`](https://github.com/nomadkaraoke/python-audio-separator)
  (`pip install audio-separator`) is the clean programmatic route: Python API,
  supports RoFormer/MDXC/Demucs/VR, downloads checkpoints itself, falls back to
  CPU.

- **Demucs** (Meta, MIT) splits a mix into vocals / drums / bass / other, and
  `htdemucs_6s` adds guitar and piano.
- **RoFormer** is better and is the current state of the art. `BS-RoFormer` and
  `Mel-Band RoFormer` beat Demucs on quality. A `BS-RoFormer SW` variant does
  six stems — vocals, drums, bass, guitar, piano, other — which maps directly
  onto roles `classify.py` already treats differently.
- Mel-band projection improves vocals, drums and "other" over plain band-split,
  but is **worse for bass**, where band-split handles low frequencies better.
  The strongest setups ensemble different models per stem.
- [`python-audio-separator`](https://github.com/nomadkaraoke/python-audio-separator)
  (`pip install audio-separator`) is the clean programmatic route: Python API,
  supports RoFormer/MDXC/Demucs/VR, downloads checkpoints itself, falls back to
  CPU.

### Shape of the integration

A pre-stage; everything downstream is untouched.

```
mix.mp3 → separation → six stems → existing classify/analyse pipeline → sheet
```

Work needed: a `services/separate.py`; a mapping from the separator's output
filenames onto StemScribe roles in `classify.py`; a flag on the job so real
stems skip separation entirely; and a warning on the sheet when stems were
recovered rather than supplied, since artifacts degrade transcription.

### Costs to be honest about

- **Slow on CPU.** HTDemucs is 10–15 minutes per track on CPU; RoFormer is
  heavier and runs a pass per stem. Plausibly 30–60 minutes for a 3.5-minute
  song without a GPU, against the current two minutes. A GPU makes it a couple
  of minutes.
- **Model downloads** of a few hundred MB on first run.
- **Separated stems are worse than real ones.** Suno's exports are the actual
  rendered tracks. Anything recovered from a mix carries bleed, which the drum
  classifier in particular is sensitive to.

Recommendation: keep separation optional. Use real stems when they exist,
separate only a mix. `separate=False` is the default on every path.

### Resolved: the aaroncodex implementation was read and ported

`goodermine/aaroncodex` was reachable this session. The separation code lives in
`voxpolish/src/voxpolish/stages/separation.py` (the `audio-separator` +
Mel-Band RoFormer pattern) with the licensing rationale in
`docs/models/separation-model.md` and `docs/separation-model-swap-plan.md`. That
pattern — the pinned model, the "never silently substitute" guard, the
`available()` check — is what `services/separate.py` is ported from. The one
difference: aaroncodex needs a 2-stem vocal/instrumental split for its scoring;
StemScribe wants per-instrument stems, so this port generalises the same shape
to a multi-stem, license-gated registry.

## Known weak spots

Ranked by how likely they are to matter.

1. **Section names are a guess.** Boundaries are detected from audio and snapped
   to bar lines, and those are sound. The labels — verse, chorus, bridge — come
   from loudness and vocal presence, and on the sample song produced six
   "verses" and one "chorus", which is almost certainly not the real structure.
   Doing this properly needs repetition analysis over the chord progression
   rather than over averaged features.
2. **Key confidence is 0.39** on the sample. F minor is very likely right — the
   chord vocabulary supports it — but a key and its relative major are close in
   chroma, and the job says so rather than hiding it.
3. **Tuning constants generalise unknown.** Everything in the table in
   `CLAUDE.md` was fitted to one real song plus the synthetic fixture. A second
   real song of a different genre is the cheapest way to find out what breaks.
4. **Cymbal types are not distinguished.** Everything bright is called a
   hi-hat. Separating crash from ride from open hat needs decay measurement
   across following hits.
5. **Power chords export as MusicXML `kind=none`**, so some notation software
   shows "F" where the chart correctly says "F5".
6. **The frontend has only been typechecked and built**, not exercised against a
   running backend. The polling flow is untested end to end.
7. **No lyrics.** Would need speech recognition on the vocal stem — a separate
   piece of work, and the thing that would most improve the singer's page.

## Starting the next session

Attach both repositories. `CLAUDE.md` loads automatically and carries the
constraints that are easy to break — the beat-space rule, the banned dependency,
the chord-scoring maths, and the tuning constants.

Run `pytest -q` first. If it passes, the analysis is in the state described
here.
