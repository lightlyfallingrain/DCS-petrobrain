---
name: claude_setup_audit_2026_09_27
description: Full audit of the Claude Code operating environment (settings.json, scripts, skills, agents) — deny-list bypasses and gate gaps found and demonstrated
metadata:
  type: project
---

Full report: `reviews/claude-setup-security.md` (this commit).

Key demonstrated findings, so a future pass doesn't re-derive them:

- **`Bash` deny-list entries are literal-prefix matches, not semantic.** `rm -fr` (flags reordered),
  `git worktree remove -f` (short flag alias), and `git -C <dir> reset --hard` (global flag inserted
  before the subcommand) all bypass their corresponding deny rule in `.claude/settings.json` and were
  each demonstrated safely (nonexistent paths / a throwaway scratch repo, never this project's
  checkout). The harness *does* correctly parse chained/multi-line commands structurally (confirmed:
  `rm -rf` embedded mid-script, and `curl` after a blank line, were both denied) — the gap is
  specifically flag-form/alias awareness, not chaining. Fix direction: an argv-aware PreToolUse hook,
  not more deny-pattern strings (that's always one rewrite behind).
- **`agent-memory-path-gate.sh` string-prefix-matches the raw `file_path`**, so a path containing
  `../../../` after `.claude/agent-memory/` still matches the `"$root"*` case and is allowed, even
  though it resolves outside the repo. [[project_wire_boundary_type_check_not_range_check]] is the
  same *shape* of gap (checks form, not full domain) recurring in a different file.
- **No file in this repo tells Investigator (or Architect, when it invokes Investigator) to treat
  fetched ED-forum/Hoggit-wiki/GitHub content as data rather than instructions.** This is the
  project's one real external-content ingestion path. Chains into `merge-skill-review.sh`, which
  replays `.claude/agent-memory/skill-candidates.md` (populated by an unsupervised haiku
  `SubagentStop` pass over the whole session transcript) into a later session's `additionalContext` —
  a stored/delayed data→instruction path with no "this is quoted data" framing, unlike `gq.sh` which
  already does this framing correctly for graph output.

Next security pass on this environment: check whether the deny-list fix landed as a hook (preferred)
vs. more string patterns, and re-run the three bypass demonstrations above against the new
settings.json.
