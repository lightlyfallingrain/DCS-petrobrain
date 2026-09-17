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

---

## Re-review: 5fcb387 — "Replace the screenshot-derived mask with measured co-pilot angles"

Post-APPROVED, post-DoD calibration swap: replaces the screenshot-derived table (`(0,45)(20,35)
(50,22)(80,15)(100,5)`, cutoff 100) with a live-measured one (`(0,22)(60,22)(90,10)(130,0)`, cutoff
130), all read directly off airframe boresight (no attitude correction needed this time, unlike
the screenshot pass).

**Calibration-only, confirmed.** `git show 5fcb387 --stat` touches only `cockpit_mask.py`,
`test_mock_flight_chain.py`, `test_visibility.py`. `geometry.py`, `visibility.py`, `source.py` are
untouched — D3's split held a second time. Mechanism does not need re-review.

**`test_visibility.py`'s azimuth→elevation pivot — sound, and verified to still fail against the
pre-mask code.** The measured table is flat (22°) across the whole 0–60° arc, so an azimuth-only
discriminator inside the old ±60° cone no longer separates anything — correct reasoning. The
rewritten test (`test_steep_depression_inside_the_old_cone_is_now_rejected`) picks azimuth 30°
(inside the old cone) and straddles 22° depression (12° passes, 32° rejected). Checked by hand
against the removed `_within_fov`: azimuth-only, no elevation term, so it would have called both
candidates visible — the steep case's `assert ... is None` would fail under the old code. Genuinely
discriminating, not just renamed.

**`test_mock_flight_chain.py`'s 57→53 — re-derived independently, confirmed for the claimed reason.**
Computed depression at every one of the fixture's 20 frames directly from the fixture JSON
(ownship `x` 0→1140 north, object 101 at `x=1400, alt=500`, ownship `alt=700`, azimuth 0 the whole
flight, so `depression = atan2(200, 1400 - ownship_x)`):

```
frame 15 (x=900):  21.80°  -- visible (< 22)
frame 16 (x=960):  24.44°  -- blocked (> 22)
frame 17 (x=1020): 27.76°
frame 18 (x=1080): 32.01°
frame 19 (x=1140): 37.57°
```

Object 101 drops out of the naked-eye channel for exactly frames 16–19 (4 frames), matching the
commit's own numbers (21.8°/24.4° at x=900/960) exactly, and the crossover point (`~495 m`
horizontal range, `x≈905`) to within rounding. 20 naked-eye observations (all visible under the old
45°-flat-nose table) → 16. Object 102 (`x=1800`, same azimuth 0) peaks at `atan2(200, 1800-1140) =
16.87°` at the closest approach, independently confirmed under the flat 22° allowance the whole
time — keeps all 17. Total: 20 Hybrid + 16 + 17 = 53. The claimed count is right, and right for the
claimed reason — not a coincidence landing on the correct number.

**`(130.0, 0.0)` breakpoint is genuinely unreachable, confirmed harmless.** `max_depression_deg`
returns `None` once `abs_azimuth_deg >= rear_cutoff_deg`, and both are `130.0`, so the interpolation
branch that would return exactly `0.0` at `az=130` is never reached — the value is only approached
in the limit as azimuth climbs toward the cutoff from below. Same shape existed in the prior table
(`(100.0, 5.0)` against `rear_cutoff_deg=100.0`) and was not flagged there either. Not worth a
required or optional fix: the breakpoint's only job is to anchor the interpolation slope from 90°
to the cutoff, which it does correctly; a value that can never itself be returned is a normal
consequence of "cutoff coincides with the table's last point," not a bug. Mentioning here for the
record, not as a finding.

**Non-negative-table caveat — accurate and correctly placed.** The new docstring paragraph
appended directly after the "upward visibility... trivially clears" claim it qualifies (same
location, immediately following). Verified the underlying claim: `is_visible` does a signed
`depression_deg <= max_depression_deg` comparison, so a negative table entry is handled correctly
by the mechanism (no crash, no special-casing needed) — but it would falsify the "above-boresight
always clears" claim (a moderately-above-boresight contact could then be rejected while a
far-above one passes). The measured -3° rear reading, simplified to 0 by user instruction, is
exactly the case that would have triggered this — correctly caught and documented rather than
silently absorbed.

**Derivation comment** — checked line by line against the shipped tuple: `(0,22)(60,22)(90,10)
(130,0)`/cutoff 130 all match the prose exactly (flat 22° to 60°, 10° at 90°, 0° at 130° cutoff).
No misstatement found.

**Gates** — re-run from `body-layer/`: `ruff format --check`, `ruff check`, `mypy src --strict`
(31 files, clean), `pytest -q` → 544 passed, matching the claim.

### Required Fixes

None.

### Optional Refinements

None beyond what the base review already recorded (unaffected by this commit).

### Verdict

APPROVED

### Review Confidence

Full read of the commit diff and commit message. Independently re-derived the depression-per-frame
numbers for both tracked objects straight from `mock_flight_canonical.json` rather than trusting
the commit message's arithmetic; independently confirmed the `test_visibility.py` rewrite would
fail against the removed `_within_fov` logic by hand; re-ran all four gates myself.
