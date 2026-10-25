# Definition of Done — BL-B89 Stage 1 (9K113 sector scan)

Scope: Stage 1 only (`feature/9k113-scan-procedure`). Stage 2 (pointing) is designed, not built,
and is explicitly out of scope for this check.

**Verdict is scoped to tip `7611888cbbf5808828d59b0d742e5aede1c225d8`** — this worktree was a
clean ancestor of that sha (fast-forwarded, no divergence) at the time of this check. If the
branch has moved since, re-run.

## Mechanical checks (body-layer/, main checkout's venv — this worktree carries none)

- `ruff format --check src tests`: **pass** (173 files already formatted)
- `ruff check src tests`: **pass** (all checks passed)
- `mypy src` (cwd `body-layer/`): **pass** (74 source files, strict)
- `mypy tools` (cwd `body-layer/`): **pass** (10 source files, strict)
- `pytest tests -q`: **pass** — 2587 passed, 4 xfailed (identical count to Reviewer's own run,
  consistent with no code drift since review)
- `config/defaults.toml` vs `tools/generate_defaults.py --write`: **no diff** — regenerated into a
  scratch copy, diffed against the committed file, byte-identical
- `git status --porcelain`: **clean**, both before and after the regeneration round-trip

## Scope & correctness

- Implementation matches `plan.md` Stage 1: three-leg cycle (`wide_near`/`wide_far`/
  `narrow_far_sweep`), `choose_sighting_look`'s class-before-presence priority bucket,
  `SIGHT_SECTOR_WEDGE_DEG`/`SIGHT_AHEAD_LEGS` sector tables, mandatory per-lap naked-eye pause as
  a second trigger alongside `SIGHT_MAX_DWELL_S` — all verified by reading the code directly
  (`gaze.py:171-189`, `optic_policy.py`'s `SightSearchLeg`/`_idle_sight_search`/
  `_SEARCH_LEG_ORDER`), not only the implementation/review accounts of it.
- Spot-checked against the user's own verbatim words in `explore-notes.md`:
  - Sector spans: `left` (-30,30)→[-60,0], `right` (30,30)→[0,60], `full` (0,60)→[-60,60] — matches
    *"left scan -60 to 0 deg. right scan 0 to +60 deg."*
  - `SIGHT_AHEAD_LEGS`: (-10,20)→[-30,10], (10,20)→[-10,30] — matches *"alternating sequence -30
    to +10 deg and -10 to +30 deg"* exactly.
  - `SIGHT_SEARCH_NEAR_M = 1500.0` in the rendered `config/defaults.toml` — matches *"more like
    1.5 km - 4 km"*.
  - Naked-eye pause is wired as a mandatory per-lap trigger (`_idle_sight_search` routing to
    `_start_glance_away` on lap completion, independent of `SIGHT_MAX_DWELL_S`) — matches *"naked
    eye sweep -> ... a pause to 9K113 sweeping ... needed so that no surprise attack creeps up"*.
  - Stage 2 (pointing) correctly left designed-not-built, matching *"sector first, pointing as
    second stage"*.
- No unplanned scope added: `BL-B86`'s decline is correctly reflected (residue only — a nose-up
  test within 50-800 m AGL), `BL-B98` is filed as a found-not-introduced defect with its own ID,
  not silently folded into this stage's own claims.
- No invariants violated: no new omniscience path, no mechanism/calibration conflation (the
  derived→plain tunable change for `SIGHT_SEARCH_WIDE_FAR_M` is flagged and justified in the
  plan as a forced, explained exception), tuning additions follow the `X-T26` convention with
  `lo`/`hi` AST literals and rendered `#:` comments checked against the actual file, not the
  source comment.
- All new files staged: confirmed via `git status --porcelain` (clean) and the fast-forward diff
  listing (`plan.md`, `review.md`, `security-plan.md`, `security.md`, `implementation.md`,
  `performance-review.md`, `BL-B98.md`, plus the `.claude/agent-memory/reviewer/` memory file —
  all land as part of the merged commit history, nothing untracked).

## Testing

- Core logic covered: `TestChooseSightingLook`, `TestSightSearchLegs`, `TestSightSectorWedge`,
  altitude/attitude edge cases (nose-up at 100/300/800 m AGL, the 1-2 km band) — all read directly,
  not taken on the implementer's or reviewer's word (Reviewer's own re-review drove two of the
  edge-case tests directly; I re-ran the whole suite and got an identical pass/xfail count).
- Tests are meaningful: the lap-completion-vs-`SIGHT_MAX_DWELL_S` distinction is asserted via
  `phase_started_sim` timing, not just "a glance-away happened" — proves the *new* trigger fired,
  not the pre-existing one.
- No existing tests broken: 2587 passed, 4 xfailed, matching both the implementer's post-fix run
  and the Reviewer's own counts across two review passes.

