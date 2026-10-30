### Implementation Summary

Built on top of `debug.md`'s already-landed root-cause fix (`_look_target_position`
using `remembered_target_alt_m`). This stage implements the user's 2026-10-30 decision
from `docs/acceptance/2026-10-30-sortie-feedback.md` §4 ("Decided"):

1. **Bearing-line depression search** -- while an ATGM run is locked onto a contact
   (`sight_lock_contact_id`) that is not currently resolved through the sight itself,
   the look sweeps depression around the believed point instead of staring at it.
   Azimuth always follows the believed bearing fresh every poll (never swept); only
   elevation steps outward, centre first, alternating shallower/steeper, repeating.
2. **"Tracking." callout** -- spoken once on the False->True edge of "the locked
   contact is resolved through the sight," and again only after a later loss and
   re-acquisition.
3. **OBSERV behaviour left untouched**, as directed -- no code in the OBSERV/
   `home_phase` path was touched.

### Files Changed

- `body-layer/src/belief/optic_policy.py` -- `_decide_sighting_locked` now branches on
  a new `sight_lock_seen: bool = False` keyword: `True` reproduces the pre-existing
  direct-stare behaviour exactly; `False` runs the new bearing-line sweep via the new
  `_bearing_line_search_offsets` helper. `sight_lock_seen` is threaded through
  `_decide_sighting`/`_decide_without_guidance`/`decide` (all default `False`, a true
  no-op for every pre-existing caller). New `OpticState.sight_lock_search_since_sim`
  field is the sweep's own per-poll clock, cleared to `None` on every `sight_lock_seen`
  poll so a later loss resumes the sweep fresh (step 0 = the believed point, by then
  improved by whatever look admitted it) rather than wherever an uninterrupted cycle's
  clock would have reached. Three new tunables (`SIGHT_LOCK_SEARCH_BAND_HALF_DEG`,
  `SIGHT_LOCK_SEARCH_STEP_OVERLAP_FRACTION`, `SIGHT_LOCK_SEARCH_STEP_S`), all
  `status="judgement"` starting values, not measurements.
- `body-layer/src/belief/speech.py` -- `render_tracking()`, the "Tracking." line.
- `body-layer/src/belief/crew_console.py` -- `CrewConsole.drain_sight_lock_tracking`,
  an edge-only speaker mirroring `drain_guidance_unit_ready`'s existing shape exactly
  (caller holds `previously_seen`/`seen`, this method only edge-detects).
