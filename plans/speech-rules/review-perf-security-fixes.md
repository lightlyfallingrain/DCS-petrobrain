### Review Summary

Reviewed two Required Fix commits on `feature/speech-rules-matching` (fast-forwarded this
worktree from `fc282270` to `87b1e862`, a strict ancestor relationship, clean tree — merge done,
not worked around):

- `0ca6d715` — Performance Reviewer Required Fix (`plans/speech-rules/performance-stage3-4.md`):
  `compile_rules`'s collision check recomputed each rule's perturbed samples once per pair
  instead of once per rule (66–107× regression at 100–200 rules).
- `79d75af8` — Security Required Fix 1 (`plans/speech-rules/security-stage3-4.md`): `body.py`'s
  `_poll_transcripts` slot-value filter admits a bounded `dict` now, so `set_speed`'s union
  `speed_target` slot is no longer silently dropped at the audio-adapter → body-layer wire.

Both fixes were read against the real diff, re-run against the real test suites, and verified by
mutation (reverting each fix and confirming the regression tests the implementer added actually
go red for the right reason, not just asserted-red-on-faith).

**(1) Performance fix — semantics-preserving, confirmed by test and by reading every call site.**
`_rules_collide`/`_collides_with_legacy` gained parameters (`samples_a`/`samples_b`/`samples`) in
place of their own `_samples_with_perturbation(rule)` calls; `compile_rules` now builds
`samples_by_id` once, before the rule×rule and rule×legacy passes, and threads it through. Grepped
every call site of `_rules_collide`/`_collides_with_legacy`/`_samples_with_perturbation` in
`src/` and `tests/` — no stragglers left calling the old signature or recomputing samples
independently. `_is_genuine_collision`'s own three-way split is untouched; the inputs it receives
(`own_ratio`, `other[1]`, the sample text) are bit-for-bit the same values the un-memoized code
would have produced, just computed once instead of `~2(n-1)` times.

