---
name: feedback_boundary_only_tested_via_fixture
description: A chaining/clustering cap or merge boundary can be correct but have no dedicated unit test, only incidental coverage inside one large end-to-end fixture — check by calling the helper directly with hand-built boundary cases.
metadata:
  type: feedback
---

When a module has a private helper implementing a boundary rule (a clustering chain cap, a
merge-distance threshold, an off-by-one-prone span check), don't stop at "the headline fixture
test passes and happens to exercise this boundary." Call the helper directly with hand-built
boundary cases: exactly-at-the-limit, one-past-the-limit, and a case designed to trigger the cap
specifically (not just incidentally).

**Why this matters**: a large fixture (e.g. a full sortie transcript) tends to cover *a* value of
the boundary, not *the* boundary — it wasn't built to stress it. The behavior can be correct (as
it was here) while still being one refactor away from breaking silently, because nothing pins the
boundary itself, only an emergent property of one scenario.

**How to apply**: for any span/cap/threshold constant, write (or in review, personally run) three
inputs against the private function directly: at the limit, just past it, and a chain that only
exceeds the *total* cap through several individually-legal steps (catches accumulation bugs a
single-pair check would miss). Report this as an optional test-coverage refinement, not a required
fix, if hand-verification against the real code confirms current behavior is correct — the gap is
in regression-proofing, not in the code's correctness today.

**Concrete case**: `belief/callouts.py`'s `_chain_by_clock` (`CALLOUT_GROUP_CLOCK_SPAN_HOURS`/
`CALLOUT_GROUP_MAX_SPAN_HOURS`, callout-scheduling review, 2026-09-22) — correct on hand-verification
(2-hour gap fails to merge, a 4-member adjacent chain correctly splits at the span cap, a 1-hour
gap correctly merges), but `test_callouts.py` had no test calling `_chain_by_clock` directly; the
only coverage was incidental, inside the large `test_2c_transcript_fixture_renders_four_lines_
not_seven` fixture.
