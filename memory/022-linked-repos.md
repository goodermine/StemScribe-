---
id: 022
slug: linked-repos
status: active
learned: 2026-08-09
---
Aaron works across three linked `goodermine` repos: **StemScribe-** (turns
labelled song stems into a playable sheet + engraved notation; has an optional
`--separate` mix→stems pre-stage), **aaroncodex** (vocal analysis + cleanup;
the only canonical `/10` engine is
`voxanalysis/vox-analysis/engine/analyse_song.py`), and **songbook** (a
how-to-sing songs reference library under `guides/`). aaroncodex ↔ songbook are
cross-linked by `SINGING_LIBRARY_LINK.md`, edited in both repos in the same
session by convention; songbook guides may cite raw measures but never emit
their own `/10`.

> evidence: aaroncodex PR #31 — "By convention, changes to this file are made in both repos in the same session." — session of 2026-08-09
