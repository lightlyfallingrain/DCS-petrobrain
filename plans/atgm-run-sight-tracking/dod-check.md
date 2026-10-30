# Definition of Done — fix/atgm-run-sight-tracking

**Verdict scope:** this report is scoped to tip `495b159a4261dd6eae01b15bcf6c3a03a8216799`. If
the branch has moved since, re-run before trusting this PASS.

Source commits: `b912a081` (sight belief aim uses remembered target altitude — stopgap,
superseded later by `BL-B104`), `cc6dafac` (bearing-line depression search + "Tracking."
callout), then harvested review/performance/security commits (`5794a105`, `d66f8a69`, `495b159a`).

## Verification method

The DoD worktree (`worktree-agent-a077c05fb719f5c89`) sits on an older `main`-derived HEAD
(`f7c1e70f`) that has diverged from the branch tip — neither is an ancestor of the other, since
the branch forked from an older `main` (`a0e8bf11`). Per the stale-base protocol this was not
force-merged. Verified instead against an isolated `git archive 495b159a` snapshot in a scratch
directory, fresh venv, every command run with cwd inside `<scratch>/body-layer`.

## Code Quality

- [x] **Checks pass, body-layer only** (confirmed the only subproject touched —
  `git diff --name-status a0e8bf11..495b159a -- body-layer` touches only `body-layer/`):
  - `ruff format --check src tests`: pass (180 files already formatted)
  - `ruff check src tests`: all checks passed
  - `mypy src` (run from inside `body-layer`): `Success: no issues found in 78 source files`
  - `pytest tests -q`: `2795 passed, 4 xfailed` — matches `implementation.md`'s and
    `review.md`'s own reported counts exactly
- [x] No unhandled errors/panics in data paths — Reviewer and Security both checked the diff; no
  new exception handling introduced
- [x] No debug output left in committed code — the one new `self._print(...)` call in
  `crew_console.py` is the module's own established speech-output funnel (same one every other
  handler in that file calls), not a debug print
- [x] No TODO/FIXME/XXX introduced — `grep` over the fork-point diff for
  `TODO|FIXME|XXX|print\(|pdb|except` found only the `_print` call above

## Scope & Correctness

- [x] Matches the plan: `implementation.md`'s three items (bearing-line depression search,
  "Tracking." callout, OBSERV left untouched) match the user's own 2026-10-30 decision in
  `docs/acceptance/2026-10-30-sortie-feedback.md` §4 ("Decided") verbatim — search along bearing
  in depression: yes; callout "Tracking.": yes; OBSERV unchanged: yes, no `home_phase` code
  touched
- [x] No unplanned scope — `git diff --name-status a0e8bf11..495b159a -- body-layer` matches
  `implementation.md`'s "Files Changed" list exactly (6 src files + defaults.toml + 3 test files
  + STRUCTURE.md)
- [x] No invariants violated — Reviewer's no-omniscience check confirms the sweep centre and
  bearing come from belief only, altitude correction uses `remembered_target_alt_m` (never DCS
  ground truth), and the "Tracking." callout gates on the real DCS-derived `aim_source == "seen"`,
  not belief/truth fabrication
- [x] All files staged — this is a review of the committed tip; nothing untracked

## Testing

- [x] Core logic covered: `TestSightLockBearingLineSearch` (5 cases), `TestSightLockSeen` (4
  cases), `TestDrainSightLockTracking` (5 cases) — 14 new tests
- [x] Meaningful, not decorative — Reviewer hand-mutated `_bearing_line_search_offsets` to return
  only `(0.0,)` (pre-fix "always stare") and confirmed 2 tests go red
  (`test_not_seen_sweeps_depression_and_crosses_the_true_depression`,
  `test_resuming_after_a_loss_starts_the_sweep_fresh_at_the_latest_belief`); independently
  re-verified by this DoD pass per "run every command before writing it down" — pytest run above
  is the real rerun, not a repeat of the claim
- [x] No existing tests broken — pre-existing `TestSightLock`'s four cases pass unmodified against
  the new default `sight_lock_seen=False`

## Documentation

- [x] Reviewer findings addressed — **Required Fixes: None.** Three optional refinements
  (gimbal-limit filtering, `STEP_S`/`SLEW_EL_DPS` coupling note, above-horizon test) are correctly
  optional per Reviewer and Security's own read; not blocking
- [x] Non-obvious behavior explained — `implementation.md`'s "Notable Discoveries" covers the
  unwired Stage 3-7 seam, the `_step_centres_deg` reuse trap, and the generator paragraph-break
  trap; all three harvested to `notes/` below

## Security

