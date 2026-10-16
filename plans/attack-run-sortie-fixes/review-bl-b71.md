### Review Summary

Reviewed `BL-B71` (the least-capable-optic guidance ladder) against `plans/attack-run-sortie-fixes/plan.md`'s
`BL-B71` section, `body-layer/ROADMAP/BL-B71.md`, `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md`
§6/§7, and `body-layer/ROADMAP/BL-B70.md`. Base-commit discipline: the worktree's `HEAD` started at
`24f217fc` (`origin/main`), a strict ancestor of the named tip; fast-forwarded cleanly to
`7f5fd54d46bd33058d9de6c1a05cee16240dd6d6` with no divergence. Full read of `optic_policy.py`'s new
code (`_LADDER`, `least_capable_sufficient_optic`, `guidance_request_for`, `_apply_guidance`, `decide`'s
wrapper), `attack_run.py`'s `decide`/`_no_look_cause`, the two new tuning constants' source and rendered
form, and both new test files.

**The hard gate holds.** `_apply_guidance`'s sight-ceiling clamp re-reads `state.home_phase` on every
call rather than caching or latching a prior verdict, and it is the only path that can turn
`decision.optic` into a sight rung — `decide` is the sole caller of `_apply_guidance`, so there is no
second entry point that could skip the clamp. Confirmed by mutation myself (not merely by reading the
implementer's report): replacing the clamp's `if` condition with `if False and (...)` and re-running
`test_the_hard_gate_the_9k113_is_never_reached_for_autonomously` and
`test_the_diverged_state_sight_granted_while_scanning_is_home_demotes_at_once` made both fail, each for
the stated reason (a sight rung passed through unclamped). Restored; `shasum` of `optic_policy.py`
matched the pre-mutation value exactly (`f0a06a7f...`).

**One required fix found independently of the implementer's own flagged items**, below — a real
correctness defect this feature introduces, not a cosmetic gap. The three design decisions the
implementer settled itself are reasonable; the fourth exit transition it found and fixed is real and the
enumeration is complete; de-escalation works in both directions; the tuning constants render correctly;
the gaze/optic deferral to `BL-B66` is a sound scope call.

Full gate re-run from this worktree, main checkout's venv, `cwd` inside `body-layer/`:
`ruff format --check`: 133 files already formatted. `ruff check`: all checks passed. `mypy src`:
Success, no issues found in 60 source files. `pytest tests -q`: **2087 passed, 4 xfailed** — matches
the implementer's reported count exactly.

---

### Required Fixes

- **`_no_look_cause`'s `TOO_FAR` test uses `UNAIDED_OPTIC` unconditionally, and this is reachable in
  practice once the ladder is live — not the inert scope gap the implementer's note and the BL-B70 entry
  both describe it as.** `attack_run.py:485-512` computes `presence_threshold_m` for the cause taxonomy
  with `optic=UNAIDED_OPTIC` hardcoded. But `logger.py` (`run_once` → `source.optic = optic`, line ~1020)
  feeds the *granted* optic — which can now be `BINOCULAR_OPTIC` or a sight rung via `BL-B71`'s own
  `_apply_guidance` — back into `perception.visibility.check_visibility`'s gate, which uses that optic's
  `presence_range_mult` to admit percepts (`tier_ranges`, `visibility.py:638`). `naked_eye_source.py`
  sets `relative_direction` on any admitted observation (line ~1262), which is exactly what
  `_tier1_alignment` needs to resolve (tier 1, a live look).

  So: once the ladder grants binoculars at a range beyond the naked eye's own presence threshold but
  within the binocular one, tier 1 **can** and does resolve — `contact.last_percept.relative_direction`
  is fresh — while `_no_look_cause`, still testing against `UNAIDED_OPTIC`'s narrower threshold, returns
  `"too_far"`. `decide`'s own docstring (lines 694-699) asserts this combination "is not reachable in
  practice (a fresh relative percept implies naked_eye_source already admitted it within presence
  range)" — true only if the optic in use for admission is fixed at `UNAIDED_OPTIC`, which `BL-B71`
  itself ends. With `cause == "too_far"` and `tier == 1`, `now_unresolved = True` takes effect
  unconditionally (lines 700-702) and, on the edge where the contact was previously resolved, the code
  takes the `losing_sight` branch (`render_attack_run_lost_sight`, the remembered-sighting "last I saw"
  phrasing) — on a tick where Petrovich is actively tracking the target live, through the exact
  instrument `BL-B71` was built so he would reach for first.

  This directly contradicts §6/§7's stated premise (*"use binoculars first; if still too far, use
  'last I saw'"*) at precisely the range band the feature exists to cover, and `_contact_at`'s own
  comment in `test_attack_run.py` (deliberately tier-2-only, "these cause-taxonomy tests are about
  `_no_look_cause`, not tier selection") means no test exercises the combination either way — the
  "not reachable" claim is untested, not merely undertested.

  Fix: `_no_look_cause` needs the optic actually resolving the look, not a hardcoded
  `UNAIDED_OPTIC` — most likely the granted `guidance_optic` (falling back to `UNAIDED_OPTIC` when
  none is standing), threaded in alongside `ownship`/`contact`/`now_sim`. `BL-B70.md`'s own entry
  flags this coupling as "out of scope for this entry," and this task's plan likewise never asked
  `_no_look_cause` to change — but `BL-B71` is the change that makes the old assumption false, so the
  fix belongs here, not in a future entry that would inherit a known-wrong "not reachable" docstring
  claim and a cause taxonomy that misfires during its own feature's steady-state case.

### Optional Refinements

- **First-grant hands-busy baseline can overcharge in one case.** `_apply_guidance` compares the first
  grant against `_HOME_OPTIC[state.home_phase]` (e.g. `UNAIDED_OPTIC` for `SCANNING`) rather than
  against what `decision.optic` already was on this same tick. If the ordinary phase dispatch happened
  to already be using the same optic the guidance request asks for (e.g. a `GLASSING` phase already up
  on binoculars for an unrelated contact, and the request also resolves to `BINOCULAR_OPTIC`), the first
  grant still charges `HANDS_BUSY_DURATION_S` even though the instrument in Petrovich's hands does not
  actually change. Narrow, not safety-relevant, and the implementer's own note names the decision
  explicitly — worth comparing against `decision.optic` instead of `_HOME_OPTIC[home_phase]` if this
  is ever revisited, not required now.
- **The cross-key coupling between `GUIDANCE_OPTIC_MIN_INTERVAL_S` and `HANDS_BUSY_DURATION_S` is
  explained only in the constant's *second* `#:` sentence**, which the generator does not render (by
  design — first sentence only) — exactly the failure shape `CLAUDE.md`'s tuning section names three
  times already. Checked the rendered `config/defaults.toml` directly: both new entries render
  correctly (no backtick corruption, matches first sentence exactly), but the coupling warning itself
  reaches nobody reading only the shipped file. Nothing enforces it (unlike `decay.py`'s import-time
  assert for its own analogous coupling), and the bounds (`MIN_INTERVAL_S` lo=1.0, `HANDS_BUSY_
  DURATION_S` hi=5.0) do allow the violation at the extremes. The implementer's choice to flag rather
  than add unrequested cross-key machinery is reasonable per the role's own guidance; moving the
  warning into the comment's first sentence (so it survives the render) would close the gap more
  cheaply than an assert, if this is revisited.
- **Design decision (a)** — hysteresis keyed on `AttackRunState.requested_optic` rather than
  `OpticState.guidance_optic`, so a standing request grants immediately when OBSERV comes on mid-run —
  is sound and matches the stated module boundary (`attack_run` tracks what geometry alone would ask
  for; `optic_policy` grants). No concern.

### Verdict

NEEDS REVISION

### Review Confidence

Full read. Hard gate verified by mutation performed directly (not merely re-reading the implementer's
report), including restoring the file and confirming the `shasum` matched. Did not independently
re-run the other two counterfactuals (fresh-`SEARCHING` carry-forward, guard 1 placement) since the
exit-transition enumeration and guard-1 code path were both read directly and independently confirmed
correct by inspection; the hard gate was treated as the one mutation worth re-running myself per the
task's own instruction, since it is the safety-critical one.
