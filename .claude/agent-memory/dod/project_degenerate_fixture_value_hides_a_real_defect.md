---
name: degenerate-fixture-value-hides-a-real-defect
description: A guard whose fixture value makes both code paths produce identical output passes incidentally; BL-13's "One armor" hid "One trucks" for three review rounds
metadata:
  type: project
---

**A third shape of unfalsifiable test, distinct from the two NOTES.md already records** (a numeric
floor no fixture can breach; a fabricated string that matches by construction): the assertion is
right, the fixture is realistic, and the *value chosen* makes both branches of the code produce the
same output.

BL-13's summary-wording guards all used `OP_ARMORED` / `OP_INFANTRY`, whose plural display word
*equals* the singular (`"armor"`, `"infantry"`). So `assert "One armor" in text` passed identically
whether the renderer picked the singular or the plural table. The real defect —
*"One trucks"*, *"One short range SAMs"*, on the single-contact scene that is the most common thing
a `report` ever answers, spoken through TTS — survived three review rounds behind that green guard,
and the same function was already *correct* in a neighbouring clause.

**At DoD, this is checkable without reading every test:** when a round's required fix is "the test
should have caught this", ask what the fixture's value was, not what the assertion said. The fix
here was not a new assertion but a new *value* (a class whose plural actually inflects) plus a
derived exhaustiveness test over both display tables, so the next `OP_*` class fails a membership
test instead of escaping.

**Occurrence: 1st as this specific shape** (the degenerate-value variant). The adjacent
already-recorded shapes are in `NOTES.md` from PB-1.5. If it recurs, it belongs at Implementer as a
habit — *pick the fixture value that can tell the two outcomes apart* — and pairs with
[[project_recurring_outcome_only_regression_test]], which is the same disease on the assertion side
rather than the fixture side.