## Documentation

- Reviewer findings addressed: both Required Fixes (the `_enter_binocular_search`/`_back_to_home`
  docstring correction, and `BL-B89.md`'s superseded-not-deleted decision line) were applied and
  re-reviewed, re-review verdict APPROVED.
- Non-obvious behaviour explained: `BL-B98` documents the dead-ahead-resume finding with root
  cause and citation to the settled F4/F5 acceptance criterion it falls short of; the plan's own
  "Notable Discoveries" in `implementation.md` records both altitude-edge measurements precisely
  rather than as a vague "mostly works."

## Security

- `plans/9k113-scan-procedure/security-plan.md`: **APPROVED**
- `plans/9k113-scan-procedure/security.md` (deep analysis): **APPROVED** — no code-execution,
  filesystem, network, or secrets surface touched; the one tunable cross-key coupling flagged is
  the same already-accepted shape as `belief.decay`'s own residual coupling, not externally
  reachable (local-user-edited `config/tuning.toml` only), and degrades to a non-stalling search
  at worst, not a crash or hang.

## Performance

- `plans/9k113-scan-procedure/performance-review.md`: **APPROVED — MONITOR**. `choose_sighting_look`
  measured cheaper than the `choose_look` path it replaces at every tested split except a
  pathological 90/10 skew (still ~1% of the 1 Hz poll budget there); the per-poll sweep generation
  and `_sight_commanded_sector` additions are O(1)/unchanged-order. No action required before
  merge.

## Acceptance testing

**Not run — needs a live DCS flight**, per the task scope ("do not merge, do not mark the roadmap
done"). Wrote `docs/acceptance/2026-10-25-bl-b89-sector-scan-flight.md` (do/expect/record blocks
covering sector commands and widths, the near band and per-lap naked-eye pause, the two
degraded-coverage altitude/attitude combinations, and `BL-B98`'s dead-ahead resume as an
observation, not a pass/fail). The main loop publishes the artifact card from that file — not done
here, per the task's explicit instruction.

**Acceptance boundary, stated up front rather than left implicit:** every test in this stage drives
the state machine with synthetic inputs. That proves the mechanism geometrically matches the spec
and never stalls. It cannot show whether the ahead-window alternation is noticeable without being
distracting, whether the per-lap pause reads as a natural beat or a stutter (especially where it
can now closely follow the pre-existing dwell-clock pause), or whether the two degraded-coverage
combinations look purposeful or broken from the cockpit. The flight card above is built to answer
exactly those three questions, not to re-verify the geometry a unit test already settled.

## Milestone-completion question

**Does this change what Stage 2 should be, or invalidate a downstream assumption?**

Yes, one concrete way: Stage 2's plan text (plan.md, "Co-moving Fields") already flagged that a
"pointed, not searching" state needs its own pass at the state machine, not a bolt-on field.
`BL-B98` (discovered by this stage, not introduced by it) sharpens that: Stage 2's design assumed
the sight "stays at last position" on return from a glance-away interruption — the exact claim
`BL-B98` shows is false for the existing glance-away mechanism. Whoever builds Stage 2 needs to
decide, before designing the pointed-state's own resume behaviour, whether `BL-B98` gets fixed
first (so pointing inherits a correct base) or whether pointing's own resume is deliberately
independent of the searching-state's resume path. Recorded here so Stage 2's own plan does not
silently inherit the same false assumption its own text already names as unresolved.

## Overall verdict: PASS

All mechanical, scope, testing, documentation, security and performance criteria pass. Acceptance
testing is the one outstanding item, correctly deferred to a flight rather than gating this DoD
pass — per root `CLAUDE.md`'s "Live verification happens in bursts, and must not gate the work."
Do not merge and do not mark `BL-B89` done until the flight card above has a recorded result.

---

# Definition of Done — BL-B98 fix folded into BL-B89 (feature/9k113-scan-procedure)

**Verdict is scoped to tip `47c8e96dbbba13f2d7dac01ec9bfd65d8f273a0c`** — this worktree
fast-forwarded from `e9fb4a2b` (an unrelated prior feature, `BL-B96`) directly to this tip with a
clean tree; no divergence. If the branch has moved since, re-run.

Scope: the `[[BL-B98]]` fix (`01a6fadd`, reviewed `47c8e96d` APPROVED) folded onto Stage 1
(which already passed DoD at `7611888c`, above). This section covers only the fix; Stage 1's own
checks are not re-run here since nothing in Stage 1's own code changed.

## Mechanical checks (body-layer/, resolved against the main checkout's venv — this worktree
carries none)

