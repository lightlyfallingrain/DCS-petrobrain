### Review Summary

Reviewed Stage 3b-i rev.2 (commit `88e493a`, branch `feature/group-contact-cardinality`) against
`plans/group-contact-model/plan.md`'s "Correction (user, 2026-09-18)" and "Stage 3b-i rev.2" design
sections, and `plans/group-contact-model/implementation.md`'s matching log entry.

**The two load-bearing claims both check out against the code, not just the design's algebra.**

- **Optic-multiplier cancellation.** `_separable` in `body-layer/src/perception/clustering.py`
  computes `resolvable = theta_sep >= 0.5 * (theta_size_a + theta_size_b)` — `BINOCULAR_RANGE_
  MULTIPLIER` never appears in that line. `M` only appears in the (A) floor check
  (`theta_sep * BINOCULAR_RANGE_MULTIPLIER >= LOWRES_ANGULAR_RADIUS_RAD`), exactly as designed.
  Confirmed in the code, not just read off the docstring.
- **(A) is provably non-binding.** Verified `visibility.py`'s admission threshold and the algebraic
  chain in the design by hand; also directly checked via `test_clustering.py`'s new
  `test_floor_self_consistency_of_the_detection_floor_at_the_detection_limit`, which places a pair
  exactly at the detection-range limit and asserts (A) holds — this is the right test for the
  claim (boundary case, not an interior example). Independently spot-checked the counting formula
  and two of the three calibration-table numbers by hand-computing the actual geometry in Python
  (perpendicular 9 km row: adjacent-pair separation 7.15 arcmin vs. mean unit width 2.67 arcmin;
  along-LOS 200 m AGL: extent 1.71 arcmin, ratio 0.639, count 1; along-LOS 1000 m AGL: extent 8.45
  arcmin, ratio 3.16, count 4 → `OP_TO5UNITS` via `count_bucket_for`'s boundary table) — all match
  the design's and the test's own numbers.

**The gate revert is genuine.** `git diff c625299^:.../association_over_time.py 88e493a:.../
association_over_time.py` shows only docstring/comment changes plus the `_naked_eye_uncertainty_m`
rename-and-move; `spatial_gate_radius_m` and `passes_gate` show *no* diff hunk at all between
`c625299^` and `88e493a`, i.e. byte-identical, confirming the implementer's stated verification.
The premise (Stage 3a's same-source/same-poll exclusion in `ContactStore.ingest` is
radius-independent) is also confirmed directly by reading that method's own docstring/logic — the
exclusion keys on `(source, t_sim)`, never on any spatial radius.

**The jitter test.** `test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` has
had its `xfail(strict=True)` marker removed with no change to the assertion body (verified via
`git diff c625299 88e493a -- .../test_contacts.py` — only the marker and docstring changed). It
passes now. The 700:1 ratio-of-angles argument is correct: a dimensionless ratio of two angular
quantities is invariant under any consistent choice of units/representation, so "expressing both in
radians instead of metres" could never have closed that gap — only decoupling the gate's magnitude
from clustering's acuity-derived one could, which is what happened.

**The "test doesn't exist" and "five tests needed rework" disclosures are accurate and, on
inspection, benign.** `test_two_real_objects_stay_two_contacts` was folded into
`test_mock_flight_chain_single_threaded_reaches_expected_contact_state` by a *prior*, unrelated
commit (`de5e7eb`, "presence-tier percepts may not merge into an existing contact", predating even
`c625299`) — not silently deleted anywhere in this rework's own history. The design's reasoning
about that geometry is confirmed to describe `test_mock_flight_chain.py`'s surviving test.
`test_naked_eye_source.py`'s five reworked tests were checked individually (diff below); four are
mechanical (adding a small cross-range offset so previously-collinear cap/debounce fixtures aren't
degenerate under the new model, confirmed to stay within the cockpit mask's forward allowance) and
preserve each test's original intent (cap/debounce mechanics, not clustering). The fifth
(`test_a_cluster_splitting_gives_the_majority_child_continuity`) is a more substantial rework
(new `_high_ownship`, moved split geometry, majority/minority identified by position instead of
`count_bucket` since both now land on `OP_1UNIT`) but still exercises the same continuity-on-split
behaviour the test's name promises.

**Calibration numbers hand-verified independently** (not just re-run): the third test
(1000 m AGL → `OP_TO5UNITS`) genuinely pins the altitude term — it is the same ground layout as the
200 m AGL row with only the observer's altitude changed, and the extent/unit ratio crosses from
<1 to >3 purely from that change, which only a 3D angular model (not a world-space ellipse) can
produce.

**Narrowness guard confirmed by `git diff`.** `test_contacts.py`'s two Stage 3a tests are untouched
(only the jitter test's marker/docstring changed in that file); `test_cross_channel_fusion.py`
shows zero diff between `c625299` and `88e493a`.

**Counting formula.** `floor(extent_rad / unit_rad) + 1` has no free parameter (both inputs are the
same two pure functions used by the merge predicate), and "a two-member cluster is always
`OP_1UNIT`" is a genuine theorem of the merge criterion — a two-member cluster's members only merge
when `theta_sep < unit_rad` by construction of (S), so `extent_rad < unit_rad` always, and
`floor(<1) + 1 == 1` unconditionally. `test_floor_a_two_member_cluster_always_reports_one_unit`
pins this at a realistic near-boundary value (6.9 m vs. a ~7.0 m threshold), not a trivial case.

**Verification run directly** (`body-layer/.venv`, from `body-layer/`):
- `ruff format --check src tests` — pass (74 files)
- `ruff check src tests` — pass
- `mypy src` — pass, no issues, 34 source files
- `pytest tests -q` — **642 passed**, matching the commit message exactly (up from 635 + 1 xfail)

Documentation (`body-layer/CLAUDE.md`, module docstrings, `plans/group-contact-model/
implementation.md`) is updated consistently with the code and honestly records both design gaps
found only by running the suite. Agent-memory entries are correctly placed at the repo-root
`.claude/agent-memory/` path, not a subproject-nested one.

### Required Fixes

- **Stale, self-contradictory fixture comment in `test_a_cluster_splitting_gives_the_majority_
  child_continuity`** (`body-layer/tests/test_naked_eye_source.py`, lines ~651 and ~701). Two
  comments say object_id=1 "moves to lat 100" / "is the one that moved to lat 100," but the actual
  fixture (and the very next line of the same comment block) uses `lat_deg=600.0` — leftover text
  from before the split geometry was moved from 100 to 600 during this rework. Not functionally
  wrong (the code is correct; only the prose is stale), but it directly contradicts adjacent text
  in the same comment and will mislead the next reader trying to reconcile the numbers. Fix by
  replacing both "lat 100" references with "lat 600."

### Optional Refinements

- `test_a_cluster_splitting_gives_the_majority_child_continuity`'s first-poll `assert first[0].
  count_bucket == "OP_2UNITS"` was dropped with no replacement (the comment correctly notes the old
  cross-range-grid-binning-specific value no longer applies and isn't easily replaced with a stable
  one, since the three-member merged cluster's new extent/unit count wasn't re-derived). Restoring
  *some* assertion on `first[0].count_bucket` — even a hand-computed exact value — would close a
  small, self-acknowledged coverage gap on this poll. Low priority: the test's actual purpose
  (continuity-on-split) is unaffected, and the surrounding calibration/clustering test files
  already exercise `_extent_count` numerically in isolation.
- The five test-impact gaps in `test_naked_eye_source.py` and the missing `test_two_real_objects_
  stay_two_contacts` are both disclosed clearly in commit message and `implementation.md`, but
  neither the plan's own "Stage 3b-i rev.2" section nor its §8 test-impact list has been updated to
  record these two gaps for future readers of the design doc itself (only the implementation log
  has them). Worth a short addendum to the plan if a future stage revisits this design's test
  surface, but not blocking.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read. Read both full diffs (`clustering.py`, `association_over_time.py`, `naked_eye_source.py`,
all five changed test files) in their entirety, independently reproduced the byte-identical gate
claim via `git diff` between `c625299^` and `88e493a`, independently hand-computed three of the
design's angular/counting numbers in Python rather than trusting the docstrings, traced the "test
doesn't exist" claim through full git history to its actual origin commit, and ran the full
body-layer verification suite myself (ruff format/check, mypy --strict, pytest) rather than trusting
the reported counts.