- [x] `plans/atgm-run-sight-tracking/security-review.md`: APPROVED, no required fixes. Not
  applicable (no LLM-read text in this feature's scope); the two player-experience findings it
  passed through are Reviewer's own optional refinements, already on record there
- [x] No separate plan-review file for this stage — Security's plan review left the AR→I slot
  2026-10-30 per root `CLAUDE.md`; this feature predates that only in the sense that its deep
  analysis (post-Reviewer) is what ran, which is correct per the current sequence

## Performance

- `plans/atgm-run-sight-tracking/performance-review.md`: **APPROVED — MONITOR**. Per-contact
  `_look_target_position` cost (~1 µs/contact, +20% on an already-O(n) loop, not credible as a
  budget problem even at 1000 contacts), offset-tuple rebuild (sub-µs, once per engaged run), and
  `_sight_lock_seen` evaluated twice per poll (required for edge detection) — all MONITOR, no
  action needed.

## Acceptance boundary — what these fixtures cannot reach

The 14 new tests and the mutation check exercise the *decision* math — offsets, edge-detection,
bearing refresh — against synthetic `OpticState`/belief inputs. **They cannot and do not exercise:**
- Whether the real 9K113 gimbal, given this sweep's commanded sequence, actually re-acquires the
  target in the sim within a plausible time window (the fixtures assert the sweep's angular
  *coverage*, not that DCS's own sight servo keeps up — the review's own flagged
  `STEP_S`/`SLEW_EL_DPS` coupling gap is exactly this boundary).
- Whether "Tracking." is heard as a well-timed, non-repetitive callout in a real run with multiple
  brief losses (e.g. terrain masking during a bank), rather than chattering on noisy edge
  detection — the edge-detector logic is unit-tested, its *cadence in a real run* is not.
- Whether the bearing-line search, run against the real MLRS-group geometry from the 2026-10-30
  sortie (run 2: believed point ~700 m short in range, ~8° too steep), actually crosses the true
  depression before the aircraft closes past the point where crossing it still matters tactically.

None of this is a fixture gap that more unit tests would close — it needs a flight.

## Inspect-and-adapt

**Does this change what BL-B104 should do?** Yes, partially: `b912a081`'s
`remembered_target_alt_m` fix removes the most urgent symptom (altitude climbing to +72°) that
BL-B104 was framed around, so BL-B104's own altitude-stopgap description is now superseded by a
landed fix — BL-B104 itself already says this explicitly ("A partial fix for the sight path only
... is on branch `fix/atgm-run-sight-tracking`"). The bearing-line depression search does **not**
replace BL-B104's range-accuracy fix; it is a *search* that compensates for a wrong range/depression
by sweeping until the sight itself resolves the target, which stays as a fallback mechanism once
BL-B104 lands (a correct ground-height-derived depression would need less sweep, not none — the
angular error BL-B104 describes is about azimuth/elevation estimation, not about guaranteeing the
sight is pointed exactly at the believed point on the first poll).

## #needs-flight

**Live behaviour is untested.** Tagging `#needs-flight` — this entry belongs on
`fix/atgm-run-sight-tracking`'s own history, not a new roadmap entry (this is a bug fix on a
pre-existing sortie-feedback thread, not a new milestone); the sortie-feedback doc
(`docs/acceptance/2026-10-30-sortie-feedback.md`) and `BL-B104.md` already carry the open-items
for this thread, so the flight-clearing condition is recorded there, not duplicated here.

**What a flight should verify** (branch to fly: `main`, after merge):
1. Engage an ATGM run (`engage target` or `engage target missiles`) on a contact the sight is not
   currently resolved through. Expected: the sight sweeps depression at the believed bearing
   (visible in the debug view as a stepping mark, centre-first) instead of staying parked at a
   wrong fixed point.
2. Once the sight resolves the contact, Petrovich says "Tracking." exactly once. A later loss and
   re-acquisition (e.g. a bank drop masking the target) produces "Tracking." again, not a repeat
   on every poll while it stays seen.
3. OBSERV behaviour during the run is unchanged from before this fix (binoculars/naked-eye glances
   stay brief, no automatic OBSERV re-enable after a bank drop — unchanged per the user's explicit
   "leave observ as it is currently").
4. Compare against the 2026-10-30 run-2 shape specifically (MLRS group ~272° bearing, ~2.4° sim
   elevation, believed point ~700 m short/~8° too steep) if a similar engagement geometry can be
   reproduced — this is the exact case the regression test encodes, and the sortie is what tells
   us whether the sweep crosses true depression in a tactically useful time window, not just
   within the test's synthetic FOV.

The unblock condition named above (the sortie itself, run against this exact geometry) cannot be
executed from this worktree — no DCS access — so it is left as the live-verification step, not
claimed as already run.

## Verdict: PASSED

Mechanical checks, scope, invariants, tests, and all three prior sign-offs (Reviewer, Performance,
Security) confirmed on an isolated snapshot of the exact reviewed tip. Acceptance is
**PENDING (live)** per root `CLAUDE.md`'s 2026-10-26 direction — merge proceeds without waiting for
a flight.
