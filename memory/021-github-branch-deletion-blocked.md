---
id: 021
slug: github-branch-deletion-blocked
status: active
learned: 2026-08-09
---
Remote branch deletion is not possible from the Claude Code session
environment: `git push origin --delete` is dropped by the git proxy
("unexpected disconnect while reading sideband packet"), and the REST
`DELETE .../git/refs/heads/...` returns 403 "Write access to this GitHub API
path is not permitted through this proxy." The GitHub MCP server has no
delete-branch tool. Normal pushes and PR merges DO work. To remove a merged
branch, point Aaron at the PR page's "Delete branch" button or give him the
`git push origin --delete <branch>` command to run himself — don't waste
retries trying from the session.

> evidence: "Write access to this GitHub API path is not permitted through this proxy." (403 on DELETE /git/refs) — session of 2026-08-09
