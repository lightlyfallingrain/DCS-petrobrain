---
name: glyph-strings-unpinned-and-unextracted
description: When a sibling ASCII-render module is extracted (canvas/colour primitives moved to a shared module), check whether the actual glyph/marker characters moved too -- and mutation-test at least one to confirm a test pins it.
metadata:
  type: feedback
---

On BL-B99 (`--pov-view`, `plans/pov-view/plan.md`), `ascii_canvas.py` was extracted out of
`eyesight_view.py` to share `Canvas`/`wrap`/ANSI colour constants with the new `pov_view.py`. The
extraction was correctly move-only and reviewed clean. But it pulled colour/canvas primitives only
-- not the literal glyph strings (`"·"` seen / `"×"` not-seen, U+00B7/U+00D7) that `eyesight_view.py`
still has hardcoded inline. `pov_view.py`, written independently against the same user instruction
("use the existing symbols from the top-down graph"), reinvented plain-ASCII look-alikes (`"."`/
`"x"`) instead of importing the real ones -- a real, explicit-instruction violation that neither the
plan nor the implementation flagged as a deviation.

**Why reading missed it**: the glyphs look-alike enough in a diff/skim (`.`/`x` vs `·`/`×`) that
nothing about the mismatch jumps out from code alone, especially split across two files reviewed at
different times.

**Confirmed by mutation, not reading**: changing `pov_view.py`'s ground-truth "visible" glyph from
`"."` to `"q"` left all 21 tests in `test_pov_view.py` passing. Nothing pinned the actual character
drawn for a seen ground-truth marker -- draw-order/clipping tests only check *presence* of a believed
label (`"AR" in line`) or *absence* of the disc glyph in the unaided case, never the specific
character used for a ground-truth marker.

**Why:** a shared-primitives extraction is reviewed as "did behaviour change", and a pure move passes
that test even when it left exactly the kind of literal (a glyph string) that a sibling module most
needed to inherit sitting behind the extraction boundary, uncaptured.

**How to apply:** when reviewing an extraction meant to let a new module reuse an existing one's
primitives, check what *didn't* move, not just what did -- specifically literal strings/glyphs the
new module will need and might instead reinvent. And when a render test's job is specifically to
prove "symbol X is used for case Y" (a direct user instruction to reuse specific symbols), mutate
that literal and re-run before trusting the test suite's green as evidence the symbol is actually
pinned -- see [[verify-by-mutation]] if that memory exists, this is the same failure mode applied to
ASCII-art glyphs specifically.
