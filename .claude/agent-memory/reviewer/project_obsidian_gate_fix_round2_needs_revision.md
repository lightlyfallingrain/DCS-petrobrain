---
name: obsidian-gate-fix-round2-needs-revision
description: fence-strip fix for roadmap-tag-vocabulary-gate.sh introduced a silent false-negative; status-page-refresh.sh's R1 check leaves a dirty tree on failure
metadata:
  type: project
---

Round 2 of `plans/obsidian-links-and-tags` (fix commit `6f1b327`, reviewed 2026-10-06): re-mutating
the author's own three proven cases held, but going one step further than the author's test
matrix found two new gaps in the fence-stripping fix itself:

1. **An unterminated (odd-count) ``` fence silently disables tag scanning for the rest of the
   file**, in both `roadmap-tag-vocabulary-gate.sh` and `roadmap-toc.sh` — the shared
   `awk '/^```/{fence=!fence;next} fence{next}...'` toggle has no EOF check, so a forgotten
   closing fence leaves `fence` true to the end of the file. A real unknown tag placed after it is
   never flagged — exit 0, no warning. This is a **false negative introduced by a fix for false
   positives** — strictly worse in kind than what was fixed, per [[feedback_every_guard_entry_needs_a_failing_counterfactual]].
   Lesson: whenever a reviewer or fix adds a stateful strip/toggle (fence-in/fence-out, quote-in/
   quote-out), test the *unbalanced* case explicitly — it's the one case a "stub this, mutate
   that" test matrix skips by construction, because every constructed test naturally balances its
   own delimiters.
2. **`status-page-refresh.sh`'s new mechanical check (R1's real mitigation) correctly exits 1
   before publish/commit, but never reverts the file it just wrote** — leaving a dirty working
   tree that the script's own guard 2 ("dirty tree -> SKIP") then uses to silently skip every
   future invocation forever. A single bad regeneration becomes a permanent silent outage. The
   author's proof tested only the check's true/false arithmetic in isolation, never the
   consequence of taking the failing branch inside the real script. Lesson, generalizing
   [[feedback_every_guard_entry_needs_a_failing_counterfactual]]: when a fix adds a "fail loudly,
   don't publish" branch, always ask what state that branch leaves behind and whether anything
   downstream (a later guard, a cron-style re-invocation) treats that leftover state as a reason
   to never try again.

Verdict: NEEDS REVISION. Both findings were confirmed by actually mutating and re-running, not by
reading the diff.
