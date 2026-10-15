---
name: tuning-generator-comment-extraction
description: generating a one-sentence description from this project's hand-wrapped #: provenance comments has two real failure modes, both found only by running the generator
metadata:
  type: project
---

Building `body-layer/tools/generate_defaults.py` (X-T26, `plans/configurable-constants/plan.md`
Stage 1) to lift "the first sentence of the `#:` block above the constant" surfaced two failure
modes that static reasoning did not predict — both only showed up by actually running the generator
and reading its output:

1. **A shared intro paragraph followed by several per-item bullets, no blank line between them.**
   `belief/attack_run.py`'s three attack-run gates each have their own bullet, but the naive "walk
   upward collecting contiguous `#:` lines, stop at the first non-`#:` line" rule merges the *whole*
   shared-intro-plus-all-bullets block for whichever constant is declared first, because there is
   no non-`#:` line between the shared intro and the first bullet. Fix: also stop at a **blank
   `#:` line** (`#:` with nothing after it) — this project already uses that as its own
   paragraph-break convention in `#:` blocks, so it's a real signal, not an invented one. This
   fixed the 2nd/3rd bullet in every case (each is already preceded by the *previous constant's
   assignment statement*, a non-`#:` line) but not the first — `LOWRES_ANGULAR_RADIUS_RAD` has no
   code line above it, only more shared prose, so it still needed its own hand-written one-line
   description (matching what the plan already required for `MEDRES`/`HIRES`, which share
   `LOWRES`'s block).
2. **A backtick-quoted dotted identifier wrapped across two comment lines**
   (`` #: ... `estimation. `` / `` #: BEARING_SIGMA_DEG`... ``) reads as a false sentence break once
   rejoined with a naive space-join, because the result looks like "...estimation. BEARING_SIGMA_DEG"
   — period, space, capital letter. Fix: track backtick parity across the accumulated joined text;
   while a backtick span is open (odd count so far), join the next line with no space instead of one.

**Why this matters beyond this one script:** any future tool that reconstructs prose from this
project's `#:` convention (2554+ lines in body-layer alone) will hit the same two shapes, because
both come from how this project *writes* `#:` comments (paragraph breaks via blank `#:` lines;
long identifiers wrapped at the 79-ish column limit), not from anything specific to
`generate_defaults.py`.

**How to apply:** when writing a comment-scraping tool against this codebase's `#:` convention,
treat "stop at a blank `#:` line" and "backtick-parity-aware line joining" as baseline requirements,
not edge-case polish — verify by actually running the tool against a handful of real multi-bullet
blocks and backtick-wrapped identifiers before trusting the output, the same way this one needed a
second pass after the first draft silently mis-attributed `MEDRES`'s own bullet as `LOWRES`'s
description.

See also [[tuning-crosskey-coupling]], the sibling lesson from the same X-T26 implementation.
