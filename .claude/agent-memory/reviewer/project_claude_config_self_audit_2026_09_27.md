---
name: claude-config-self-audit-2026-09-27
description: Reviewer pass on the project's own Claude Code config (X-B5) — two live UserPromptSubmit hooks had drifted from CLAUDE.md text they summarize
metadata:
  type: project
---

Ran the Reviewer half of X-B5 (todo/backlog.md) — a config/process audit of this repo's own
CLAUDE.md/AGENTS.md/agents/skills/hooks, not source code. Full report: `reviews/claude-setup-review.md`.

Headline finding, and the pattern worth remembering: the project had already fixed most of its own
2026-09-25 seed findings (stale 3-subproject lists in most CLAUDE.md sections, the graphify-corpus
mirror contradiction, dod-check's hardcoded subproject list) by the time this audit ran. What was
still live were two `UserPromptSubmit` hooks in `.claude/settings.json` / `session-start.sh` that
**inject a fixed summary of CLAUDE.md/AGENTS.md text into every turn** — one hardcodes the old
pre-2026-09-24 role sequences (no Security anywhere) and frames the *current* once-per-feature
cadence as a possible "exemption," inverting the actual rule; the other tells the agent to derive
milestones from `todo.md` sections and never mentions ROADMAP.md at all, contradicting CLAUDE.md's
explicit "todo.md no longer duplicates milestone narrative" and skipping the git-branch state check
added after a ~2000-line duplicated-implementation incident.

**Why this is a distinct class from the doc-drift CLAUDE.md already knows about**: a stale sentence
in a doc is at least readable and correctable by a human noticing it. A hook-injected string fires
silently on every prompt/session-start with nobody re-reading it — the docs' own "unenforceable rule"
diagnosis (graph-query rule, worktree rule) is about rules with no observable trigger; this is the
inverse failure — a *mechanism* that is observable and firing, but has drifted from the rule it was
built to enforce, which is arguably worse because it looks like enforcement while being wrong.
**Lesson for future audits of this project's config surface: check hook-injected `additionalContext`
strings for currency against CLAUDE.md, not just the doc files themselves** — they're a competing
source of truth that nothing forces to stay in sync on a CLAUDE.md edit.

Also flagged, lower confidence (inferred from config shape, not reproduced — no mypy available in
the audit sandbox): `commit-quality-gate.sh`'s per-subproject mypy loop doesn't `cd body-layer &&`
the way `/check`, `/dod-check`, and `posttooluse-mypy.sh` all do for body-layer's CWD-only mypy
config discovery — and world-model/aircraft-layer/audio-adapter have the identical
strict+relative-mypy_path config shape, so the same silent weakening may affect all four, just
louder for body-layer (cross-import to world-model breaks visibly) and silent for the rest (just
loses `strict`). Worth reproducing with mypy actually installed before fixing.

See [[transform_confidence_verification]]-style discipline: don't assert the mypy finding as
confirmed just because the config shapes line up — said so explicitly in the report with a repro
command.
