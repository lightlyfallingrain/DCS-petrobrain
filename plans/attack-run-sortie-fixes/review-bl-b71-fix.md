### Review Summary

Reviewed the two fix rounds answering the required finding in
`plans/attack-run-sortie-fixes/review-bl-b71.md` — `b72d4153` (the required fix, threading the
granted optic into `_no_look_cause`'s range gate) and `91b3c489` (correcting that fix to measure
against the optic actually *used*, per the user's direct ruling: "actual behavior must measure by
used optic"). Base-commit discipline: worktree `HEAD` started at `24f217fc` (`origin/main`), a
strict ancestor of the named tip `91b3c48908337af6c3db5c24e4d3190b62ba68e8`; tree was clean;
fast-forwarded with no divergence.

**The core correctness claim holds, verified by reading the call chain directly, not by trusting
the implementer's report.** `runner.optic` (`self.optic = optic_decision.optic`, `logger.py:593`)
and the value `_apply_active_gaze` assigns onto `source.optic` (`logger.py:1020`, where
`optic = decision.optic if decision is not None else UNAIDED_OPTIC` and `decision` is the same
`optic_decision` object) are not merely "kept in sync" — they are two reads of the same attribute
off the same object within the same `run_once()` call, so there is no sequencing window in which
they could disagree. `NakedEyePerceptionSource.poll` passes that same `self.optic` straight to
`check_visibility(..., optic=self.optic, ...)` (`naked_eye_source.py:754`). Read
`_run_crew_text_poll_loop` end to end (`logger.py:1913-2032`): nothing between `runner.run_once()`
and the `drain_attack_run` call mutates `runner.optic` — the only writes in that span
(`runner.optic_state = replace(...)` for the OBSERV on/off transitions) touch `optic_state`, a
different attribute. So `resolving_optic=runner.optic` is exactly the optic that admitted this
tick's percepts, not an approximation of it.

**Counterfactual re-run myself, both the existing one and the test's own, not accepted from the
report:**
- Reverted the `logger.py:2031` call site to `resolving_optic=runner.optic_state.guidance_optic`
  and re-ran `test_crew_text_poll_loop_passes_the_used_optic_not_the_guidance_grant` — failed with
  `AssertionError: assert None is Optic(name='binocular', ...)`, exactly as the implementation log
  states. Restored; `shasum` of `logger.py` matched exactly before and after
  (`0c7887dd70f6d7d4534a83d0b39b0eb60a7e7de5`).

**The rename (`granted_optic` → `resolving_optic`) is complete and the new name is accurate.**
`grep -rn "granted_optic" src/ tests/` finds only one hit, a past-tense explanatory reference in
`attack_run.py`'s docstring describing what the *prior* cut got wrong — not a leftover live
parameter. Both docstrings (`decide`, `_no_look_cause`) and both call-site comments
(`crew_console.py`, `logger.py`) describe the used-optic contract correctly and consistently.

**The new `test_logger.py` test's design is a fair test of the production call site.** It stubs
`run_once` to isolate exactly one thing — which attribute the loop body reads at the
`drain_attack_run` boundary — from how `decide_optic` arrives at either value (already covered by
`test_optic_policy.py`). This does not remove the ordering guarantee the fix depends on, because
that guarantee is not a sequencing property across calls that a stub could hide — it is the
structural fact (confirmed above) that `runner.optic` and the admitting optic are the same
attribute read twice off the same object. Stubbing `run_once` cannot un-couple two reads that are
coupled by construction; it only removes the unrelated work of recomputing `OpticDecision` for a
test that doesn't need to.

**Guard-3 edge case is genuinely moot, not merely asserted moot.** The previous round's leftover
gap (guard-3-refused grants, where `decision.optic` and `state.guidance_optic` could briefly
disagree, and the then-current fix read the more conservative `guidance_optic`) is closed by
construction: `resolving_optic` now reads `runner.optic` directly, which *is* `decision.optic` —
there is no remaining path where the two diverge.

**No regression elsewhere.** `git diff --stat 37f137d9 91b3c489` touches only `attack_run.py`,
`crew_console.py`, `logger.py`'s one call site, `optic_policy.py` (comment-only — diffed and
confirmed no logic change), `config/defaults.toml`, tests, and `implementation.md`. The hard-gate
clamp, the fourth-exit-transition carry-forward, and de-escalation code are untouched by either
round. The cross-key coupling warning (`GUIDANCE_OPTIC_MIN_INTERVAL_S` vs. `HANDS_BUSY_DURATION_S`)
is now in the comment's rendered first sentence — checked the actual `config/defaults.toml` output
directly, not the source: it reads correctly, no backtick corruption, no eaten space across the
line wrap.

**Formatting:** confirmed the committed tree is `ruff format --check`-clean (133 files already
formatted) and that nothing unrelated was reformatted — the diff stat above lists only the files
the implementation log describes touching.

Full gate re-run from this worktree, main checkout's venv, `cwd` inside `body-layer/`:
`ruff format --check src tests`: 133 files already formatted. `ruff check src tests`: all checks
passed. `mypy src`: Success, no issues found in 60 source files. `pytest tests -q`: **2090 passed,
4 xfailed** — matches the implementer's reported baseline exactly.

---

### Required Fixes

None.

### Optional Refinements

- **The user's ruling ("actual behavior must measure by used optic") is recorded in commit
  messages and `implementation.md` but not in a `docs/acceptance/` note of its own.** For a
  one-line mid-fix course correction this is a reasonable proportionality call — nothing here rises
  to the "flight feedback" capture-then-explore protocol — but if this phrasing is likely to be
  cited again (e.g. as a precedent for "used, not granted" elsewhere in the optic/attention model),
  a short `docs/acceptance/` entry would make it findable without grepping commit history. Not
  required; the implementation log already preserves the wording and reasoning adequately for this
  item's own scope.
- **First-grant hands-busy overcharge and the `_apply_guidance` first-grant baseline** — both
  carried forward unchanged from the first review as explicitly-flagged, non-safety-relevant,
  out-of-scope-for-this-task items. No new concern; restating only to confirm they were not
  silently dropped between rounds.

### Verdict

APPROVED

### Review Confidence

Full read. Both required-fix verification points were re-run by mutation myself (the call-site
revert reproducing the exact reported `AssertionError`, with a `shasum`-confirmed exact restore),
not accepted from the implementation log. The full call chain (`logger.py` → `naked_eye_source.py`
→ `visibility.check_visibility`) was read directly to confirm `runner.optic` and the admitting
optic are the same value by construction, not merely claimed to be. Did not re-run the counterfactual
for the first round's now-superseded `granted_optic`/`guidance_optic` wiring, since it is dead code
as of this round and the current code's own correctness was independently re-derived rather than
inherited from that earlier finding.
