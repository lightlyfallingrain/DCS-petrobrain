# Review: BL-16 LV-1 debug pass 3 (a1eec022)

Reviewed against parent `de2e6d4c`, inputs `plans/flight-lift-vector/debug-2026-11-24c.md`,
`docs/acceptance/2026-11-24-sortie-feedback.md`, `debug-2026-11-24b.md`/`review-debug-1124b.md`,
and the gitignored data-flight logs the report cites.

### Review Summary

Two independent claims, verified independently rather than taken from the report:

**Finding 2 (collective law-domain sign) — confirmed, and the fix is correctly scoped.**
Re-derived from the law's own equations (`c_dot_nominal`, `u_c_rate`, the RPM/blade-stall/pedal-limit
guards, the torque feed-forward at line 1018, anti-windup) that every one of these was already
written assuming "`u_c` positive = more lift" — none of that internal math changed in this diff.
The only places that changed are the two domain crossings: `law_init_at_take`'s seed
(`law_domain(command)` instead of raw `command`) and the output write (`law_domain(law_outputs(...))`
via `command_for`). Confirmed by mutation: flipping `LAW_DIR.collective` back to `+1.0` fails
`TestCollectiveLawDirection` (written 2087 goes to −0.57 instead of rising past −0.25 while climbing)
— the regression test genuinely exercises the fixed boundary, not a tautology. The torque
feed-forward term (`k_pedal_from_collective_rate * u_c_rate * rotor_dir`) is unaffected: `u_c_rate`
was always computed in the physical domain (it was never SIGN-mapped), so its calibration from
`debug-2026-11-24b` carries over unchanged — this pass does not need to, and does not, touch it.
Guards, shortfall chain, anti-windup, the integrator split (`u_c_i`), release/handback and the
unpark-take path are all internal to the law and likewise untouched and unaffected. Mode-2 paths
don't exist yet at LV-1 (forward flight only), so there is nothing there to check. Body-layer's
`GET /flight_control/latest` carries no goal/`u_c` field (diagnostics only since Stage 3) — nothing
on that side depends on the domain.

**Pitch/roll `LAW_DIR = +1` — correctly left alone, and the open risk is pre-existing, not new.**
Traced the pitch loop by hand: `SIGN.pitch = 1.0` is documented in the module header as "probe v2's
own unverified guess, flip once M0-E reports" — i.e. this was already an open, named risk before
this commit, not something this pass introduced or was obligated to close. Working through
`k_theta_i`'s sign against the M0 finding that arg 1100 positive = stick forward = nose down gives
an inversion *if* the command-to-arg relationship is 1:1 at `SIGN.pitch = 1` — but M0-E (the step
probe that would settle this) was never flown, so there's no independent ground truth to check it
against, same gap the debug report's own "what remains unproven" table names. Two things keep this
from being a required fix here: (1) the debug report is explicit that this is unexamined rather than
silently assumed correct, and (2) the data flight's own log says "pitch, roll and collective args
follow their commands with no offset" and the user has not reported a pitch/roll runaway the way
the collective one was reported — empirical evidence (though not a derivation) that whatever the
sign convention is, it isn't producing positive feedback in practice. Flagged as optional below;
not a defect in this commit.

**Finding 1 (pedal write bias) — the learner measures the real quantity, not a circular one.**
`observed = written − SIGN·arg` in `learn_write_bias` reduces to the physical offset `B` regardless
of the current bias estimate `b` (because `written = intended + b` and `p_meas = written − B_true`
algebraically cancel `b` out of `observed`), so the EMA converges on the measured quantity from
finding 1's own table, not on the law's assumption about itself. Confirmed this isn't accidentally
circular by re-deriving it, not just reading the comment.

- **Seat tracking**: `fc_capture_seat` is set once at take and the learner reads that seat back for
  the whole session. This matches the real log (pilot set carried both capture and write even with
  the player in the operator seat) and the finding that which argset tracks the live controls is a
  DCS-side property, not something that changes mid-session — reasonable not to re-resolve every
  frame.
- **Reset paths**: `on_stop` clears `fc_write_bias`/`fc_write_bias_anchor`/`fc_capture_seat`, and
  `reset(epoch)` calls `on_stop`, so a body-layer epoch reset also returns to the seed — checked
  both call sites directly.
- **Take re-anchoring**: `fc_write_bias_anchor = {}` is reset on every take, preventing a stale
  anchor's elapsed time from falsely satisfying the settle gate right after a take.
- **Saturation/settle gates**: present on both the write side (`math.abs(written) >= 0.999`) and the
  read side (`math.abs(arg) >= 0.999`, plus a `nan` check).
