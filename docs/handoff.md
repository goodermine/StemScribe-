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

## The next piece of work: stem separation

**This is the main gap.** StemScribe cannot pull stems out of a song — it needs
them already separated. That limits it to Suno exports and multitracks. Making
it accept any MP3 is the obvious next step.

### What was established

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
separate only a mix.

### Unresolved

There is a repository `goodermine/aaroncodex` that reportedly does RoFormer
separation and is worth reading before building anything. **It could not be
reached from this session** — it was not attached as a source, and `add_repo`
returned `MCP error -32003: MCP tool call requires approval` with no prompt
arriving. Start the next session with both `goodermine/stemscribe-` and
`goodermine/aaroncodex` attached, and read that first — porting a working
implementation beats writing a new one.

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
