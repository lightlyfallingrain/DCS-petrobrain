# Review: BL-16 LV-1 pitch law-domain sign fix (5105b9a8)

Reviewed against parent `16ac9ed9`. Inputs: `plans/flight-lift-vector/debug-2026-11-24c.md` ("Pitch
direction, main-loop finding" section), `review-debug-1124c.md` (the prior review that left pitch/roll
`LAW_DIR = +1` as an open, optional risk). Log (read-only, outside this worktree):
`/Users/sg/Code/DCS-petrobrain-epochfix/docs/acceptance/logs-2026-11-24/data_flight_trace.log`,
session index 9 (0-based, split on `t=0.000 `), t=24–42.

### Review Summary

**(1) Independent trace verification — confirmed, not just re-read from the report.**

Pulled session 9's own `theta_d`/`pitch`/`t_p`/`out_pitch`/`thetadot` columns directly (not the
debug note's numbers). At t=28.05–30.21, `theta_d − pitch` grows from slightly negative to +6.4°
(pitch falls from 3.2° to −3.7° while `theta_d` keeps rising — the law correctly wants more
nose-up), `t_p` (the integral term) rises 0.113→0.191 over the same window, and `out_pitch`
(the pre-wobble *written* command, confirmed from the module's own comment to be `last_command` in
command/write domain) rises 0.051→0.377 in lock-step. Separately, correlating `out_pitch` against
`thetadot` (pitch rate, independently established as positive = nose-up from the trace itself, not
assumed) shows the rising command *preceding* a swing to strongly negative `thetadot` (−0.28 →
−5.35 as `out_pitch` climbs 0.052→0.203): a rising written command drives the nose further down,
confirming the arg-1100 correlation from the M0 probe independently, from this flight's own data.
So: with `LAW_DIR.pitch = +1` (as flown, the buggy value), P and I both correctly ask for more
nose-up (positive, growing) while that positive law output passes straight through to a command
that the aircraft's own response shows drives the nose further down — textbook positive feedback,
exactly the claimed defect. The `k_q` damping term sits inside the same `u_pitch` expression that
gets flipped as one unit by `LAW_DIR` at the output boundary (`law_domain(law_outputs(...))`), so
its sign relative to P/I is preserved by the fix and needed no separate check — confirmed by reading
`command_for`/`law_domain`, not assumed.

**(2) Every pitch consumer — single conversion point, domain-consistent.** Traced each one named in
the task:
- `t_p`/`theta_d`/`theta_i` (`law_update`, `law_outputs`) — law domain throughout, `measured.pitch_deg`
  itself already reasons nose-up-positive (confirmed from `read_measured`'s own M0 citation: arg 1100
  correlates −0.56 with `pitch_deg`, and arg 1100 positive = nose down, so `pitch_deg` positive = nose
  up). Unaffected by `LAW_DIR`.
- `theta_speed_give`/`d_theta_i` (speed-give chain, line 944/985) — computed and applied entirely
  inside the law-domain trim integrator; never touches `LAW_DIR`.
- Anti-windup on `t_p` (±1) — a symmetric bound, correct regardless of which physical direction
  "positive" maps to.
- `trim_hold` attitude check (line 974) — compares `state.theta_d` against `measured.pitch_deg`,
  both law domain, unaffected.
- Unpark/take seed — `law_init_at_take`'s `theta_i = measured.pitch_deg` (law domain, unaffected) and
  `t_p = command.pitch + k_q*rate`, where `command` is `law_domain(command)` at the one call site
  (line 2638) — confirmed this is the *only* other `law_domain()` call, and that it is the inverse
  operation of the output-side `law_domain(law_outputs(...))` at `command_for` (line 2533), so the two
  cancel exactly at take. The new `test_take_stays_bit_exact_on_pitch` exercises this directly
  (0.23 captured → 0.229–0.231 written, inside the existing ±0.0011 wobble tolerance) and I did not
  just trust the assertion — read both `law_domain` call sites myself to confirm there is no third.