- **Pause/re-issue path**: `write_outputs(fc_last_command, nil)` on a paused frame re-sends the
  already-biased value directly — bias is not re-applied on top of itself. Checked, correct.
- **Mutation, independently re-run**: flipping `LAW_DIR.collective` fails the collective test (above).
  Separately re-ran the report's disclosed gap — removing the settle-*time* half of the settle gate
  (keeping only the saturation checks) — and confirmed it independently: all 1007 tests still pass.
  The report discloses this honestly and defends it with the real log instead of a test; that is an
  accepted, not hidden, gap (see Optional below).

**Tests**: `TestCollectiveLawDirection` asserts a real-domain fact (2087 rises while climbing, where
"rising" is independently established as "down" by the measured `SIGN.collective`/arg correlation,
not re-derived inside the test) — not circular. `TestPedalWriteBias`'s toy plant models the
independent physical relationship from finding 1 (`arg = 0.32 − command`, first-order lag) rather
than restating the law's own assumption, and exercises seed/learn/carry/clear as the debug report
claims. Pedal take-capture assertions were correctly updated to add the bias seed rather than
rewritten to hide the change.

**Checks**: `ruff format --check`/`ruff check` clean, `mypy --strict` clean (`cd aircraft-layer &&
.venv/bin/mypy src`), `luac5.1 -p` clean on every `dcs-export` file, `.claude/scripts/fast-tests.sh
aircraft-layer` → 1007 passed. `GETGLOBAL` scan of `flight_control.lua` (the project's own
hoisting-bug detector) shows no new local function/variable leaking as a global read — `law_domain`,
`learn_write_bias`, `command_for`, `trace_write_bias`, `fc_write_bias`, `fc_write_bias_anchor`,
`fc_capture_seat`, `fc_last_steady_seat` are all absent from the list; everything present is stdlib,
a DCS API, or an existing cross-module name.

**Provenance/research**: the 0.32 pedal offset and its per-take table are recorded, dated, in
`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md` with "cause in DCS unknown"
stated plainly rather than guessed at — matches the project's no-unverified-claims rule.
`write_bias_seed`/`write_bias_bound`/`write_bias_tau_s`/`write_bias_settle_s`/`write_bias_settle_band`
are behaviour-affecting constants with `--` comments; aircraft-layer has no tuning loader (confirmed
against `aircraft-layer/CLAUDE.md`), so a bare profile-table field with a comment is the right form,
same posture as every other field in `flight_profile.lua`.

**Scope**: the diff stays inside `flight_control.lua`/`flight_profile.lua` plus tests/research/a
debugger memory note — no drift into body-layer, no unrelated refactor. `command_for`'s new
responsibility (domain mapping + bias) sits at the one existing output seam (`write_outputs`'
caller), not a new parallel write path.

### Required Fixes

None.

### Optional Refinements

- **Pitch/roll `LAW_DIR = +1` is still an open, unverified risk** (pre-existing, not introduced here)
  — `SIGN.pitch`/`SIGN.roll` are themselves documented as "probe v2's own unverified guesses" pending
  M0-E. Worth flying M0-E (the step-response probe) before this stage is considered settled on all
  four axes, since the method that caught the collective bug (checking every consumer of a sign
  against an independently measured fact) hasn't been applied to pitch/roll yet. Not a required fix
  for this commit because this commit doesn't touch, and doesn't claim to settle, that axis.
- **The settle-*time* half of the write-bias settle gate has no test discriminating it** (confirmed
  independently by mutation: removing it leaves 1007/1007 green). The report defends this with the
  real log instead of a test and says so plainly, which is the right posture given the toy plant's
  constant-command limitation — but a toy-plant scenario with a *moving* command through the settle
  window (not just a step-then-hold) would close the gap without needing a new plant model.
- **The dangling memory link** `[[bl16-sign-revert-guard-flowthrough-check]]` in
  `.claude/agent-memory/debugger/project_bl16_law_vs_command_domain.md` has no matching file in this
  worktree yet — fine per the memory convention (a link may precede the memory it names), just
  noting it isn't resolved today.

### Verdict

APPROVED

### Review Confidence

Full read of the diff (`flight_control.lua`, `flight_profile.lua`, the test file) and the debug
report. Independently re-derived finding 2's domain fix from the law's own equations rather than
accepting the report's account, and independently verified two of its mutation claims by actually
reverting `LAW_DIR.collective` and by actually removing the settle-time gate (both reproduced the
report's stated result). Pitch/roll were traced by hand against the module's own documented
SIGN-pitch/roll uncertainty; not independently flight-verified (no live DCS access from this review).
Body-layer side checked only for the absence of a `u_c`/collective-domain field to worry about
(confirmed absent, diagnostics-only) — not a full body-layer sweep, since the diff does not touch
that subproject.