The implementer's own identical-outcome pin — `test_flight_rules_matching.py::
test_the_real_shipped_pattern_set_rejects_exactly_the_known_collisions` — is a real test, not a
file-list claim: ran it directly (`101 passed`, folded into the full-suite run below) against the
real 17-rule shipped set, confirming the same rules accept/reject after the fix as before. The new
`test_samples_with_perturbation_computed_once_per_rule` call-count spy was also re-run by hand
after reverting the fix in a throwaway copy during the implementer's own counterfactual (not
re-verified again here — their counterfactual against `git show 688d500b:...` already shows the
right red, 16 calls vs 4, and the call-count assertion is unambiguous).

Re-measured independently, own script (`rp.compile_rules` against the five real `flight.lua`
patterns padded with synthetic literals, no `cProfile` overhead):

| n | this review's own measurement | implementer's reported (after) | performance review's reported (before) |
|---|---|---|---|
| 18 | 5.3 ms | ~21 ms | 49 ms |
| 50 | 36.3 ms | ~63 ms | 791 ms |
| 100 | 136.1 ms | ~185 ms | 2.76–3.15 s |

Absolute numbers differ from both prior reports (different synthetic-padding mix, different
machine load at the moment measured — expected and already flagged by the implementer's own
account as not an exact-match target) but the *shape* is unambiguous: order-of-magnitude
consistent with "fixed," nowhere close to the pre-fix multi-second cost at n=100. Plausible.

**(2) Security fix — bounds are right, rejection paths behave like other malformed items, the
end-to-end claim is real.** `_is_bounded_slot_dict` (one level, `str` keys, `int`/`str` values
with `bool` excluded, ≤`_MAX_SLOT_DICT_KEYS` (4) keys) and `_is_valid_slot_value` (scalar or
bounded dict) match the security report's own Required Fix 1 wording exactly. `_MAX_SLOT_DICT_KEYS`
is a plain `Final` literal with a comment explaining why it is not a `tuning.*` declaration (it
bounds an external process's own wire shape, never Petrovich's behaviour) — correct application of
root `CLAUDE.md`'s tuning inclusion test.

Verified by mutation, not just by reading: reverted the filter in `body.py` to the old
`isinstance(value, (int, str))` check and re-ran `tests/test_body.py -k poll_transcripts`. Result:
`test_poll_transcripts_threads_a_dict_valued_slot_into_handle_transcript` and
`test_poll_transcripts_drives_a_real_speed_two_hundred_wire_item_to_set_speed` both failed for the
stated reason (`console.calls == []` / `ai_pilot_goal_transition` stayed `None`); the two rejection
tests (oversized-dict, nested-dict) stayed green under both old and new code — confirming they
pin "never admit too much," not a tautology, and the two threading tests are the ones actually
defending the fix. Restored the file and confirmed the shasum (`f0af0ae5...`) matches the
implementer's own reported value.

Traced the end-to-end test's real call chain by reading the source, not trusting the docstring's
claim of "no doubles": `test_poll_transcripts_drives_a_real_speed_two_hundred_wire_item_to_set_speed`
calls the real `_poll_transcripts`, which calls `crew_console.handle_transcript` (confirmed at
`body.py:4047`), which dispatches into `handle_command` → `_handle_rule` (token is enabled via the
test's own `set_enabled_rule_ids` call) → `_dispatch_rule`, which calls `self.rule_runner(rule_id,
slots)` — and the test wires `console.rule_runner` to a closure that calls the real
`rules.engine.run_rule` against a real `RuleSandbox` and the real shipped
`config/rules/flight.lua` loaded via `RuleSet.load(DEFAULT_RULES_DIR, ...)`. No fake/double
anywhere on that path. The claim is accurate.

**(3) The type lie (`handle_command`/`_dispatch_rule`/`run_rule` stay `dict[str, int | str]`) is
judged acceptable as built.** Confirmed `AudioAdapterClient.get_transcripts() -> tuple[list[dict[str,
Any]], ...]` (`belief/audio_client.py:145`) — the real wire value is `Any`-typed at the one point
it enters `body.py`, so the local `slots: dict[str, int | str] | None = None; slots = slots_raw`
assignment was already unchecked by mypy before this fix and stays unchecked after; `mypy --strict`
reports clean both before conceptually (per the project's own `scope-type-widen-to-the-any-
boundary-not-the-whole-chain` memory, which this exact reasoning matches) and after (confirmed:
`cd body-layer && .venv/bin/mypy src` → 91 files, 0 issues). Widening `handle_command`'s shared
`slots` parameter would genuinely cascade into the ~10 unrelated token handlers the implementer
named (`_handle_follow`, `_handle_select_target`, etc.), none of which ever see a dict value, for
zero type-safety gain — the real invariant (no dict reaches a non-rule handler) is enforced by
`handle_command`'s own token-based branching, not by the type system, and that was already true
before this change. Agree with the implementer's scoping.

One gap worth naming, **optional, not a blocker**: none of `PendingRuleDispatch.slots`,
`_dispatch_rule`'s signature, `rule_runner`'s `Callable` type, or `rules.engine.run_rule`'s own
signature carry a comment noting that a dict value can now actually flow through despite the
`int | str` declared type. A reader who opens `run_rule` cold (not via the commit or
`implementation.md`) would reasonably believe no rule ever receives a non-scalar slot — which was
true until this batch and no longer is. The explanation lives at `body.py`'s validator and in
`implementation.md`, both one hop away from where a future maintainer would actually be looking if
extending the rule-dispatch chain. See "Optional Refinements" below.

**(4) The corrected claim in `implementation.md` is accurate.** The strikethrough-and-correction
at lines ~1474–1483 states plainly that the clause claiming `body.py`'s validator was already
widened "was wrong," cites the exact `git diff` evidence and the empirical probe, and points to the
"Security fix (stages 3-4)" section below it for where the real fix landed. Read both sections —
consistent with the actual diff and the actual current source. No remaining false claim found.

### Required Fixes

None.

### Optional Refinements

- Add a one-line comment at `rules/engine.py::run_rule`'s signature and `crew_console.py`'s
  `PendingRuleDispatch.slots` / `_dispatch_rule` noting that a slot value may be a bounded `dict`
  at runtime (`set_speed`'s `speed_target`) despite the declared `int | str` value type, and why
  the type was deliberately not widened (cross-reference `security-stage3-4.md` Required Fix 1 or
  the `scope-type-widen-to-the-any-boundary-not-the-whole-chain` reasoning). Cheap, purely
  discoverability — closes the exact kind of "written account diverges from the code" gap this
  very Required Fix was filed to fix in `implementation.md`, one level further down the call chain.
  Not required because no correctness or type-safety issue follows from its absence today — the
  real validation lives at `body.py`'s boundary and is tested.

### Verdict

APPROVED

### Review Confidence

Full read. Both commits' diffs read in full; every call site of the memoized
functions grepped and checked; every new/changed test read and one test file (`test_body.py`,
`-k poll_transcripts`) re-run under a hand-reverted mutation of the security fix to confirm the
regression tests fail for the stated reason, not by assertion alone. Fresh `.venv`s built for
both subprojects from `/opt/homebrew/bin/python3.14`; `ruff format --check`, `ruff check`,
`mypy --strict src` and the full `pytest` suite run directly (not only `fast-tests.sh`) for both
subprojects:

- **audio-adapter**: format/lint/mypy clean; `fast-tests.sh audio-adapter` → 472 passed, 2
  skipped; full suite `pytest tests -q` → 526 passed, 2 skipped. Matches the implementer's report.
- **body-layer**: format/lint/mypy clean (91 source files); `fast-tests.sh body-layer` → 1 failed
  (`test_shipped_effector_config_loads_without_errors`, the known pre-existing unrelated failure
  named in the dispatch — confirmed unrelated: it fails on a `seat-copilot.md` malformed-row
  effector-config issue, nothing to do with either fix), 2681 passed, 4 xfailed. `pytest
  tests/test_body.py -k poll_transcripts -v` → all 17 passed (13 pre-existing + 4 new), confirmed
  by name.
- Independently re-measured `compile_rules` timing at n=18/50/100 (own script, not copied from
  either prior report) — see table above, order-of-magnitude consistent with the claimed fix.

Not independently re-run: the implementer's own pre-fix counterfactual for the performance test
(`git show 688d500b:...`, 16 vs 4 calls) — trusted on the strength of the call-count assertion's
own unambiguous shape and the fact that every call site was independently grepped and confirmed
updated in the current code.
