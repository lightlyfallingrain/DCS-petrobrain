---
name: generator-strips-legitimate-closing-backtick
description: body-layer's tools/generate_defaults.py _first_sentence() corrupts a rendered tunable description whenever the source comment's first sentence ends with a legitimately-closed inline-code span (`` `X`. ``) or contains an embedded quoted period -- a fourth and fifth instance of the "check the rendered file, not the comment" defect class, found on BL-B80 v2 (SLEW_EL_DPS, SEEN_AIM_HEIGHT_OFFSET_M).
metadata:
  type: project
---

`body-layer/tools/generate_defaults.py`'s `_first_sentence()` has two related bugs, both newly
exposed (not newly introduced) by BL-B80 v2's two new tunables:

1. `_SENTENCE_SPLIT` matches `\.` optionally followed by `**`/backtick, assuming any markup
   *closing* a sentence sits *after* the period. The normal, correct Markdown form is the
   opposite -- `` `X`. `` -- markup closes, *then* the full stop. When the split fires on that
   trailing period, `parts[0]` correctly retains the sentence's own trailing backtick. But
   `_first_sentence` then does `parts[0].strip().strip("*\`")`, which blindly strips trailing
   backticks/asterisks regardless of why they're there -- eating the legitimate, correctly-placed
   closing backtick of an inline-code span that happens to be the sentence's last token. Found on
   `SLEW_EL_DPS`'s comment ("same source as `` `SLEW_AZ_DPS`. ``" rendered as
   "same source as `` `SLEW_AZ_DPS. ``" -- closing backtick gone, confirmed byte-for-byte with
   `od -c`, not a terminal-rendering artifact).
2. The same regex has no awareness of an embedded quotation's own internal punctuation. A comment
   quoting the pilot verbatim with its own full stop (`` verbatim: *"no idea. let's assume on
   ground"*) ``) splits at the *first* period, i.e. the one inside the quote, discarding
   everything after it -- including the actual substance of the quote. Found on
   `SEEN_AIM_HEIGHT_OFFSET_M`'s comment, where the rendered description cuts off mid-quote and
   also loses the comment's opening backtick (the leading-strip half of the same `.strip("*\`")`
   call).

Both corruptions regenerate identically from a fresh run, so `test_tuning_defaults_toml.py`'s
staleness check passes on both -- it only proves the committed file matches a fresh regeneration,
never that the generator itself is correct. This is the fourth/fifth instance of this project's
`X-T26`-named defect class ("the generator emits only the first sentence... reaches nobody"), and
the pattern repeats: **read the rendered file with `od -c` or equivalent, don't infer it from the
source comment** -- a diff review of the `.py` comment alone would never surface either bug, since
the comment itself is correct in both cases.

**Transferable lesson for future tunable comments in this codebase**: avoid an embedded
sentence-ending period inside a quoted phrase in the comment's *first* sentence (move the quote
later, or rephrase without an internal full stop) until the generator's splitter is fixed to
respect quote nesting. The trailing-backtick-eating half is a pure generator bug with no
comment-side workaround beyond ending the first sentence on a word rather than a code span.

See `plans/9k113-sight-pointing/review.md`'s "Finding 1" for the full trace, and
`.claude/agents/reviewer.md`'s "Verifying the tuning pattern" section, which this is a new,
concrete instance of (the "three separate X-T26 defects" paragraph now has analogues outside that
one feature).
