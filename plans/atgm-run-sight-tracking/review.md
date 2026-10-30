### Review Summary

Reviewed `fix/atgm-run-sight-tracking` at `cc6dafacabdc9458da91d3f78b6d06024d40c51a`
(two commits over an older `main`: `b912a081` — belief aim uses remembered target
altitude instead of stale ownship altitude; `cc6dafac` — bearing-line depression
search while the ATGM-locked contact is not yet resolved through the sight, plus a
"Tracking." callout). Against `plans/atgm-run-sight-tracking/debug.md`,
`implementation.md`, root `CLAUDE.md`, and `body-layer/CLAUDE.md`.

**Note on base:** my review worktree started from `origin/HEAD` and diverged from
`cc6dafac` (neither is an ancestor of the other — the fix branch sits on an older
`main`). Per the stale-base protocol I did not force a merge. The branch's own
dedicated worktree (`/Users/sg/Code/DCS-petrobrain-atgm-track`) already holds
`cc6dafac` cleanly (`git status --porcelain` empty, `HEAD` = the expected sha), and
all commit objects are shared across worktrees in this repo, so the diff/show-based
review below is against the real commit content, not a reconstruction. All checks
were run against an isolated `git archive` snapshot of `cc6dafac` (plus `main`'s
`world-model/`, the in-process-import pair, read-only) in the scratch directory, with
a fresh venv — not inside that other worktree, to avoid touching a tree outside this
agent's own.

**No-omniscience:** confirmed clean. `_decide_sighting_locked`'s sweep centre
(`found.elevation_deg`/`found.azimuth_deg`) comes from `_look_targets`, which is
belief-only — `_look_target_position` (the `b912a081` fix) corrects altitude from
`remembered_target_alt_m` (reconstructed from the last tier-1 look's
`relative_direction.up_m`), never DCS ground truth. The "Tracking." callout gates on
`sight_head.aim_source == "seen"` for the locked contact — the real, DCS-derived
sight state, not belief or truth fabrication, which is the legitimate thing to speak
from. Bearing is re-derived fresh every poll from belief (never swept, since it is
the trustworthy part); only depression is swept, matching the user's own framing in
the sortie feedback.

