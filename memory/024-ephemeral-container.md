---
id: 024
slug: ephemeral-container
status: active
learned: 2026-08-09
---
Claude Code sessions run in a Linux ephemeral remote container, not on Aaron's
own machine: `HOME=/root`, working repos cloned under `/home/user/`, and the
container is reclaimed after the session (commit + push anything worth keeping —
this is exactly why `memory/` lives in the repo). The live working copy of the
Claude Code memory sits at `/root/.claude/memory/` during a session, but the
committed repo copy is the one that survives. The `/dream` skill header's
"OS is Windows, home C:\Users\Rustwood" describes Aaron's own machine, not this
environment.

> evidence: disk in session showed `HOME=/root`, `Platform: linux`; repos under `/home/user/` — session of 2026-08-09
