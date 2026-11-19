# Definition of Done: BL-16 mode-1 batch (break turn, break away, rotor envelope, VRS, rates as goals)

**Scope of this verdict**: branch `feature/bl16-mode1-break`, tip `fd40f7ea` — this report is
scoped to that exact commit. The branch has not moved since; if it moves before merge, this
verdict is stale and must be re-run.

Worked in the feature's own dedicated worktree, `/Users/sg/Code/DCS-petrobrain-bl16-m1-break`
(already at `fd40f7ea`, clean), rather than this agent's own isolated worktree — `git rev-parse
HEAD` there matched the expected tip exactly on first check.

## Code Quality

Subprojects touched, derived from `git diff --name-only a6e869f6..HEAD` (the plan+amendment
commit before this batch) against the tip, never from memory: **body-layer**, **aircraft-layer**.

Checks run from inside each subproject, using the main checkout's `.venv` by absolute path
(symlinked in, removed afterward — this worktree had no `.venv` for either subproject, same gap
the Implementer and Reviewer both hit and recorded):

**body-layer:**
- `ruff format --check src tests` — pass (227 files already formatted).
- `ruff check src tests` — pass.
- `mypy src` (run from inside `body-layer/`) — pass, 92 files.
- `tools/check_rules.py config/rules` — `ok: 1 rule file(s) checked` (wording/dry-run steps
  skipped with a warning: `audio-adapter/.venv` not built in this worktree, pre-existing, unrelated
  to this diff).
- `luac5.1 -p config/rules/flight.lua` — pass.
- `.claude/scripts/fast-tests.sh --full body-layer` (parallel, `pytest-xdist`): **3687 passed,
  4 xfailed, 0 failed** — matches `implementation.md` and `review-mode1-batch.md` exactly.

**aircraft-layer:**
- `ruff format --check src tests` — pass (85 files already formatted).
- `ruff check src tests` — pass.
- `mypy src` (run from inside `aircraft-layer/`) — pass, 28 files.
- `luac5.1 -p dcs-export/Petrobrain/flight_control.lua` — pass.
- `.claude/scripts/fast-tests.sh --full aircraft-layer` (parallel): **979 passed, 0 failed**.

No unhandled errors/panics in data paths — confirmed by Reviewer's and Security's full diff reads
(`review-mode1-batch.md`, `security-mode1-batch.md`); nothing new in this DoD pass contradicts
that. No debug output or leftover TODOs introduced by this batch — grepped the diff for
`print(`/`TODO`/`FIXME`/`XXX` across every changed file, none found beyond the pre-existing,
unrelated hits the grep also returns elsewhere in each file.

## Scope & Correctness

Implementation matches `plans/flight-control/plan.md`'s "Revised 2026-11-19 — mode-1 batch"
(Decisions 27–31) and "Main-loop amendment 2026-11-19" (Decision 32), per `implementation.md`'s
own "Mode 1 batch" section and confirmed independently by Reviewer's full diff read. No unplanned
scope added — the three Departures recorded in `implementation.md` (NOT_READY on unknown heading
instead of `assert`; Decision 32's exact seeding mechanism, not literally specified; the 60–80°
bank figure not reached) are all local, reversible engineering calls within the plan's own scope,
not scope additions, and Reviewer independently judged each one correct.

No CLAUDE.md invariants violated: single-player scope untouched; the behaviour-as-actions-and-
params shape (Decision 27's `goal.<x>_override` → `state.<x>_override` → settle-clear template) is
exactly the pattern root `CLAUDE.md` asks new behaviour code to use, named by the plan itself as
reusable for `[[BL-B95]]`'s later scripting work; tuning constants for every new behaviour-
affecting value (`ROTOR_RPM_FLOOR_PCT`, `RETREATING_BLADE_STALL_IAS_KMH`, `BREAK_MAX_HEIGHT_LOSS_M`,
`VRS_IAS_THRESHOLD_KMH`, `VRS_MAX_DESCENT_MPS`) went through `body-layer/tuning.py`, except
`BREAK_TURN_RATE_DEG_S`, which the user's own F-M2 answer explicitly routed to `config/rules/
flight.lua` instead — a stated, user-directed exception, not a silent departure from the standard
mechanism.

**`plan.md`'s "Decisions Requiring User Input" section for this batch is explicitly "None"** — the
2026-11-19 goal check's F-M1/F-M2 and Q-M1-1..3 cover every open question the batch raised,
verbatim, in `explore-notes.md`. Ran `.claude/scripts/accepted-items-ledger.sh plans/flight-
control`: it reports `U1 U2 U3 not yet answered (no **Answered line)` — those are an earlier,
unrelated section of this same long-lived plan file (mode-2's own decisions), already handled by
prior DoD passes on this plan (`dod-m1-m2.md`, `dod-p3p4.md`); the ledger script resolves only the
plan's *first* "Decisions Requiring User Input" section (a known limitation this plan's prior DoD
passes have already hand-verified past), and this batch's own section has no `U<n>` ids to check
against it. No gap.

All new/modified files staged and committed as part of the feature branch (confirmed below).

## Testing

Core logic covered: offline/`luajit` toy-plant tests for every new Lua mechanism (break turn
channel, rate-override clearing, break height floor, rotor/stall envelope guards, VRS descent cap,
rotor-RPM-read dummy/arg-proxy/fail-soft paths) plus pure-function tests for the Python-side action/
console changes and Decision 32's seeding. Tests are meaningful, not decorative — they assert the
qualitative mechanism (steeper-than-ordinary bank, converges, clears on settle/supersession, caps
only a rise never a fall) rather than pinning an unmeasured number, which both Implementer and
Reviewer flag explicitly as the correct choice given the 60–80° figure is not currently reached.
No existing tests broken — both full suites pass clean; the two "removal ripple" tests the plan
named for deletion did not exist in the first place (a phantom-test mismatch the Implementer caught
and recorded before touching anything), so nothing was wrongly deleted or inverted.

## Documentation

**Reviewer findings addressed**: `review-mode1-batch.md` — **APPROVED, no Required Fixes.** Every
Optional Refinement is accounted for (the Co-moving-Fields-table omission judged correctly not to
need a row, against prior memory and precedent; the 60–80° gap and integrator windup both already
flagged prominently for Flight M-A; Departure 1's NOT_READY guard confirmed correct).

**Accepted-items ledger**: see Scope & Correctness above — this batch raised no `U<n>` items, so
nothing to account for beyond confirming the ledger script's own report is the known limitation,
not a real gap.

**Non-obvious behaviour explained**: via `plan.md`'s own Decision sections, `implementation.md`'s
Departures, and two new `notes/feedback-control-law-design.md` entries added by this DoD pass (the
shaper-ceiling-vs-gain distinction behind the bank-figure gap; removing an output clamp also
removes the anti-windup it was incidentally providing).

## Security

`plans/flight-control/security-mode1-batch.md` exists and is **PASS**, no required fixes — every
new wire field bounded both at the HTTP boundary and (for `limits.*`) re-checked at the DCS-side
boundary; the one goal-field-not-rechecked-in-Lua observation is a pre-existing, non-exploitable
documentation-accuracy note, not a new gap; the rotor-RPM draw-arg read reuses an established,
read-only pattern.

## Deferred items, and whether their clearing condition was executed

- **Rotor RPM `arg_proxy` flip** — clearing condition is a live cockpit check (block 8/9 on the
  test card below), which genuinely cannot be run here; left `#needs-flight`, not run as a
  mechanical command because none exists yet.
- **The 60–80° bank figure / integrator windup** — clearing condition is Flight M-A's retune, also
  genuinely a live/architect-level action, not a script. Confirmed the *code path* that will carry
  the eventual fix (Decision 27's shaper branch) is exercised by the existing toy-plant tests, which
  is the only mechanical check available before that retune happens.
- **M3 reconciliation with Decision 29's break floor** — no clearing condition exists yet; M3 is
  not planned. Nothing to run.

No deferred item in this batch names a runnable command, script, or query as its own clearing
condition — each is genuinely gated on a future flight or a future planning stage, which is the
correct, not accidental, shape of `#needs-flight` debt here.

## Acceptance boundary

**What this batch's fixtures structurally cannot reach**: the toy-plant Lua tests drive the control
law against a simulated plant, not the real Mi-24P's actual rotor inertia, engine response, or
collective-coupling aerodynamics — so the measured bank angles (~43°/~54°), while a faithful
reproduction of what the *shaper* does, say nothing about whether the real aircraft's rotor RPM
genuinely droops the way the dummy-value code path assumes, whether the pedal bias feels right
under real yaw-rate feedback, or whether the integrator windup the fixtures show as a clean,
bounded overshoot stays bounded against real atmospheric turbulence and control lag. The rotor RPM
reading itself is entirely synthetic this batch (`"dummy"` at 90%) — no fixture or test exercises
the real cockpit gauge, its calibration, or its relationship to engine RPM. A fixture pass here is
not a flight pass; the test card below exists precisely because none of this can be learned any
other way.

## Verdict: PASSED

Acceptance testing: **PENDING (live)** — tagged `#needs-flight` on `body-layer/ROADMAP/BL-16.md`'s
mode-1-batch entry. Card published:
https://claude.ai/artifact/5ppAnRDqhdrapYbgLwZVKu
(source: `docs/acceptance/2026-11-19-bl16-mode1-break-card.md`). **Branch to fly: `main`, after
merge.**
