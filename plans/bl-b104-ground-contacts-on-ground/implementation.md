### Implementation Summary

BL-B104 Stages 1-5 implemented as planned, across five commits (one per
stage) plus a sixth closing a test-coverage gap found while verifying the
belief-side chain. Stage 6 (live test card) is explicitly out of scope for
this role.

### Files Changed

**Stage 1 — unit domain on the wire and through perception**
- `aircraft-layer/dcs-export/Export.lua` — forwards `Type.level1`/`level2`
  as `category`/`subcategory`; `EXPORT_SCRIPT_VERSION` bumped to
  `2026-10-30`.
- `aircraft-layer/src/schema/world_objects.py` — `WorldObjectSample.category`/
  `.subcategory` (`int | None`), `_optional_int` helper.
- `body-layer/src/perception/domain.py` (new) — `surface_domain(category,
  subcategory, agl_m)`, the wsType enumeration, `HELI_SURFACE_AGL_MAX_M`
  tunable.
- `body-layer/src/perception/association.py` — `WorldObjectCandidate.is_surface`,
  resolved once in `from_dict` (now also takes `agl_m`, wired in Stage 5).
- `body-layer/src/perception/clustering.py` — `ClusterCandidate.is_surface`/
  `Cluster.is_surface`.
- `body-layer/src/perception/naked_eye_source.py` — clusters each domain
  separately (`surface_cluster_candidates`/`air_cluster_candidates`) and
  concatenates; `_cluster_candidate` carries `is_surface` through.

**Stage 2 — surface units at their own height**
- `body-layer/src/perception/source.py` — `Observation.surface_alt_m`.
- `body-layer/src/perception/naked_eye_source.py` — surface clusters emit
  `surface_alt_m = cluster.centroid_alt_m`.
- `body-layer/src/perception/hybrid_source.py` — surface candidates emit
  `surface_alt_m = result.candidate.alt_m`.
- `body-layer/src/belief/percept.py` — `Percept.surface_alt_m`.
- `body-layer/src/belief/association_over_time.py` — `implied_position`
  places a surface percept at `surface_alt_m`.
- `body-layer/src/belief/contacts.py` — `Contact.on_surface`, written
  beside `last_alt_m` in `record`/`from_percept`.
- `body-layer/src/belief/attack_run.py` — `remembered_target_alt_m` reads
  `contact.last_alt_m` directly for a surface contact.
- `body-layer/src/body.py` — `_look_target_position` docstring only (no
  behaviour change: it already follows the line above).
- `body-layer/src/belief/enrichment.py` — `_terrain_aware_world_position`
  short-circuits to `contact.last_position` for a surface contact.
- `body-layer/src/belief_truth_log.py` — `position_error_m` compared
  horizontally (`perception.geometry.horizontal_range_m`, new); rows carry
  `believed_alt_m`/`on_surface`.
- `body-layer/src/perception/geometry.py` — `horizontal_range_m` (new);
  `project_from_bearing_range` docstring notes the flat convention now
  applies to air contacts alone.

**Stage 3 — the two-cue fused range estimate**
- `body-layer/src/perception/estimation.py` — `DEPRESSION_SIGMA_DEG`
  tunable, `surface_range_estimate(...)`.
- `body-layer/src/perception/naked_eye_source.py` — surface clusters call
  it for range (bearing still via `perturbed_bearing_range`).
- `body-layer/src/perception/hybrid_source.py` — surface candidates'
  true range switched to horizontal (`horizontal_range_m`), not
  `associate()`'s own slant.
- `body-layer/config/defaults.toml` — regenerated (`DEPRESSION_SIGMA_DEG`,
  `HELI_SURFACE_AGL_MAX_M`).

**Stage 4 — association verification (no gate code changed)**
- `body-layer/tests/test_bl_b104_association_scenarios.py` (new) — the
  three scenario tests, see Notable Discoveries.

**Stage 5 — helicopters landed/hovering low**
- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — one
  more pcall'd `land.getHeight` per candidate; `agl_m` appended as a
  fourth, optional entry field.
- `aircraft-layer/src/schema/line_of_sight.py` — `LineOfSightVerdict.agl_m`;
  `_parse_entry` tells the old/new entry shape apart by content.
- `body-layer/src/perception/naked_eye_source.py` — `_ResolvedLos.agl_m`,
  parsed from the verdict dict and joined onto `WorldObjectCandidate.from_dict`'s
  new `agl_m` parameter.

**Closing commit — Stage 2 belief-chain test gap** (see Notable
Discoveries): `test_percept.py`, `test_association_over_time.py`,
`test_contacts.py`, `test_attack_run.py`, `test_enrichment.py`,
`test_belief_truth_log.py`.

### Tests Added

See per-stage commit messages for the full list; highlights:

- `test_domain.py` (new) — the domain rule table, including the
  helicopter AGL threshold and ignoring AGL for a fixed-wing aircraft.
- `test_naked_eye_source.py` — mixed-domain candidates never share a
  cluster; air-only/`None`-only polls unchanged; surface cluster range
  uses the fused estimator and is tighter than cue A alone; helicopter
  AGL threshold (below/above/unknown).
