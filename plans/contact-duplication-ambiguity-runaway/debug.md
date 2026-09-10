### Debug Report

### Observed Issue

Live BL-5a (`--crew-text`) acceptance testing on `feature/bl5a-text-mode-crew-interaction`
(rebased onto main, which already includes BL-2.6/BL-3/BL-4/BL-5) produced 40+ `CONTACT_*`
records in the belief store for what the user confirmed is the same small set of real units in
the test mission -- massive duplication, `situational_header.contact_counts` growing from 2 early
in the session (t_sim=98.621) to dozens later. Symptom shape (alternating `OP_ARMORED`/
`OP_GROUPSOMETHING` classification labels, runaway growth over time) superficially matches the
BL-2.6 bug already fixed in commit `7581928` (`plans/classification-refinement/debug.md`).

### Hypothesis

Investigated in order, per the parent task's three candidate explanations:

1. **Regression of the 7581928 fix.** Ruled out. `body-layer/src/belief/association_over_time.py`
   `spatial_gate_radius_m` still sums `uncertainty_radius_m(percept)` +
   `contact.last_position_uncertainty_m` + growth term, unmodified since 7581928
   (`git log --oneline -- src/belief/association_over_time.py` shows no commits touching this
   function after 7581928). `Contact.last_position_uncertainty_m` is still set from
   `uncertainty_radius_m(percept)` in both `Contact.from_percept` and `Contact.record`
   (`contacts.py`). The existing regression test
   (`tests/test_contacts.py::test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts`)
   passes.

2. **`--crew-text`'s new polling path doing something different from `--console`.**
   Ruled out. `_run_crew_text_poll_loop` (`logger.py`) mirrors `_run_console_poll_loop`
   byte-for-byte: both call `_build_sources(..., emit_mode="every_poll")`, both call
   `runner.run_once()` in a loop against the *same* `ConsolePerceptionRunner`/`ContactStore`
   instance (never reconstructed mid-session), both feed the identical `ingest`+`tick` path. The
   one addition (`crew_console.drain_events`) only reads/acknowledges events; it never touches
   `ContactStore.ingest` or contact geometry.

3. **A distinct-but-same-class bug the original fix didn't cover.** Confirmed as the actual root
   cause -- see Evidence. The original fix (7581928) only budgeted a *single* real object's own
   position uncertainty against itself, symmetrically. It did not, and structurally cannot, budget
   for **two or more distinct real objects** whose gates now legitimately overlap because the fix
   necessarily widened `spatial_gate_radius_m` (summing both sides roughly doubles it). At typical
   naked-eye operating ranges (1000-2500m), a single side's own `uncertainty_radius_m` is already
   several hundred meters (e.g. ~590m at 1200m range, from `hypot(range*sin(15deg), range_bucket_
   width_m)`), so the *symmetric* gate between any two contacts at that range is over 1km wide --
   wider than a typical DCS multi-unit scene's own object spacing (a convoy, an escorted vehicle
   pair, infantry dismounted near their carrier, etc). This is exactly the risk
   `plans/classification-refinement/review.md` flagged as an "optional refinement" and left
   unaddressed: *"the wider symmetric gate roughly doubles the close-range floor, raising
   false-merge risk for two distinct real objects at ~300-600m separation."*

   The mechanism that turns this into unbounded, runaway growth (not just a one-time
   miscount) is `ContactStore.ingest`'s deliberate, documented anti-guessing invariant
   (`plans/pb2-contact-memory/plan.md` Stage 1: "two or more passing candidates -> always a new
   contact, never a best-match merge"). That policy has **no mechanism to prune, merge, or
   exclude contacts once ambiguity has fired** -- every contact ever spawned, including ones
   spawned *by* a prior ambiguity event, remains a permanent, equally-weighted candidate for every
   future percept near that area. Once two real objects' gates first overlap (poll 1 in the
   reproduction below), essentially every subsequent percept for either object sees 2+ (and a
   monotonically growing number of) passing candidates, so `ingest` spawns exactly one new contact
   per percept, forever, for the rest of the session -- independent of source, object type, or
   which of the two real objects the percept came from. This reproduces the "one new contact per
   poll" and "alternating classification label" shape the user observed without any regression of
   the 7581928 fix.

### Evidence

