---
name: generator-blank-hash-line-drops-paragraph
description: a blank `#:` line inside a multi-paragraph tuning comment makes generate_defaults.py render the SECOND paragraph's first sentence, silently dropping the first paragraph entirely
metadata:
  type: feedback
---

When writing a multi-paragraph `#:` comment above a `tuning.*` declaration in body-layer, a
blank `#:` line between paragraphs is not just a visual separator -- `tools/generate_defaults.py`'s
`_comment_block_above` treats it as the boundary of a "shared intro paragraph" and only captures
the block **directly above** the declaration, walking upward until it hits that blank line. The
practical effect: if you write two paragraphs (general framing, then detail) separated by a blank
`#:` line, the rendered `config/defaults.toml` shows the **second** paragraph's first sentence, not
your intended lead sentence -- and your actual first sentence is silently dropped, not truncated,
so it is easy to miss even when checking the rendered file (it looks like a normal, complete
sentence, just the wrong one).

**Why:** found while implementing `BL-B108`'s review follow-up (`CROSS_OPTIC_RANGE_SHARE`,
`plans/relative-distance-grouping/`). A two-paragraph comment (lead sentence + a "tried and
rejected" detail paragraph) rendered the detail paragraph's first sentence instead. This is a
*different* failure mode than the known "e.g./i.e. truncates mid-sentence" bug (root `CLAUDE.md`'s
"Behaviour-affecting constants are tunable") -- that one truncates visibly mid-clause; this one
produces a complete-looking but wrong sentence, which is harder to catch by eye.

**How to apply:** when a tuning constant's comment needs more than one paragraph of reasoning,
either (a) keep it as one continuous comment block with no blank `#:` line, so the whole thing is
one capture and the generator's first-sentence split picks your actual lead sentence, or (b)
if you genuinely want the "shared intro paragraph above several related constants" behaviour,
confirm that is what you want by reading the rendered `config/defaults.toml` for *every* key in
that shared block, not just the one you were editing. Default to (a) for a single constant's own
reasoning.
