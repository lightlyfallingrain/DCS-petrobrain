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