- Capping the `GATE_GROWTH_RATE_MPS * elapsed_s` growth term (the only unbounded-over-time term in
  `spatial_gate_radius_m`) to 30s/10s/5s worth of growth made **no difference** to the runaway
  (still 120 contacts after 60 polls in every case) -- ruling out "stale zombie contacts with an
  ever-widening gate" as the amplifier. The amplifier is the *fixed* per-side uncertainty budget
  itself, which is already large enough at realistic ranges, not its growth over time.
- Random-sweep reproduction (2000+ trials, single naked-eye channel, and separately 3000+ trials
  mixing naked-eye + hybrid/scope channels) driving the real `naked_eye_source._quantise_bearing`/
  `_quantise_range_m` and `association_over_time.passes_gate`/`spatial_gate_radius_m` against one
  stationary object, with aggressive heading rates (up to +/-40 deg/s) and ownship translation (up
  to 60 m/s): **never** produced more than 2 contacts for one real object. This confirms the
  single-object case the original fix targeted is genuinely solid and not what's failing here.
- Random-sweep reproduction with **two** real, stationary objects at randomised separation
  (200-2000m) and range (400-2400m), same real gating/quantisation code, 60 polls, moderate
  heading drift (+/-15 deg/s): found parameter combinations producing **120 contacts for 2 real
  objects** (e.g. separation ~874m, range ~1171-1462m, heading drift ~-10.4 deg/s). Traced
  poll-by-poll: from poll 1 onward, essentially every percept has 2+ (climbing to 30+ by poll 19)
  candidates passing the gate simultaneously, and the contact count grows by exactly 1 per percept
  from that point on -- the identical "snowball" shape as the original bug's own "isolated repro"
  in `plans/classification-refinement/debug.md`, but triggered by realistic multi-object geometry
  rather than a single object's own bucket requantisation.
- Existing test coverage has a gap that let this through: `test_two_well_separated_objects_
  produce_two_contacts` uses 2000m separation (safely outside any realistic gate overlap) and
  `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge` only asserts the *first*
  ambiguity event (3 contacts after one extra percept) -- neither test drives multiple polls
  after an ambiguity fires, so neither could have caught the unbounded-growth behavior.

### Fix Applied

None. This is not a regression of 7581928 and not a localized bug fixable by a small, invariant-
preserving code change -- see below.

Both plausible mitigations require a genuine design trade-off, not a mechanical patch:

- Shrinking `uncertainty_radius_m`'s naked-eye bucket-derived formula (or `SCOPE_UNCERTAINTY_M`)
  to reduce cross-object gate overlap directly reopens the original bug's single-object miss
  case -- the two failure modes pull the gate size in opposite directions, and picking a value
  requires knowing what real DCS mission object spacing and naked-eye range distributions actually
  look like, not just a code read.
- Making `ContactStore.ingest`'s "two-or-more candidates -> always new contact" rule
  self-limiting (e.g. recognizing when the *candidates themselves* are mutually within gate of
  each other and were spawned by a prior ambiguity, and merging/pruning instead of spawning again)
  is a change to a deliberately-designed, explicitly-documented invariant
  (`plans/pb2-contact-memory/plan.md` Stage 1's "never a guessed merge" decision, reaffirmed by
  name in 7581928's own commit as untouched). Changing that policy is exactly the kind of
  module-boundary/invariant decision this project's process reserves for the Architect role.

Per this role's own constraint ("If the fix requires architectural change, stop and escalate to
the Architect"), escalating rather than applying a speculative patch to either the gate sizing or
the ambiguity policy.

### Verification

N/A -- no fix applied. Verification of the diagnosis itself:

- `ruff format --check body-layer/src body-layer/tests` -- passed (no files touched).
- `ruff check body-layer/src body-layer/tests` -- passed (no files touched).
- `pytest body-layer/tests -q` -- 390 passed, unchanged (no files touched); confirms the
  reproduction above was done entirely in ad hoc scripts against the real, unmodified library
  code, not against a modified copy.
- Recommend the Architect's eventual fix add a regression test that extends
  `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s scenario across many polls
  (mirroring `test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts`'s shape but
  with two real, moderately-separated objects instead of one) -- this is the coverage gap that
  let both the sizing trade-off and the un-self-limiting ambiguity policy through.
