# Review — BL-16 Stage P1 takeover/stabilisation revision

Reviewed: `d3bfe9df` (aircraft-layer), `72bac70e` (body-layer mirrors), `f3fc0f5d`
(implementation.md), diffed against `993be9a5`. Against `plans/flight-control/plan.md`'s "Revised
2026-11-16" section (including the "Amended 2026-11-16" sub-section, which wins where it
disagrees) and `plans/flight-control/alignment.md`'s "Plan check — 2026-11-16". The later merge of
`main` (raster-viewer/docs) was not reviewed, per the dispatching instructions.

Worktree note: dispatched tip was `c29a67c0`, built on top of the three commits above via a merge
of `main`. `git merge --ff-only` from a clean ancestor HEAD landed it with no conflict.

### Review Summary

The state machine (detect → handover snapshot → blind toggle → menu open/keep-open → quick path
or two-phase hold → unpark) is implemented correctly against the plan for every path I could trace
and test: detection on 852 alone, the handover snapshot taken in the same frame as the rising
edge, the keep-open settle/reopen logic, the two-phase hold's live-then-snapshot targets with
phase skipping, the unpark reset, the restricted press vocabulary (no generic `press(direction,
duration)`, nothing ever presses `WHEEL_RIGHT`/`AI_WHEEL_LEFT`), the old one-shot nudge fully
removed, the version bump genuinely justified (`apw_last_press`'s vocabulary changed), and the
single shared `list_indication(6)` read per 5 Hz tick preserved from the Batch A perf fix. Both
subprojects' format/lint/type/test checks are clean, including the Lua integration-test tier run
against a real interpreter (`luajit` here, Lua-5.1-compatible).

One real correctness gap and one process-compliance gap need fixing before this goes to DoD; both
are small.

### Required Fixes

- **The quick path's second centre pulse (R → B) resolves the whole takeover with no check that
  the resulting barometric target is actually within tolerance of the handover altitude**
  (`update_ai_pilot_wheel_overlay`, the `correction_substage == "quick_read2"` branch,
  `Export.lua:2588-2593`: sets `correction_substage = nil; stage = nil` unconditionally on the
  next read, regardless of what `ai_pilot_alt_text` says).
  - The implementer's own justification — "trusted per the plan's own 'then go on to step 6's
    checks'" (`implementation.md:269-270`, repeated at `:393-395`) — **cites text that does not
    exist anywhere in `plan.md`**: I grepped the current file and the full history of
    `plans/flight-control/plan.md` for `"step 6"` and for `"go on to"`; the only hits are an
    unrelated `step 6a` reference (a different plan section, about a grep-for-write-sites
    discipline) and the implementer's own two mentions of the phrase. The plan is silent on
    whether the second pulse needs a tolerance re-check — this was the implementer's own call, not
    a plan instruction, and the citation supporting it does not check out.
  - The underlying risk the plan exists to guard against is exactly this: ED's own barometric
    target-setting is the thing documented as unreliable ("sometimes it has set something way
    incorrect," pilot, quoted in `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`), and the
    probe measured it wrong on **both** of the two times the *first* toggle after takeover was
    observed (+742 m, +737 m). The plan's evidence for the *second* toggle being reliable is
    **exactly one sample** (1080 against 1084, from the rehearsal probe's T4). Nothing establishes
    that the second toggle is immune to the same bug the first one demonstrably isn't.
  - If it recurs on the second pulse, the sequence resolves to `stage = nil` /
    `correction_path = "quick"` with nothing left watching the altitude — no hold ever opens,
    because the quick path's own eligibility and this resolution are the only things that run.
    That is the uncorrected-sink/climb failure this entire revision exists to fix, reached through
    the one path that was supposed to be the fast, low-risk option, and it would be silent: the
    status push would show `correction_path = "quick"`, which reads as success.
  - Quick-path eligibility is gated on the aircraft's own AGL being below 700 m — i.e. this path is
    attempted precisely in the project's normal low-altitude operating envelope, so an unverified
    error here is not a rare-corner concern.
  - No test exercises "pulse 2 succeeds but the resulting target is still wrong" — `test_quick_
    path_success` only exercises the case where pulse 2's reading already happens to be correct.
  - **Fix**: after the `quick_read2` read, compare the held altitude against
    `ai_pilot_takeover.handover_altitude_m` within `AI_PILOT_ALT_TOLERANCE_M` (the same comparison
    `ai_pilot_decide_correction` already makes for the initial decision); if out of tolerance, fall
    through into the two-phase hold (`ai_pilot_begin_hold_phase`) instead of resolving to `nil`,
    the same way the first pulse's refusal already falls through when it reads back `"B"`. Add a
    test for that fallback the same way `test_quick_path_falls_back_to_hold_when_still_baro` covers
    the first pulse's refusal.

- **The Co-moving Fields table (plan.md) was never extended for the "Amended 2026-11-16" quick
  path**, despite the plan's own explicit instruction to do exactly this once the stage lands
  (`plan.md:769`: *"Implementer's grep, once this stage lands: `grep -n "takeover_stage\s*="
  aircraft-layer/dcs-export/Export.lua` and the same for every other field above — confirm every
  write site matches a row here, and extend the table with any that does not"* — citing `BL-B71`'s
  fourth construction site as the precedent this guards against).
  - The table (`plan.md:758-767`) only documents `apw.parked_active`, `apw.takeover_stage`,
    `apw.menu_open`, and `apw.altitude_correction_{cmd,target_m,deadline_t}`. It predates the
    "Amended 2026-11-16" sub-section, which introduced `correction_substage`
    (`"quick_read1"`/`"quick_read2"`) and the `correction_path = "quick"` write — neither appears
    in the table.
  - I ran the grep the plan asks for (`grep -n "correction_substage\s*=\|correction_path\s*="
    aircraft-layer/dcs-export/Export.lua`): real write sites exist
    (`Export.lua:2358-2371`, `2571-2593`) with no corresponding table row — a one-for-one repeat of
    the `BL-B71` failure mode the plan itself names as the reason this step exists.
  - No evidence in `implementation.md`'s "Revision 2026-11-16" section that this grep was run; no
    update to `plan.md`'s table accompanies these commits (confirmed: `plan.md` has no commits
    between `993be9a5` and `d3bfe9df`).
  - This is a documentation-only gap — I traced the state machine by hand and found it internally
    consistent — but it is a plan-mandated step that was skipped, and it is the exact gap future
    stages (P2-P6) will need the table for when they extend this sequence. **Fix**: extend the
    table with `correction_substage`'s transitions and the quick-path's own `correction_path`
    write, per the plan's own instruction, before this lands.

### Optional Refinements

- **Lua 5.1's 200-live-local ceiling is now at exactly 200, with zero headroom**, confirmed by my
  own `luac5.1 -p` run (clean) and the implementer's own count (193 before this revision, 217
  before dedup, 200 after). The removed constants (`LONG_PRESS_HOLD_S`, `AI_WHEEL_LEFT`/`RIGHT`)
  are genuinely dead — I grepped for every one and found no remaining reference — so the count is
  honest, not hiding a bug. Acceptable for *this* merge: nothing is broken, the constraint and its
  resolution are well documented (inline comments, `implementation.md`, and an implementer
  agent-memory note). But Stage P2 is already known to need a real goal channel and mode-cycle
  state, and starts with no slack at all — worth a line in the plan's "Downstream effects" or in
  P2's own kickoff flagging that it must budget locals (e.g. folding more of the existing
  individual-local fields into a table) before it can add anything, not discover the ceiling again
  mid-stage (optional — not blocking this revision).
- **`ai_pilot_check_hold_convergence`'s phase-1→phase-2 transition duplicates
  `ai_pilot_begin_hold_phase`'s own dir2-computation/open-hold/`last_press` logic** instead of
  calling it (`Export.lua:2403-2419` vs `2335-2343`). Plausibly deliberate, given the local-count
  pressure (extracting a shared helper would not even help, since a new function is itself a
  local), but it is dual-maintenance risk if `ai_pilot_begin_hold_phase`'s phase-2 logic is ever
  changed and this copy is missed. Not required — no behavioural difference found between the two
  copies today.
- The blind centre tap (point 2) and the menu-open tap (point 3) now fire on the **same frame**
  in production (`run_ai_pilot_wheel`'s sequential `if` blocks fall through within one call), where
  the rehearsal probe that validated this sequence live used a 1.0 s gap between them
  (`MENU_OPEN_DELAY_S`). The plan does not mandate a gap, and nothing in the probe's own write-up
  attributes the gap to anything but measurement convenience, so I'm not flagging this as a
  required fix — but it is a real divergence from the exact sequence that was flown, worth a
  one-line note if a live Flight P1 ever shows the menu failing to open reliably right after the
  blind toggle.

### Checks run

**aircraft-layer/** (fresh `.venv`, `python3 -m venv .venv && pip install pytest mypy ruff`)
- `ruff format --check src tests`: pass (79 files already formatted)
- `ruff check src tests`: pass
- `cd aircraft-layer && .venv/bin/mypy src`: pass, no issues (27 source files)
- `pytest tests -q`: **765 passed** (matches implementation.md)
- `luac5.1 -p aircraft-layer/dcs-export/Export.lua`: pass (Homebrew `luac5.1`)
- `luac5.1 -l -p ... | GETGLOBAL check`: only genuine DCS/stdlib/debug-flag globals
  (`GetDevice`, `list_indication`, `Lo*`, `io`, `lfs`, `DUMPED_*`, stdlib) — no accidental-local bug
- Lua integration tests (`TestTakeoverSequence`, 7 tests) ran for real against `luajit`
  (Lua-5.1-compatible; no bare `lua5.1` interpreter on this Mac) — not skipped

**body-layer/** (fresh `.venv`, plus `pyproj`/`numpy` for the world-model seam)
- `ruff format --check src tests`: pass (204 files already formatted)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, no issues (83 source files)
- `PYTHONPATH=src:../world-model/src pytest tests -q`: **3284 passed, 4 xfailed** (pre-existing,
  matches implementation.md)

Live DCS behaviour is the pilot's to test; nothing above claims it works in flight. The branch to
fly is `feature/bl16-takeover-fix` (or wherever this lands after merge) — Flight P1 (revised),
named in `plan.md`, is the test card.

### Verdict

**NEEDS REVISION** — both required fixes are small (one Lua branch plus a test; one plan-table
edit) and this should return from Implementer straight back to Reviewer for a quick re-check, not
a new planning pass.

### Review Confidence

Full read of the three commits' diffs and the full state machine in `Export.lua`; traced every
write site for every Co-moving Field by hand and by grep (not just read the table). Ran every
check myself rather than trusting the implementer's reported numbers (they matched). Did not
re-review the plan/alignment documents' own prior findings beyond confirming they were resolved
(Finding 1's transient-disclosure fix and Finding 2's status-push field are both present in
`plan.md` as written) — those were plan-aligner's and the user's own closed loop, not re-litigated
here.

---

## Re-review — fix round `306af5f0` (2026-11-16)

Diffed `306af5f0` against this review's own tip (`a2282097`, i.e. the three commits reviewed
above). The later merge of `main` (`fdbfe9b5`, raster-viewer/docs/tooling) carries nothing of this
feature; not re-reviewed.

### Required Fix 1 — quick path's second pulse re-check

**Done as specified.** `update_ai_pilot_wheel_overlay`'s `correction_substage == "quick_read2"`
branch (`Export.lua:2600-2614`) now re-reads the held altitude, compares it against
`ai_pilot_takeover.handover_altitude_m` via `ai_pilot_correction_direction` (the same helper
`ai_pilot_decide_correction` uses for the initial decision), and on an out-of-tolerance result sets
`correction_path = "hold"` and calls `ai_pilot_begin_hold_phase`, the same shape `quick_read1`'s own
refusal branch already used. Within tolerance, behaviour is unchanged (`stage = nil`,
`correction_path` stays `"quick"`).

New test `test_quick_path_falls_back_to_hold_when_pulse2_still_wrong` exercises exactly the gap the
required fix named: both pulses complete (B → R → B) but the readback is still wrong. I mutated the
fix out (reverted the branch to its pre-fix unconditional `stage = nil`) and re-ran that one test —
it failed for the stated reason (`path` read back `"quick"` instead of `"hold"`) — then restored
the file and confirmed `sha256` matched the pre-mutation value exactly (`de7cdbf4...`, `git status
--porcelain` clean afterward). The counterfactual the implementer reported checks out; this is not
a test that would pass either way.

### Required Fix 2 — Co-moving Fields table

**Substantially done, one residual gap.** The table (`plan.md:758-772`) now carries a row for every
transition the "Amended 2026-11-16" quick path introduced — both `correction_path` values from
`ai_pilot_decide_correction`, both `quick_read1` outcomes, and both `quick_read2` outcomes including
this round's own new fallback — plus a row for the falling-edge (unpark) clear of both fields. I
independently re-ran the plan's own grep
(`grep -n "correction_substage\s*=\|correction_path\s*=" aircraft-layer/dcs-export/Export.lua`) and
every site it names does have a matching row.

The grep also turns up one site neither this round's note nor my own first review named: the
**rising-edge reset** (`Export.lua:2503`, inside `run_ai_pilot_wheel`'s `if rising then` block) sets
`ai_pilot_takeover.correction_path = nil` at the start of a new takeover cycle, and no row in the
table documents it — the existing `apw.parked_active | rising edge` row only lists
`takeover_stage`/`takeover_t` in its "Must hold true after" column. This line predates the fix round
(`git blame` puts it at `d3bfe9df`, the original revision commit, same commit that introduced
`correction_path` itself), so it isn't something this round broke; it's a one-site gap this round's
own "ten write sites, all now covered" claim overstates slightly (by my count, excluding the two
`==` comparisons the grep pattern also matches, there are 14 literal assignment/initialiser lines
for these two fields, not 10 — the discrepancy is this one site plus how the grouped falling-edge
pair is counted). Behaviour is correct and already covered by the state-machine trace in the first
review; this is a documentation-completeness miss only, same category as the original finding, one
site smaller. Not worth another Implementer round for a single table row — flagged below as an
optional follow-up rather than reopening this fix.

### Main-loop timing decision — 0.5 s centre-to-menu gap

Matches the rehearsal probe's measured timing. `ai_pilot_takeover.menu_open_at_t` is set to
`t + AI_PILOT_MENU_OPEN_DELAY_S` (0.5) when the blind centre tap fires, and the menu-open tap is
gated on `t >= ai_pilot_takeover.menu_open_at_t` rather than firing same-frame. Checked the three
points asked for:

- **Cleared on unpark**: `run_ai_pilot_wheel`'s falling-edge branch sets
  `ai_pilot_takeover.menu_open_at_t = nil` alongside the rest of the sequence state
  (`Export.lua:2489`).
- **No misbehaviour in the gap**: during `"opening_menu"` but before `menu_open_at_t`,
  `ai_pilot_takeover.menu_open` is still `false`, so `update_ai_pilot_wheel_overlay`'s keep-open
  check (gated on `menu_open`) cannot fire; `awaiting_correction_decision` isn't set until the
  menu-open tap actually lands, so the one-shot correction decision cannot act on a menu that isn't
  open yet. The `elseif` chain in `update_ai_pilot_wheel_overlay` has nothing else to catch a tick
  mid-gap — it is a correct no-op.
- **Constant placement**: `AI_PILOT_MENU_OPEN_DELAY_S` lives as a field on `ai_pilot_takeover`
  rather than a new top-level local, consistent with the file's own 200-live-local ceiling (review's
  prior Optional Refinement) — confirmed by `luac5.1 -p` passing and no new global leaking
  (spot-checked the diff; nothing added a bare top-level `local`).

All of `TestTakeoverSequence`'s pre-existing scripts were updated for the new gap (an extra
`run_ai_pilot_wheel` call at the +1.0 s mark, every later timestamp shifted +0.5 s) rather than left
to silently test the old same-frame behaviour; `test_menu_reopens_after_the_settle_window` is
correctly left untouched since it drives the keep-open check directly.

### Optional refactor — `ai_pilot_check_hold_convergence` calling `ai_pilot_begin_hold_phase`

**Behaviour unchanged.** At the call site, `held` has just converged to within tolerance of
`live_m` (that is what releases phase 1), so `ai_pilot_begin_hold_phase`'s own `dir1 =
ai_pilot_correction_direction(held, live_m)` recomputes `live_m` on the same tick with no state
change in between and resolves to `nil` by construction, falling straight through to the `dir2`
check against `handover_altitude_m` — the same check, same outcome, the duplicated code performed.
`test_hold_path_two_phases` and `test_hold_path_skips_phase1_when_already_at_live` both still pass
and exercise this transition.

### Attribution correction

`implementation.md`'s "then go on to step 6's checks" misattribution is corrected in place (not a
new paragraph pretending it was always right): the prior entry now says plainly the phrase was the
main loop's dispatch-brief wording, not the plan's, confirmed absent from `plan.md` by grep, and
points at the 2026-11-16 fix for the behaviour itself. Matches what actually happened.

### Checks run (independent)

**aircraft-layer/** (fresh `.venv`)
- `luac5.1 -p aircraft-layer/dcs-export/Export.lua`: pass
- `ruff format --check src tests`: pass (79 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside the subproject): pass, no issues (27 source files)
- `pytest tests -q`: **766 passed** (matches `implementation.md`)
- `pytest tests/test_ai_pilot_wheel_lua.py -v`: all 26 pass, including all 8
  `TestTakeoverSequence` tests by name, against `luajit` (Lua-5.1-compatible; no bare `lua5.1` on
  this Mac) — not skipped
- Counterfactual on the new test: reverted the `quick_read2` fix, confirmed red, restored,
  confirmed `sha256` match and clean `git status --porcelain`

**body-layer/** (fresh `.venv`, plus `pyproj`/`numpy` for the world-model seam; source unchanged
this round, confirmed via `git diff --stat a2282097 306af5f0 -- body-layer/` — empty)
- `ruff format --check src tests`: pass (204 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside the subproject): pass, no issues (83 source files)
- `PYTHONPATH=src:../world-model/src pytest tests -q`: **3284 passed, 4 xfailed** (matches
  `implementation.md`)

### Optional Refinements (new this round)

- **One Co-moving Fields row still missing**: the rising-edge reset of `apw.correction_path` to
  `nil` (`Export.lua:2503`) has no row in the table. Pre-existing (from `d3bfe9df`, not introduced
  this round), behaviour is correct and already traced, and it's a single line to add — not worth
  another Implementer dispatch. Add `| apw.correction_path | internal | rising edge | reset to nil
  alongside apw.takeover_stage above |` (or fold it into the existing `apw.parked_active` rising-edge
  row's "Must hold true after" column) whenever `plan.md` is next touched for this feature.

### Verdict

**APPROVED** — both required fixes are done and independently verified (behaviourally, not just by
re-reading the diff): Required Fix 1 by mutation-testing its own test, Required Fix 2 by re-running
its own grep and tracing the one site it still misses back to a pre-existing, non-regressing gap.
The main-loop timing decision and the optional refactor both check out with no behavioural
surprise. All checks pass in both subprojects, matching `implementation.md`'s reported numbers
exactly. Nothing in this round broke what the first review already traced as correct.

### Review Confidence

Full read of `306af5f0`'s diff against all four changed files. Verified Required Fix 1 by
mutation (reverted/confirmed red/restored/confirmed sha match), not just by reading the branch.
Independently re-ran the Required Fix 2 grep rather than trusting the ten-sites count in
`plan.md`'s own note, which is how the one residual gap (rising-edge reset) surfaced — logged as an
optional follow-up rather than treated as a new blocker, since it predates this round and is
documentation-only. Ran every check myself in a fresh venv rather than trusting reported numbers
(all matched). Did not re-trace the full state machine from scratch — relied on the first review's
own full trace for everything this round did not touch.
