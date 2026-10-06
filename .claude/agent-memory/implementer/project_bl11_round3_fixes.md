---
name: bl11-round3-fixes
description: BL-11 round 3 — deleting dead code invalidates prose in more places than a reviewer enumerates, and historical vs forward-looking references need opposite treatment.
metadata:
  type: project
---

BL-11 `feature/bl11-tick-cost` round 3 applied three claim-accuracy fixes plus
the approved deletion of `_resolvable` / `_cohesive` from
`perception/group_salience.py`.

**A deletion's prose fallout is wider than the enumerated list, and the extra
entries are found by grep, not by reading the diff.** Review round 2 named
three dangling references (`group_salient_ids`'s docstring and two test
comments). A repo-wide grep found **three more that mattered**:
`_cohesive_from_terms`'s own docstring claimed two callers when only one
remained; `_resolvable_terms` attributed the old recomputation to `_cohesive`
*by name*; and the equivalence test's two `_reference_*` docstrings described
the wrappers as live. None was in the list, and all three sit in the same two
files the deletion touches.

**Why:** a reviewer enumerates what it noticed, and a docstring that says
"called by both X and Y" is false the moment X goes — but it reads as fine
until you grep for X. Same class of miss as a plan's test-impact list naming
a file that does not exist while omitting one that needed five tests reworked.

**How to apply:** after any deletion of a named function, grep the whole repo
for the name before committing, then sort the hits into two piles that get
**opposite** treatment:

- **Dated records — leave them alone.** Research notes, review documents,
  plan/implementation logs, `ROADMAP.md`/`BACKLOG.md` measurement entries and
  agent-memory files are history. Rewriting them launders the record; the
  function really did exist when they were written.
- **Forward-looking prose — it is a live defect.** Here
  `plans/player-bubble/performance.md:64` reasons about "avoiding the `O(n)`
  `_resolvable()` pass" for an unbuilt feature. That one can mislead a future
  implementer, so it gets flagged even when fixing it is out of scope (it
  belonged to another plan).

The tell is tense and purpose, not file type: the same `plans/` directory
holds both kinds.

Two further notes from the same run:

- **Deleting `_cohesive` required no import changes at all**, because every
  name it used was still used by `_resolvable_terms` or the hoisted pair loop.
  That is the mechanical form of "it was a second copy of a computation the
  live code already does" — worth checking as evidence when arguing a
  deletion, since an unchanged import block is easy to verify and hard to
  argue with.
- **Commit split that worked:** mechanism (close-test teeth), then deletion
  plus only the prose *that deletion* invalidates, then the two docstring
  corrections that were about claims rather than about the deletion. Keeping
  one file's hunks in two commits is fine — do the earlier commit's edits
  first, commit, then make the later ones, rather than trying to stage
  selectively (`git add -p` is interactive and unavailable).
