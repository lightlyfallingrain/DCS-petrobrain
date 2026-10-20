---
name: describe-position-fake-fixtures-fanout
description: Adding/changing a field on a query.describe.PositionDescription info dataclass (SettlementInfo, WaterInfo, RoadInfo, ...) breaks a _FakeInfo-shaped stand-in duplicated across several body-layer test files, not just the one the plan names
metadata:
  type: feedback
---

body-layer has **no shared test-fixture module** for world-model's `query.describe`
info dataclasses (`SettlementInfo`/`WaterInfo`/`RoadInfo`/...) — each test file that
monkeypatches `enrichment.describe_position` declares its own private `_FakeInfo`
dataclass as a stand-in, by this project's own documented "per-test-file fixture
convention". As of 2026-10-20 that shape exists independently in `test_enrichment.py`,
`test_speech.py`, `test_console.py`, `test_tools.py`, and `test_crew_console.py`.

**Why this matters:** if `belief.enrichment.semantic_facts_for` (or anything it calls)
starts reading a field unconditionally that it used to read only in a narrower branch —
e.g. `landmark-words-no-names` (F7) made `settlement.area_m2` read on every
settlement/inside_settlement fact, not just when `subtype` was absent — every one of
those five `_FakeInfo` copies needs the new field added, or the test raises
`AttributeError` at fixture-construction/call time (not a wrong assertion you'd catch by
reading expected output).

**How to apply:** when a plan touches a `SettlementInfo`/`WaterInfo`/`RoadInfo`/etc.
field read inside `enrichment.py`, grep the whole `body-layer/tests/` tree for
`class _FakeInfo` (and any other ad hoc stand-in for the same dataclass) before trusting
a plan's test-impact list for that file — the plan that introduced this instance named
only one of the five files. Don't assume a shared fixture exists; this project
deliberately doesn't have one here.

Also watch for a stale assertion of a **real settlement/place name appearing in rendered
speech text** (e.g. `assert "Jableh" in speech.text`) surviving in a file the plan didn't
list for changes to `belief.speech` — a wording change that removes proper names from
speech will make such an assertion newly wrong, not newly crashing, so it only surfaces
by running the full suite rather than the plan's named subset.

See `plans/landmark-words-no-names/implementation.md` ("Notable Discoveries") for the
worked incident this was learned from.