**Tunables:** all three new constants (`SIGHT_LOCK_SEARCH_BAND_HALF_DEG`,
`SIGHT_LOCK_SEARCH_STEP_OVERLAP_FRACTION`, `SIGHT_LOCK_SEARCH_STEP_S`) go through
`tuning.real` with `lo`/`hi` AST-literal bounds and `status="judgement"`, matching
the existing pattern elsewhere in `optic_policy.py`. I read the **rendered**
`body-layer/config/defaults.toml`, not the source comments: all three entries render
as one continuous paragraph (the generator's "last `#:` paragraph before the
assignment" trap, which `implementation.md` says bit this stage twice and was fixed
by removing the blank-line break) — nothing truncated, nothing cut mid-sentence, no
corrupted backtick span. Checked the arithmetic against the code's own constants
(not the author's stated figure, per the standing rule): `SIGHT_LOCK_SEARCH_BAND_HALF_DEG
= 15.0` is indeed comfortably wider than the ~8° depression error the run-2 trace
implies (`implementation.md`'s own worked test uses an 8° offset and asserts
coverage) — consistent, not just plausible.

**Actions/params/"when" shaping:** this change extends an existing branch
(`_decide_sighting_locked`) inside `optic_policy.py`'s single `decide()` state
machine, in the same idiom every other branch of that module already uses (plain
function, explicit `OpticState` in/out, no separate action/param/when split).
Root `CLAUDE.md`'s shaping rule is aimed at future event-driven Lua scripting
(deferred) and says existing hard-coded behaviour stays unless a change touches it
anyway — this change does touch existing behaviour, but it stays inside the
established `optic_policy` convention rather than introducing a second, divergent
shape. No concern here.

**"Tracking." repetition:** `CrewConsole.drain_sight_lock_tracking` fires only on the
`False -> True` edge of `previously_seen`/`seen`, mirroring
`drain_guidance_unit_ready`'s existing shape exactly. Confirmed by reading
`test_crew_console.py`'s five new cases, including the specific "silent on every poll
it stays seen" and "fires again after a loss and re-acquisition" cases — ran them,
all pass.

**Mutation check (not just reading):** I hand-mutated
`_bearing_line_search_offsets` in the archived snapshot to return only `(0.0,)` (the
pre-fix "always stare" behaviour, exactly what `implementation.md` claims the test
is built to catch) and reran `TestSightLockBearingLineSearch`. Two tests went red as
claimed (`test_not_seen_sweeps_depression_and_crosses_the_true_depression`,
`test_resuming_after_a_loss_starts_the_sweep_fresh_at_the_latest_belief`); reverted
afterward. The claim in the implementation doc holds — this is a real regression
test, not a decorative one.

**Three flagged limits — judged:**
1. **Sweep steps beyond gimbal mechanical limits are not clamped in
   `_decide_sighting_locked`.** Checked downstream: `sight_head.py`'s
   `advance_sight_head` already runs every commanded direction through `_clamp_gimbal`
   before actually slewing, regardless of where the direction came from — the same
   "reject at selection, clamp at the gimbal" split the rest of this module already
   uses. So the real physical limit is still respected; an out-of-band step merely
   parks at the stop for that one dwell instead of productively searching, which
   wastes a step rather than violating an invariant. **Acceptable to ship as-is.**
   Optional refinement: skip offsets that `within_field_of_regard` would reject,
   the same filter the ordinary (unlocked) sweeps already apply at the selection
   point, so a wasted step doesn't happen at all.
2. **Above-horizon targets untested.** Acceptable given the project's own operating
   envelope (ground-attack passes, mostly below-horizon depression) and that the
   shallower-is-farther assumption is stated, not hidden. Worth a test eventually,
   not now.
3. **Possible double-talk with `BL-B67`'s attack-run module once its range/
   launch/impact stages are wired.** Confirmed via `implementation.md`'s own
   discovery note: `atgm_run.decide`'s Stage 3-7 state machine is not wired into
   `body.py`'s poll loop at all today, so there is no live conflict yet — only a
   named seam for whoever wires Stage 7. Correctly flagged, not a defect now.

**Checks (body-layer only — the only subproject touched):** ran against an isolated
snapshot (fresh venv, not the shared dedicated worktree) since I could not install
tooling into another agent's/the user's worktree from here.
- `ruff format --check .`: one pre-existing, unrelated finding in
  `research/2026-10-05-security-audit.md` (markdown code-block reformatting), not
  touched by this branch's diff — not a finding against this change.
- `ruff check .`: all checks passed.
- `mypy src` (run from inside `body-layer`, per its own `CLAUDE.md`): `Success: no
  issues found in 78 source files`.
- `pytest tests -q`: `2795 passed, 4 xfailed` — matches `implementation.md`'s own
  reported count exactly.

**Cross-key coupling check:** `_bearing_line_search_offsets`'s `step = max(step_deg,
0.01)` floor prevents a zero/negative step from looping forever even at the
`SIGHT_LOCK_SEARCH_STEP_OVERLAP_FRACTION` extremes (fraction -> 1.0 would otherwise
drive `step_deg` -> 0). `SIGHT_LOCK_SEARCH_STEP_S` vs. the sight's own
`SLEW_EL_DPS` (mentioned in the constant's own comment as the reason for the lower
bound) has no enforced relationship — a developer could set `STEP_S` and
`BAND_HALF_DEG`/`STEP_OVERLAP_FRACTION` to a combination where the sight physically
cannot reach a step before the sweep moves on. This is the same class of soft,
behavioural-only coupling as limit 1 above (wastes dwell time, does not crash or
violate an invariant, no `_COUPLED_KEYS`-style hard assertion exists for it) —
**optional, not required.**

**Scope:** matches `implementation.md` exactly — no files touched beyond what it
lists, no scope drift. `body-layer/` is the only subproject touched, consistent with
root `CLAUDE.md`'s module-independence note (no new world-model coupling introduced).

### Required Fixes

None.

### Optional Refinements

- Filter `_bearing_line_search_offsets`' resolved elevations through
  `within_field_of_regard` the way the unlocked sweeps already do, so a step beyond
  the gimbal mechanical limit is skipped rather than parking at the stop for a full
  dwell (limit 1 above).
- Consider a documented or lightly-asserted relationship between
  `SIGHT_LOCK_SEARCH_STEP_S` and `belief.sight_head.SLEW_EL_DPS` (and the resolved
  per-step angular distance), so a future tuning change can't silently produce a
  sweep the sight can never physically keep up with.
- Add a test for an above-horizon target once one is easy to construct, per limit 2.

### Verdict
APPROVED

### Review Confidence
Full read — plan docs, every changed source file (full diffs), every new test (read
in full, not skimmed), rendered `defaults.toml`, and a hand-mutation check on the
two tests implementation.md claims are regression tests rather than decorative
ones. Format/lint/type/test all run and green on an isolated snapshot of the exact
reviewed sha.
