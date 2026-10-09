---
name: obsidian-links-stage1-review
description: Stage 0+1 of obsidian-links-and-tags (audio-adapter conversion) review — two real gate gaps found by mutation, R1's "assertion" is prose not code
metadata:
  type: project
---

Reviewed `feature/doc-conventions-audio-adapter` tip `a982bb9` (branch already checked out
elsewhere, worktree landed on unrelated `main` commit `ab18d03` — verified via `git archive`
snapshot per AGENTS.md rule 4). Content fidelity across the 577-line-to-22-file conversion was
clean on a full read; no sentence, quote or measurement lost. Verdict: APPROVED WITH MINOR FIXES.

**Two real gaps found by mutation in the new gates, both inside failure classes the task asked me
to probe for by construction rather than by reading:**

1. `roadmap-entry-consistency-gate.sh` check 3 enforces "at least one index" when both the plan's
   own R5 statement and `docs/DOC_CONVENTIONS.md`'s own "Gates" section describe it as "exactly
   one". Confirmed: adding a second index file with the same `[[AA-B2]]` link passes with exit 0.
   Invisible at 22 files (audio-adapter has one index); becomes live the moment a subproject gets
   two indexes sharing one `ROADMAP/` directory — which is body-layer's planned Stage 2 shape.
2. `roadmap-tag-vocabulary-gate.sh`'s tag regex (`#[A-Za-z][A-Za-z0-9/_-]*`) was already patched
   once this conversion (to stop matching prose ordinals like "RECOMMENDED #1") but the fix
   patched the instance, not the class: a `#` inside inline code (`` `#heading` ``, literally used
   in `docs/DOC_CONVENTIONS.md` itself) and a URL fragment (`...#section-heading`) both still
   false-positive as tags. Confirmed by appending each to a real entry file and re-running.

See [[feedback_every_guard_entry_needs_a_failing_counterfactual]] — this is the same lesson
(drop/stress each clause of a guard, don't trust a passing baseline) applied to markdown-convention
gates rather than exception tuples.

**R1 (the plan's own "dominant risk" — a consumer silently reading a stub and reporting PASS) is
mitigated entirely by prose inside a prompt handed to a `claude -p` subprocess in
`status-page-refresh.sh`, not by any code-level check.** There is no way to mutation-test this the
way the other four Stage 0 consumers were tested (regex/grep, run directly) without actually
invoking a live LLM subprocess, which I did not do. Flagged as a risk, not a required fix — the
script's three mechanical guards already bound how often it runs and it is manual/optional, not
gating. Worth remembering for any future review of an "assertion" that turns out to live inside an
agent prompt rather than in code: it cannot be verified the same way, and should be named as such
rather than silently treated as equivalent to a real gate.
