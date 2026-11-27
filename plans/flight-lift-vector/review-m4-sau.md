### Review Summary

BL-16 M4 (commit `03b67fcb`, branch `fix/bl16-flight-epoch-bound`, same tip as
`feature/bl16-lift-vector-law`): on `fd_mode` entering mode 1 (voice take or unpark m2 -> m1),
fires a new `controls-to-petrovich` effector sequence that switches SAU H/K/T off, B on — the twin
of the existing `controls-to-player` hand-back sequence. Adds three curated OFF-button effectors,
a new per-sequence-file `step-delay-s` header override, and the `controls_to_petrovich_edge`
pure-function twin of `controls_to_player_edge`.

This is a focused, well-scoped change. Against spec (`explore-notes.md` "M4 SAU explore
(2026-11-28)" and BL-16.md's "M4 re-scoped" paragraph): matches exactly — H/K/T off, B on, on
mode-1 entry only, never on mode-2 entry, zero spacing on both SAU sequences only, every other
sequence's default spacing untouched.

**Verification performed** (this review's own runs, body-layer/):
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, no issues, 95 files
- Targeted tests (`test_flight_authority.py test_body.py test_effector_engine.py
  test_effector_sequences.py`, `-m "not slow"`): 435 passed
- `tools/render_switch_reference.py --write` and `tools/render_triggers.py --write`: both
  regenerate byte-identical to the committed files (confirmed via `git status`) — the two
  generated docs are current, satisfying the staleness requirement without relying on the
  implementer's own say-so
- `test_render_triggers.py`, `test_tuning_defaults_toml.py`: pass — confirms `defaults.toml` is
  correctly unaffected (`step-delay-s` is a sequence-file field, not a `tuning.*` constant, so it
  correctly does not go through the tuning mechanism)
- Cross-checked the three new OFF-button curated entries (`p_sau_h/k/t_channel_off`) directly
  against `config/effectors-raw/mi-24p.toml`: device 10, cmds 3007/3003/3011, args 236/242/248,
  `cmd_names` `ButtonHoff`/`ButtonKoff`/`ButtonToff` — genuinely separate momentary buttons from
  the existing `ButtonHon`/`Kon`/`Ton` ON buttons, matching `effectors.toml`'s claim and the
  `switch-reference.md` "Curated as" cells exactly
- Traced `controls_to_petrovich_edge`'s and `controls_to_player_edge`'s shared call site in
  `body.py`: both read the same `previous_flight_authority` capture and the same post-advance
  `crew_console.flight_authority_state`; the two edges are mutually exclusive by construction
  (one requires `new.fd_mode == "off"`, the other `new.fd_mode == "m1"`), so there is no ordering
  question across a single transition, and the fast-release-and-retake case within one poll is
  the same pre-existing polling limitation every other edge detector in this file already has —
  not a defect introduced here
- Traced the "momentary press, zero spacing" mechanism: all four SAU rows write to the same DCS
  device (10, AUTOPILOT) via four distinct `cmd`s, in a single `advance()` call when
  `step_delay_s=0.0`. This is the same "write multiple cmds on one device within one poll" shape
  the pre-existing `test_cold_takeoff_writes_four_switches_in_order_with_spacing` fixture already
  exercises (two of its four writes target device 6, different cmds) — zero-spacing only removes
  the *inter-row* delay the engine already had no principled reason to apply across different
  switches (the delay exists for the same-switch animation-to-readback margin, per
  `EFFECTOR_SEQUENCE_STEP_DELAY_S`'s own docstring); it does not introduce a new write shape

### Required Fixes

None.

### Optional Refinements

- **`step-delay-s` has no dedicated `nan`/`inf` test, though the code already rejects both
  correctly.** Root `CLAUDE.md`'s standing rule (implementer.md "Code Rules", 2026-11-25) asks for
  a float parsed from outside the process to be checked with `math.isfinite()` *and* to carry a
  `nan`/`inf` test. The parse here (`_parse_header`, `effector_sequences.py`) does call
  `math.isfinite(step_delay_value)` and correctly rejects both — confirmed by hand: `step-delay-s
  | nan` in a sequence file's header is dropped with `"step-delay-s must be a finite number >= 0,
  got 'nan'"`. But `test_step_delay_s_negative_drops_the_file` only exercises the `< 0` half of
  that `or`, and `test_step_delay_s_non_numeric_drops_the_file` exercises the separate
  `float(...)` `ValueError` path (a string that doesn't parse as a number at all, e.g. `"soon"`)
  — neither is a `nan`/`inf` case, since `float("nan")`/`float("inf")` both parse successfully in
  Python and only fail the `isfinite` check. A genuine test gap against the standing rule, not a
  correctness bug; worth a two-line addition (optional, since the code path is already verified
  correct by hand in this review).
- **No flight-test card exists yet for this specific behaviour** — zero-spaced, same-device,
  multi-cmd cockpit writes is a DCS-internals question this project's own posture says can only be
  settled by a live sortie, not static review (`aircraft-layer/CLAUDE.md`: Export.lua/the live path
  has no automated test, correctness is validated by hand against a running mission). Nothing in
  the implementation gives reason to expect a problem (see verification above), and the user's own
  direction explicitly asked for this exact behaviour knowing it touches DCS internals — so this is
  not a blocker, but DoD/the next test card for this branch should include a check that all four
  SAU channel lamps/indications land correctly on a take and a hand-back, not just that the law
  flies correctly afterward.

### Verdict
APPROVED

### Review Confidence
Full read — plan/spec, implementation note, all touched source and test files read in full; ran
format/lint/type/targeted-test checks myself rather than trusting the implementer's own report;
independently cross-checked the three new effector entries against the raw command dump;
regenerated both derived docs (`switch-reference.md`, `triggers.md`) to confirm no staleness.