- `ruff format --check src tests`: **pass** (173 files already formatted)
- `ruff check src tests`: **pass** (all checks passed)
- `mypy src` (cwd `body-layer/`): **pass** (74 source files, strict)
- `pytest tests -q`: **pass** — 2588 passed, 4 xfailed (one more pass than Stage 1's own
  2587 — the new regression test in `test_body.py`; identical to both the debugger's and the
  Reviewer's own reported counts)
- `config/defaults.toml` vs `tools/generate_defaults.py --write`: **no diff** — regenerated into a
  scratch copy, diffed against the committed file, byte-identical (no tunable touched by this fix,
  as expected — confirmed rather than assumed)
- `git status --porcelain`: clean after the fast-forward merge

## The fix against the user's three-part rule — verified against the code directly, not only the
review's account

Read `_start_glance_away`'s docstring and body, and `body.py`'s `run_once` OBSERV-observed-off
branch, directly (not taken on the debugger's or Reviewer's word):

1. **OBSERV on→off, any cause → believed aim resets to boresight.** Confirmed in two places:
   `_force_observ_off` (manoeuvre-triggered, via `_back_to_home`'s non-SIGHTING branch, unchanged
   by this fix) and `body.py`'s `run_once` (`elif observ_observed is False and home_phase is not
   SCANNING`, lines ~705-721) — the latter is the fix's own new edge-trigger, closing the gap
   where OBSERV turned off mid-glance-away.
2. **While OBSERV stays on, the aim persists.** Confirmed: `_start_glance_away` no longer nulls
   `look_azimuth_deg`/`look_elevation_deg` on entry (both its call sites only fire while
   `home_phase is SIGHTING`), so `_back_to_home`/`_enter_binocular_search` resume from the real
   last position.
3. **A zero axis write is "stop moving," not "go to boresight."** Unchanged by this fix — that
   logic lives entirely in `aircraft-layer/dcs-export/Export.lua` (the 2026-10-24 F1 fix,
   `e1d16037`), outside body-layer's believed-aim state; this fix only touches what Petrovich
   *believes*, not the physical servo command, and no file under `aircraft-layer/` is touched by
   this commit.

Matches the Reviewer's independent mutation-testing of both fix halves. No discrepancy found.

## Scope & correctness

- Matches `plan.md`'s now-added Stage 2 note (this DoD pass added the performance/security-debt
  note to `plan.md` near the Stage 2 section, per the task's instruction, so the carried-over
  waiver is visible to whoever picks up Stage 2 — not merely recorded in a dod-check file nobody
  reads before starting that work).
- No unplanned scope added: the fix is exactly the two call-site-local changes the review
  describes, plus the tests that pin them. No touch to `_force_observ_off`, `lower_binoculars`, or
  the natural-look-finished commit — all three explicitly checked and left alone with a stated
  reason in `debug-bl-b98.md`, confirmed by reading `optic_policy.py` directly.
- No invariants violated: no new omniscience path (this is entirely within the already-sanctioned
  believed-aim state), no mechanism/calibration conflation (no `tuning.py` constant touched — a
  correctness fix to existing transitions, not a new threshold).
- All new files staged: confirmed via the fast-forward diff and `git status --porcelain` (clean).

## Testing

- Core logic covered: the two updated `TestSightSearchLegs` assertions (now asserting resume at
  the real last position instead of pinning the bug) plus the new `test_body.py` regression test
  for the observed-edge gap — both read directly, not taken on account.
- Tests are meaningful: the new regression test isolates `run_once`'s own pre-`decide_optic`
  transition handling from `decide_optic` itself (via a faked `decide_optic` that echoes its
  input), which is exactly the gap this fix's second half closes — a test that only exercised
  `decide_optic` would not have caught it.
- No existing tests broken: 2588 passed (2587 + 1 new), 4 xfailed — identical to both the
  debugger's and Reviewer's reported counts.

## Documentation

- Reviewer findings addressed: Required Fixes — **none** (Reviewer's verdict: APPROVED, no
  required fixes).
- Non-obvious behaviour explained: the three touched docstrings
  (`_back_to_home`/`_start_glance_away`/`_enter_binocular_search`) keep the pre-fix behaviour
  description alongside the new one with attribution to `[[BL-B98]]`, confirmed by reading them
  directly (lines ~1569-1583 of `optic_policy.py`).
- **Acceptance card updated** (this DoD pass, per task instruction):
  `docs/acceptance/2026-10-25-bl-b89-sector-scan-flight.md` Block 4 rewritten from "known defect,
  observe only" to two do/expect/record cases with speakable answers — OBSERV staying on through
  a glance-away (resume at last position), and OBSERV off-then-on (reset to boresight), plus a
  manoeuvre-forced OBSERV-off variant. The card's branch/tip line, "What this tests" summary, and
  "Acceptance boundary" paragraph were updated to match; the old "snap to center, known defect"
  framing was removed everywhere it appeared. The "Observ on"/"Observ off" command phrasing used
  in the new blocks was checked against `crew_console.py`'s `observ_on`/`observ_off` tokens and
  `config/sequences/mi-24p/copilot-observ-on.md`/`copilot-observ-off.md`'s trigger names before
  writing it down — not assumed from the pre-existing Setup step's wording alone. **Then ran every
  card utterance through the real matcher** (`audio-adapter/src/command_matcher.py`'s
  `match_transcript`, per `[[feedback_run_the_card_utterances_through_the_matcher]]` — a card is
  what the pilot says and hears, not what a review document reasoned about):
  `"Observ on"` → `token='observ_on', match_ratio=1.0, ambiguous=False`,
  `"Observ off"` → `token='observ_off', match_ratio=1.0, ambiguous=False`, and (pre-existing
  Block 1 utterances, re-checked since this pass touched the same file) `"Scan left"` →
  `scan_left`, `"Scan right"` → `scan_right`, `"Scan one o'clock"` → `scan_clock_1`, all
  `match_ratio=1.0`, none ambiguous. No surprises — unlike the 2026-10-06/BL-13 cases this check
  exists for, every utterance in this card matches exactly what the card claims.

## Security & Performance

**Waived for this fix, by user direction** (2026-10-25, `BL-B98.md`: *"this should be a small fix,
skip perf and sec now, do them with stage 2 code"*). Not run. This is recorded as a named
end-condition, not open-ended debt: `plans/9k113-scan-procedure/plan.md`'s Stage 2 section now
carries a note that Stage 2's own performance/security passes must cover this fix's code too
(`_start_glance_away`'s removed nulling, `body.py`'s new OBSERV-off-edge branch) — not only
whatever Stage 2 itself adds.

**Executing the unblock condition**, per this role's own standing instruction: the clearing
condition here is "Stage 2's own batch runs Performance Reviewer and Security over the combined
diff" — there is no command to run today that clears it; it clears only when Stage 2 is
implemented and its own batch pass includes this fix's diff. Confirmed the note naming that
condition is now actually present in `plan.md` (not just asserted in this report) by reading the
edited section back. Nothing else to execute here — unlike a `#needs-flight` tag, this is not a
live-DCS condition, it is a scheduling condition tied to Stage 2's own implementation.

## Acceptance testing

**Not run — needs a live DCS flight**, same as Stage 1. The existing flight card now covers this
fix (Block 4, rewritten above) rather than needing a second card — one flight clears both Stage 1
and this fix, per root `CLAUDE.md`'s "batch what a single flight can clear."

**Acceptance boundary**, restated for this fix specifically: a believed sight aim is not itself
observable from the cockpit — only the simulated `SightHead`'s own slewing to it is. No fixture
here can show whether the resume motion looks smooth/natural versus abrupt, or whether the
boresight-reset-on-OBSERV-off is itself noticeable or expected. That is exactly Block 4's job.

## Milestone-completion question

**Does folding BL-B98 in change what Stage 2 should be?**

Yes, narrower than Stage 1's own dod-check already flagged: Stage 1's pass noted Stage 2's design
assumed a "stays at last position" resume that `BL-B98` showed was false, and asked whoever builds
Stage 2 to decide whether to fix `BL-B98` first. **That question is now answered — `BL-B98` is
fixed, on this same branch, before Stage 2 starts.** Stage 2's "pointed, not searching" state
(plan.md's own flagged co-moving-fields question) can now be designed against a sight that
genuinely holds position through OBSERV-on interruptions and resets cleanly on OBSERV-off, rather
than against the broken base Stage 1's pass warned about. The one new carry-over is the
performance/security waiver above — Stage 2's implementer and its Reviewer should treat the
`BL-B98` diff as in-scope for their own batch pass, not already covered.

## Overall verdict: PASS

All mechanical, scope, testing, and documentation criteria pass. The fix matches the user's
three-part rule, verified directly against the code. Security and Performance are deliberately
waived per user direction, with the end-condition now recorded in `plan.md` where Stage 2's
implementer will see it. Acceptance testing remains outstanding (needs a live flight) and is
correctly deferred rather than gating this pass — the updated flight card covers both Stage 1 and
this fix in one trip.

**Acceptance Testing Plan: BL-B89 Stage 1 + BL-B98 fix (9K113 sector scan + sight resume
behaviour)**

**Goal:** Verify the sector-scan procedure matches the described cockpit behaviour, and that the
sight now holds its aim through a glance-away and resets only on OBSERV going off.

**Prerequisites**
- [x] Type-checked (`mypy src` from `body-layer/`) — verified above, pass.
- [ ] DCS running, Mi-24P, air start — see the card's own Setup section (UNVERIFIED, needs
  Windows).

**Test Cases** — see `docs/acceptance/2026-10-25-bl-b89-sector-scan-flight.md` Blocks 1-4 for the
full do/expect/record detail; summarized:
1. Free scan sweeps `ahead`'s two alternating windows, and `scan left`/`scan right`/a commanded
   o'clock hour each produce the described width.
2. A full lap (`wide_near`→`wide_far`→`narrow_far_sweep`) shows the ~1.5 km near edge and a
   per-lap naked-eye pause.
3. The two degraded-coverage altitude/attitude combinations (800 m/10° nose-up, 1500 m level)
   still look purposeful, not stuck.
4. The sight resumes at its last position through a glance-away (OBSERV staying on), and resets
   to boresight only on OBSERV off (commanded or manoeuvre-forced).

**Edge Cases to Probe**
- Does the per-lap pause ever visibly collide with the pre-existing `SIGHT_MAX_DWELL_S` pause
  (two pauses close together)?
- Does the boresight reset on a manoeuvre-forced OBSERV-off look the same as a commanded one?

**Pass Criteria**
The feature passes if all four blocks produce the expected result and no regression is visible in
ordinary sight behaviour (power-up, target looks, binocular excursions) outside what this card
tests.

Does the feature pass acceptance testing? (yes / no + details) — **UNVERIFIED, needs the user's
own flight; not run in this session.**

---

# Definition of Done — BL-B89 as a whole (Stage 1 + BL-B98 fix + Stage 2)

**Verdict is scoped to tip `0c56453214fd602213805305ad96a953506c312b`** on
`feature/9k113-scan-procedure` — "Performance review: BL-B89 Stage 2 + carried-over BL-B98 fix
(APPROVED)". This worktree's prior HEAD (`8b21e866`, a different merged feature, BL-B99) was
**not** an ancestor of this tip — reported per rule 4 — so this check ran on a `git checkout
--detach` of the named sha directly, not a fast-forward; tree confirmed clean before and after. If
the branch has moved since, re-run.

Scope: the whole feature as merged — Stage 1 (already passed DoD at `7611888c`, above), the
`BL-B98` fix (already passed DoD at `47c8e96d`, above), and Stage 2 (`look`/`sight`/`what is [at]
<where>`, not previously DoD-checked). Diff taken against `main`'s merge-base
(`e9fb4a2b41fdbf98f7d4e35a7c4fc09f847c1bde`): 37 files, two subprojects touched —
`audio-adapter/{src,tests}` and `body-layer/{src,tests,config,ROADMAP}` — plus `notes/`, `plans/`
and `docs/acceptance/`.

## Mechanical checks (run in both touched subprojects, main checkout's venv — this worktree
carries none)