- `test_estimation.py` — cue-B-absent equivalence to
  `perturbed_bearing_range`, the wrong-sign/level-look fallback,
  determinism, no NaN/negative range across the AGL x distance
  envelope, the upward-ray case, tighter-at-steep-geometry and
  never-worse-than-cue-A-alone (E3), narrow-tighter-than-naked-eye, the
  no-omniscience grep fence (the function's own executable code, not
  its docstring), and convergence to a systematic offset (E7).
- `test_bl_b104_association_scenarios.py` (new) — one group stays one
  contact on a closing run; two groups on one bearing stay two, both at
  level flight and during a closing run; 200 object-id seeds each,
  >=99% success required.
- `test_line_of_sight_schema.py` — `agl_m` parsing (present, empty,
  absent, negative), round-trip.

### Checks

**aircraft-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (26 source files)
- pytest: pass (661 passed)
- `luac5.1 -p` on `Export.lua` and `petrobrain-line-of-sight-hook.lua`
  (including the bridged scripting-state block extracted separately):
  pass

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (79 source files)
- pytest: pass (2846 passed, 4 xfailed — the 4 xfailed are pre-existing,
  unrelated to this feature, pinned by `fix/flexible-sequence-tests`
  already on `main`)

### Notable Discoveries

1. **Stage 4's first scenario-test draft failed, and the cause was the
   test harness, not the gate or the estimator.** The plan's own
   instruction ("if (a) or (b) fails, STOP there, commit what you have,
   and report — do not retune the association gate without a decision")
   was taken seriously: before concluding the gate was broken, I
   re-ran the identical closing-run scenario (a) against the OLD,
   pre-BL-B104 cue-A-only model and got the same failure rate (168/200
   vs 157/200 for the new fused estimator — within noise, not a
   regression). The actual cause: my first harness never threaded
   `Observation.continues_observation_id`, so every poll re-ran the full
   spatial gate from scratch instead of taking the object-permanence
   shortcut `naked_eye_source._object_id_to_last_observation_id` always
   gives a re-observed object in production — a harness defect, not a
   finding about BL-B104. Once continuity was threaded the same way
   production code provides it, all three scenarios pass at the required
   >=99%. Worth recording because the plan anticipated exactly this stop
   condition and it would have been easy to report a false positive
   without the counterfactual check.
2. **`generate_defaults.py`'s first-sentence splitter does not split
   after a period preceded by a digit** (`_SENTENCE_SPLIT`'s own
   `(?<!\d)` lookbehind, there specifically so `"0.1"` never splits). My
   first `DEPRESSION_SIGMA_DEG` comment ended its intended first sentence
   with "... Stage 3." and the renderer silently merged it with the next
   sentence into `config/defaults.toml`. Caught only by reading the
   rendered file (per this role's own standing instruction to check the
   rendered TOML, not the source comment) rather than the diff. Rewrote
   the comment so the first sentence does not end on a numeral.
3. **Two cross-key relationships worth flagging, neither guarded by a
   per-key bound**: `DEPRESSION_SIGMA_DEG` and the four `_SIGHT_*_SCALE`
   constants in `estimation.py` jointly determine how much weight cue B
   gets at a given optic/geometry — tuning `DEPRESSION_SIGMA_DEG` down a
   lot while leaving the sight scales alone could make cue B dominate at
   geometries the Monte Carlo table was never checked against. Also,
   `HELI_SURFACE_AGL_MAX_M` and whatever a future speed term might add
   (recon's own open question, not built) are not currently coupled to
   anything.
4. **Gap not closed, by scope**: no dedicated tests were added for the
   cockpit-mask behaviour change the plan names explicitly (forward/abeam
   boundary cases, a pitched-down attack attitude bringing a forward
   target back into view) — `_callout_may_speak`/`_no_look_cause` already
   read `contact.last_position`, so the behaviour change is automatic
   once a surface contact's altitude is real, and the full existing
   suite (2846 tests) passes unmodified, but the specific boundary
   scenarios the plan calls out are untested. Flagged for Stage 6's test
   card or a follow-up, not silently dropped.
5. **Pointer amendments the plan reserves for merge time, not done here**
   (plan's own "On merge (role step 10)" section): `plans/attack-run/plan.md`
   Decision 4 REVISED needs a pointer saying surface contacts now carry
   their own height in belief; `.claude/agent-memory/architect/
   project_last_alt_m_is_the_ownship_altitude.md` and
   `.claude/agent-memory/debugger/project_contact_last_alt_m_flat_projection_trap.md`
   need amending to say the trap now applies to air contacts only.

## Stage 7 — Manoeuvre-based scenario mock flights

### Files Changed

- `body-layer/tests/support/mock_flight_scenario.py` (new) — `OwnshipStart`,
  `Level`/`Descend` (`FlightLeg`), `PlacedUnit`, `build_scenario_frames`.
  Only `Level`/`Descend` are implemented, not the plan's full `Level`/
  `Climb`/`Descend`/`Turn`/`RunIn`/`Hover` sketch — these two are the only
  kinds the four scenarios below actually need. A scenario needing
  `Climb`/`Turn`/`RunIn`/`Hover` adds that leg kind here when one is
  actually needed, per the plan's own "how a later feature adds a
  scenario" step.
- `body-layer/tests/support/mock_world_model.py` — added
  `build_flat_world_model(db_path, *, region_name, theatre, centre_x,
  centre_z, half_extent_x_m, half_extent_z_m, origin_x, origin_z,
  spacing_m, n_rows, n_cols, elevation_m=FLAT_ELEVATION_M)`, the general
  form of the existing flat-plane builder; `build_mock_world_model` is now
  a thin wrapper calling it with its original fixed bounds (unchanged
  behaviour for every existing caller). Needed because the canonical
  fixture's own small, fixed bounding box (x in [-500, 2000], z in
  [-500, 500]) does not cover a 5 km closing run.
- `body-layer/tests/test_bl_b104_scenario_mock_flights.py` (new) — the
  four scenarios, each driven through the real threaded crew-text loop
  (`body._run_crew_text_poll_loop`), a persistent `scan_area` "ahead"
  task (same device `test_mock_flight_chain.py`'s own single-threaded
  test uses), and a `_ForegroundEnrichment` helper (see Notable
  Discoveries) for the one scenario that issues a command from the
  foreground thread.

### Tests Added

- `test_run1_overflight_believed_altitude_never_exceeds_ownship` — a
  ~400 m descent-and-overflight run; asserts the believed point is never
  above ownship at any observed poll (the sortie's own overflight defect).
- `test_run2_shallow_approach_range_error_converges_and_bounded` — a
  level closing approach from 5 km at 400 m AGL (shortened to stop short
  of point-blank range, see Notable Discoveries); asserts range error
  stays within the plan's ~700 m budget throughout and converges
  (non-increasing) up to the poll "engage" is issued; also asserts
  `handle_command("engage", ...)` produces a real readback.
- `test_two_groups_one_bearing_stay_two_contacts` — two T-72-sized groups
  at 3 km/4.5 km on one bearing, ownship stationary at 500 m from the
  near group (see Notable Discoveries for why stationary, not closing);
  asserts exactly two contacts throughout and exactly two
  `CONTACT_DETECTED` events (no spurious third founding event).
- `test_cockpit_mask_forward_boundary_suppresses_then_recovers_callout` —
  closes a forward unit through the ~743 m forward cockpit-mask
  threshold at 300 m AGL; asserts `Contact.last_observable_sim` stops
  advancing once inside the believed-masked band.
- `test_cockpit_mask_pitch_down_recovers_masked_forward_target` —
  approach, then a level hold well inside the mask radius (masked
  throughout), then a pitch-down leg; asserts observability resumes once
  the nose pitches down.

### Checks

**body-layer/** (fresh `.venv` created for this role; none existed in
this worktree)

- ruff format --check: pass
- ruff check: pass
- mypy --strict (`src`): pass (79 source files)
- mypy (new test support + test file, explicit run per role instruction):
  pass (3 source files)
- pytest: pass (2851 passed, 4 xfailed — the 4 xfailed are the same
  pre-existing, unrelated ones Stage 1-6 already carried)
- Scenario file run 3x in a row standalone to check for timing-related
  flakiness: pass every time (20.6s each)

### Notable Discoveries

1. **The plan's own "issuing 'engage target' (`CrewConsole.handle_line`)"
   does not reach `_handle_engage` at all — confirmed by running it, not
   assumed.** `handle_line` routes free text through `_handle_utterance`'s
   contact-reference grammar (`belief.utterance.parse_utterance`), which
   has no bare-verb entry for "engage target" with no antecedent contact
   reference; the line is read as unmatched and escalated to the brain
   layer. This is a plan-prose inaccuracy about which `CrewConsole` method
   to call, not a `body-layer/src` defect —
   `CrewConsole.handle_command("engage", now_sim, slots={...})` is the
   call every existing `engage` test in `test_crew_console.py` already
   uses, and is what the scenarios call instead.

2. **A genuine class of cross-thread bug, already fixed once in
   production, had to be fixed again in this test harness — not a new
   `body-layer/src` defect, but worth flagging because the mechanism is
   real.** Calling `CrewConsole.handle_command("engage", ...)` from the
   foreground (test) thread while `ConsolePerceptionRunner`'s background
   poll thread owns `runner.enrichment` raises
   `sqlite3.ProgrammingError: SQLite objects created in a thread can only
   be used in that same thread` — confirmed by running it. This is the
   *exact* bug `body._run_crew_text_repl`'s own docstring documents fixing
   for the real REPL thread (BL-B96): "this used to copy
   `crew_console.enrichment` straight from `runner.enrichment` ...
   thread-affine ... raised `sqlite3.ProgrammingError`." `_run_crew_text_
   poll_loop` itself still sets `crew_console.enrichment = runner.
   enrichment` once per poll (line ~3525) — fine for same-thread callers,
   a trap for a foreground caller that doesn't know to override it first.
   Fixed in the test file with `_ForegroundEnrichment` (opens its own
   `sqlite3.Connection` on the foreground thread, same pattern
   `_run_crew_text_repl` uses), not in `body-layer/src` — this is test
   infrastructure calling a dispatcher the way only a REPL-equivalent
   caller should, and the REPL's own fix pattern was ready to reuse. Worth
   someone's attention regardless: `_run_crew_text_poll_loop` setting
   `crew_console.enrichment` to its own thread-local value at all is a
   footgun for any *other* future caller that drives `CrewConsole` from a
   third thread and doesn't know this history.

3. **A real, intended behaviour change in scenario 2's range-error
   series had to be isolated before trusting the test, following this
   role's own "state what would make X false, run that command" rule.**
   After issuing "engage" mid-run, the range-error series diverged from
   its no-engage baseline (identical up to that poll, then jumping from
   ~2 m to ~148 m at the next two polls) — initially looked like `engage`
   was corrupting belief position. Isolated by running each piece of
   `_handle_engage` individually against the same scenario: a read-only
   `get_contacts` call, `set_attention` alone, and `attack_target_task`
   alone each left the post-call series bit-for-bit unchanged from the
   no-engage baseline; only going through the real `_handle_engage` (which
   also sets `attack_run_transition`, activating `body.py`'s attack-run/
   gaze machinery every subsequent poll) changed it. Conclusion: engaging
   changes which polls the naked-eye channel actually looks at this
   contact (no longer purely the scan-ahead task's own 11->12->1 cycle),
   which changes which per-look hash draws land on the believed position
   — a real, intended attention effect, not a position-writing defect.
   The convergence assertion is scoped to the pre-engage prefix of the
   series for this reason; the ~700 m budget assertion still covers the
   whole run including the post-engage polls.

4. **The plan's own "two groups on one bearing ... closes" and "no
   `CONTACT_CLASSIFICATION_CHANGED` event" both needed correction against
   the real pipeline, not just the bare-`ContactStore` drive Stage 4's own
   version of this scenario uses.** A closing run (as literally described)
   overflies the near group (3 km) and masks it (cockpit mask) well before
   the far group (4.5 km) ever enters the naked-eye channel's angular-size
   gate (~2.3 km for a 7 m object at the default optic) — the only poll
   with a single admitted candidate at that point is the far group's first
   look, which the belief-side spatial gate folds into the near group's
   own (by-then masked, decay-widened) contact, collapsing two contacts
   into one. This is a geometry artifact of closing on both groups at once
   through a real angular-size gate — neither this plan nor Stage 4's own
   `ContactStore`-only version of this scenario exercises that gate at
   all. Fixed by holding ownship stationary (500 m from the near group,
   2 km from the far one — both continuously admissible, neither masked)
   instead of closing. Separately, a benign `CONTACT_CLASSIFICATION_
   CHANGED` event does fire once (one group refining its classification
   after more looks) and is not itself evidence of a merge — the
   assertion was changed from "never this event kind" to "exactly two
   `CONTACT_DETECTED`, never a third."

5. **A fresh `body-layer/.venv` had to be created for this role** — none
   existed in this worktree (confirmed: `ls .venv` reported "No such file
   or directory" before any check ran). Built per `body-layer/CLAUDE.md`
   ("Running the live logger" / dependency list): `pyproj`, `numpy<2.5`,
   plus `ruff`/`mypy`/`pytest`.

6. **No new behaviour-affecting constant was introduced** — this stage is
   test infrastructure only (no `body-layer/src` changes), so the tuning
   mechanism does not apply here.

## Stage 8 — motion-aware position-uncertainty growth

### Files Changed

- `body-layer/src/belief/association_over_time.py` — new tunable
  `UNOBSERVED_MOTION_GROWTH_RATE_MPS` (0.3 m/s, `lo=0.0, hi=1.0`,
  `status="judgement"`); `contact_growth_rate_mps` gains the
  motion/domain gate (installation components win first, unconditional
  `0.0`; air contacts — `not contact.on_surface` — take the
  unconditional class-rate branch regardless of `Contact.motion`, bit-
  identical to pre-Stage-8; surface contacts with `motion` `"stopped"`
  or `None` get the tiny rate, `"moving"` gets the class rate).
- `body-layer/config/defaults.toml` — regenerated.
- `body-layer/tests/test_association_over_time.py` — four new tests
  (see below); `_percept` helper gained a `surface_alt_m` parameter.

### Tests Added

- `test_contact_growth_rate_mps_surface_contact_unobserved_motion_is_tiny`
  — a surface contact with `motion=None` and with
  `motion=MotionBelief(state="stopped", ...)` both resolve to
  `UNOBSERVED_MOTION_GROWTH_RATE_MPS`.
- `test_contact_growth_rate_mps_surface_contact_moving_uses_class_rate`
  — `motion.state == "moving"` resolves to the class rate (15.0 m/s,
  `OP_TRUCK`), unchanged from pre-Stage-8.
- `test_contact_growth_rate_mps_air_contact_stays_bit_identical` — an
  air contact (`on_surface=False`) resolves to the class rate
  regardless of `motion` being `None`/`"stopped"`/`"moving"` — the
  bit-identical guarantee, asserted directly.
- `test_contact_growth_rate_mps_installation_component_wins_unconditionally`
  — `0.0` for an installation-component contact regardless of
  `on_surface` or `motion`.

### Checks (body-layer/)

- ruff format --check: pass
- ruff check: pass
- mypy src: pass (79 source files)
- pytest: pass (2855 passed, 4 xfailed — same 4 pre-existing,
  unrelated xfails Stages 1–7 already carried)

### Notable Discoveries

1. **The plan's own Stage 8 "Tests this stage extends vs. rewrites"
   section was checked against the real fixtures before touching
   anything, and found wrong for both `test_contacts.py` fold-
   displacement tests it named** — confirmed by running them unmodified
   (both pass, no code change) and by direct inspection
   (`contact_growth_rate_mps(contact_d)` returns `15.0`, not the tiny
   rate). The plan's own pseudocode gates the tiny rate on
   `contact.on_surface`, and `tests/test_contacts.py`'s `_observation`
   helper defaults `surface_alt_m=None` and is never overridden by
   either flagged test — so the contacts those tests build have
   `on_surface=False` throughout (both at founding and after every
   fold), which takes the unconditional class-rate branch exactly as
   before this stage. The plan's assumption that these ground-vehicle-
   classified contacts would be `on_surface=True` by default did not
   hold against the actual fixture. **Left unmodified** — the dispatch's
   permission to rewrite them was not exercised because rewriting would
   have changed a passing, correct test for no reason. The full
   `test_contacts.py` suite (79 tests) and the full body-layer suite
   (2855 passed, 4 xfailed, matching the pre-Stage-8 baseline plus the
   4 tests actually added) both pass unmodified.
2. **`test_lost_contact_rejoins_clustering_cleanly_on_reacquisition`'s
   docstring staleness (plan's own note) is pre-existing and unrelated
   to Stage 8, for the same reason as above** — its contacts are also
   `on_surface=False` by the same default, so Stage 8 changes nothing
   about this test's behaviour either; the docstring's `GATE_GROWTH_
   RATE_MPS` reference was already stale before this stage (that name
   is used elsewhere in the module only as a *default-parameter*
   fallback, not as what this test's own path actually reads). Not
   touched, per the plan's own "extend/correct the comment, not the
   test" instruction and the "prune only the comment you are standing
   next to" rule — this stage did not touch this test or the code path
   its docstring describes, so pruning it here would be a drive-by
   edit, not a change local to what this stage actually modified.
3. **The empirical check this stage's own worked-numbers section asked
   for (Stage 7 amendment's restored closing-run scenario) was run, and
   held**: see Stage 7 amendment's own section below for the measured
   outcome (no fold).

## Stage 7 amendment — Turn leg, real manoeuvres, scenario 3 as a genuine closing run

### Files Changed

- `body-layer/tests/support/mock_flight_scenario.py` — new `Turn`
  dataclass (heading interpolated per-step, entry heading ->
  `end_heading_deg`, linear in `step / n_steps`; `bank_deg` a stated,
  constant telemetry value for the leg's duration, `0.0` elsewhere,
  same convention as `pitch_deg`). `FlightLeg` widened to
  `Level | Descend | Turn`. `build_scenario_frames`'s per-leg loop now
  branches on `isinstance(leg, Turn)` for per-step heading/dx/dz
  (unlike `Level`/`Descend`, which still compute heading/dx/dz once per
  leg); `_build_frame` gained a `bank_deg` parameter, threaded into
  `bank_rad` (previously hardcoded `0.0`).
- `body-layer/tests/test_bl_b104_scenario_mock_flights.py`:
  - Scenario 3 (`test_two_groups_one_bearing_stay_two_contacts`)
    rebuilt as `Level` (offset heading 35°) → `Turn` (35°→0°) → `Level`
    (closing, 300 m AGL), replacing the fully-stationary redesign.
    Geometry (start position, offset heading/duration, turn duration/
    bank, final closing duration) computed by direct numeric
    integration of the real `build_scenario_frames` trajectory via a
    throwaway script (not guessed) — see Measurement below.
  - Scenario 1 (`test_run1_overflight_...`) and scenario 4a
    (`test_cockpit_mask_forward_boundary_...`) each gained a short
    `Turn` onto their existing leg's heading, per the main loop's
    "every scenario should contain at least one non-Level leg";
    scenario 2 (`test_run2_shallow_approach_...`) gained the same, with
    its closing `Level` leg's duration retuned (82s → 68s) so the final
    true range lands close to its original ~900 m (942 m, confirmed by
    the same throwaway-script integration).
  - Scenario 3's assertion rewritten from "exactly two contacts at
    every poll once any were seen" to "non-decreasing, and 2 by the end
    of the run" — see Measurement below for why.
  - Scenario 2's "steep-depression blow-up" comment corrected per
    review.md's Optional Refinement.
  - Sight-tracking assertion (review.md's Finding 3/Optional
    Refinement) investigated and **not added** — see Notable Discovery
    below.

### Measurement — does the restored closing-run scenario 3 fold?

**No.** Run empirically (not assumed from Stage 8's own order-of-
magnitude argument), via a probe script driving the real threaded
pipeline and recording `(t_sim, len(store.contacts), [contact ids])`
every poll:

```
t= 80.0  contacts=0
t= 85.0  contacts=1  ['CONTACT_1']   <- near group founds
...
t=130.0  contacts=1  ['CONTACT_1']
t=135.0  contacts=2  ['CONTACT_1', 'CONTACT_2']   <- far group founds
...
t=165.0  contacts=2  ['CONTACT_1', 'CONTACT_2']
```

`store.events` carries exactly two `CONTACT_DETECTED` events (one per
group), never a third — the count only ever increases, never drops
from 2 back to 1. The true-geometry closest approach to the near group
in this run is ~508 m (inside the 743 m, 300 m AGL forward-mask
threshold), so the near group genuinely is masked during this run, not
merely closed-on — this is a real exercise of the geometry Finding 1
described, not a geometry chosen to avoid it (the opposite of the
redesign review.md flagged).

**Why the original fix's assertion ("always exactly 2 once any were
seen") was itself wrong, caught by running it rather than assumed**:
the near group is admitted (founds `CONTACT_1`) well before the far
group is in range at all — there is a real, expected single-contact
*prefix* (`t=85` through `t=130`) that is not a fold, just "the far
group hasn't been seen yet." The actual E5 fold signature is the count
**dropping back to 1 after reaching 2** (a later look merging into an
earlier, still-founded contact), which never happens here. The
assertion was corrected to `contact_counts == sorted(contact_counts)`
(non-decreasing) and `contact_counts[-1] == 2` (both founded by the
end) — the invariant that actually distinguishes a fold from a normal,
staggered founding sequence.

Per the dispatch's own stop condition, since this run does **not**
fold with Stage 8 in place, no escalation is needed and the gate/
scenario were not retuned or re-flattened.

### Notable Discoveries

1. **The sight-tracking assertion review.md's Finding 3/Optional
   Refinement asked for is untestable in this harness, confirmed by
   running it, not assumed.** `runner.sight_head.mode` stays `"off"`
   for scenario 2's entire run, before and after `"engage"` —
   `aim_source` is `"belief"` throughout regardless, for the same
   reason this scenario already documents `weapon="missiles"` as out
   of scope: the sight only leaves `"off"` mode once the guidance
   unit's readiness/effector-engine wiring is in place, which this
   harness deliberately does not build. Asserting `aim_source !=
   "belief"` here would be a tautological failure the harness could
   never pass — not a check of the real mechanism. Recorded in the
   test's own docstring instead of as an assertion; a scenario that
   actually exercises sight tracking across `engage` needs the same
   effector-engine wiring the `weapon="missiles"` note already flags
   as a later addition.
2. **Scenario 3's new geometry and scenario 2's retuned duration were
   both derived by direct numeric integration of the real
   `build_scenario_frames` function in a throwaway script** (not
   hand-calculated from first principles) — the same practice this
   plan's own `implementation.md` already used for scenario 2's
   original 900 m stopping point, kept rather than reinvented.

## Follow-up implementation, 2026-10-30 — review.md's "Follow-up review" Findings 5/6

Both required fixes from `review.md`'s "Follow-up review, 2026-10-30" section
addressed. No `src/` change — both fixes are test-only, confirmed by
`git status --porcelain src/` staying empty throughout this round.

### Files Changed

- `body-layer/tests/test_bl_b104_scenario_mock_flights.py` —
  `test_two_groups_one_bearing_stay_two_contacts` rebuilt with new leg
  parameters (Finding 5).
- `body-layer/tests/test_contacts.py` — `_observation` helper gains an
  `apparent_motion` passthrough param; new test
  `test_fold_displacement_m_uses_the_tiny_unobserved_rate_for_a_surface_contact`
  (Finding 6, also serves as Finding 5's narrower differential per the
  review's own recommendation (b)).

### Finding 5 — scenario 3 is now a real differential

**Root cause of the original "no fold" result being unearned**: the
Stage 7 amendment's geometry (51 m/s closing speed, 300 m AGL, z=-500
lateral offset) masked the near group for only ~30 s before the far
group founded — short of the ~42 s the plan's own Stage 8 worked-numbers
section computes the pre-Stage-8 unconditional class rate (`OP_ARMORED`,
8.0 m/s) would need to close the ~340 m gap and fold. The scenario never
exercised the mechanism either way.

**What widens the masked window, measured rather than guessed.** A
throwaway probe script (`sys.path`-wired to this worktree's `body-layer/
src` and `../world-model/src`, not committed) ran the real
`build_scenario_frames` → `MockAircraftLayerServer` → `ConsolePerceptionRunner`
pipeline directly (reusing the test module's own `_run_scenario` helper
via `importlib`) across a grid of speed/altitude/offset/separation
candidates, instrumenting `Contact.last_observable_sim` and true
ownship-to-unit ranges per poll. Findings, in the order they ruled
options out:

- **Widening the two groups' own separation (e.g. 3 km/5.9 km instead of
  3 km/4.5 km) does lengthen the time gap, but is self-defeating**: it
  also increases the down-range distance the fold needs to span, so the
  same elapsed time that would have folded at 1500 m separation no
  longer does at 2900 m. Tried at 35 m/s/300 m AGL/far unit at x=5900:
  masked window widened to ~105 s, but the scenario still did not fold
  even with the gate reverted (growth of `8.0 m/s * ~50s ≈ 400m`, nowhere
  near the ~2900 m needed). Ruled out.
- **The natural masked-window-to-far-founding gap at the original 300 m
  AGL is small (~10-25 s) across every speed/offset tried, and is
  structurally bounded**: the near group's own masking threshold
  (`AGL / tan(22°)`, ~743 m at 300 m AGL) sits well *inside* the ~1900-
  2400 m true range where either group typically first gets admitted (a
  property of the naked-eye admission gate, not of this scenario's
  geometry), so by the time the near group masks, the far group is
  usually already close to its own admission range. The maximum
  achievable gap at a fixed separation is bounded by
  `separation - admission_range + mask_range`, which caps out well under
  the ~42 s threshold at 300 m AGL regardless of lateral offset.
- **Altitude is the lever that actually works**: raising AGL raises the
  mask threshold (`AGL / tan(22°)`) without changing the separation the
  fold needs to span. Tried 600/650/700/800 m AGL at 1500 m separation,
  12 m/s, z=-100 offset, 50 s poll-cadence-consistent elapsed:
  - **800 m AGL (mask threshold ~1980 m) produced *zero* detections for
    the entire run** — the mask threshold exceeded the admission range,
    so the near unit was masked before it could ever be founded at all.
    Confirms the review's own caution that over-raising AGL breaks the
    scenario a different way; ruled out.
  - **600/650/700 m AGL (mask thresholds 1485/1609/1733 m) all produced a
    genuine fold when reverted**, with Stage 8's shipped gate keeping two
    contacts in every case. 600 m AGL was selected (closest to the
    original 300 m, smallest departure, comfortable margin below the
    admission range).
- **Total run length (frame count) had to be kept compatible with
  `_THREAD_JOIN_TIMEOUT_S = 10.0`** (the shared poll-thread deadline every
  scenario test in this file uses): the slower 12 m/s closing speed
  needed for a long masked window, combined with the original scenario's
  far starting point (`x=-3000`), would have produced ~70+ frames
  (>10 s wall time at the real `_POLL_INTERVAL_S = 0.15s`). Compressing
  the approach to start near the action (`x=600`, not `-3000` — the
  offset/turn legs are still real manoeuvre, just spatially closer to
  the groups) brought the run to 45 frames / ~6.75 s wall time, inside
  the existing precedent set by this file's other scenarios (34-45
  frames) and with ~3.25 s of margin below the timeout.

**Final chosen parameters** (`test_two_groups_one_bearing_stay_two_contacts`):
600 m AGL, 12 m/s closing speed, `ownship_start=(x=600, z=-239.1,
heading=35°)`, `Level(15s) → Turn(15s, end_heading=0°) → Level(190s)`,
lateral offset settling to `z=-100.0` after the turn, near/far units
unchanged at `x=3000`/`x=4500` (separation preserved at 1500 m, matching
Stage 4's own geometry).

**The required before/after control experiment, run through the real
test (not a standalone probe), both ways:**

- **With Stage 8's shipped gate** (`pytest -k two_groups_one_bearing`):
  **PASSED**, 7.32 s wall time. Measured trace: `CONTACT_1` (near group)
  founds at `t≈25s`; near group's `last_observable_sim` stops advancing
  (masked) from `t≈75-80s` onward, continuously, through the end of the
  run; `CONTACT_2` (far group) founds at `t≈150s` — a ~70-75 s unseen gap
  on the near contact at the moment the far percept arrives, well past
  the ~42 s threshold; `contact_counts` ends at `[..., 2]`, never drops.
  Exactly two `CONTACT_DETECTED` events.
- **With `contact_growth_rate_mps` locally reverted** to the pre-Stage-8
  unconditional class rate — in **both** `belief.contacts` and `belief.
  association_over_time`'s own module-level bindings (`Contact.record`'s
  clamp call resolves its own `from belief.association_over_time import
  contact_growth_rate_mps` copy; the spatial gate's `_contact_covariance`
  resolves the name from its own module globals — patching only one of
  the two leaves the other call site unaffected, confirmed the hard way
  by a first attempt that patched only `belief.contacts`/`belief.
  attack_run` and saw no behaviour change at all) — not committed,
  applied via a one-off `python -c` monkeypatch around `pytest.main(...)`:
  **FAILED** — `AssertionError: expected exactly two contacts by the end
  of this run, got 1 -- the far group was never founded as its own
  contact / assert 1 == 2`. The far group's own look folded into the near
  group's masked, decay-widened contact instead of founding its own —
  exactly the E5 fold this scenario exists to catch.
- Reverted-state `git status --porcelain src/` confirmed empty
  throughout (the revert never touched a file); the shipped-gate run was
  re-confirmed passing immediately afterward with no `src/` diff.

Per the dispatch's own stop condition: since the differential confirms
Stage 8's gate — not the scenario's own geometry — is what prevents the
fold, no escalation is needed and the gate itself was not retuned.

### Finding 6 — integration coverage for the surface fold-bound path

New test `test_fold_displacement_m_uses_the_tiny_unobserved_rate_for_a_surface_contact`
in `test_contacts.py`, same D/E/F shape as the existing
`test_fold_displacement_m_is_bounded_by_the_contacts_own_plausible_speed`
but with `surface_alt_m=0.0` on every observation (`on_surface=True`,
unlike the existing test's contacts, which default to `on_surface=False`
and so never exercise Stage 8's branch at all — confirmed by reading
`_observation`'s own default). Elapsed time is `50.0s` (not the existing
test's `0.1s`), chosen because it straddles the Stage 8 worked-numbers
section's own ~42 s threshold — so this test doubles as Finding 5's
narrower, cheaper differential (the review's own suggested
recommendation (b)), without needing scenario-level integration timing.

**Geometry derivation, measured not guessed**: D at range 1000 m, E at
range 1100 m (100 m apart, wider than the existing test's 50 m — needed
so a 40 m fold offset still reads as ambiguous at 50 s elapsed; a
tighter D/E group loses the ambiguous match before an offset wide
enough to make the clamp bind), fold F at range 1040 m. Measured
directly against the real gate (a throwaway script probing a grid of
range offsets): at this geometry, the unclamped fuse (measured by
reverting the gate the same way as Finding 5's control experiment) would
move the contact **~37.2 m**; Stage 8's shipped tiny rate
(`UNOBSERVED_MOTION_GROWTH_RATE_MPS = 0.3 m/s`) bounds it to
`0.3 * 50.0 = 15.0 m` instead — confirmed the clamp actually binds (not a
coincidence of the fuse landing on 15.0 m independently).

A second contact (G/H/I, same shape, `apparent_motion=True` on the
founding observation so `Contact.motion.state == "moving"`) contrasts
the class-rate branch at the same elaped time: bound
`15.0 m/s * 50.0 s = 750.0 m` (`OP_TRUCK`), far wider than the achievable
fold, so unclamped — confirming the first case's tiny bound is really
Stage 8's `on_surface`/`motion` gate and not some other always-tiny rule.

**Control experiment, run the same way as Finding 5's**: with
`contact_growth_rate_mps` reverted to the pre-Stage-8 unconditional class
rate in both `belief.contacts` and `belief.association_over_time`, this
test **FAILS**: `assert 750.0 == 15.0 ± 1.5e-05` — `bound_m` becomes
`15.0 (OP_TRUCK class rate) * 50.0 = 750.0`, no longer the tiny rate, so
the clamp no longer binds at `15.0 m` and the first assertion
(`bound_m == pytest.approx(UNOBSERVED_MOTION_GROWTH_RATE_MPS * 50.0)`)
fails immediately. Confirms the test is a real differential, not a
tautology.

### Checks (this round)

- `ruff format --check src tests`: one file (`test_contacts.py`)
  needed reformatting (a single `_observation(...)` call split across
  lines by the formatter); reformatted, then re-checked clean.
- `ruff check src tests`: pass.
- `cd body-layer && mypy src`: pass, 79 source files (no `src/` changes
  this round; re-run per the role's own checklist regardless).
- `pytest tests -q`: **2856 passed, 4 xfailed** (2855 baseline from the
  prior review round + 1 new test; same 4 pre-existing xfails). Both new/
  changed tests confirmed passing **by name** in an unfiltered `-v` run,
  not via a `-k` filter: `test_two_groups_one_bearing_stay_two_contacts`
  and
  `test_fold_displacement_m_uses_the_tiny_unobserved_rate_for_a_surface_contact`.

### Notable Discoveries (this round)

1. **A module-level function imported with `from x import f` is a
   separate binding from `x`'s own module attribute, and both must be
   patched for a faithful revert when the function is called from
   inside its own defining module as well as by importers.**
   `contact_growth_rate_mps` is called from `belief.association_over_time`
   itself (`_contact_covariance`, the spatial gate) and, via
   `from belief.association_over_time import contact_growth_rate_mps`,
   from `belief.contacts` (`Contact.record`'s clamp) and `belief.
   attack_run`. A first control-experiment attempt patched only the two
   importers' bindings and observed **no behaviour change at all** —
   the spatial gate, resolving the name from its own module globals,
   never saw the patch. This is the same class of defect this round's
   own Finding 5 fix exists to catch (an empirical check that doesn't
   actually exercise the thing it claims to), caught here before it
   reached a committed test rather than after.
2. **The scenario's own masked-window-to-admission gap is structurally
   bounded by `separation - admission_range + mask_range`, not freely
   tunable via speed or lateral offset alone** — worth recording because
   a future scenario needing a similarly long masked window will hit the
   same ceiling. Altitude is the lever that actually moves `mask_range`
   independent of separation; widening separation instead increases the
   distance the fold needs to span by exactly as much as it buys in time,
   making it self-defeating for this specific purpose.
