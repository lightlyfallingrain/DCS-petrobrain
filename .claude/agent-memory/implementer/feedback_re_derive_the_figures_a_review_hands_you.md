---
name: re-derive-the-figures-a-review-hands-you
description: A review's own counts and figures can be the defect you are being asked to document; re-derive each one before writing it into a docstring.
metadata:
  type: feedback
---

When a review's required fix is *"document this figure"*, **re-derive the figure before writing it
down**. The review is prose like any other prose, and its numbers have not been through the gate
it is applying to yours.

**Why:** on BL-12 round 2 (2026-10-11) the required fix was a docstring paragraph, and three of the
figures handed over were off:

- the review said *"all four of its cross-checks are ground truth"* about a block with **five**
  cross-check bullets, of which **three** are spacings (the two measured percentiles and one
  zero-noise fixture) and **two** are conversions of the capped value itself with no spacing in
  them. Writing "four" would have been this project's seventh count-in-prose defect.
- the orchestrator's brief, and the acceptance document, both said `sigma_delta` is *"≤ ~336 m"* at
  the group-admitted limit. `0.17 × √2 × 1406.25 = 338 m`; 336 comes from rounding the range to
  1 400 m first. Small, but a figure cited to 3 digits derived from a 2-digit range.
- the first draft of my own rewording attributed a no-duplicate-copy property to a companion test
  that is actually an upstream-coverage guard — caught only by opening that test and reading its
  docstring, which says so in its first sentence.

**How to apply:** run the real function, not arithmetic on quoted constants
(`tier_ranges(...)` over both optics × both salience flags gave all four ceilings directly), and
write the **decomposition** into the docstring (`3 + 2 = 5`, `0.17 × √2 = 0.2404`,
`3 gaps × 400 m = 1200 m`) so the next reader can tell "the table grew" from "the original was
wrong". See [[feedback_cite_what_was_counted_not_just_how_many]].

**For a documentation-only round, prove it is documentation-only structurally.** Baseline-identical
test counts are necessary but weak. Parse both versions with `ast`, blank every docstring constant,
and compare `ast.dump` — a `SAME` result proves no code path moved, which a diff grep for
comment-shaped lines only suggests.
