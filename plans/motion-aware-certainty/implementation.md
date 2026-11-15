### Implementation Summary

BL-B112, all seven stages of `plans/motion-aware-certainty/plan.md`, implemented on branch
`feature/motion-aware-certainty` (worktree branch `worktree-agent-a99bdcaee8b5c71d2`, fast-forward
target for the caller).

**Decisions taken per the plan's own defaults** (all pre-settled by the plan, not re-litigated
here): SA-2 `op_class="OP_LRSAM"`; SA-10 `installation_component` fixed to `True` alongside the
new `immobile=True`; Buk/SA-11 not added. `plausible_speed_mps`'s now-dead `installation_component`
kwarg (`position_belief.py`) was **left in place** — deleting it would force a rewrite of
`tests/test_position_belief.py::test_plausible_speed_mps_stage_2a_is_flat_for_every_class`'s sibling
test that passes it directly (`installation_component=True`), which is exactly the "other test must
be rewritten, stop and report" case the brief named; leaving it costs nothing (no behaviour either
way, per the plan) and keeps that test unmodified.

### Files Changed

- `src/perception/object_model.py` — new `ObjectTypeProfile.immobile: bool` field (independent of
  `installation_component`); `immobile=True` on S-125/SA-3, S-300/SA-10 (both rows); `immobile=False`
  on Kub/SA-6 (user's explicit mobile override, `installation_component` stays `True` for cohesion);
  fixed S-300's two rows' `installation_component` from `False` to `True` (opportunistic, plan
  Decision 2); four new SA-2 rows (`snr_75v`/`rd_75`/`s_75m_volhov`/`s_75_zil_trailer`, all
  `op_class="OP_LRSAM"`, `installation_component=True`, `immobile=True`), placed before the generic
  `"zil"` truck keyword so first-match order is correct.
- `src/belief/association_over_time.py` — `contact_growth_rate_mps` reads `profile.immobile`
  instead of `profile.installation_component`.
- `src/belief/decay.py` — new `distance_since_last_seen_m`; `certainty_of`'s tracked/estimated
  split is now growth-distance-based (`< LAST_I_SAW_GROWTH_THRESHOLD_M`), no longer reading
  `POSITION_HALF_LIFE_S`; new tunable `LAST_I_SAW_GROWTH_THRESHOLD_M` (500.0 m, `lo=100.0,
  hi=2000.0, status="agreed-guess"`); real (non-`TYPE_CHECKING`) import of `belief.
  association_over_time.contact_growth_rate_mps` (confirmed no cycle); corrected the module
  docstring, the `POSITION_HALF_LIFE_S` declaration comment (the sentence the generator renders),
  and the `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` assert's surrounding comment/message — all
  three previously described `certainty_of`'s now-gone dependency on this half-life; the assert
  itself is unchanged, now documented as protecting `position_confidence`'s own curve instead.
- `src/tuning.py` — `_check_scan_decay_coupling`'s I1 docstring bullet corrected to match (code and
  the check itself unchanged).
- `src/belief/motion.py` — `fold_motion`'s founding-`False` branch now runs the same
  `MOTION_STOP_CONFIRM_S` countdown the demotion branch uses, instead of adopting `"stopped"`
  outright from one reading; module docstring and `FoldMotionOutcome`'s docstring corrected to
  match (the old "adopt the founding claim as-is" paragraph was previously load-bearing and is now
  reversed, flagged per Escalation Rules — user-directed, explore-notes.md Q2).
- `src/belief/contacts.py` — `from_percept` calls `fold_motion` once (was discarding the outcome's
  `pending_stop_since_sim`) and persists it onto the new `Contact.motion_pending_stop_since_sim`,
  so a founding contact's watch actually survives to the next poll.
- `src/mission_memory/entries.py` — `CompositionItem.immobile: bool = False`; `SCHEMA_VERSION` 1 →
  2; `_encode_composition` writes it, `_decode_composition` reads it via
  `item.get("immobile", False)` (every existing on-disk entry predates the field).
