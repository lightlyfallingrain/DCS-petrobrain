---
name: obsidian-gate-round3-approved
description: Round-3 fix review of doc-conventions-audio-adapter (revert-on-failure + fence-balance) — APPROVED, with a third silent-degrade instance found but sized theoretical
metadata:
  type: project
---

Reviewed `66e7244` (`feature/doc-conventions-audio-adapter`), the round-3 fix addressing both of
round 2's required fixes: `revert_page()` in `status-page-refresh.sh` now runs on all four
post-generation exit paths (not just the one named), and a fence-balance check in
`roadmap-tag-vocabulary-gate.sh`/`roadmap-toc.sh` fails loudly on an odd delimiter count instead of
silently swallowing the rest of the file.

**Why this is worth recalling:** probing beyond the task's own named mutations found two real but
low-severity gaps the author didn't test — an untracked `$PAGE` makes `git checkout --` fail
(swallowed by `2>/dev/null || true`, no log line), and `~~~` fences are invisible to the new
backtick-only balance check. Both turned out to be **theoretical for this repo today** (verified by
`grep`: `$PAGE` is already tracked and committed; zero `~~~` fences exist anywhere in the repo), so
neither became a required fix — but the method matters more than the verdict: check a claimed-fixed
mechanism's *other* exit paths and *other* syntax variants even when the three named mutations all
pass, and settle "is this really a risk" by grepping the actual corpus rather than reasoning about
it in the abstract (the same bar the author/round-2 already applied to the declined
`#`-in-link-title case).

**The standing pattern now has three confirmed instances across two rounds**: round 2 found two
(unterminated fence swallowing tags, `FORWARD_COUNT=0` not reverting), this round's own new
`revert_page()` helper is itself a third (silently swallows a failed `git checkout` on an untracked
path). Every new guard this feature has added has had at least one failure path that said nothing —
worth treating as a repo-wide bash-gate habit (log every swallowed error) rather than re-finding it
file by file. See [[every-guard-entry-needs-a-failing-counterfactual]] for the sibling check (drop
each guard entry and rerun) — this is the same shape applied to a guard's own error-handling branch
rather than to which inputs it recognizes.

Full detail: `plans/obsidian-links-and-tags/review.md`, "Review round 3 — the fix" section.
