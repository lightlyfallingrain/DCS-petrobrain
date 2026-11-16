# Definition of Done — BL-16 revised Stage P1 (takeover and stabilisation)

Branch `feature/bl16-takeover-fix`, verdict scoped to tip **`72062c1f58464b5e9f39efecba12c175b8a8a41e`**
(fast-forwarded cleanly from this worktree's prior tip `cfb06b19`, which was a strict ancestor; no
conflict, no rebase). **If the branch moves past this sha before merge, this verdict is stale.**

## Mechanical checks (run and quoted, not assumed)

**Lua syntax / local-count ceiling**

```
$ luac5.1 -p aircraft-layer/dcs-export/Export.lua
```
→ passes silently (no "main function has more than 200 local variables" error). Independently
confirmed `AI_WHEEL_LEFT`/`AI_WHEEL_RIGHT` are not declared anywhere (`grep -n "AI_WHEEL_LEFT\|AI_WHEEL_RIGHT" aircraft-layer/dcs-export/Export.lua` → no hits), matching the Implementer's
"removed, exactly 200 locals" claim and the Security review's E-P6 finding.

**aircraft-layer/** (fresh `.venv`, built in this worktree)

```
$ cd aircraft-layer && .venv/bin/ruff format --check src tests
79 files already formatted
$ .venv/bin/ruff check src tests
All checks passed!
$ .venv/bin/mypy src
Success: no issues found in 27 source files
$ .venv/bin/pytest tests -q
766 passed in 82.26s (0:01:22)
```

**body-layer/** (fresh `.venv`, built in this worktree)

```
$ cd body-layer && .venv/bin/ruff format --check src tests
204 files already formatted
$ .venv/bin/ruff check src tests
All checks passed!
$ .venv/bin/mypy src
Success: no issues found in 83 source files
$ PYTHONPATH=src:../world-model/src .venv/bin/pytest tests -q
3284 passed, 4 xfailed in 280.33s (0:04:40)
```

All four numbers (766 / 27 mypy-clean files / 3284+4xf / 83 mypy-clean files) match
`implementation.md`'s and `review-takeover.md`'s own independently-run numbers exactly. The
body-layer run took ~4.5 minutes in this fresh worktree (no cached bytecode) — ran to completion
in the foreground via a bounded Monitor wait, not assumed from a background task's silence.

**Debug output / dead code scan** — `git diff 993be9a5..72062c1f` over
`aircraft-layer/dcs-export/Export.lua`, `aircraft-layer/src`, `body-layer/src` for
`TODO|FIXME|XXX|print(|console.log|debugger|pdb.set_trace`: no hits outside test files. No
unhandled-error/panic pattern introduced (Security's own grep covered `eval`/`exec`/`loadstring`/
secrets — none found; this pass independently re-ran the TODO/debug grep).

**Staging** — `git status --porcelain` empty at `72062c1f`.

## Scope & correctness

- Implementation matches `plans/flight-control/plan.md`'s "Revised 2026-11-16 — takeover after
  the Batch A flights" section (including "Amended 2026-11-16") point for point:
  detection on arg 852 alone (952 demoted to diagnostic), handover-altitude snapshot taken on the
  rising edge, 0.5 s blind centre tap then menu-open tap, keep-open/reopen on a settled nil read,
  quick path (AGL-gated, two pulses, re-verified against tolerance after Required Fix 1) falling
  back to the two-phase hold, unpark resetting everything and closing the menu. Independently
  re-traced against `Export.lua` (not just re-read from `implementation.md`'s account) for the
  quick-path re-check (`correction_substage == "quick_read2"` branch) and the Co-moving Fields
  table's write-site coverage (`grep -n "correction_substage\s*=\|correction_path\s*="` →
  14 sites: 2 table-literal initialisers + 12 assignments, all with a matching row in the table,
  including the rising-edge reset row the re-review flagged as missing and which is present in
  the merged file).
- No unplanned scope: `implementation.md`'s "Notable Discoveries" items (the 200-local ceiling
  fix, the `ai_pilot_takeover` table departure from the "no `apw` table" convention, the three
  undeclared-but-behaviour-affecting constants) are all consequences of building the plan, each
  flagged in place rather than silently introduced, and each already covered by Reviewer/Security.
- No CLAUDE.md invariant violated: no generic `press(direction, duration)` entry point (E-P6,
  confirmed structurally — the only paths that can open a press are the two altitude directions
  and the restricted `ai_pilot_tap30`), no cockpit write outside the two already-accepted channels,
  no scope creep into mode 1 (unparked) or P2–P6.
- `git status --porcelain` empty — all new/modified files are committed at `72062c1f`.

## Testing

- Core logic covered: `TestTakeoverSequence` (8 cases, Lua integration against a real
  interpreter) exercises detect→toggle→open→{none, quick success, quick-refused-to-hold,
  quick-succeeds-then-still-wrong-falls-to-hold}→unpark end to end; pure-function tests for
  `ai_pilot_correction_direction`/`ai_pilot_quick_path_eligible`; body-layer/aircraft-layer schema
  round-trip tests for the four new wire fields including a `bool`-is-not-a-number regression.
  Reviewer independently verified both required-fix tests by mutation (revert → confirm red →
  restore → confirm sha match) rather than trusting them read-only — I did not repeat the mutation
  myself but did independently re-run the full suite and the targeted `-v` listing
  (`aircraft-layer`: 766 passed including all 8 `TestTakeoverSequence` tests by name).
- No regressions: both subprojects' full suites pass at the numbers quoted above, matching every
  prior round exactly — no silent drop in collected test count.

## Documentation

- **Reviewer findings addressed**: `review-takeover.md`'s first pass was NEEDS REVISION with two
  required fixes (quick-path second-pulse tolerance re-check; Co-moving Fields table gap). Both
  fixed and independently re-verified by the Reviewer's own re-review (behaviourally, by
  mutation and grep re-run, not just by re-reading the diff) → **APPROVED**. Both Optional
  Refinements from the first review (table-field-not-top-level-local for the menu-open delay;
  `ai_pilot_check_hold_convergence` reusing `ai_pilot_begin_hold_phase`) were applied. The
  re-review's own one Optional Refinement (missing rising-edge `correction_path` reset row) is
  present in the merged `plan.md` — confirmed by grep above, not carried as an open item.
- **Accepted-items ledger** (`.claude/scripts/accepted-items-ledger.sh plans/flight-control`):

  ```
  ledger plans/flight-control: decisions U1 U2 U3 not yet answered (no **Answered line) --
  nothing accepted to check.
  ```

  **This mechanical result is a false negative, checked by hand rather than trusted**: the
  script's `^\*\*Answered` regex requires the marker at column 0, and the mode-2 "Decisions
  Requiring User Input" section's U3 answer is indented two spaces as a list-item continuation
  (`  **Answered 2026-11-15 (user, verbatim):** ...`), so the script never sees it. Reading the
  section directly (`plan.md:562-577`):
  - **U1** (refusal posture for `cbtm_align` outside CBTM-reachable state) — **unanswered**,
    deferred to Stage P2/P3. Nothing to build in this round; correctly out of scope.
  - **U2** (same question, mid-cycle vs. post-exhaustion) — **unanswered**, deferred to Stage
    P2/P3. Same posture.
  - **U3** (player changing the AI wheel's mode himself: reassert at once vs. defer) —
    **answered** 2026-11-15, verbatim *"reassert at once"*. **Governs Stage P2's mode-cycle-back
    logic, not built in this batch** — Stage P1 (this revision) has no goal channel or
    mode-cycle-back at all, so U3 has nothing to land against yet. Deferred to Stage P2, stated
    explicitly in `plan.md`'s own "Decisions Requiring User Input — unchanged by this revision"
    note and in `body-layer/ROADMAP/BL-16.md`'s existing text. Not a gap in this round.

  All three accounted for: U1/U2 correctly deferred-unanswered, U3 correctly deferred-answered.
  None required by this revision's own scope (altitude-only takeover stabilisation).
- **Non-obvious behaviour**: explained via `implementation.md`'s "Notable Discoveries" (both
  rounds) and `plan.md`'s own Risks section — the correction-loop rate being unmeasured for a
  multi-second hold, the telemetry mystery being "resolved by construction, pending
  re-observation," the "AI always starts on radar" residual assumption. All already on the
  record; nothing further needed from this pass.

## Security

`plans/flight-control/security-takeover.md` — **APPROVED**, both rounds (plan review was not run
for this revision per the current on-demand-only posture; this is the deep-analysis pass).
E-P6 holds structurally (forbidden commands not even declared); no new network-reachable write
surface, no code-execution surface, no prompt-injection surface (the new wire fields are a closed
numeric/enum vocabulary); the wire-field NaN/Infinity pattern is on the safe `float()` side.
**One non-blocking finding** (`LuaExportStop` not releasing an open AI-pilot-wheel press across a
mission-end/restart inside an up-to-60s hold window) was presented via the Risk Communication
Format, not silently waived — the user's own prior direction (scheduling) already resolved it:
filed as `aircraft-layer/ROADMAP/AC-B13.md`, folded into `AC-B12` (the Export.lua module-split,
scheduled before BL-16's next stage). Confirmed both entry files exist and are correctly cross-
linked (`AC-B12.md` "Also carries `[[AC-B13]]`"; `AC-B13.md` "Pick it up in `[[AC-B12]]`") and
indexed in `aircraft-layer/ROADMAP/aircraft-layer-roadmap.md` (`grep -n "AC-B12\|AC-B13"` → both
present, `#status/open`).

## Performance

`plans/flight-control/perf-takeover.md` — **APPROVED**. The one `list_indication(6)` read per
5 Hz tick is still shared by every consumer (confirmed by reading the call site directly); the
new takeover/correction state machine is stage-gated, not continuous per-frame allocation.

---

## The acceptance boundary — what fixtures structurally cannot reach

Every check above is a fixture, a Lua-interpreter integration test, or a static read of the
source. None of them can observe:

- **Whether ED's AI actually behaves the way the rehearsal probe measured it behaving** on a
  *different* sortie, mission, or airframe state — the wild-baro-target bug, the 700 m AGL radar
  cap, the held-press acceleration profile (dead time → ~16 m/s → ~50 m/s) are all measured from
  **one pilot, one probe session**. A fixture can assert "given this sequence of overlay reads,
  the state machine does X" — it cannot assert ED's overlay will *produce* that sequence again.
- **Whether the pilot actually experiences the accepted ~130 m climb-then-descend transient as
  tolerable in a real sortie**, as opposed to accepting it in the abstract from a probe log and a
  plan-aligner write-up. The acceptance of Q1 (alignment.md) happened before this specific
  implementation flew.
- **The P1 telemetry mystery** (`apw_parked_active` reading `false` while the AI was demonstrably
  flying, one unexplained sample from Batch A) — "resolved by construction" is this revision's own
  stated hypothesis, explicitly flagged as pending re-observation on the next real flight, not
  something any test here proves.
- **Whether the menu staying open is actually acceptable in practice** over a longer flight, not
  just the ~2-minute probe session it was validated against.

This is exactly the class of gap the DoD role exists to name, not close: a fixture pass is not a
flight pass. Live acceptance is carried forward as `#needs-flight`, below.

## Acceptance Testing Plan — Flight P1 (revised)

**Goal:** verify the takeover/stabilisation sequence against real ED AI behaviour: no sink, the
command menu's own keep-open behaviour, the altitude converging to the handover value, and which
correction path actually ran.

**Branch to fly:** `main`, after this DoD report triggers the automatic merge.

**Prerequisites**
- [x] Type-checked and importable — confirmed above (`mypy src` clean in both subprojects).
- [ ] Deploy the updated `Export.lua` to the Windows box (`aircraft-layer/WORKFLOW.md` deploy
      steps) — the version string changed (`"2026-11-16"`), so a stale deployed file is caught by
      the collector's `EXPECTED_EXPORT_VERSION` mismatch log, not silently.
- [ ] Start from the operator (CPG) seat, controls unparked, in flight.

**Test Cases**
1. From the operator seat, hand over with **"Request Aircraft Control"** (the real binding name,
   category "Petrovich AI Helper, Multicrew" — not "park", which the original Batch A card
   wrongly implied) — expected: no sink; the command menu opens on its own within a second or two.
2. While the AI flies, manually close the command menu — expected: it reopens within about a
   second (keep-open/reopen logic).
3. Watch `apw_alt_text`/`apw_last_press`/`apw_correction_path` via
   `curl http://<aircraft-layer-host>:7791/ai_pilot_wheel/latest` (or the equivalent debug view)
   through the takeover — expected: the held altitude converges to the actual altitude at
   takeover (the handover snapshot), and `apw_correction_path` reads one of `quick`/`hold`/`none`.
   Note which one fired and how long convergence took — the rate for a multi-second hold is
   unmeasured beyond one probe session (Risks, above).
4. If `apw_correction_path` reads `"hold"` (the measured-common case per the plan's own evidence):
   expect the aircraft to climb roughly 100–150 m above the handover altitude before descending
   back to it — **this is the accepted, expected transient** (pilot, 2026-11-16: *"the workaround
   as planned is acceptable"*), not a regression to report.
5. Watch `apw_arg852`/`apw_arg952` — expected: 852 alone crosses 0.9 on takeover, 952 is its exact
   mirror (settles near 0 as 852 settles near 1).
6. Give the AI a moment to settle, then **unpark** (whatever binding returns control) — expected:
   the command menu closes, any open altitude press releases immediately, and nothing resumes
   (no leftover correction state) on the *next* park.

**Edge Cases to Probe**
- Park again shortly after a previous unpark — expected: the whole sequence restarts cleanly
  (fresh handover snapshot, fresh correction decision), nothing carried over from the prior
  takeover (E-P10).
- If the aircraft is above 700 m AGL at takeover — expected: the quick path (instant double pulse,
  no transient) is skipped; falls straight to the two-phase hold.
- Re-check whether `apw_parked_active` ever reads `false` while the AI is visibly flying (the
  unresolved telemetry mystery) — if it recurs, that is the trigger for a Debugger pass per the
  plan's own instruction, not something to carry forward unverified a second time.

**Pass Criteria**
No sink at any point; the menu opens/stays open/reopens as described; the held altitude converges
to the handover value (via whichever path); 852/952 behave as measured; unpark is clean and
nothing resumes on the next park. A ~130 m climb-then-descend on the hold path is a PASS, not a
fail, per the accepted transient above.

**Card published**: https://claude.ai/artifact/ASTZkpr1xRuaUhqR61jScf (source:
`docs/acceptance/2026-11-16-bl16-p1-revised-card.html`, index:
`docs/acceptance/2026-11-16-bl16-p1-revised-sortie.md`).

## Outstanding non-blocking items (not re-opened as gaps)

- **AC-B12/AC-B13** (Export.lua module split; `LuaExportStop` press release) — scheduled before
  BL-16's next stage (P2), not before this merge. Nothing to execute now: both are future
  Implementer work with no runnable "unblock" command today (they are code changes, not a
  probe/query that could be run from here).
- **P2's downstream dependency on the 5 Hz tick for readback-release** — a MONITOR item carried
  from the perf report, resolved only by a live P2 test, not by anything runnable now.
- **The correction-loop rate for a multi-second hold is a judgement call** (60 s safety ceiling),
  not independently re-measured by this pass — the one probe session's numbers (14 s to close a
  742 m error) are the only data point on record, and Flight P1 (above) is the next chance to add
  to it.

## Verdict: PASSED

All mechanical checks pass (re-run independently in this worktree, not trusted from
`implementation.md`'s report alone), Reviewer/Security/Performance Reviewer all APPROVED with
every required fix independently traced, no scope drift, no invariant violation, all three U-ids
accounted for (with the mechanical ledger's false negative explained rather than silently
accepted), tree clean at `72062c1f58464b5e9f39efecba12c175b8a8a41e`. Acceptance testing is
**PENDING (live)** — carried as `#needs-flight`, not blocking merge, per root `CLAUDE.md`'s
auto-merge-on-DoD-PASSED workflow.