- `body-layer/src/body.py` -- new `_sight_lock_seen(sight_head, atgm_run_state) ->
  bool` helper (one definition, two readers: `run_once`'s `sight_lock_seen` keyword to
  `decide_optic`, and the poll loop's own "Tracking." edge detector), so the two can
  never disagree about what "seen" means. `run_once` passes the previous-poll value
  into `decide_optic` (same one-poll lag `sight_lock_contact_id`/`guidance_request`
  already accept). The poll loop captures `_sight_lock_seen` immediately before
  `runner.run_once()` and again after `drain_attack_run`'s own run-ends fold-in, and
  calls `crew_console.drain_sight_lock_tracking` with both.
- `body-layer/config/defaults.toml` -- regenerated (`tools/generate_defaults.py
  --write`) for the three new tunables.
- `body-layer/tests/test_optic_policy.py`, `test_body.py`, `test_crew_console.py` --
  new tests (below).

### Tests Added

- `TestSightLockBearingLineSearch` (`test_optic_policy.py`):
  - `test_not_seen_sweeps_depression_and_crosses_the_true_depression` -- run-2 shape
    (believed point short in range, steeper than true); asserts the sweep's own cycle
    passes close enough to a true depression 8 degrees shallower that it would fall
    inside the look's field of view. Verified to go red (fails) when
    `_bearing_line_search_offsets` is monkeypatched to return only the centre offset
    (the pre-fix "always stare" behaviour).
  - `test_seen_stares_directly_with_no_sweep` -- `sight_lock_seen=True` reproduces the
    exact pre-existing stare, across several polls.
  - `test_sweep_azimuth_follows_the_believed_bearing_every_poll` -- azimuth tracks a
    changed believed bearing between two polls while not seen.
  - `test_resuming_after_a_loss_starts_the_sweep_fresh_at_the_latest_belief` --
    not-seen (well into the sweep) -> seen (belief improves) -> not-seen again; the
    resumed sweep's first poll is exactly the improved believed point (no offset).
    Verified to go red when the `sight_lock_search_since_sim=None` reset on the
    `sight_lock_seen` branch is removed (confirmed, then reverted, by checksum).
  - `test_no_lock_is_unaffected_by_sight_lock_seen` -- `sight_lock_contact_id=None`
    makes `sight_lock_seen` a true no-op (identical state/decision either way).
- `TestSightLockSeen` (`test_body.py`): `_sight_lock_seen` -- `False` with no ATGM run,
  `False` when the sight sees a different contact, `False` for `"held"`/`"belief"`
  aim sources, `True` only when `aim_source == "seen"` matches the locked contact id.
- `TestDrainSightLockTracking` (`test_crew_console.py`): fires on False->True; silent
  while never seen; silent on every subsequent poll it stays seen (verified to go red
  if the edge check is loosened to "fire whenever seen", confirmed then reverted by
  checksum); silent on the True->False edge (losing it says nothing by itself); fires
  again after a loss and re-acquisition.
- OBSERV-unchanged and "no sweep when not locked/already seen" are covered by the
  pre-existing test suite continuing to pass unchanged (no OBSERV/`home_phase` code
  was touched; `TestSightLock`'s four pre-existing tests all pass unmodified against
  the new default `sight_lock_seen=False`, by construction of the fresh-sweep-starts-
  at-centre behaviour on each test's single `decide()` call).

### Checks

(body-layer/ only -- the only subproject touched)

- `ruff format --check`: pass
- `ruff check`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (`Success: no issues found in 78 source files`)
- `pytest tests/ -q`: pass (2795 passed, 4 xfailed -- 2781 passed before this stage per
  `debug.md`, +14 new tests)

### Notable Discoveries

- **`atgm_run.decide`'s own Stage 3-7 state machine (range calls, launch/impact
  speech, the "Shturm, N seconds." line) is not wired into `body.py`'s poll loop at
  all** -- only Stage 1 (constructing/tearing down `AtgmRunState` at engage/disengage)
  is live. The "Tracking." callout could not reuse that module's own `(state, speech,
  actions)` return shape for that reason; it is implemented directly in the poll loop
  via a dedicated `CrewConsole.drain_sight_lock_tracking`, mirroring
  `drain_guidance_unit_ready`'s existing edge-detector shape instead. Worth flagging
  for whoever wires Stage 7: once `atgm_run.decide` is live, "Tracking." sits oddly
  alongside it as a second, independently-driven speech source over the same run --
  not a conflict today, but a seam to be aware of.
- **`look_sweep`/`_step_centres_deg`'s "centre step always survives" is not generally
  true for an even step count** (verified by hand: `half_width=10, fov=6` gives centres
  `{-7.5, -2.5, 2.5, 7.5}`, none exactly `0.0`). Not a defect in that function --
  its docstring's "survives the filter" claim is about `within_field_of_regard`
  filtering, not about `0.0` being present in the offset list -- but it meant
  `_step_centres_deg` was the wrong tool for this feature's own requirement ("index 0
  is always the believed depression exactly"), so `_bearing_line_search_offsets` is a
  small bespoke function instead, not a reuse.
- **The generator's "first sentence" is the *last* `#:` paragraph before the
  assignment, not the first one in the block** (`generate_defaults.py`'s
  `_comment_block_above` walks upward and stops at a blank `#:` line). Two of the
  three new tunables' rendered `defaults.toml` entries initially showed the wrong
  paragraph (provenance detail instead of the what-it-does-plus-danger-direction
  sentence) until the comments were rewritten as one continuous paragraph with no
  blank-line break. Confirms the project's own stated trap ("read the rendered
  `defaults.toml`, not your source comment") -- caught here by actually reading the
  rendered file, not by re-reading the source diff.
