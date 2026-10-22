---
name: feedback_tuning_comment_leading_backtick_strip_asymmetric
description: FIXED 2026-10-22 (BL-B80 review fix 1) -- generate_defaults.py used to eat a #: comment's leading/closing backtick and split on a period inside a quote; now regression-tested, but still read the rendered defaults.toml
metadata:
  type: feedback
---

**Fixed 2026-10-22** on `feature/9k113-sight-pointing` (BL-B80 v2 review fix 1). Until then
`tools/generate_defaults.py`'s `_first_sentence()` did `parts[0].strip().strip("*`")`, which ate
an opening backtick at position 0 and a legitimate closing one before the period, and
`_SENTENCE_SPLIT` split on a period inside a quoted pilot verbatim (`*"no idea. let's ..."*`).
Regenerating after the fix repaired 9 rendered entries, 7 of which nobody had reported. That count
is the measure of how often a reader of the source comment misses this.
`body-layer/tests/test_generate_defaults_first_sentence.py` pins each case. It also requires
balanced `"` in every declaration block, because the quote rule counts parity.

**Rule that survives the fix:** read the rendered `config/defaults.toml` line after every `#:` edit.
The old workaround (never open the first sentence with inline code) is no longer needed. The habit
of checking the rendered line still is: this bug recurred three times before anyone fixed the
generator, and each time it was caught only by someone reading the rendered line.

**Generator-bug class, transferable:** a staleness test that compares committed output against a
fresh regeneration cannot catch a bug *in the generator*. Both sides carry the bug. Test the
extraction function directly, case by case.

Related: [[feedback_backtick_span_across_line_wrap_eats_space]],
[[project_tuning_generator_comment_extraction]].
