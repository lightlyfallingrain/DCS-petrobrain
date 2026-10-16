---
name: feedback_tuning_comment_leading_backtick_strip_asymmetric
description: a #: comment's first sentence starting with a backtick-wrapped term renders with only the opening backtick eaten in config/defaults.toml -- never open the first sentence with inline code
metadata:
  type: feedback
---

`tools/generate_defaults.py`'s `_first_sentence()` does
`parts[0].strip().strip("*`").strip()` -- `str.strip("*\`")` only removes characters that are in
the given set from the very *start* and *end* of the whole string, not every inline-code span
inside it. Writing a `#:` comment whose first sentence opens with a backtick-wrapped term, e.g.
`` `BL-B71`'s de-escalation-only hysteresis band... ``, renders in `config/defaults.toml` as
`` BL-B71`'s de-escalation-only hysteresis band... `` -- the opening backtick is silently eaten
(it was at position 0) but the term's *closing* backtick survives (it is not at the very end of
the sentence), leaving a stray trailing backtick glued to the word.

**How to apply:** never open a `tuning.real`/`tuning.whole`/etc. `#:` comment's first sentence
with a backtick-wrapped term (an identifier, a module name, a milestone id). Reword so the first
word is plain text -- e.g. `BL-B71's de-escalation-only hysteresis band...` instead of `` `BL-B71`'s ``.
Found and fixed on `GUIDANCE_OPTIC_HYSTERESIS_FRACTION`/`GUIDANCE_OPTIC_MIN_INTERVAL_S`
(`body-layer/src/belief/optic_policy.py`, `BL-B71`) -- caught only by reading the rendered
`config/defaults.toml`, not the source diff, exactly the failure mode root `CLAUDE.md`'s "read the
rendered file, not your source comment" rule exists to catch.

This is a sibling bug to [[feedback_backtick_span_across_line_wrap_eats_space]] (same generator,
same `#:`-comment convention, different trigger: that one is about a span wrapped across two
physical lines, this one is about a span sitting at the very start of the rendered sentence) and to
[[project_tuning_generator_comment_extraction]] (the generator-author's own account of the two
failure modes found while *building* the tool -- this is a third, found while *writing against*
it).
