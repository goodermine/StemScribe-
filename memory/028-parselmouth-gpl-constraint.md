---
id: 028
slug: parselmouth-gpl-constraint
status: active
learned: 2026-08-09
---
The voice-quality metrics (jitter/shimmer/HNR/CPPS/formants) are computed with
`praat-parselmouth`, which is GPLv3 linked in-process — so combining it with the
proprietary engine makes a derivative work. Effect: it blocks any desktop /
plugin / on-prem / embeddable build; hosted-only neutralises it (no distribution
→ copyleft doesn't trigger). Lowest-effort fix identified: de-link and call the
standalone Praat CLI at arm's length (subprocess + a `.praat` script) — Praat's
numbers are identical to parselmouth's, so no re-calibration, and only the Praat
binary stays GPL. Surfboard (Apache-2.0) is a possible full replacement but is a
downgrade: different algorithm (rank-correlated, not numerically equal to Praat),
no clinical pedigree, and forces re-validation + re-calibration of the 50-pro
pack. Get legal sign-off before a sale.

> evidence: docs/dependency-license-audit.md — "praat-parselmouth ... GPLv3+ copyleft — forces your linked code open ... BLOCKER" — session of 2026-08-09
