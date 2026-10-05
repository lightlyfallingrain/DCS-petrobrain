# Skill Candidates

Candidate patterns observed repeatedly in sessions that might warrant a dedicated skill.
Populated automatically by the SubagentStop skill-gap detector hook (see `settings.json`) after
each `dod` agent run. Reviewed and cleared during `merge-skill-review.sh`'s post-merge check —
entries are removed once created or rejected by the user.

**Resolved** (deliberately not a `##` heading — `merge-skill-review.sh` treats any
`^##` line as an open candidate and would re-trigger review on every merge)

Entries are removed once created or rejected. Rejections are recorded here so the detector's
recurring false positives are not re-litigated every merge.

- 2026-09-09 `dcs-file-investigation` — **created** as `.claude/skills/dcs-file-investigation/`.
- 2026-09-09 `partial-document-reader` — **rejected**. `sed -n 'X,Yp'` shows up only because auto
  mode prefers Bash over the `Read` tool, which already has `offset`/`limit`. Harness artifact,
  not a project pattern.
- 2026-09-09 `python-inline-file-transformation` — **rejected**. That is the `Edit` tool. A
  "apply these regex rules" skill would be strictly more dangerous than Edit's exact-match
  semantics, which fail loudly instead of silently over-matching.
- 2026-09-09 `test-and-commit-cycle` — **rejected**, already covered by `/check`, `/compile`,
  `/test`, `/stage-commit`, `/dod-check` and `/done`. The detector missed them because it only
  counts `Skill`-tool invocations and cannot see the `.md` slash commands in `.claude/skills/`.
- 2026-09-10 `venv-qualified-tool-fallback` — **fixed in place** rather than a new skill: `/check`
  and `/dod-check` now fall back to `<subproject>/.venv/bin/<tool>` when the bare `ruff`/`mypy`/
  `pytest` isn't on PATH, instead of every DoD run rediscovering the venv path itself.
- 2026-10-04 `agent-dispatch-preamble` — **rejected**. ~30x invocations across the session. Belongs
  in the existing `PreToolUse:Agent` hook rather than a skill; the hook runs for every agent launch
  and handles the security dispatch/worktree-addressing logic.
- 2026-10-04 `scratch-hillshade-render` — **rejected**. ~5x render cycles. Now mostly covered by
  `tools/inspect_terrain.py`, which automates the multi-scale hillshade snapshot pipeline.
- 2026-10-04 `harvest an agent's worktree commit` — **created** as `.claude/skills/harvest-agent-commit/` (user approved 2026-10-05).
- 2026-10-04 `sortie-log triage` — **created** as `.claude/skills/sortie-log-triage/` (user approved 2026-10-05).
