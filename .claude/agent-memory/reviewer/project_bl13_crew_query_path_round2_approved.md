---
name: bl13-crew-query-path-round2-approved
description: BL-13 fix round APPROVED; a derived guard set must be broken in BOTH directions, and a count-agreement comment's reason was false while its conclusion held
metadata:
  type: project
---

`feature/bl13-crew-query-path`, `44cb1db..417cce6`, one commit answering round 1's single required
fix (`"One trucks"` — a plural display word folded into a singular count clause) plus four optional
corrections. **APPROVED, no required fixes.** Round 1 is
[[project_bl13_crew_query_path_review]]-adjacent and lives in the same `plans/crew-query-path/review.md`,
which is append-only across rounds ([[project_pb2_review_log_append_only]]).

## Break a derived guard set in BOTH directions, not one

The round claimed `_INFLECTING_OP_CLASSES` was *derived* from two display tables and asserted equal
to the parametrised case table, so "a later class addition fails a membership test". Dropping one
entry (my standing per-entry rule) proves each entry is pinned — but it does **not** prove the
derivation is live. The second mutation is the one that does: **add a fake class to the source
tables and confirm the cover test goes red.** Both fired here (1 failed each). A hand-written set
would survive the second and fail only the first, so the one-direction check cannot distinguish
"derived" from "a list that happens to match today".

Corollary worth keeping: the round named `OP_GROUPSOMETHING` in the guard *with its own
non-folding expectation* rather than filtering it out. That read like a placeholder; it was the one
fold-table case that went red under the `_unit_word` perturbation. **A deliberately-included
"this one doesn't fold" case can be the strongest entry in the set** — check before calling it
decorative.

## The "X, so Y" docstring, fifth-plus instance, and the measurement that found it

New code added a comment: *"'mostly' is a claim about a mix, which needs at least one unclassified
contact alongside the classified ones, so the count is never one."* Both clauses measurably false —
two classified contacts of *different* classes fire the hedge with nothing unclassified, and a
`(0,1)+(0,1)` pair speaks `"About one unit, mostly trucks"`. The **conclusion** (keep the hedge
unconditionally plural) is right on other grounds. See
[[feedback_docstring_so_clause_delete_the_mechanism]] — this is now routine enough that the method
is the finding: **running the renderer over a hand-built input beat reading the branch**, and the
branch read as obviously correct.

## Scope of a claimed "complete enumeration"

`_unit_word`'s docstring enumerates "all three of `_summary_count_clause`'s branches". That is
checkable and complete (three `return`s, all routed) — but the module has other `"unit"` literals in
a *different* renderer. **Check what unit a completeness claim scopes itself to before calling it
incomplete**; a narrower claim that is true is not a defect.

## A contract case vs a live-reachable case

The new hedged-count-of-one test defends `render_report_summary`'s dict contract; today's
`cardinality.py` vocabulary cannot produce the input (its only `lo == 0` bucket is `(0, inf)`, which
lands in a different branch). Right call for a public renderer, but worth one clause in the
docstring — otherwise the next reader hunts a sortie log for a state belief cannot currently reach.
