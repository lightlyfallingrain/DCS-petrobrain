### Review Summary

Reviewed BL-16 mode-1 batch (break turn, break away, rotor envelope, VRS, rates as goals) —
branch `feature/bl16-mode1-break`, diff `e62b7ff9..88d99d5b` (feature commit `5fe44225`, memory
commit `88d99d5b`). Fast-forwarded cleanly; HEAD was a strict ancestor of the stated tip with a
clean tree.

Checked against `plan.md`'s "Revised 2026-11-19 — mode-1 batch" (Decisions 27–31) and the
"Main-loop amendment 2026-11-19" (Decision 32), `explore-notes.md`'s verbatim mode-1 goal-check
answers, `alignment.md`'s goal/plan check, and the implementer's own account in
`implementation.md`'s "Mode 1 batch" section. The implementation matches the plan closely —
`turn_rate_deg_s` as a goal field, `BREAK_TURN_RATE_DEG_S` in `config/rules/flight.lua` (not
Python), `MAX_BANK_DEG` fully removed, the rotor-RPM seam (`read_rotor_rpm_pct`, `"dummy"` default),
Decision 29's break-height floor, Decision 30's rotor/stall collective-rate caps, Decision 31's VRS
descent cap in every mode-1 state (not gated on a break being active), and Decision 32's unpark-take
seeding from a mode-2 break's held heading.

Re-ran the checks myself (worktree had no `.venv` for either subproject; used the main checkout's
venvs by absolute path from inside the worktree, confirmed Python-version match, then removed the
symlinks afterward so the tree stayed clean):

- **body-layer**: `ruff format --check` / `ruff check` / `mypy src` (92 files) all pass.
  `tools/generate_defaults.py --write` reproduces the committed `config/defaults.toml` byte-for-byte
  (no diff) — the rendered tuning text is current, not just the source comment.
  `tests/test_tuning_defaults_toml.py`/`test_tuning_comment_renders.py` pass.
  Full suite (`pytest tests -q`): **3687 passed, 4 xfailed** — matches `implementation.md` exactly.
  `.claude/scripts/fast-tests.sh body-layer`: **2613 passed, 4 xfailed**, no failures (the
  documented order-dependent `test_main_print_tuning_works_without_aircraft_layer_url` flake did
  not reproduce in my run — consistent with it being order-dependent, not a latent regression from
  this diff).
- **aircraft-layer**: `ruff format --check` / `ruff check` / `mypy src` (28 files) all pass.
  `luac5.1 -p` on both `flight_control.lua` and `config/rules/flight.lua` pass. Full suite:
  **979 passed**. `.claude/scripts/fast-tests.sh aircraft-layer`: **455 passed**.

### Required Fixes

None.

### Optional Refinements

- **Decision 32's new state (`ParkedFlightState.cbtm_break_entry_heading_deg`) has no row in any
  Co-moving Fields table** — flagged by the implementer themselves (Departure 2) as "new state, not
  in the plan's own Co-moving Fields table." I checked this against agent memory before deciding
  whether to require it: two prior instances on this same plan
  (`project_bl16_comoving_table_missed_amendment`, `project_bl16_comoving_table_rising_edge_still_
  missed`) were required fixes, but both concerned the mode-2 takeover table, which carries an
  explicit plan instruction to grep every write site before merging — that table is unrelated to
  this field and, for its own fields, is complete (verified by grep). A third memory
  (`feedback_comoving_table_scope_is_participation_not_mere_membership`) says a new field only needs
  a row when it has multiple writers and participates in a tracked transition, not merely because it
  shares a dataclass with fields that are tabled, and to check precedent rather than assume either
  way. `cbtm_action_sent` — the existing field `cbtm_break_entry_heading_deg` is co-moving with
  (same capture/clear/read shape, same functions) — was itself never given a row when it was
  introduced in the P3+P4 batch, and no review round flagged that omission. That is a real precedent
  for how this specific field class (the Python-side CBTM one-shot command state bridging
  `ParkedFlightState` and `FlightControlState` at one transition) is treated in this plan, distinct
  from the Lua-side law state the mode-1 batch's own Decision 27 table does track. On that basis I
  am not requiring a table row here — doing so would mean retroactively demanding one for
  `cbtm_action_sent` too, which no prior round asked for. Worth a line in the plan's own text (not
  necessarily a table row) saying the two fields move together, so a future reader does not have to
  re-derive this from `body.py`; optional, not blocking. The write/clear/read sites themselves are
  correct and each has a passing test (`body.py:3405` unpark-clear, `:3511-3515` capture-on-break,
  `:3552` carry-through; `crew_console.py:5639` read; tests in `test_body_ai_pilot_wheel.py`'s
  `TestCbtmTransitions`/`TestApplyAiPilotWheelGoal` additions).

