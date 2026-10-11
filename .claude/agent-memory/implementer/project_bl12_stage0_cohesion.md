---
name: bl12-stage0-cohesion
description: BL-12 Stage 0 (both-EAGER + 500 m eager cap + BL-B51) — a guard assertion saved a fixture from going hollow; spoken-range rounding is a calibration source.
metadata:
  type: project
---

BL-12 Stage 0 narrowed `belief.groups` cohesion: `_pair_backstop_m` requires **both** members
`EAGER` (was either), and the eager backstop is a finite 500 m (was `math.inf`).

**The transferable finding: a fixture that only cohered because of the defect.**
`test_crew_console.py::test_slotted_report_summary_does_not_leak_an_out_of_scope_group_member`
used `_three_banded_contacts` (armor 1 km / truck 3 km / infantry 7 km), which formed one group
**only through the BL-B48 infantry bridge**. Fixing the bridge made the fixture produce zero
groups — and the test would have gone **green over an empty group set**, silently no longer
testing the leak, except that a previous author had written
`assert len(store.groups) == 1, "fixture must reproduce the cohering group"` with the comment
*"without it this test would pass while exercising nothing."* That one line is what caught it.

**How to apply:** when a change narrows a predicate that *produces* the structures other tests
consume, the dangerous casualties are tests that still pass. Look for fixtures whose setup depended
on the loose behaviour, and add the "the thing I am testing over must exist" guard when writing any
test that reads a derived structure. The amendment's test-impact list named one test; three changed,
two in files it never mentioned.

**Calibration source worth remembering: the resolution of the spoken sentence.**
`belief.speech._format_range_km` rounds to the nearest 0.5 km (verified by running it: 2 750 /
3 000 / 3 249 m all say *"3 kilometres"*). So any "how wide may a thing be and still be reported as
one thing" question has a defensible answer in metres already in the tree — 500 m — with a clock-hour
cross-check (`2·tan(15°)·R = 0.536 R`, so 500 m fits one clock hour from R ≥ 933 m). Cite the
renderer, do not import it: `groups.py`'s docstring forbids reading anything speech-shaped.

**Test-fixture gotcha, measured.** In `test_crew_console.py`, `_observation_for_follow`'s `range_m`
**is** the reported range exactly, because `_enrichment_context` stubs `project_terrain_aware` to a
passthrough — and since all such contacts sit on one radial, **member spacing equals the `range_m`
difference**. Reasoning from `_xz_for_clock`'s geometry instead gave the wrong answer and put three
contacts meant to straddle a band boundary all in one band.

**A false reference survived a commit.** Stage 0a's own docstring cited a test name that did not
exist; caught one commit later. Same class as cited line numbers: `ruff`'s import sort moved a line
I had just cited `:216` for, inside the same change. **Prefer a decomposition over offsets** — "1
import + 3 uses + 4 docstring mentions, counted by `grep`" survives; `:216` did not survive one
commit.
