---
name: generator-abbreviation-period-truncates-sentence
description: generate_defaults.py's first-sentence splitter treats the period in an abbreviation like "e.g." as a sentence end, silently truncating the rendered defaults.toml comment mid-clause -- a sixth instance of the "check the rendered file" defect class
metadata:
  type: feedback
---

`tools/generate_defaults.py`'s `_SENTENCE_SPLIT` regex special-cases a period preceded/followed by
a digit (so "0.1" never splits) and periods inside quoted spans, but does **not** special-case
common abbreviations like "e.g." or "i.e." -- a period followed by a space still reads as a
sentence end there. Found reviewing `BL-B108` (`relative-distance-grouping`): the source comment
for `RANGE_DECORRELATION_BEARING_DEG` read "...the estimate stays "the same look" longer, e.g.
through a shallow orbit. Judgement default..." and rendered into `defaults.toml` as "...longer,
e.g." with the rest of the clause silently dropped.

**Why:** this is now the sixth distinct instance of the "the rendered first sentence is not what
the diff suggests" defect class on this generator (see `[[reference_generate_defaults_sentence_
split_digit_period]]`, `[[feedback_generator_strips_legitimate_closing_backtick]]`, the blank-line
paragraph-break gotcha, the leading-backtick-strip asymmetry, and the backtick-span-across-line-wrap
gotcha). Each one was invisible to a reviewer reading only the source diff and only caught by
opening the rendered file, exactly as `reviewer.md`'s tuning-pattern section instructs.

**How to apply:** when a `#:` comment contains "e.g.", "i.e.", "etc." or any other abbreviation
with an internal period followed by a space, assume the rendered first sentence truncates there
until the generator is fixed to special-case it. Flag it as a required fix (reword to avoid the
abbreviation, cheapest path) rather than asking for a generator change, unless the user wants the
regex itself hardened. Always read the rendered `config/defaults.toml` line itself, never infer it
from the source comment's prose -- this is the standing instruction and this is why.