- **The 60–80° bank figure the plan's text promises the pilot is not reached** (measured: ~43°/~54°
  at 150/220 km/h, against the plan's worked ~71°/~76°), traced by the implementer to
  `OMEGA_HEADING`'s own critically-damped shaper capping the achieved rate well below the
  commanded ceiling, plus some margin from the now-unclamped `phi_i` integrator windup. The
  implementer did not fix this (correctly, in my judgment) — `OMEGA_HEADING` is an Architect-level
  gain the plan itself says is "owed by M0-E," not an Implementer call, and the tests assert the
  qualitative claims the mechanism actually guarantees (steeper than an ordinary turn, converges,
  settling clears the override, left/right mirror symmetry) rather than pinning a number the
  mechanism cannot currently deliver. Given the user's own direction — "no bank limit for now,
  refine from flight later" — and that a break is explicitly a hard evasive turn rather than a
  precision manoeuvre, shipping this as `#needs-flight` with the gap flagged (which the implementer
  already did, prominently, in both the plan's own Risk list and `implementation.md`) is the right
  call rather than a required fix. Flight M-A's own retune is the right venue to close the gap, not
  a Lua-shaper rewrite inside this batch. (Optional in the sense that no code change is required
  here — it should stay flagged, which it already is, for Flight M-A.)
- **Integrator windup in `phi_i` with no bank clamp** is correctly recorded as a named Risk in
  `plan.md` ("Integrator windup in `phi_i` once the roll axis saturates, now unguarded by any bank
  clamp... Flagged for Flight M-A/M5") rather than silently engineered around — this is exactly
  what the review brief asked me to confirm is recorded, not lost, and it is. No further action
  needed from this round; noting it here only so the record is visible in one place.
- **Departure 1** (`axes_break_turn`/`axes_break_away` answering `NOT_READY` on an unknown current
  heading, rather than the plan's own `assert` pattern) is the correct engineering call: the break
  actions' rule category (`"flight_control"`) is shared with mode 2's no-refusal body and carries no
  hold-until-known-heading gate, so a break commanded in the one-poll gap right after a take is
  genuinely reachable and would otherwise crash. The alternative the implementer considered and
  rejected — moving the break actions to the `"_heading"`-holding category — would also hold mode
  2's own no-refusal body for a beat, a cross-mode behaviour change the plan never asked for. Both
  tests (`test_mode_1_break_not_ready_without_a_known_heading`/`..._away_...`) exercise this path.
  No fix needed.

### Verdict

APPROVED

### Review Confidence

Full read — plan sections (Decisions 27–32, the Co-moving Fields tables, Risks & Unknowns), the
full diff for every changed file (`flight_control.lua`, `belief/flight_control.py`,
`belief/ai_pilot_wheel.py`, `body.py`, `belief/crew_console.py`, `rules/actions.py`,
`config/rules/flight.lua`, both test files' new classes), `MAX_BANK_DEG`/`max_bank_deg` grepped
clean across both subprojects, `defaults.toml` regenerated and diffed against the committed file,
and both subprojects' full test suites run (not just the targeted fast-tests selection).
