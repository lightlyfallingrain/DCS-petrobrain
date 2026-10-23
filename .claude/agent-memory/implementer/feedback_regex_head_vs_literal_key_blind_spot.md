---
name: feedback-regex-head-vs-literal-key-blind-spot
description: a quoted-literal-key regex (elements["X"]) silently never sees a non-literal-key head (elements[key..i]) at all -- match a broader "head" pattern first, then try the literal pattern at that same position
metadata:
  type: feedback
---

Found on BL-B90 Stage 0b's Stage 0 review fix (`body-layer/tools/generate_effector_registry.py`,
`plans/effector-sequences/plan.md`/`review-stage0.md`). The original `scan_clickabledata` matched
`elements[...]` heads with a single regex requiring a quoted-string key
(`elements\s*\[\s*(["']).*?\1\s*\]`). A dynamic/computed key form the real file does not currently
use but could after a future DCS patch (`elements[key..i] = ...`) simply never matches that regex
at all -- not counted as a head, not unhandled, not reported anywhere. The completeness invariant
this generator is built around (`heads == handled + unhandled + patches`) gave false confidence:
since the dynamic head was never counted as a head either, the invariant held and looked clean
while silently missing data.

**Why:** a parser built around "match the one literal form I expect" has no way to notice a
different form of the same construct exists, because the non-matching text simply isn't visited at
all -- unlike an unrecognised *value* inside an otherwise-matched construct (which at least reaches
the unhandled path), an unrecognised *head shape* is invisible to a completeness check built on top
of the same regex.

**How to apply:** when a completeness/fail-closed check is built on "every occurrence of pattern P
lands in bucket A, B, or C," first ask whether P is a narrow pattern (e.g. requires a literal key)
layered on top of a broader true population (e.g. "any subscript into this table"). If so, match
the **broader** pattern first (just the head token, e.g. `elements\s*\[`), then try the narrow
pattern at that same position; a match that fails the narrow pattern is a new, real "unhandled"
case rather than invisible. Also useful as a review technique on its own: for any "X items always
land in one of N buckets" invariant, ask what population the matching regex *cannot even see*, not
just what it sees and misclassifies.

See also [[feedback_static_lookup_table_entries_need_per_entry_mutation]] -- a sibling lesson from
the same review pass, about verifying a static table by mutating untested entries rather than
reading them by eye.
