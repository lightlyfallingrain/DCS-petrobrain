### Debug Report

### Observed Issue

Sortie feedback, `docs/acceptance/2026-10-30-sortie-feedback.md` §4 (branch
`docs/2026-10-30-sortie-feedback`): during `engage ... missiles` ATGM runs, the ASP-17/9K113
sight pointed "nowhere near the target," sometimes toward completely wrong directions, and the
debug view showed binoculars/naked eye in use for many seconds during the run rather than only an
occasional quick glance. User: *"Engaging a target with the 9K113 that he cannot see with 9K113 is
utterly pointless. The whole point is that he *sees* it AND tracks it with the 9K113."*

Logs: `body-layer/logs/dcs-slew-trace-20261030-143312.jsonl`,
`dcs-detection-trace-20261030-143312.jsonl`, `dcs-speech-20261030-143312.jsonl`.

Run 1 (`engage target missiles` at sim 531.4, on a contact selected at 503.7 via `select_target`
"ground one o'clock"): `aim_source` stayed `belief` for the whole run (never `seen`); the sight's
own `sight_fov` (what it actually looked at) admitted zero objects for the entire run.
`head_goal_world_elevation_deg` climbed smoothly from +2.5° to **+72.5°** (t≈531→597), then fell
back; `head_goal_world_azimuth_deg` swung from ~30° through 356°/251° late in the run. At
t≈602.96 `observ_observed` flipped `False` and `head_mode` went `off` for the rest of the run
(603→651.4, the disengage) — the window the user's "binoculars/naked eye for many seconds"
observation maps onto.

### Hypothesis

