---
name: feedback_backtick_span_across_line_wrap_eats_space
description: writing (not generating) a #: block whose inline-code backtick span wraps across two lines silently drops the space when rendered -- keep the whole span on one physical line
metadata:
  type: feedback
---

While fixing X-T26's pilot-facing range sentences in `body-layer/src/perception/visibility.py`
(`plans/configurable-constants/plan.md`), moved the inverse-relationship sentence
(`` `range = size_m / threshold` ``) into the comment's *first* sentence so
`generate_defaults.py`'s `_first_sentence()` would actually render it into `defaults.toml`. My
first wrap of the `MEDRES_ANGULAR_RADIUS_RAD` block happened to break the physical `#:` line right
inside that backtick span -- `` (`range = size_m / `` on one line, `` threshold` under ... `` on
the next. `_join_comment_lines()`'s backtick-parity join (documented in
[[tuning-generator-comment-extraction]]) treats an odd backtick count as "span still open" and
joins the next line with *no* space, which is correct for its intended case (a dotted identifier
wrapped mid-name) but silently produced `size_m /threshold` (missing space) here, where the wrap
point was just an ordinary word-wrap that happened to fall after a backtick.

**Why:** that previous memory documents the join behavior from the generator-author's side
("build the tool to do this"); this is the opposite side ("writing prose against a tool that
already does this") -- a #: block can accidentally trigger the same rule with an entirely
different, undesired effect, and the diff looked completely fine; only the regenerated
`defaults.toml` showed the missing space, because the sentence was previously never rendered
before this fix. Grepping the diff would not have caught it.

**How to apply:** when writing or rewrapping a `#:` comment block in this codebase that contains
an inline-code span (anything between a pair of backticks, not just dotted names), always keep the
whole span on one physical `#:` line -- let that one line run a little longer rather than breaking
inside the backticks. After any such edit, regenerate `config/defaults.toml`
(`tools/generate_defaults.py --write`) and read the actual rendered line, not just the source diff,
to catch this before it ships. Relevant to Stage 3 (the remaining ~80 body-layer constants), which
will touch many more `#:` blocks with similar adjacent-calibration-note prose.
