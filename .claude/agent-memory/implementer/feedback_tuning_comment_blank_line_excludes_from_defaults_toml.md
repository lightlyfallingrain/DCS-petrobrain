---
name: tuning-comment-blank-line-excludes-from-defaults-toml
description: A blank `#:` line above a tuning.real/whole/... call is a paragraph break the generator stops at -- only the paragraph directly adjacent to the assignment (and only that paragraph's first sentence) ever renders into config/defaults.toml
metadata:
  type: feedback
---

When writing a `#:` doc-comment above a `tuning.real(...)`/`tuning.whole(...)`/etc. declaration in
body-layer, `tools/generate_defaults.py`'s `_comment_block_above` walks upward from the assignment
and **stops at the first blank `#:` line it meets**. Anything above that blank line is invisible to
the generator, full stop -- not deprioritised, not included-but-truncated, simply never read.

**What this causes if missed:** writing two `#:` paragraphs -- a first one stating what the
constant does/the dangerous direction, a blank `#:` line, then a second paragraph with
measurement/provenance detail -- and expecting the renderer to use the first. It instead renders
**the second paragraph's first sentence**, because that is the one paragraph actually adjacent to
the assignment. The rendered `config/defaults.toml` line reads as a garbled mid-paragraph fragment
("Measured, not guessed, but a bracket rather than a point** (`docs/...`" -- missing the opening
clause the first paragraph was supposed to supply), which `root CLAUDE.md`'s "read the rendered
file, not your source comment" rule exists precisely to catch, but which is easy to miss if you
only check that the generator ran without error.

**How to apply:** when a constant's rationale needs multiple sentences, write them as **one
contiguous `#:` block with no blank line**, and make sure the literal first sentence (ending in a
real sentence-terminating period, not swallowed by `**bold**`/backtick markup spanning across it)
is the one sentence you want a pilot to read in `defaults.toml` -- the generator's `_first_sentence`
only takes everything up to that first qualifying period regardless of how long the rest of the
block runs. Reserve the blank-`#:`-line paragraph break for the case it is actually meant for: a
shared intro paragraph above several sibling bullets, not a single constant's own rationale.

Found on `plans/emitter-visibility/plan.md`'s `FIRE_LIFE_FRACTION_MAX` -- the fix was merging two
paragraphs into one and regenerating with `tools/generate_defaults.py --write`, then re-reading
`config/defaults.toml` to confirm the rendered line was now a clean, self-contained sentence.
