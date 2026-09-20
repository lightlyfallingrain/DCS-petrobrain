# Archived plans

**Kept, not deleted — and excluded from search indexes.** Everything here is finished or
superseded work whose reasoning may still be worth reading, but which nothing current cites.

## What "archived" means here

A plan lands here when **no current document and no code docstring references it**. That is a
deliberately strict test, and it archives far less than expected: of 51 plan directories, 44 are
actively cited — most of them from `.py` docstrings rather than from other markdown, because this
project puts design reasoning next to the code it explains. The `plans/` tree is live reference
material, not a graveyard.

## Why the exclusion matters

This directory exists to be **left out of knowledge-graph and search indexes** (`graphify` and
anything like it). A retrieval tool that surfaces a superseded plan with the same confidence as a
current one is worse than one that misses it: the reader cannot tell which they are holding.

## What archiving does NOT solve

Most staleness in this project is **inside living documents**, not in dead ones — a plan that is
90% current with one overturned decision in the middle. Moving folders cannot separate those.
That case is handled by convention instead: **a superseded section opens with a pointer to what
replaced it** (see `docs/PROCESS.md`), so the correction travels with the original rather than
sitting somewhere above it.

## Contents

| Plan | Why archived |
|---|---|
| `association-namespace-mismatch` | fixed; behaviour now described in `belief/association_over_time.py` |
| `brain-layer` | early sketch, predates the current layering; not started |
| `contact-report-wording` | delivered; the wording rules live in `belief/speech.py` |
| `m1-coordinate-transform` | world-model M1, complete |
| `m4-dcs-elevation` | world-model M4, complete |
| `roadnet-resync-false-positive` | fixed |
| `vision-range-calibration` | superseded by the 2026-09-17 lossless-PNG pass; the constants and the binocular premise live in `perception/visibility.py` |
