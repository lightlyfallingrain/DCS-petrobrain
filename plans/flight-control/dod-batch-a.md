# Definition of Done: BL-16 parked mode (mode 2), batch A — Stage P-ICS, Stage P0 probe, Stage P1

**Branch:** `feature/flight-control`. **Verdict scoped to tip `98d251f0`** ("Reviewer: BL-16
flight-control perf fix (8331086d) -- APPROVED"). If the branch moves after this report, the
verdict is stale.

**Worktree note:** this agent's worktree was created from a stale `origin/HEAD` (`0fa6c92f`), not
an ancestor of the task's tip. Moved with `git switch -C worktree-agent-a51093798ffde60d8
98d251f0`; confirmed `HEAD == 98d251f0`, tree clean, before doing anything else.

## Verdict: PASSED

## Scope

Diff `fde7398e..98d251f0` (27 files, 3529 insertions / 36 deletions): `aircraft-layer` and
`body-layer` only — confirmed by `git diff --name-only`, nothing outside those two subprojects
plus `plans/flight-control/*` and two `.claude/agent-memory/` files. Matches the plan's own
Stage P-ICS/P0/P1 scope; grepped for every P2+ symbol (`set_parked_heading`, `cbtm_align`,
`recover_to_level`, `goal_seq`, `AI_PILOT_SPEED_STEPS_KMH`, `BREAK_AWAY_GAP_S`,
`HVRT_TRANSLATE_MAX_HOLD_S`) in production code — none present outside docstrings/plan
cross-references, confirming nothing from P2 onward shipped.

## Code Quality — checks run fresh in this worktree, not taken from any report

Both subprojects' `.venv`s were absent (fresh agent worktree); created
(`python3 -m venv .venv && .venv/bin/pip install -e . ruff mypy pytest`).

**aircraft-layer/**
- `ruff format --check aircraft-layer/src aircraft-layer/tests` — 79 files already formatted
- `ruff check aircraft-layer/src aircraft-layer/tests` — all checks passed
- `cd aircraft-layer && .venv/bin/mypy src` — success, no issues, 27 source files
- `pytest aircraft-layer/tests -q` — **753 passed** in 81s (matches review's own count)
- `luac5.1 -p` on `Export.lua` and `Export.probe-ai-pilot-wheel.lua` — both OK
- `luac5.1 -l -p` GETGLOBAL scan on `Export.lua` — only genuine DCS/stdlib globals and the
  pre-existing `DUMPED_*` one-shot dumps; no accidental global from this diff

**body-layer/**
- `ruff format --check body-layer/src body-layer/tests` — 204 files already formatted
- `ruff check body-layer/src body-layer/tests` — all checks passed
- `cd body-layer && .venv/bin/mypy src` — success, no issues, 83 source files
- `pytest body-layer/tests -q` — **3281 passed, 4 xfailed** in 280s (4 xfailed pre-existing per
  implementation.md, unrelated to this batch)
- `tools/generate_defaults.py` reran against the committed `config/defaults.toml` — up to date,
  no diff

No debug output, no unhandled errors/panics in data paths, no stray TODOs introduced by this
batch (confirmed by reading every changed production file during the review/security passes and
spot-checking here).

## Reviewer findings addressed

`review-batch-a.md`: first pass CHANGES REQUIRED (one required fix — missing aircraft-layer-side
test tier for `AiPilotWheelState`/`AiPilotWheelCache`/collector-routing/the `GET
/ai_pilot_wheel/latest` endpoint). Fixed at `618ec14f` (`test_ai_pilot_wheel_api.py`, 15 tests,
mirroring `test_sight_servo_api.py`'s structure); re-reviewed and **APPROVED**. Perf fix
(`8331086d`, moving the per-frame `list_indication(6)` parse to the 5 Hz tick) reviewed
separately and **APPROVED** — the change-request-reenters-the-loop rule
(AGENTS.md) was followed: Performance Reviewer → Implementer → Reviewer, not straight to DoD.

**Independently re-verified, not taken on trust:**
- E-P6 (`HDG LOS`/short-right never pressed): `grep -n "AI_WHEEL_RIGHT\|WHEEL_RIGHT"
  aircraft-layer/dcs-export/Export.lua` → exactly one hit, the constant's own declaration
  (line 1993). No call site pairs it with a press.
- E-P10 (unpark releases every open press, drops state, same frame): read
  `run_ai_pilot_wheel`'s `if not now_parked then` branch (`Export.lua:2194-2200`) directly —
  clears overlay fields, the pending press, and `ai_pilot_pending_nudge`, all in the unpark
  branch.
- `git status --porcelain` — clean. No build artefacts, `.sqlite`/`.pyc`/image files in the diff
  (`git log --name-only fde7398e..98d251f0 | grep -iE ".png|.jpg|.sqlite|.pyc"` — empty).
  `aircraft-layer/research/img` does not exist.

## Performance Reviewer

`perf-batch-a.md`: NEEDS MITIGATION (unthrottled per-frame `list_indication(6)` read + full
recursive parse while parked, 12-24x the project's conservative device-read rate). Mitigated at
`8331086d` exactly to the mitigation's own shape (moved the read+parse to the existing 5 Hz
block, reusing one `list_indication` read for both the AI-wheel overlay and the existing
`petrovich_indication` push); re-reviewed by Reviewer and **APPROVED**, including an independent
mutation-test rerun. One MONITOR item carried forward to Stage P2 (don't reintroduce per-frame
reading for the "release on readback-within-tolerance" check) — not a batch-A gate.

## Security

`security-batch-a.md`: **APPROVED**. No dependency change; one new LAN-facing read-only endpoint
(`GET /ai_pilot_wheel/latest`), same risk class as 8+ sibling `/latest` endpoints already
accepted; E-P6 independently re-verified (not taken on the Reviewer's grep alone); no
code-execution surface, no new write-capable endpoint, no prompt-injection surface wired yet (no
spoken line in this batch).

## Accepted-items ledger (U1/U2/U3)

`.claude/scripts/accepted-items-ledger.sh plans/flight-control` reports "decisions U1 U2 U3 not
yet answered (no `**Answered` line)" — **this is a false negative of the mechanical script, not a
real gap**: `plans/flight-control/plan.md:564` does carry a `**Answered 2026-11-15` line for U3,
but it is indented two spaces (inside the U3 bullet's own continuation), and the script's `grep
-qE '^\*\*Answered'` only matches a line with no leading whitespace. Checked by hand instead:

- **U1** (silent no-op vs. spoken refusal for `cbtm_align`/`cbtm_align_for_launch` outside
  CBTM-reachable state) — **not answered by the user**, architect's own recommendation stands
  provisionally. Concerns **Stage P3** (`cbtm_align`), not built in this batch. **Deferred to
  Stage P3.**
- **U2** (same question, restated for scope — mid-cycle refusal vs. only after exhaustion) —
  same status. Concerns **Stage P2/P3**'s mode-cycle-then-press machinery, not built in this
  batch. **Deferred to Stage P2/P3.**
- **U3** (player changes the AI wheel's mode himself — always-reassert vs. a grace window) —
  **answered by the user, 2026-11-15, verbatim**: *"reassert at once — the goal is to use the
  wheel command via Petrobrain, not player directly."* The mechanism this answer governs is
  `decide_ai_pilot_wheel`'s mode-cycle-back logic, which is **Stage P2** (the goal/mode-cycle
  loop) — Stage P1 (this batch) has no goal channel and no mode-cycle-back at all, so there is
  nothing in this batch for U3 to have been built into. **Deferred to Stage P2**, where the
  answer is already recorded as the production design (plan.md's E-P traceability table, E-P5
  row, and `alignment.md`'s "Plan check Q-P1 answered by the user").

None of U1/U2/U3 needed to land in batch A; all three are correctly scoped to later stages and
the plan already says so. Flagging the script's indentation-sensitivity as process debt (see
memory note below) rather than treating it as a real gap.

## Scope & Correctness

- Implementation matches `plans/flight-control/plan.md`'s "Revised 2026-11-15" parked-mode series
  for Stages P-ICS/P0/P1 exactly — confirmed by implementation.md's own file list and the scope
  grep above.
- No unplanned scope added: `implementation.md`'s "Notable Discoveries" lists exactly one
  necessary addition beyond the plan's letter (`FakeConsoleAircraftClient.
  get_ai_pilot_wheel_latest`, required because the poll loop now calls the method
  unconditionally — a mechanical consequence of Stage P1's own design, not scope drift), caught
  by running the full suite rather than the targeted new tests.
- No CLAUDE.md invariants violated: module independence held (aircraft-layer stays stdlib-only;
  body-layer's new file imports only `tuning`/`aircraft_client`, both already in the codebase);
  no omniscience violation (the new state is all AI-wheel overlay text, not ground truth); the
  HTTP-only aircraft-layer↔body-layer seam is unchanged.
- All new files staged and committed — `git status --porcelain` clean at tip `98d251f0`.

## Testing

Core logic covered: Lua pure functions (`parse_helperai_overlay_fields`, `ai_pilot_park_rising`,
`ai_pilot_should_nudge_altitude`) run against a real Lua interpreter; the PttSample OR-semantics
truth table; the new `AiPilotWheelState`/`AiPilotWheelCache`/collector-routing/endpoint tier
(`test_ai_pilot_wheel_api.py`, added as Required Fix 1); body-layer's `advance_parked_flight_state`
against a real loopback `AircraftLayerClient` (no mocked urllib, per project convention). Three
mutation checks across the review/security/perf passes (construction-site carry-forward,
unpark-clears-pending-nudge, nudge-fires-only-once) independently confirmed load-bearing, not
tautological. No existing tests broken — 753/753 aircraft-layer and 3281/3281 (+4 pre-existing
xfail) body-layer, full suites, both green.

## Documentation

Reviewer findings addressed (above). Non-obvious behaviour explained in `implementation.md`'s
"Notable Discoveries" (the `apw.mode`/`apw.press` notation is conceptual not literal Lua; the
tolerance-constant duplication across Lua/body-layer, flagged for Stage P2 to resolve into one
source) — both are also carried in the plan itself, not left to code comments alone.

---

## Acceptance boundary — what batch A's fixtures structurally cannot reach

Every check above is a fixture/unit/mutation check or a direct code read. **None of it can tell
whether the AI pilot wheel actually behaves this way in a running DCS mission.** Specifically out
of reach without a live flight:

- **Whether `list_indication(HELPERAI_DEVICE_ID)` is actually populated while parked with the
  wheel/overlay closed** (P0-1) — this is the one genuinely open empirical question in this
  batch; the Lua parse functions are tested against *known* overlay text shapes from the research
  note, not against whatever DCS actually returns in the closed-overlay case.
  the park-sink fix (do fewer frames stutter, does the readback converge, does a real
  `GetDevice(30):performClickableAction` press actually move the AI's held altitude by the amount
  the overlay says) have no fixture that can stand in for DCS's own encrypted native AI-pilot
  logic.
- **Whether the ICS-capture OR-of-two-raw-values change (P-ICS) is heard correctly from the
  operator seat in a real cockpit** — the Lua debounce-on-either-change logic is proven against a
  Lua interpreter, not against the real arg-856 trigger under a real headset.
- **Whether the per-frame cost reduction (the perf fix) is actually imperceptible in the
  cockpit** — the perf report's own numbers are architectural (call-rate multiplier, discarded
  work), not a measured frame-time delta on a running mission.

This is why Flight P-ICS and Flight P1 exist as named test cards below, and why this report's
acceptance verdict is **PENDING (live)**, not PASSED.

## Acceptance testing — what the user must fly (verbatim from the plan)

**Flight P-ICS**: from the **operator seat**, hold the ICS trigger to its intercom stop (not the
pilot's), confirm `GET /ptt/state`'s `"intercom"` goes true and capture starts — the same
observable behaviour the pilot's own trigger already produces. Release, confirm it drops. Then
repeat from the pilot seat, to confirm nothing regressed.

**Flight P0** (seven rows, Stage P0 probe script `Export.probe-ai-pilot-wheel.lua`, parked,
operator seat, ED's AI flying):
1. **P0-1** — `list_indication(HELPERAI_DEVICE_ID)` content while parked, wheel/overlay closed
   vs. open. Pass: populated either way, or only with the overlay open (if the latter, that is a
   known cosmetic limitation to state on the card, not a redesign).
2. **P0-2** — one held press at 0.7 s on each outer-ring position in FLT, confirmed against the
   overlay readback moving as a long action, not a repeated short tap. Pass: 0.7 s reliably reads
   as long on this wheel too.
3. **P0-3** — speed tap sequence from 0 to MAX, reading `speed_text` after each tap. Pass: the
   exact step list and MAX's displayed value are recorded.
4. **P0-4** — press-release-to-readback latency. Pass: a number, used as `MODE_READ_SETTLE_S`'s
   floor.
5. **P0-5** — centre press (baro/radar toggle) from each reference. Pass: confirm readback flips,
   and whether re-setting altitude after the toggle is actually required.
6. **P0-6** — on park, confirm the sink and the fix: set altitude to current immediately on park,
   observe whether the AI still sinks first. Pass: no sink, or sink stops within a few seconds.
7. **P0-7** — FLT→HVR speed criterion: tap speed down to 0 in FLT, observe when `mode_text`
   itself flips without a mode-cycle press. Pass: a number or a settle time.

Go/no-go: nothing here can fail into a blocker — every row either confirms a number already
believed or narrows a cosmetic detail (P0-1).

**Flight P1**: park with the AI holding some altitude, confirm no sink and no speech. Unpark,
confirm nothing untoward (no goal exists yet to drop).

**Pass criteria**: Flight P-ICS's intercom-open/close behaves identically from both seats; Flight
P0's seven rows each produce *a* recorded answer (none can fail outright, per the plan's own
go/no-go); Flight P1 shows no altitude sink on park and no speech on either park or unpark.

## Acceptance: PENDING (live)

Per root `CLAUDE.md` "Workflow" and the user's 2026-10-26 direction (batched live testing, DoD
PASSED merges automatically): this DoD pass does not wait for a flight. `#needs-flight` is set on
`body-layer/ROADMAP/BL-16.md` for Flight P-ICS, Flight P0 and Flight P1; the branch to fly is
`main` once this merges. The main loop publishes the test card via `/test-card` — not this report.

## Milestone-completion question

**Does batch A change what Stage P2 should be, or invalidate a downstream assumption?** Yes, in
one concrete way the perf review already flagged and this report inherits rather than
re-deriving: **Stage P2's "release when readback reaches target" should default to riding the
same 5 Hz tick the perf fix just established**, not reintroduce a per-frame `list_indication(6)`
read — the AI wheel's fields move in discrete, human-press-rate steps, not a continuously-moving
analog value, so a 5 Hz comparison costs at most ~200 ms of extra hold, the same slack already
accepted for the one-shot nudge. This is a MONITOR item, not a blocker: if a live P2 test shows
visible overshoot at 5 Hz, that is the trigger to revisit, not an assumption to build around now.
Separately, **the 20 m altitude tolerance is duplicated in two places** (body-layer's
`AI_PILOT_ALTITUDE_TOLERANCE_M` and Export.lua's `AI_PILOT_NUDGE_EPSILON_M`) until Stage P2 wires
a real goal channel between them — Stage P2 should resolve this into one source of truth rather
than let both drift independently; no behavioural risk today since no channel exists yet to carry
either value anywhere.

## Commit

Staged: this file (`plans/flight-control/dod-batch-a.md`). Both `.venv` directories created in
this worktree are gitignored (not staged). No other files changed by this DoD pass.
