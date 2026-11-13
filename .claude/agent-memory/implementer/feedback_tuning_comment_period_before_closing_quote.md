---
name: feedback_tuning_comment_period_before_closing_quote
description: generate_defaults.py's sentence splitter never splits a period that sits inside a double-quoted span (an even quote count must follow) -- a verbatim-quoted phrase ending a tuning comment's first sentence ("Unable, no answer.") merges with the next sentence too
metadata:
  type: feedback
---

`tools/generate_defaults.py`'s `_SENTENCE_SPLIT` regex requires the period to be followed by
whitespace/end, *and* requires an even number of `"` after it (closing the quote span is what
`(?=(?:[^"]*"[^"]*")*[^"]*\Z)` checks) -- deliberately, so a quoted pilot verbatim's own full stop
inside the sentence does not end it early. Side effect: a period that sits **right before the
closing quote mark** (`says "Unable, no answer." Too low cuts off...`) is not followed directly by
whitespace at all -- the quote character is in the way -- so this period never matches either, and
the splitter walks on to the *next* real sentence boundary, merging everything up to there into
`config/defaults.toml`'s rendered first line.

This is a third, distinct trap from the two already on file
([[feedback_backtick_span_across_line_wrap_eats_space]],
[[feedback_tuning_comment_leading_backtick_strip_asymmetric]]/digit-before-period in
[[reference_generate_defaults_sentence_split_digit_period]]) -- none of those three involve a
quoted phrase's own closing punctuation.

Hit on `BRAIN_REPLY_MAX_AGE_S` (`plans/brain-tool-calls/plan.md` Stage 1): the first sentence was
written as `...Petrovich gives up and says "Unable, no answer." Too low cuts off...`, and the
rendered `defaults.toml` line ran both sentences together verbatim, exactly the class of defect
this project's "read the rendered file, not your source comment" rule exists to catch.

**How to apply:** never end a tuning comment's intended first sentence on a quoted verbatim phrase
immediately followed by more prose in the same sentence slot. Either put the quoted phrase in a
*later* sentence (reword the first sentence to not need it at all, e.g. "speaks the turn's unable
reason" instead of quoting the literal line), or make the quoted phrase's own sentence the deliberate
last thing rendered. Regenerate and read the actual `config/defaults.toml` line every time -- the
diff of the source `#:` block looks completely innocuous for all three trap classes.
