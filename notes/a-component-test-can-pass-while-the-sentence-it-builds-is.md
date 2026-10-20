# A component test can pass while the sentence it builds is wrong

Stage 4b composed a crew callout from two functions: `_cardinality_phrase` returned a quantity word,
and `_contact_report_text` joined it to a noun. Every unit test of the phrase passed —
`_cardinality_phrase(4, 5) == "a handful"` was correct in isolation. The composed sentence was
`"a handful trucks"`.

The defect existed **only** in the join, and nothing in the suite rendered the join and looked at
it. It surfaced the first time a human-facing tool printed whole callouts
(`body-layer/tools/speak_samples.py`), which was written for a different purpose entirely — to let
the user *hear* phrasing without needing DCS.

Two things worth carrying:

- **Where output is assembled from parts, assert on the assembled output**, not only on the parts.
  The parts were each correct; correctness did not compose. Grammar is a property of the sentence,
  so it cannot be tested anywhere else.
- **A tool built for a human to judge something subjective will also catch objective defects**, for
  free, because it is the first thing that looks at the real end product. That is an argument for
  building such tools earlier than they feel necessary.

The fix put the connector inside the phrase (`"a handful of"`), so the join stays a plain
phrase-plus-noun concatenation and the grammar lives in one place rather than being split across
two functions that must agree (2026-09-19).