- Body-layer fields — `out_pitch` etc. in `format_trace_line` are `fc_last_command` (command/write
  domain, diagnostics only, confirmed by the module's own new comment at the trace formatter) and
  `schema/flight_control.py` only reads them for display, no sign logic. `flight_desired.lua` has no
  `pitch` reference at all (grepped directly) — nothing there to re-convert.

No second conversion site exists; the domain crossing happens exactly twice (seed, write) and they
cancel at take, same structure already verified for the collective fix.

**(3) Roll `LAW_DIR = +1` — checked against the same trace, still not a defect here.** Pulled
`phi_d`/`bank`/`t_r`/`out_roll`/`phidot` from the same session/window. Unlike pitch, roll shows no
divergence: `phi_d` and `bank` track each other with an ordinary lag throughout — `phi_d` peaks at
46.3° (t=28.67), `bank` peaks at 44.0° about 0.9 s later (t=29.59) and then both reverse together;
`out_roll`'s sign and magnitude follow the proportional error (`phi_d − bank`) plus a damping term
that visibly opposes fast rate swings (e.g. at t=31.75, `phi_d − bank` is strongly negative yet
`out_roll` is still mildly positive while `phidot` is already strongly negative — consistent with
rate damping preventing overshoot, not a sign error). This is a real, if informal, trace-based check
(not just "no reported runaway"), and it is consistent with roll being correctly signed — but it is
still not a derivation, and `SIGN.roll` is still flagged in the module header as an unverified
probe-v2 guess pending M0-E. Carried forward as the same optional risk the prior review named, now
with one additional piece of (non-conclusive) supporting evidence from this flight.

**(4) New test — independent plant fact, not circular.** `TestPitchLawDirection`'s assertion rests on
"command 2001 positive drives pitch down" (the arg-1100 correlation), which is a fact about the real
aircraft established independently of the law's own `theta_d`/`t_p` convention — not restated from
`LAW_DIR` or any law-internal quantity. The test drives `pitch_rad` down via direct mutation (an
external disturbance the module never writes itself) and asserts the *written* command falls — this
is checkable without reference to what the law "intends," which is the right shape for a regression
test on a sign bug. Confirmed non-circular by re-deriving it, not just reading the docstring.
Mutation: reverting `LAW_DIR.pitch` to `+1.0` alone reproduces the report's stated failure
(`0.37025 ≮ -0.001`) — re-ran this myself rather than trusting the commit message's account.

**(5) Checks** — `ruff format --check`/`ruff check` clean on `aircraft-layer/src` and `tests`;
`mypy --strict` clean (`cd aircraft-layer && .venv/bin/mypy src`, 29 files); `luac5.1 -p` clean on
every file in `dcs-export/` and `dcs-export/Petrobrain/`; `.claude/scripts/fast-tests.sh
aircraft-layer` → 1 failure (`test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers`,
`OSError: [Errno 48] Address already in use`), reran that file alone and got 2/2 passed — the known
flake, not a regression. No `GETGLOBAL` scan needed: this diff adds no new local function or
module-level variable to `flight_control.lua`, only a constant value and comments, so there is
nothing new for the hoisting-bug detector to catch.

**Scope** — the diff stays inside `flight_control.lua` (constant + comments), the two docs
(`debug-2026-11-24c.md`, the M0 research note), and the one new test class. The superseded table row
in `debug-2026-11-24c.md` is marked "**Superseded 2026-11-24**" rather than deleted, per
`docs/PROCESS.md`'s supersession convention — correct, not a comment-pruning violation. No drift into
body-layer or any other subproject.

### Required Fixes

None.

### Optional Refinements

- **Roll's `LAW_DIR = +1`/`SIGN.roll` is still an open, unverified risk** (pre-existing, not
  introduced by this commit, and this commit does not touch it). The trace-based check above (3) adds
  one more data point of informal support but is not a substitute for flying M0-E. Not a required fix
  here.

### Verdict

APPROVED

### Review Confidence

Full read of the diff (`flight_control.lua`'s changed sections, the test addition, both doc edits).
Independently re-extracted and re-derived the trace evidence for both pitch (required check 1) and
roll (required check 3) from the raw log myself, rather than taking the debug report's numbers on
trust — the numbers matched the report's account for pitch, and for roll showed tracking consistent
with (though not proof of) the existing sign. Verified the single-conversion-point claim (2) by
reading both `law_domain()` call sites directly. Ran all checks in (5) directly rather than citing the
commit message. No live DCS access from this review — the fix is not flight-verified by this pass,
only by the data flight that found the bug (unchanged collective/pedal behaviour from the prior
review is assumed, not re-verified here, since this diff does not touch those axes).
