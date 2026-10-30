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
