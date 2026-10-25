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
