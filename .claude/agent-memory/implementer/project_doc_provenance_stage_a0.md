---
name: doc-provenance-stage-a0
description: Stage A0 (doc-provenance block) implementation gotchas -- no-H1 plan.md, bare plan-dir citations, blank-line idempotency
metadata:
  type: project
---

Implemented `plans/obsidian-links-and-tags/plan-document-graph.md` Stage A0: generated
`<!-- doc-provenance:start/end -->` blocks on documents cited in prose by
`audio-adapter/ROADMAP/AA-*.md`, plus the R1 union-of-IDs fix to
`roadmap-entry-consistency-gate.sh`. See `plans/obsidian-links-and-tags/implementation.md`'s
"Stage A0 (2026-10-07)" section for the full account; this file is the reusable lesson.

**No `plans/*/plan.md` in this repo has an H1.** Every one opens directly with `### Goal`. A
generator design that assumes "placed immediately after the H1" (true for research notes and
acceptance cards) needs an explicit no-H1 fallback (block at the very top of the file) the first
time it touches a plan directory. Don't assume H1 presence for a document kind until you've
actually grepped a few of them.

**A stateful block-insert/strip transform that must be idempotent is worth writing in Python, not
awk/bash**, even inside a script family (`roadmap-*.sh`) that is otherwise pure shell. Precedent
for `python3` in this family already exists (`commit-quality-gate.sh`). The complexity that
justifies it: the insertion point and the "which side has the separator blank" question differ
by document shape (H1 vs no-H1), and getting that wrong doesn't corrupt content -- it breaks
idempotency silently, which only a second real run (not code review) will catch.

**That exact bug happened here**: the first `strip_existing_block` removed at most one adjacent
blank line (an `if`, not a `while`). Correct on a clean file; wrong on the no-H1 path specifically,
where the separator blank is *after* the block rather than before it, and a buggy first run can
leave more than one blank for the "remove one" logic to under-strip on the next pass. Found only
by actually running `refresh` twice and diffing/checksumming -- not by reading the code. Fix:
strip *every* consecutive blank adjacent to the block, not just one.

**Bare-directory citations in prose (`plans/<name>/`, with or without a brace-expanded file
list) all collapse to one unit: the block always lands on `plan.md`.** This matches
plan-document-graph.md §1's own "plan directory is one unit" rule for the later generator stage,
applied one stage early. Don't special-case the one example named in a task prompt (here,
`plans/spu8-intercom/`) if the same shape recurs elsewhere in the real corpus (it did, twice) --
generalize the rule instead of writing three near-duplicate branches.

**"Cite what is there, infer nothing" is mechanically checkable against the plan's own prior
measurement.** The plan predicted "7 entries cite something, 15 cite nothing" and "~8-10 external
documents" before any code was written. A clean-room grep-based extraction reproducing those exact
counts (7 citing entries, 13 unique documents, matching per-entry citation shapes) is real
evidence the earlier estimate wasn't a guess that happened to sound right -- worth doing this
cross-check explicitly rather than treating the plan's numbers as untestable color.