- `src/mission_memory/admission.py` — `_composition_for` resolves `object_model.profile_for` and
  sets `immobile`; new `LostContactTracker` (direct sibling of `FiredOnTracker`, same shape/lifetime,
  `reset_for_new_mission`) plus `_write_lost_entry`/`_write_lost_entries`: a `CONTACT_LOST` event
  writes one forced terminal snapshot (air defence always; a group contact only if
  `memory.latest_entry` is not `None`, i.e. it already cleared `GROUP_ENTRY_CONFIDENCE_FLOOR` on the
  way in), bypassing `RESIGHT_MIN_INTERVAL_S`/`_material_change` entirely, reusing every other
  per-contact helper unmodified. `step` takes an optional `lost_contact_tracker` parameter.
- `src/body.py` — owns a `LostContactTracker` instance alongside `FiredOnTracker`
  (`_run_crew_text_poll_loop`), threaded into `_mission_memory_step`, `_check_for_new_mission`, and
  `_reset_mission_state` (including its mission-restart reset call), mirroring `FiredOnTracker`'s own
  wiring exactly.
- `src/belief/speech.py` — `render_report_summary`'s "Last I saw" trigger is now
  `_needs_hedge(facts)` (`facts["certainty"] == "estimated"`), replacing the age-based
  `_is_stale(facts, stale_window_s)`; `stale_window_s` parameter dropped from
  `render_report_summary`, `_summary_deferral_clause`, `_summary_air_defence_freshness_clause`.
- `src/belief/crew_console.py` — the one `render_report_summary` call site drops its now-gone
  `stale_window_s=OBSERVED_WINDOW_S` kwarg; the now-unused `OBSERVED_WINDOW_S` import removed.
- `body-layer/docs/STRUCTURE.md` — notes added to the `mission_memory/entries.py` and
  `mission_memory/admission.py` entries for schema 2 / `LostContactTracker`.
