---
name: los-hook-statics-security-approved
description: Admitting DCS statics to the LOS gate tightens it (SRTM fallback is building-blind); the real finding was a ';' in an object name dropping a whole poll.
metadata:
  type: project
---

`fix/los-hook-statics` (`1fc35c7`), deep analysis 2026-10-08. **APPROVED WITH REQUIRED FIXES.**
Full report: `plans/los-hook-statics/security-review.md`.

## The direction-of-change argument, so it is not re-derived

Admitting `coalition.getStaticObjects` to the LOS Hook **tightens** the perception gate, it does not
widen it. Before, a static's `live_los_clear` was always `None`, so `visibility.py:789` fell through
to world-model's offline `line_of_sight_clear` — **terrain-only, building-blind**, plus a permissive
12 m tolerance. After, it gets `land.isVisible` *and* a `world.searchObjects`/`SEGMENT` building test.

**How to rate a change that admits a population to an existing gate:** compare the new verdict
against *what the fallback would have said*, not against silence. Here the fallback was the
permissive one, so admission is the no-omniscience direction. "More objects reach the gate" is not by
itself a widening.

## Three things checked that each held, with the sufficient reason

- **Advisory `isExist` for statics cannot attach a stale verdict.** The join loop iterates the live
  `objects` feed and looks names up in `verdicts`; **nothing anywhere iterates `verdicts`.** Also a
  verdict makes no aliveness claim. And the test is `(not okE) or exists` — an `isExist` that *works
  and returns false* still drops the object; only a failing call admits.
- **Ownship hole costs one wasted sightline.** Barrier nobody had named: for ownship to be admitted,
  `player:getName()` must fail *while* `obj:getName()` on the same unit succeeds inside the shared
  filter. Plus the mission-scripting name (`01-A-Mi-24P011`) differs from Export's `unit_name`, which
  is the player **callsign** (`sg`), so the join finds nothing. Plus `association.py:286`.
- **Load-time splice is safe**: both spliced constants are module `local`s assigned once from
  literals, never reassigned (grep all mentions), and the chunk's `GETGLOBAL` sweep shows zero
  `SETGLOBAL` and no name the splice could introduce.

## The finding, and the generalisable lesson

A `;` in any mission-author object name raises `LineOfSightParseError` and drops **the whole poll's**
verdicts, logged at `debug`. Every object then silently falls back to the building-blind primitive —
a sortie reads as "the fix did nothing". **Probed by executing the real parser, not reasoned:** `:`
is safe (`rsplit(":", 2)`), `|` is safe (`split("|", 6)` maxsplit), `;` is fatal.

**Lesson — when a feature multiplies a population feeding a strict parser, probe the delimiter set
by execution.** The hazard pre-existed for units; what made it worth reporting is that the feature
tripled the population, added the population most likely to carry decorative author prose in its
names, and created the single shared filter that is the natural home for the one-line guard.

**Second lesson:** a feature that adds a *second* code-generation splice inherits the first one's
guard test only if someone extends it. Here `grep` over the tests found no reference to the new
splice at all. See [[dostring_in_numeric_splice_naN_clamp_gap]].

## Base-commit note

The worktree landed **diverged** from the named tip (HEAD was `main`'s tip with 8 unique commits), so
`--ff-only` was unavailable and the branch was in the main checkout being flown. `git show
<tip>:<path>` for documents plus a one-file source delta check was enough: the whole feature was one
Lua file and one module docstring, so the 252 aircraft-layer tests ran validly against the base.
