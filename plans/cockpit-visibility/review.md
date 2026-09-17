### Review Summary

Replaces `perception/visibility.py`'s elevation-blind azimuth cone with a body-relative cockpit
occlusion mask (`perception/cockpit_mask.py` + `perception/geometry.body_relative_direction`),
per plan D1-D7. Reviewed against `plans/cockpit-visibility/plan.md`,
`plans/cockpit-visibility/implementation.md`, and `git diff main...HEAD`. All gates re-run
independently (not trusted from the implementer's report): `ruff format --check`, `ruff check`,
`mypy src --strict` (from `body-layer/`), `pytest tests -q` — all pass, 543 passed, matching the
claimed count.

**1. Rotation math (`body_relative_direction`).** Verified by hand, not just re-run: the
yaw→pitch→bank composition (each step rotating about the *previous* step's unaffected axis —
pitch about `right0`, bank about `forward1`) is the standard 3-2-1 Euler decomposition, and every
sign checks out against the stated convention (positive pitch = nose up, positive bank = right
wing down):
- Yaw removal: at heading 90° (facing east), `right0` correctly maps to south, i.e. clockwise-right
  of forward — verified algebraically, not just via the test suite.
- Pitch: a nose-up aircraft (`pitch>0`) makes a level target read negative elevation (appears below
  boresight) — correct real-cockpit behavior, and matches
  `test_body_relative_direction_target_along_pitched_nose_is_dead_ahead`.
- Bank: a target straight below, rolled 90° right, resolves to azimuth +90°/elevation ~0 — i.e.
  rolling right opens a downward view to the right, matching the plan's own physical justification
  for reading bank at all (and `docstring` symmetric case: roll left → downward view opens left).
  Confirmed by independent derivation, not just by trusting
  `test_body_relative_direction_bank_rotates_elevation_into_azimuth`.
- Degenerate cases: `observer==target` → `atan2(0,0)=0.0` in Python, documented not special-cased,
  correct. Rear ±180° wrap verified (`test_body_relative_direction_rear_hemisphere`). Below-horizon
  negative elevation verified.

No error found in the mechanism. This is the right rotation, not merely an internally-consistent
one.

**2. Sign-convention gap (bank).** Confirmed the plan's own risk assessment is accurate:
- No test can catch an inverted `bank_deg` sign — every test either constructs `OwnshipState`
  directly with hand-picked degrees, or drives `from_telemetry_dict` with hand-picked radians; both
  paths check the code's own convention against itself, never against a real DCS wire sample. This
  matches the plan's own claim exactly (§"Also worth 10 seconds...").
- **Fails dangerous, not fail-safe, if inverted.** There is no clamp or sanity bound on
  `bank_deg`'s effect — `body_relative_direction` rotates unconditionally. An inverted sign does not
  degrade to "gate always closed" (safe) or "gate always open" (also identifiable); it silently
  swaps which side gains and which side loses visibility during a bank, i.e. Petrovich would see
  *worse* toward the side he's actually banking into and *better* toward the side he isn't — the
  exact inversion the plan's own writeup already names. This is disclosed, not hidden, and a
  live-sortie confirmation is already queued in the plan's calibration follow-up — not a required
  fix here, but worth restating plainly: until that sortie happens, every banked detection in this
  channel is running on an unverified sign.
- Pitch's partial evidence (parked sample, `pitch_rad=+0.0482`) is consistent with the assumed
  convention, as the plan states, and correctly caveated as inference, not verification.

**3. D3 mechanism/calibration split.** Verified directly via `git show f0945c2`: the diff touches
only `_PLACEHOLDER_CO_PILOT_MASK`/`_CO_PILOT_MASK`'s breakpoint tuple, its rename, and the
derivation-note docstring above it. No other line in `cockpit_mask.py` changed, and no other file
changed in that commit. The split held exactly as designed — `test_cockpit_mask.py` (pure
mechanism) and `test_cockpit_mask.py`'s own docstring confirm it is built against a hand-authored
synthetic mask, never `COCKPIT_MASKS`, so a future table retune is genuinely isolated from needing
this file re-reviewed.

**4. Detection-envelope regression.** Confirmed `_within_fov` and `NAKED_EYE_FOV_HALF_WIDTH_DEG` are
fully gone from source (`grep` across `body-layer/src` finds them only in docstring prose
describing what was replaced, in `visibility.py`, `cockpit_mask.py`, and `geometry.py` — no live
reference, no caller). The envelope change (±60° azimuth/no elevation → ±100° azimuth (rear cutoff)
with a depression cap tapering 45°→5°) is the plan's explicit, user-approved D2/D7 shape, not a
silent drift — correctly reflected in `todo/todo.md`'s updated backlog entry and
`crew_console.py`'s docstring, both checked and consistent with the code.

**5. Test quality.** `test_cockpit_mask.py`'s
`test_is_visible_abeam_contact_rejected_at_a_depression_the_nose_allows` is a clean, table-agnostic
proof that the mechanism does real azimuth-dependent depression gating (same depression accepted at
azimuth 0, rejected at azimuth 90) — this is the load-bearing test for the whole feature, and it is
solid.

The four `test_visibility.py` integration tests are real wiring tests, but only one of the four
(`test_candidate_rejected_level_becomes_visible_when_banked_toward_it`) would actually produce a
different result against the pre-change `_within_fov` code — I checked each by hand:
- `forward_and_below` (azimuth 0, depression 10°): old cone also passes it (bearing 0 is inside
  ±60°) — doesn't discriminate.
- `same_depression_abeam` (azimuth 90, depression 40°): old cone already rejects at azimuth 90 on
  azimuth alone — doesn't discriminate; the rejection isn't attributable to depression from this
  test alone.
- `rear_hemisphere` (azimuth 150): old cone also rejects on azimuth alone — doesn't discriminate.
- `banked_toward`: old code computes bearing 0 for a dead-below target (zero horizontal delta) and
  would call it visible regardless of the ~90° depression — this is the literal "sees through the
  floor" bug, and this test does correctly fail against the old code.

So the claim "boundary-clear, holds across both tables" is true and verified (I confirmed `f0945c2`
changes nothing these tests read), but the accompanying implication that they'd guard the specific
regression this plan fixes is only fully true for one of the four. This isn't a real gap given
`test_cockpit_mask.py`'s direct, table-agnostic proof above already covers the "depression matters
even when azimuth alone would admit" case unambiguously — but it means the four `test_visibility.py`
integration tests are wiring-correctness tests foremost, not regression proofs, and shouldn't be
read as the latter.

`test_logger.py`'s `pitch_rad`/`bank_rad` fixture additions are a genuine schema requirement, not a
patch-to-fit: `from_telemetry_dict` now reads both keys unconditionally (no `.get()`/default), so
any fixture omitting them would raise `KeyError` — confirmed by reading `source.py`'s diff directly.

**6. Invariants.** No-omniscience: `body_relative_direction`/`cockpit_mask.is_visible` read only
`OwnshipState` (position/heading/pitch/bank) and candidate geometry — no DCS ground truth beyond
what `visibility.py` already legitimately uses elsewhere in the same function. Sim-time
determinism: no wall-clock or randomness introduced. Testable without live DCS: yes, all new tests
are pure/synthetic. `mypy --strict`: clean, re-verified. `aircraft-layer` genuinely needed no
change: confirmed — `TelemetrySample.pitch_rad`/`bank_rad` were already serialized in `to_dict()`
pre-branch (only `body-layer` files changed, confirmed via diff stat), so `from_telemetry_dict`
only had two more keys to read. `COCKPIT_MASKS` keying (D6) is used only through `visibility.py`'s
single call site — no other module hardcodes `STATION_CO_PILOT`.

**Out-of-scope observation, not a finding on this branch:** the working tree currently has
untracked files `world-model/run.sh`, `world-model/syria-full-build.log`,
`world-model/syria-theatre-unfiltered.osm.pbf` (dated 2026-09-16, before this branch's commits,
not staged, not part of any commit on this branch, and not covered by `.gitignore`). These predate
and are unrelated to `cockpit-visibility`'s work — noted only so they don't get swept into a future
unrelated `git add -A`, not a defect in this review's scope.

### Required Fixes

None.

### Optional Refinements

- Consider adding one more `test_visibility.py` integration case at a small-but-nonzero azimuth
  (e.g. ~30°) with a depression the mask rejects but the old ±60° cone would have admitted — this
  would make the headline bug-fix scenario from the plan ("a contact 200 m out at 100 m AGL, ~27°
  below the horizon, off-axis but within the old cone") directly regression-tested at the
  integration level, not only provable via the pure mechanism test. Low priority: the mechanism
  test (`test_is_visible_abeam_contact_rejected_at_a_depression_the_nose_allows`) and the
  banked-contact integration test already jointly cover the underlying logic; this would only add
  belt-and-suspenders directness. (optional)
- The untracked `world-model/*` build artifacts noted above are unrelated debris in the working
  tree — worth a `git status` sanity check (or `rm`) before any future `git add -A` in this repo,
  but not something this branch introduced or is responsible for cleaning up. (optional)

### Verdict

APPROVED

### Review Confidence

Full read. Read `plan.md`, `implementation.md`, and the complete diff; hand-verified the rotation
math in `geometry.body_relative_direction` algebraically against three independent scenarios
(yaw-only, pitch-only, bank-only) rather than trusting the tests' self-consistency; confirmed the
D3 commit split via `git show f0945c2` directly; re-ran `ruff format --check`, `ruff check`,
`mypy src --strict`, and `pytest -q` myself from `body-layer/` rather than trusting the reported
"543 passed"; confirmed `_within_fov`/`NAKED_EYE_FOV_HALF_WIDTH_DEG` have no remaining live
reference via `grep`; hand-checked each of the four new `test_visibility.py` cases against the old
`_within_fov` logic to determine which would actually have caught the regression.