- `body-layer/CLAUDE.md` — `LAST_I_SAW_GROWTH_THRESHOLD_M` added to the Tuning section's constant
  list.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`).

### Tests Added / Changed

- `tests/test_object_model.py` — no new tests needed beyond the existing coverage-floor fixture
  update (below); the new SA-2 rows and `immobile` field are exercised by that fixture plus manual
  verification (see Notable Discoveries).
- `tests/fixtures/object_type_coverage_sample.json` — the four SA-2 entries' `expected_op_class`
  updated from `null`/`"OP_TRUCK"` to `"OP_LRSAM"`, matching the new real coverage.
- `tests/test_decay.py` — rewrote the `POSITION_HALF_LIFE_S`-boundary certainty tests into
  growth-distance-based ones; added `test_distance_since_last_seen_grows_with_the_class_rate`,
  `test_certainty_is_tracked_below_the_growth_threshold`,
  `test_certainty_is_estimated_once_growth_crosses_the_threshold`,
  `test_immobile_contact_never_reaches_estimated_via_growth`,
  `test_immobile_contact_still_goes_lost_at_the_lost_threshold`. `_contact` fixture gained a
  `last_class_raw` parameter.
- `tests/test_belief_motion.py` — **rewrote**
  `test_founding_false_adopts_stopped_outright` (user-directed, Q2) into
  `test_founding_false_starts_a_watch_rather_than_adopting_stopped_outright`; added
  `test_founding_false_confirms_stopped_once_the_watch_completes` and
  `test_founding_false_watch_is_cancelled_by_a_true_reading`.
- `tests/test_mission_memory_entries.py` — added
  `test_composition_item_immobile_round_trips` and the Stage 5a-named
  `test_schema_1_composition_without_immobile_decodes_as_false`.
- `tests/test_mission_memory_admission.py` — added six tests for the lost-write path:
  terminal-entry-and-strike, air-defence-always, below-floor-writes-nothing, tracker dedup, tracker
  reset.
- `tests/test_mission_start_reset.py` — added
  `test_reset_mission_state_resets_lost_contact_tracker_when_given`.
- `tests/test_speech.py` — rewrote `_summary_facts` (new `certainty` parameter, driving the hedge
  directly; `_STALE_WINDOW_S` removed) and every `render_report_summary` call site across the file
  (dropped `stale_window_s`, converted staleness-via-age fixtures to `certainty="estimated"`).
  Named in the plan's own Affected Modules list.
- `tests/test_body.py` — `_f4_poll`/its one call site and the `_mission_memory_step` direct call
  threaded the new `lost_contact_tracker` parameter (not named in the plan's list — see Notable
  Discoveries).
- `tests/test_crew_console.py` — **rewrote**
  `test_slotted_report_freshness_window_is_the_decay_modules_own` into
  `..._is_growth_distance_based` (the old test's premise — `OBSERVED_WINDOW_S` is the freshness
  boundary — no longer holds); updated `test_slotted_report_does_not_filter_by_where_petrovich_is_
  looking`'s elapsed-time fixture to cross the real growth boundary instead of
  `POSITION_HALF_LIFE_S`. Neither file was in the plan's Affected Modules list — see Notable
  Discoveries.
- `tests/test_mock_flight_chain.py` — updated one integration assertion
  (`CONTACT_2`'s certainty: `"estimated"` → `"tracked"`) and its surrounding comment, a correct
  consequence of growth-based certainty for a slow/never-observed-moving infantry contact. Not in
  the plan's list — see Notable Discoveries.

### Checks

(body-layer/)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (0 errors, 81 source files)
- `pytest tests -q`: pass — 3173 passed, 4 xfailed (same 4 pre-existing xfails as the pre-change
  baseline; no new xfails/skips introduced)
- `tools/generate_defaults.py` (no `--write`): pass (defaults.toml matches the generator)

No other subproject was touched (no world-model/aircraft-layer/brain-layer source changes).

### Stage 6 re-check (plan's own instruction, no code change expected)

- `callouts.py:856`'s merge-echo suppression (`certainty_of(other, now_sim) != "lost"`) —
  unaffected; confirmed by reading, still purely `LOST_THRESHOLD_S`-gated and this plan does not
  touch `LOST_THRESHOLD_S`.
- `tools.py`'s `"observed"`-filtered call sites — unaffected; the `"observed"` band's own boundary
  (`OBSERVED_WINDOW_S`) is untouched by this plan.
- `tuning._check_scan_decay_coupling` I1/I2 — code and values unchanged; only I1's prose corrected
  (see Files Changed).
- `GROUP_REIDENTIFY_WINDOW_S`/I2 and their consumers — confirmed not touched; `POSITION_HALF_LIFE_S`
  keeps its value, `GROUP_REIDENTIFY_WINDOW_S = 2 * POSITION_HALF_LIFE_S` is unaffected.
- `_PHRASING_CERTAINTY` (`tools.py`) — left as-is, per the plan.

### Stage 6 acceptance measurement — the Kub/SA-6 growth-rate reversal (Decision, BL-B111 interaction)

The plan's own flagged risk: Stage 2 makes Kub/SA-6 the *one* place this change **widens** a bound
(`association_over_time.contact_growth_rate_mps` no longer returns `0.0` for Kub) rather than
narrowing one, and `belief.expected_area.area_half_width_deg`/`EXPECTED_AREA_MAX_HALF_WIDTH_DEG`
(`[[BL-B111]]`'s own feasibility gate) reads that same growth rate directly. Measured directly
against the real functions (`area_half_width_deg`, a synthetic Kub `Contact`), not assumed:

| Kub motion state | growth rate | range | elapsed unseen | `area_half_width_deg` | fits one look? (bound 15°) |
|---|---|---|---|---|---|
| never observed moving (typical, surface, `motion=None`) | 0.3 m/s (`UNOBSERVED_MOTION_GROWTH_RATE_MPS`) | 5000 m | 700 s | 7.18° | yes |
| never observed moving | 0.3 m/s | 1500 m | 60 s | 2.06° | yes |
| never observed moving | 0.3 m/s | 1500 m | 300 s | 10.20° | yes |
| never observed moving | 0.3 m/s | 1500 m | 700 s | 22.78° | **no** |
| seen moving (class rate) | 8.0 m/s (`OP_MRSAM`) | 1500 m | 60 s | 43.83° | **no** |

Before this plan Kub's growth rate was unconditionally `0.0` (via `installation_component`), so
`area_half_width_deg` was `0.0` at every range/elapsed time and Kub always "fit one look." After
this plan, a Kub not re-looked-at for several minutes at close-to-medium range genuinely stops
fitting one look — the expected-area trigger no longer opens a check for it, the same "no check"
treatment `OP_ARMORED` already gets at 700 s (`tests/test_expected_area_look_sweep.py`'s own
`TestArmourNoCheckFence`). This is the intended, documented consequence (Kub is a real mobile
platform by the user's own classification) and not a regression — but it does mean a
long-unobserved Kub will not get BL-B111's benefit at close range, same as any other mobile unit.
**`tests/test_expected_area_look_sweep.py`'s own production-mode fences do not exercise Kub at all**
(checked by reading the file — every cell names `"s-125"` or `"OP_ARMORED"`), so none of that
file's committed acceptance fences are affected by this change; all 17 of its tests still pass
unmodified.

### Deviations

- SA-2's `op_class="OP_LRSAM"` — the plan's own flagged, non-blocking judgment call (Investigator
  found no ED source assigns one); implemented as specified, not re-litigated.
- `installation_component` kwarg on `plausible_speed_mps` left in place rather than deleted — see
  Implementation Summary above.

### Notable Discoveries

- **Three test files outside the plan's Affected Modules list needed real changes**, found by
  running the full suite rather than trusting the plan's own list (per role instructions, step
  1b): `tests/test_mock_flight_chain.py` (one integration assertion whose age/certainty
  relationship changed under growth-based `certainty_of`), `tests/test_crew_console.py` (two
  tests whose fixtures drove staleness purely by elapsed time against `OBSERVED_WINDOW_S`/
  `POSITION_HALF_LIFE_S`, both now-wrong premises once the hedge boundary became growth-distance
  based), and `tests/test_body.py` (two call sites of `_mission_memory_step`/`_f4_poll` that
  needed the new `lost_contact_tracker` argument threaded through — a mechanical fix, not a
  behavioural one). All three are exactly the "missing entry" risk the role brief names: a plan's
  test-impact list is a hypothesis, and the gap here was silent (the suite would have run green on
  the listed files alone, with coverage quietly missing the growth-based wording everywhere it
  isn't named).
- **`contact_growth_rate_mps`'s existing `on_surface` gate matters a lot for which rate a contact
  actually gets.** An air contact (`Contact.on_surface is False`) takes the full class rate
  *unconditionally*, regardless of observed motion; only a *surface* contact is gated on whether
  motion has actually been seen (`UNOBSERVED_MOTION_GROWTH_RATE_MPS`, 0.3 m/s, otherwise). This
  mattered directly for fixing `tests/test_crew_console.py`'s two now-wrong tests (their
  `_observation_for_follow` fixture never sets `surface_alt_m`, so its contacts are air contacts
  and always get the full `OP_ARMORED` class rate of 8.0 m/s) — worth knowing for anyone writing a
  new growth-rate-dependent test against that fixture.
- **A contact seen only through the scope/hybrid channel effectively behaves as immobile for
  "last I saw" wording purposes, for a typical-length sortie leg.** `belief.motion`'s own module
  docstring already states that channel supplies no motion percept at all, so such a contact's
  `Contact.motion` stays `None` forever; if it is also a surface contact, its growth rate is the
  tiny `UNOBSERVED_MOTION_GROWTH_RATE_MPS` (0.3 m/s) for its whole life, and crossing
  `LAST_I_SAW_GROWTH_THRESHOLD_M` (500 m) at that rate takes ~1667 s — past `LOST_THRESHOLD_S`
  (120 s), so such a contact goes straight from "tracked" to "lost" and never passes through
  "estimated"/"last I saw" at all. This is a real, silent consequence of this plan worth surfacing
  to the user (not a defect — the wording is honest either way, since "last I saw" would be a
  needless hedge for something that plausibly hasn't moved far — but it means the "last I saw"
  phrase will be heard almost exclusively for contacts that were actually seen moving, or for the
  fast mobile classes).
