# Memory index

Durable facts, preferences and corrections learned from Claude Code working
sessions — one small markdown file per fact, indexed here. Read this at session
start.

**Why this lives in the repo, not `~/.claude/`:** sessions run in ephemeral
containers — the home directory is reclaimed, the repo is pushed. A memory that
is not committed does not exist.

Facts `021`–`029` are the **shared cross-repo session memory**, mirrored across
StemScribe-, aaroncodex and songbook so it travels whichever repo a session is
in. IDs are aligned with the aaroncodex memory system, which is the primary copy
(it also holds singer-specific facts 001–020 that are not mirrored here).

_Last updated: 2026-08-09_

## Facts

- `021-github-branch-deletion-blocked.md` — can't delete remote branches from the session; use the PR page
- `022-linked-repos.md` — the three linked goodermine repos: StemScribe-, aaroncodex, songbook
- `023-commercial-safe-licensing.md` — default to MIT/commercial-cleared; gate non-commercial behind opt-in
- `024-ephemeral-container.md` — sessions run in a Linux ephemeral container (HOME=/root); commit to persist
- `025-act-on-terse-commands.md` — act decisively on short commands; confirm only irreversible/ambiguous steps
- `026-aaroncodex-product-shape.md` — concise product summary of aaroncodex
- `027-exploring-aaroncodex-sale.md` — exploring a sale of aaroncodex (figures kept out of the note)
- `028-parselmouth-gpl-constraint.md` — GPL parselmouth blocks off-server builds; de-link to the Praat CLI
- `029-machine-and-artist-name.md` — artist name Rustwood; own machine Windows, home C:\Users\Rustwood
