### Review Summary

Reviewed `feature/movement-detection` (commits `3df1c4a`..`2af3803`, 6 commits, 48 files,
+3179/-49) against `plans/movement-detection/plan.md` and the seven priorities given for this
review. Read every file named in the plan's Affected Modules section plus the priority-specific
call-outs; ran format/lint/type-check/test for both touched subprojects independently (not trusting
`implementation.md`'s reported numbers) and confirmed `luac5.1 -p` on both changed Lua files.

**All seven priorities verified, no violations found:**

1. **Omniscience boundary.** `grep -rn "velocity\|Vec3" body-layer/src/belief/` finds only
   docstring prose (three files), never a `Vec3`, a velocity component, or an import of
   `perception.motion`'s types. `grep -rn "^from belief\|^import belief" body-layer/src/perception/`
   is empty. `Observation.apparent_motion: bool | None` (`source.py:225`) is the only field crossing
   the boundary. Structurally sound, not just documented.

2. **Replay determinism / no `dt`.** `perception/motion.py` never references `dt` or any inter-poll
   interval — `evaluate_motion_gate`/`apparent_angular_rate_rad_s` take only `(observer, target,
   velocity)`, confirmed by reading both function bodies. The Hook script
   (`petrobrain-mission-telemetry-hook.lua`) stamps `timer.getTime()` **inside** the
   `dostring_in("scripting", ...)` payload (`VELOCITY_CODE`'s own `return ... tostring(timer.getTime())
   ...`), never `DCS.getRealTime()` in the Hook body — `DCS.getRealTime()` is used only for the 1 Hz
   poll-gate check, which is a legitimate wall-clock use (deciding *when* to poll), not a value that
   reaches the payload. `MOTION_VELOCITY_MAX_SKEW_S = 2.0` genuinely drops to `None` rather than
   reusing a stale sample past the bound (`_resolve_velocity_by_object_id`'s `if skew_s >
   MOTION_VELOCITY_MAX_SKEW_S: return {}, skew_s`).

3. **`UnitName` join.** `_resolve_velocity_by_object_id` (`naked_eye_source.py`) builds a
   `Counter` of `unit_name` occurrences across the current poll's own objects and drops any
   candidate whose name collides (`if name_counts[name] > 1: continue`) rather than guessing.
   Missing name / missing object_id / non-dict sample all fall through to "not resolved" (`.get()`
   returning `None`). No positional-matching fallback exists anywhere in the diff.

4. **Both self-reported findings.** (a) `get_unit_velocity_latest()` is wrapped in a narrow
   `try/except AircraftLayerError` (not a bare `except`), confirmed against
   `aircraft_client.py`'s `_get_json` contract (raises `AircraftLayerError` on transport/parse
   failure, same pattern as every other `get_*`). (b) `motion_event_kind`'s `previous is None`
   handling is deliberately inverted from the other four kinds, documented at length in its own
   docstring, and I independently confirmed no other `Contact` attribute shares motion's
   "can stay `None` indefinitely past founding" property — classification/cardinality are always
   seeded a real claim at founding (`belief.motion`'s and `belief.classification`'s own docstrings),
   so `previous is None` still means "tick one" for those three, and the other three comparison
   functions in `events.py` were left untouched.

5. **Collision-course blind spot.** `test_constant_bearing_collision_course_reads_as_not_moving`
   pins `is_apparently_moving(...) is False` for a target closing at 200 m/s along the line of
   sight, with a docstring explicitly stating "this is a feature, not a bug."

6. **Wire-format version bump.** `EXPORT_SCRIPT_VERSION` (Export.lua) and `EXPECTED_EXPORT_VERSION`
   (`collector/server.py`) both read `"2026-09-22b"`. `unit_name` is genuinely additive: not in
   `_REQUIRED_OBJECT_FIELDS`, defaults to `None` on both the dataclass and at parse time, so a
   pre-bump `Export.lua` (which never sends the field) still parses cleanly under a newer
   collector. A version mismatch only logs a warning (`_handle_line`'s `"export_version"` branch) —
   it never raises or drops the connection, so a stale deployed `Export.lua` degrades to
   "motion unknown" (no `unit_name` → no join → `None` throughout) plus the documented warning,
   not to bad data.

7. **Scope.** No occurrence of `peripheral_stimulus_ids` outside plan-doc prose (the two hits in
   the whole diff are both inside `plan.md`/`implementation.md` text, not code). No changes to
   `optics.py`, `gaze.py`, any callout-scheduler or task/watch/scan file.
   `MOTION_HALF_LIFE_S: Final[float] = 60.0` is unchanged in value; `decay.py`'s diff only adds a
   consumer (`motion_confidence_at`) and a new sibling constant (`MOTION_STOP_CONFIRM_S`).

**Independently verified, beyond the seven priorities:**
- `ContactStore.tick`'s ordering is exactly lifecycle → classification → cardinality → motion →
  attention, matching the plan and the module's own updated docstring; the cooldown/snapshot-update
  split for the new `CONTACT_MOTION_CHANGED` kind mirrors the three pre-existing kinds exactly (no
  new suppression mechanism invented).
- `test_motion_benchmark.py` synthesizes 300 units through the real
  `_resolve_velocity_by_object_id`/`evaluate_motion_gate` functions (not a hand-rolled stand-in),
  with an honestly generous 500ms regression ceiling rather than a tight timing assertion —
  non-vacuous.
- Checks re-run independently rather than trusting `implementation.md`'s reported numbers:
  - **aircraft-layer**: `ruff format --check` / `ruff check` clean, `mypy src` clean (17 files),
    `pytest` 159 passed, `luac5.1 -p` clean on both changed Lua files.
  - **body-layer**: `ruff format --check` / `ruff check` clean, `mypy src` clean (43 files),
    `pytest` 929 passed / 4 xfailed — matches the reported baseline delta exactly.
- `git status --porcelain` on the feature branch (checked out via detached commit `2af3803` in this
  isolated worktree) is clean — nothing uncommitted.

### Required Fixes

None.

### Optional Refinements

- `MOTION_STOP_CONFIRM_S = 5.0` and `MOTION_COCKPIT_PENALTY = 4.0` are both stated as uncalibrated
  placeholders in their own docstrings/comments — already flagged honestly by the implementation,
  no action needed before merge, just worth carrying into the live-acceptance test plan alongside
  the two Stage-0-deferred measurements (bridge call overhead, `timer.getTime()`/
  `LoGetModelTime()` clock identity) `body-layer/ROADMAP.md` already names.
- `Contact`'s per-attribute fold surface is now four beliefs deep (classification, cardinality,
  motion, attention), each with its own fold/decay/twin-comparison boilerplate — the plan's own
  "Second-order effect" section already flags this as worth a consolidating pass before a fifth
  attribute joins. Not blocking here, just restating the plan's own note since this review
  independently arrived at the same observation reading `contacts.py`/`events.py`/`decay.py`
  side by side.

### Verdict
APPROVED

### Review Confidence
Full read — every file in the plan's Affected Modules section was read, all seven review priorities
were checked against the actual code (not the implementation summary's claims), and all four
subproject check suites (format/lint/type/test x2, plus Lua syntax) were re-run independently in
this worktree rather than trusted from `implementation.md`.
