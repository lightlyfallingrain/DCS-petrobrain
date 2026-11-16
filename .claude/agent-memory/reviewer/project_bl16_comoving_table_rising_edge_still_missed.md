---
name: bl16-comoving-table-rising-edge-still-missed
description: re-running a plan's "grep every write site" instruction myself, rather than trusting the implementer's reported count, found one more uncovered site after the required fix round claimed the table was complete
metadata:
  type: project
---

Follow-up to [[bl16-comoving-table-missed-amendment]]. The implementer's fix round for that
finding (`306af5f0`) extended BL-16's Co-moving Fields table and recorded a grep re-run in
`plan.md` itself: *"ten write sites (two table-literal initialisers, eight assignments), all now
accounted for."* On re-check (the Reviewer → Implementer loop's own re-review step) I re-ran the
exact grep the plan's note names, rather than trusting the "all covered" claim, and found a
fourteenth matching line the count missed: the rising-edge reset of `apw.correction_path` to `nil`
(`Export.lua:2503`, inside `run_ai_pilot_wheel`'s `if rising then` block) — pre-existing from the
original revision commit, not introduced by this fix round, and still uncovered by any table row.

The miscounting itself is informative: the grep pattern (`"correction_substage\s*=\|correction_path
\s*="`) also matches `==` comparisons (two of them), and grouping multiple field writes inside one
code block as "one site" is a judgment call that can silently absorb a sibling site at a different
line. A reported "N sites, all covered" is a claim about *that count*, not a re-derivable fact —
counting differently (by literal assignment line vs. by code block) changes the total, and the
miscount's shape is exactly where a real site can hide.

**How to apply**: when a required fix's own verification is "re-run this grep and record the
result," don't accept the recorded count as given — re-run the grep yourself and reconcile every
line it returns (including filtering out comparisons the pattern incidentally matches) against the
table, the same way [[verify-by-mutation-per-entry]] says to drop every entry of a set rather than
trust a set-level pass. This is the second time this exact table, on this exact feature, has had an
uncovered write site survive a round that explicitly set out to find and fix that. Treat "grep
re-run, N sites, all covered" as a claim to verify, not a result to cite.
