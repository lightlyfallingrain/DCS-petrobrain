---
name: obsidian-links-stages-4-5-final
description: Final roadmap conversions (world-model/aircraft-layer/mission-interpreter) — bare M<n> broke three gates' ID regex half-silently; fold order sets an entry's apparent status.
metadata:
  type: project
---

Stages 4 and 5 of `plans/obsidian-links-and-tags/plan.md`, 2026-10-09 — the last three roadmaps,
62 entry files, completing the split of every subproject. Things worth keeping, none of them
derivable from the diff.

## An irregular ID shape is a tax on every consumer that recognises an ID

world-model's milestones are bare `M0`…`M11`, not `WM-<n>`. `docs/DOC_CONVENTIONS.md` had already
accepted that as "recorded, not fixed" — correct, since several hundred prose mentions outweigh a
regex. **The bill arrived a stage later, in the tooling, and two thirds of it was silent.** All of
`roadmap-entry-consistency-gate.sh`, `roadmap-tag-vocabulary-gate.sh` and `roadmap-toc.sh` spelled
an entry ID `^[A-Z]+-[A-Za-z0-9.]+$`, which `M5` does not match:

| check | pre-fix behaviour on `M5.md` |
|---|---|
| dangling-link resolution | 12 **false** danglings — loud, caught at once |
| filename vs. own H1 | wrong H1 planted → reported **0 times** |
| appears in exactly one index | index row deleted → reported **0 times** |

The loud half is the trap: someone "fixes" it by deleting twelve correct links, and the two silent
checks then skip twelve files forever. Widened to
`^([A-Z]+-[A-Za-z0-9.]+|M[0-9]+(\.[0-9]+)?)$` — **enumerate the alternatives, do not loosen to
`^[A-Z]`**, which would also match a stray `README.md`/`RUN.md` in one of those directories.

**Generalisable: when a convention admits an exception to a shape, grep for every consumer that
matches that shape before the exception lands on disk.** The directory-discovery gap Stage 3 found
was the obvious one and was fine here; the shape gap was not on anyone's list.

## Fold order decides an entry's apparent status, silently

An entry file can hold two checkbox blocks. **The first one is the entry's state** for
`roadmap-toc.sh` and for any `grep '#status/done'`. Putting a `[x]` live-acceptance-debt record
above `WM-B6`'s own `[~]` block made an in-progress item read as done. So:

- item + its own superseded text → **source order** (current form is written first anyway).
- item + a folded debt record → **entry first, debt record after**, regardless of source order.
  The debt list lives at the head of a roadmap, far above what it refers to.

Found by reading `roadmap-toc.sh`'s real output after converting, not by inspecting the entry.
Worth running the TOC over a freshly converted directory purely as a status cross-check.

## A checkbox-shaped count cannot see an item written as a prose bullet

[[project_obsidian_links_stage3_todo_split]]'s lesson was the inverse: a `^- \[` block that is an
entry's own history, not a new item. Here three top-level `- **…**` bullets in world-model's
Backlog section were items with no checkbox and no ID — invisible to `grep -cE '^- \['`, and absent
from the task brief's own mint list. Two became `WM-B15`/`WM-B16`; the third was the backlog-side
duplicate of a Status entry and was folded into it rather than given a second permanent ID.
**Enumerate every top-level bullet, then judge each one.** Deriving boundaries by matching
`^- \[` *and* `^- \*\*` is what surfaced them at all.

## Read the source from `git show HEAD:<path>`, never the working tree

A conversion overwrites its own source with the pointer. Re-running the converter then sliced line
ranges out of an 8-line pointer and corrupted the entry files. Reading every source through
`git show HEAD:<path>` makes the pipeline idempotent and re-runnable, and the fidelity checker was
already doing it.

## Build the index by splicing verbatim line ranges

Stages 2 and 3 hand-rewrote index preambles and had 12/17/12 source lines to account for as "not
carried verbatim". Splicing each reusable passage in by line range — preambles, section
headings-as-sections, the whole narrative tail — gave **0 not-carried on all three files**, H1s
included. It turns "which lines did I paraphrase" from a judgement into a measurement.

## A mostly-narrative document does not split profitably — now measured twice

`mission-interpreter` saved **47%** (index 1,628 tokens against a 305-token median entry), the
lowest of the eight files converted; 28% of it is orientation narrative that must stay whole in the
index. Stage 3 saw the same at 70% on `todo/todo.md`. world-model, which is almost all entries,
saved 93%. **Split entry lists; do not go looking for prose documents to split.**

## Relevant to anyone touching root `CLAUDE.md`

Its Backlog Management prefix table (around line 367) still says only audio-adapter is split, and
four sibling rows point at files that are now 4-line pointers. Nothing is stranded — pointers
resolve — but the table is the stale-list failure `docs/DOC_CONVENTIONS.md`'s own opening warns
about. Left alone deliberately; it is the user's wording to change.