`Contact.last_alt_m` (the altitude half of `Contact.last_position`, read by `body._look_targets`
to build every `optic_policy.LookTarget`, including the sight's own "belief" aim-source row) is
documented as *"the most recent look's own flat-projection altitude — not fused"*
(`belief/contacts.py`) — concretely, `perception.geometry.project_from_bearing_range` sets a
look's implied target altitude to **the observer's (ownship's) own altitude at the moment of that
look**, never the target's. This is a known, accepted approximation for a frequently-re-observed
contact (the gap between consecutive looks is small, so the ownship's own altitude barely moves).

It stops being harmless once (a) a contact is observed exactly once by the naked-eye/sight channel
and then goes a long time without a second admission, and (b) the aircraft's own altitude changes
substantially in that gap — exactly an ATGM run's own shape: pick a target while still high, then
fly the approach, descending. The believed altitude stays pinned to the ownship's *old* altitude
while the real target (ground-level) and the ownship's *current* altitude both move on, so the
altitude delta `body_relative_direction` feeds through `atan2(delta_alt, horizontal_range)` grows
without bound as the aircraft closes in — and because the sight is pinned at that increasingly
wrong direction, it never looks anywhere near the real target, so it can never get a fresh,
correcting look. A self-sustaining failure with no built-in recovery.

This is not a new bug class for this codebase — `belief/attack_run.py` already carries the exact
same finding, already fixed once, for its own guidance words: *"never `Contact.last_alt_m`, which
is the ownship's own altitude at the last look, not the target's"* (module docstring; Decision 4
REVISED). Its fix is `remembered_target_alt_m` (was `_remembered_target_alt_m`): reconstruct the
target's real MSL altitude from the last tier-1 look as `ownship_at_observation.alt_m +
relative_direction.up_m`, which stays correct as the aircraft's *own* altitude later changes,
because it is an absolute altitude, not a relative snapshot. The 9K113 sight's own "belief" aim
path (`body._look_targets` → `optic_policy.look_target_for` → `_decide_sighting`/
`_decide_sighting_locked`) never adopted this fix — it independently builds `LookTarget`s straight
from `contact.last_position`, reintroducing the identical defect `attack_run.py` had already
retired.

### Evidence

- `Contact.last_alt_m`'s own field docstring (`belief/contacts.py`): *"The most recent look's own
  flat-projection altitude — not fused (no altitude uncertainty model exists)."*
  `perception.geometry.project_from_bearing_range`'s docstring: *"this function therefore assumes
  the target is at the observer's own altitude."*
- `belief/attack_run.py` module docstring and `_remembered_target_alt_m`'s (now
  `remembered_target_alt_m`'s) own docstring state the same finding already fixed once, for a
  different consumer (attack-run guidance words), via `AttackRunState.last_known_target_alt_m`.
- Log reconstruction: the engaged contact (`CONTACT_30`, a BTR-60, `object_id=16790528`) was
  admitted into a percept exactly **once**, at `t_sim=472.645`, with `true_elevation_deg=-6.96`
  at `true_range_m=6895`, `motion_speed_mps=0.0` (stationary). It was never admitted again through
  the rest of the log (`outcome` stays `optic_fov`/`gaze`/`cockpit_mask` for 1,160 subsequent
  samples of this object). Ownship's own altitude at that one admission was **1584.5 m**
  (`dcs-slew-trace`, t=472.64); by the ATGM run's peak-elevation moment (t≈597) ownship had
  descended to **1165.5 m**, a **419 m** drop. The ground-truth detection trace for the same object
  shows the aircraft genuinely flying a close pass on the real target over this window (true range
  6895 m → 408 m at t=602, true elevation −7° → **−84°**, bearing wrapping through 180° as
  expected for an overflight) — **opposite in sign** and comparable in magnitude to the believed
  goal's +72.5° excursion. The believed elevation's smooth, continuous climb and its timing track
  the real close-approach geometry; the sign is wrong because the believed *altitude* input is
  wrong (pinned at the old, higher ownship altitude instead of the real ~constant ground-level
  target altitude), not because of a sign error in the geometry itself.
- `observ_observed` (the real DCS 886/898-derived alignment readback) flips `False` at t≈602.96,
  the same poll the commanded elevation (clipped at the +20° gimbal per the user's screenshot
  description) is most extreme — consistent with the sustained, several-seconds, far-outside-
  normal-envelope AI-axis demand disrupting the real sight's own alignment. `body.py`'s own rule
  (`home_phase` tracks `observ_observed`) then takes `home_phase` out of `SIGHTING`, which is what
  hands the gaze back to the ordinary naked-eye/binocular ladder for the rest of the run (t=603→
  651.4, the window the user's "binoculars for many seconds" observation describes) — a downstream
  consequence of the same root cause, not a second, independent defect.
- A written reconstruction of the belief/truth geometry (`_look_target_position`'s new regression
  test, below) confirms numerically: with the flat (buggy) altitude, the believed elevation grows
  unboundedly as the ownship descends past a close, fixed point; with the remembered (fixed)
  absolute altitude, it does not.

### Fix Applied

1. `belief/attack_run.py`: made `_remembered_target_alt_m` public
   (`remembered_target_alt_m`), documenting it as a second, sanctioned export out of this module's
   fenced reading of `Percept.relative_direction` — the same pattern `seen_world_direction`
   already uses for `belief/sight_head.py`. No behaviour change for `attack_run.decide` itself
   (same function, same call site, new name only).
2. `body.py`: added `_look_target_position(contact)`, which asks `remembered_target_alt_m` for a
   better altitude and returns `contact.last_position` with that altitude substituted when one is
   available (a real tier-1 look with a `relative_direction` happened at some point), else returns
   `contact.last_position` unchanged — no worse than today for a contact that was only ever seen
   through the scope/hybrid channel. `_look_targets` (the one function that builds every
   `LookTarget` the optic-policy/sight-pointing code reads, for every contact, both locked-ATGM
   and ordinary SIGHTING) now calls `_look_target_position(contact)` instead of reading
   `contact.last_position` directly.
3. This fixes both of the user's observed symptoms from one root cause: the sight's believed
   elevation no longer runs away as the aircraft's own altitude changes after a contact's last
   look, so it keeps pointing near the real target — closing the loop that lets it be re-admitted
   into the sight's field of view and recover `aim_source == "seen"` on its own (requirement 1),
   and it no longer drives the real sight's commanded elevation far outside its envelope, so
   `observ_observed`/`home_phase` should stay in `SIGHTING` instead of handing the gaze to
   binoculars/naked eye for the rest of the run (requirement 2). No separate "give up and
   re-sweep" workaround was added — the user asked for the belief behaviour itself to be fixed,
   and this is a genuine root-cause fix, not a palliative.
4. Updated `docs/STRUCTURE.md`'s existing note on `_remembered_target_alt_m` to the new public
   name and recorded the second caller.

Not changed: `perception.geometry.project_from_bearing_range`/`Contact.last_alt_m`'s own
derivation (still the flat, ownship-altitude-at-look projection) — that stays the right
approximation for *gating* (percept↔contact association) and for a contact with no tier-1 look to
do better from; only the sight-pointing *consumer* now asks for a better number when one exists,
exactly the boundary `attack_run.py`'s own fix already drew.

### Verification

- New regression tests in `body-layer/tests/test_body.py`:
  - `test_look_target_position_uses_remembered_altitude_not_ownship_altitude_at_look` — a contact
    seen once at ownship altitude 1500 m (200 m below the aircraft at the time) must resolve to
    MSL 1300 m through `_look_target_position`, not the flat 1500 m `contact.last_position.alt_m`
    still carries.
  - `test_look_target_position_falls_back_to_last_position_without_a_tier_1_look` — a contact with
    no `relative_direction` ever recorded is unchanged (no new guess).
  - `test_look_targets_elevation_does_not_run_away_after_the_aircraft_descends` — integration-level:
    after the aircraft descends 300 m past a contact's one-and-only look, `_look_targets`'
    elevation for that contact matches the geometry computed against the remembered (correct)
    altitude and differs from the stale flat one — the direct regression for the observed bug.
- `body-layer` full suite: `pytest tests/ -q` → **2781 passed, 4 xfailed**, no new failures and no
  regressions (ran before and after the fix; the fixed run is the one quoted).
- `ruff format --check src tests` and `ruff check src tests`: clean (one new test needed
  `ruff format` to apply — the single-line function-signature wrap — then both checks pass clean).
- `cd body-layer && .venv/bin/mypy src` (run from inside the subproject, per `body-layer/CLAUDE.md`):
  `Success: no issues found in 78 source files`.

Left unverified (needs a live DCS flight, `#needs-flight`): whether `observ_observed` dropping out
at the extreme commanded elevation is exactly what the real DCS sight does (strongly suggested by
the trace's timing correlation, not independently confirmed against DCS internals) — this does not
change the fix itself, since the fix removes the extreme elevation demand that would trigger it
either way, but it is the mechanism by which requirement 2's symptom should also disappear and is
worth watching for on the next flight.