**body-layer/**, from inside the subproject:
- `ruff format --check src tests`: **pass** (173 files already formatted)
- `ruff check src tests`: **pass** (all checks passed)
- `mypy src` (strict): **pass** (74 source files)
- `pytest tests -q`: **pass** — 2612 passed, 4 xfailed (no sign of the filed `BL-B93` flake this
  run)
- `config/defaults.toml` vs `tools/generate_defaults.py --write`: **no diff** — regenerated
  in-place, `git status --porcelain` clean before and after
- `git status --porcelain`: **clean**

**audio-adapter/**, from inside the subproject:
- `ruff format --check src tests`: **pass** (31 files already formatted)
- `ruff check src tests`: **pass** (all checks passed)
- `mypy src` (strict): **pass** (16 source files)
- `pytest tests -q`: **pass** — 357 passed, 2 skipped

**Debug output / TODOs / bare excepts**: grepped the full diff
(`git diff e9fb4a2b41fdbf98f7d4e35a7c4fc09f847c1bde HEAD -- body-layer/src audio-adapter/src`) for
`print(`, `TODO`, `FIXME`, `XXX`, `pdb.set_trace`, bare `except:`/`except Exception:` — zero hits
in added lines.

## Scope & correctness — verified by reading the shipped code directly, not only the review/plan
accounts

- **Stage 1 + `BL-B98`**: already verified at their own DoD passes above; nothing in that code
  changed again in Stage 2 (confirmed by `git diff` scope — Stage 2's diff touches
  `optic_policy.py`/`crew_console.py`/`body.py` additively, no re-edit of the Stage 1/`BL-B98`
  functions those passes already checked).
- **`scan`/`look` split** (`crew_console.py:_handle_scan`'s own docstring, `handle_command`
  dispatch): `scan <where>` is unchanged — still Petrovich's own eyes/binoculars/9K113 choice.
  `look`/`sight`/`what is [at] <where>` dispatch to the new `_handle_point`/`_start_point` path,
  confirmed by reading both functions, not inferred from the plan.
- **Attack-run refusal, checked first** (`_handle_point`, line ~3464): `if
  self.attack_run_engaged: return [render_unable("ATTACK_RUN_ENGAGED").text]` —
  `_UNABLE_TEMPLATES["ATTACK_RUN_ENGAGED"] = "Unable, attack run."`, matching the explore-notes
  decision verbatim.
- **OBSERV gating reuses the existing confirm band exactly as decided**: read
  `handle_transcript`'s affirm branch directly — `pending.observ_request is not None and (answer
  == "affirm" or token == "observ_on")` dispatches `observ_on` then queues the deferred look only
  if `sight_ready`; `answer == "negative"` under the same `if` returns `[]` (silent cancel, no
  "unable") — matches *"no -> cancel look"* / *"yes/confirm/observ on -> observ on"* verbatim,
  including the narrow, explicitly-scoped `observ_on`-counts-as-yes exception the explore notes
  call for.
- **`look left`/`look right` reuse Stage 1's own sector dispatch**: `_start_point`'s `relative`
  branch calls `_handle_scan(... relative_sector=...)` — the exact function `scan left` already
  uses — confirmed by reading `_start_point`, not assumed from its docstring.
- **`look <o'clock>` is a 30° wedge near-to-far, not a line sweep** — matches the user's correction
  verbatim (*"scan not in line, but that 30 deg sector near to far"*): `clock_wedge_body_relative`
  feeds `BoundedSightLook`, consumed by `_advance_bounded_look`/`_sight_point_sweep`'s S-shaped
  step generation, the same `search_pattern` mechanism the idle cycle's legs already use.
- **Two sweeps, then "<where>, clear.", then resume** — `POINT_SWEEP_COUNT = 2` (`lo=1, hi=5`);
  `_advance_bounded_look` only sets `point_clear_label` once `sweeps_completed >=
  POINT_SWEEP_COUNT`; `render_clear("two o'clock")` → `"Two o'clock, clear."`, reusing the
  `report` family's existing empty-answer phrasing, matching *"if nothing, say '<where> clear' and
  continue what the previous action was"* and the mock's own `"Two o'clock clear"` line.
- **A found target interrupts the sweep, is reported, and the sweep resumes** —
  `choose_sighting_look` runs before `_advance_bounded_look` is ever reached (the bounded-look
  branch is only reached when `chosen is None`), and `bounded_look` is not cleared by a found
  target — matches *"report, then go back to scanning. target count makes no difference"*.
- **Supersession**: `_POINT_LOOK_SUPERSEDING_TOKENS` includes every scan/look/task-changing
  command named in explore-notes' point 6, and excludes `silence` — matching *"new command
  replaces if it is look or scan command"* and the later-approved *"silence does not cancel a
  look"* decision. The Reviewer's own Required Fix (an unrelated superseding command was
  clobbering an in-progress, unrelated sight look via a shared `look_started_sim` field) is fixed
  via the named `_apply_point_request_transition` helper — re-verified here by grep
  (`grep -n look_started_sim src/body.py` → exactly one conditional write site, the helper itself)
  rather than re-trusting the re-review's own account.
- **No unplanned scope added**: the "quick position check" and the exact wide/far band-edge
  numbers past 1.5 km remain explicitly out of scope, as both Stage 1's plan and this stage's own
  plan state; nothing in the diff builds either.
- **No invariants violated**: no new omniscience path (the point-slot parsers are closed-vocabulary
  table lookups and a bounded integer range, confirmed by `security-stage2.md` and re-checked by
  grep here — zero `eval`/`exec`/`subprocess`/`open(`/network hits in the diff); no
  mechanism/calibration conflation (three new tunables — `POINT_SWEEP_COUNT`,
  `POINT_READY_TIMEOUT_S`, `POINT_DISTANCE_BAND_HALF_KM` — all AST-literal `lo`/`hi`, all rendered
  in `config/defaults.toml`, checked against the regenerated file above, not the source `#:`
  comment).
- **All new/modified files staged**: `git status --porcelain` clean at the checked-out tip.

## Testing

- Core logic covered: `test_an_unrelated_superseding_command_does_not_abandon_a_running_look`
  (the Reviewer's own Required Fix, mutation-confirmed against the real pre-fix code by the
  re-review), `test_two_sweeps_then_clear_and_resume`, `test_two_where_slots_is_a_detected_error`
  (both independently mutation-tested by the Reviewer against the real code, not just read), plus
  the full `TestSightSearchLegs`/`TestChooseSightingLook` suites carried from Stage 1.
- Tests are meaningful: the regression test for the Required Fix calls
  `body_module._apply_point_request_transition` directly — the same function the poll loop calls —
  not a reimplementation that could drift from the real code path (re-confirmed by reading the
  test, not taken on the re-review's word).
- No existing tests broken: 2612 passed / 4 xfailed (body-layer), 357 passed / 2 skipped
  (audio-adapter) — both full runs, no regressions.

## Documentation

- **Reviewer findings addressed**: Stage 1 (`review.md`, re-reviewed APPROVED), `BL-B98`
  (`review-bl-b98.md`, APPROVED, no required fixes), Stage 2 (`review-stage2.md`, one Required
  Fix, re-reviewed APPROVED) — all three verdicts read directly, not summarized from memory.
- **Non-obvious behaviour explained**: `_apply_point_request_transition`'s own docstring documents
  the `look_started_sim` sharing hazard the Required Fix closed; `_advance_bounded_look`'s
  docstring documents why "resume" restarts the current traversal rather than the exact step (a
  deliberate simplification, stated as such, not silently approximate).
- **Acceptance card updated for the merged state** (this pass):
  `docs/acceptance/2026-10-25-bl-b89-sector-scan-flight.md` rewritten to cover the whole feature —
  branch/checkout instructions changed to `main`, "Stage 2 not built" wording removed, five new
  flight blocks added (5: `look left`/`look right`; 6: `look <o'clock>`'s two-sweep-then-clear; 7:
  compass bearing + stated distance; 8: OBSERV-off confirm, attack-run refusal, supersession; 9: a
  found target during a look). **Every spoken-command utterance in the new blocks was run through
  the real matcher** (`audio-adapter/src/command_matcher.py::match_transcript`, not reasoned about
  from the plan):

  | utterance | token | slots |
  |---|---|---|
  | `"look left"` | `point` | `{'relative': 'left'}` |
  | `"look right"` | `point` | `{'relative': 'right'}` |
  | `"look two o'clock"` | `point` | `{'clock': 2}` |
  | `"look north"` | `point` | `{'sector': 'north'}` |
  | `"sight two o'clock three kilometres"` | `point` | `{'clock': 2, 'distance_km': 3}` |
  | `"sight left"` | `point` | `{'relative': 'left'}` |
  | `"what is at two o'clock"` | `point` | `{'clock': 2}` |
  | `"what is north"` | `point` | `{'sector': 'north'}` |
  | `"observ on"` | `observ_on` | — |
  | `"scan left"` | `scan_left` | — |

  all `match_ratio=1.00`, none ambiguous — no surprises. The exact spoken wording in the card
  (`"Two o'clock, clear."`, `"Need observ, confirm?"`, `"Unable, attack run."`, `"Left."`/
  `"Right."`) was read off `render_clear`/`render_confirm_request`/`_UNABLE_TEMPLATES`/
  `render_point_readback` directly, not guessed from the plan's mock. **The published card at
  https://claude.ai/artifact/M9jAnsomghXnV1bSyds9Mj was republished from the updated source file**
  (same URL, version 3) — not left stale.

## Security

- `plans/9k113-scan-procedure/security-plan.md` (Stage 1): **APPROVED**
- `plans/9k113-scan-procedure/security.md` (Stage 1 deep analysis): **APPROVED**
- `plans/9k113-scan-procedure/security-plan-stage2.md`: **APPROVED**
- `plans/9k113-scan-procedure/security-stage2.md` (deep analysis, covers Stage 2 **and** the
  `BL-B98` fix's carried-over debt): **APPROVED** — closes the end-condition the `BL-B98` DoD pass
  above recorded ("clears only when Stage 2's own batch pass includes this fix's diff"); confirmed
  by reading `security-stage2.md`'s own "Covers two pieces whose own security pass was deferred to
  this batch" section, not assumed.

## Performance

- `plans/9k113-scan-procedure/performance-review.md` (Stage 1): **APPROVED — MONITOR**
- `plans/9k113-scan-procedure/performance-review-stage2.md` (covers Stage 2 **and** the carried-over
  `BL-B98` fix): **APPROVED** — every hot-path addition is either O(1)/early-return in the common
  case, or outside the 1 Hz poll budget entirely (the matcher's two new branches run once per
  spoken utterance, measured cheaper than the pre-existing fallback path). Closes the same
  end-condition as Security above.

## Acceptance testing

**Not run — the user has authorised merging on DoD pass without waiting for this flight**
(2026-10-25: *"When ready DoD BL-B89 as a whole and merge"*). Per root `CLAUDE.md`'s "Live
verification happens in bursts, and must not gate the work": this is accepted, not waived — the
updated flight card above is the live-acceptance vehicle, and `BL-B89`'s roadmap entry carries
`#needs-flight` until a real sortie clears it.

**Acceptance boundary, stated up front:** every test in this feature drives the state machine and
the matcher with synthetic inputs/transcripts. That proves the mechanism matches the spec
geometrically and lexically and never stalls. It structurally cannot show whether the scan/look
procedure *sounds and feels* right spoken aloud with a real voice, real cadence, and a real
microphone in a real cockpit — whether "Look two o'clock" is recognised promptly under flight
noise, whether the per-lap pause and the OBSERV-off reset read as natural rather than jarring, or
whether a found-target interruption mid-look feels like a report or like the look silently
breaking. The card's nine blocks are built to answer exactly those questions, not to re-verify
geometry or vocabulary a unit test already settled.

## Milestone-completion question

**Does BL-B89's completion change what the next milestone should be, or invalidate a downstream
assumption?**

Three concrete ways, named rather than left implicit:

1. **`BL-B99`'s own roadmap entry names the exact re-check this merge triggers**: *"when
   `[[BL-B89]]` merges, re-check `body._render_pov_frame`'s per-optic boresight table against
   BL-B89's gaze/optic changes."* `BL-B99` (the Petrovich POV debug view, already merged to `main`
   ahead of this feature) renders a per-optic boresight table that predates Stage 2's new bounded
   look and the final shape of Stage 1's sector/wedge geometry. That re-check is now unblocked and
   owed — not done as part of this DoD pass, since it is `BL-B99`'s own entry's open item, not
   `BL-B89`'s.
2. **The "quick position check" remains deliberately unbuilt**, as both Stage 1's and this
   stage's plans state (`plan.md`'s Decision 6: "how short, how often" are new judgement calls the
   source material does not supply). This is a scoped-out decision, not debt dressed as one — no
   `#needs-flight` or backlog item is owed for it unless the user raises it as a new ask.
3. **The `review-stage2.md` fuzzy-collision finding** (`"book"`/`"cook"`/`"hook"`/`"took"` vs
   `"look"`, `"fight"`/`"sighted"` vs `"sight"`, all clearing `VERB_FLOOR` at full confidence) is
   accepted debt, not a defect — `implementation-stage2.md`'s own disposition is "a measurement
   task, not an implementation one," deferred to a `tools/stt_bench.py` corpus pass. **Executing
   the unblock condition**: `tools/stt_bench.py` is a corpus-measurement tool, not a command that
   clears on its own — there is no corpus entry yet naming "book"/"fight" as confusable with
   "look"/"sight" to run it against. Checked `tools/stt_bench.py`'s own corpus file and confirmed
   it does not yet contain either collision pair, so the clearing condition is "add corpus entries
   for the two new collision pairs, then run the bench" — not yet executable today, and not
   something this DoD pass can manufacture a corpus entry for without guessing at real STT output.
   Left as a named, unblocked-when-ready item rather than closed.

## Overall verdict: PASS

All mechanical, scope, testing, documentation, security and performance criteria pass for the
whole feature (Stage 1 + `BL-B98` fix + Stage 2), re-verified at this pass's own tip rather than
re-trusting the three prior passes' accounts. Acceptance testing is accepted as outstanding per
user authorization to merge without waiting for it — tracked via `#needs-flight` on `BL-B89`'s
roadmap entry, with the flight card updated and republished to cover the whole feature in one
trip.

---

**Acceptance Testing Plan: BL-B89 whole feature (9K113 scan + point procedure)**

**Goal:** Verify the sector-scan procedure, the sight's resume behaviour, and the new explicit
`look`/`sight`/`what is at` point request all match the described cockpit behaviour.

**Prerequisites**
- [x] Type-checked (`mypy src` from both `body-layer/` and `audio-adapter/`) — verified above,
  pass.
- [ ] DCS running, Mi-24P, air start, on `main` after the merge — see the card's own Setup section
  (UNVERIFIED, needs Windows).

**Test Cases** — see `docs/acceptance/2026-10-25-bl-b89-sector-scan-flight.md` Blocks 1-9 for the
full do/expect/record detail; summarized:
1-4. Stage 1 + `BL-B98` (unchanged from the prior Acceptance Testing Plan above).
5. `look left`/`look right` match `scan left`/`scan right`'s width with a shorter readback.
6. `look <o'clock>` sweeps the 30° wedge twice, then "<where>, clear.", then resumes.
7. A compass bearing sweeps a wider (~45°) wedge; a stated distance narrows the sweep.
8. OBSERV-off confirm/yes/no, the attack-run refusal wording, and supersession by a later command
   all behave as described.
9. A found target during a look is reported normally, and the look resumes afterward.

**Edge Cases to Probe**
- (carried from Stage 1) Does the per-lap pause ever visibly collide with
  `SIGHT_MAX_DWELL_S`? Does a manoeuvre-forced OBSERV-off reset look the same as a commanded one?
- Does "look" ever get misheard as "book"/"cook"/"hook"/"fight" in practice? (the accepted,
  deferred fuzzy-collision finding — worth noting if it happens, not expected to be common under
  push-to-talk discipline)

**Pass Criteria**
The feature passes if all nine blocks produce the expected result and no regression is visible in
ordinary sight/scan behaviour outside what this card tests.

Does the feature pass acceptance testing? (yes / no + details) — **UNVERIFIED, needs the user's
own flight; merge proceeds without waiting for it, per explicit user authorization.**
