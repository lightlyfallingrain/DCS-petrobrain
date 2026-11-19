### Review Summary

Branch `fix/rule-collision-misheard`, one commit on `main` (`763d4288`, tip verified via
`git rev-parse HEAD` after fast-forwarding from `36d7e63c`). Bug fix, no plan directory — reviewed
against the user-approved intent stated in the dispatch, `plans/speech-rules/plan.md` D9/D13, and
`body-layer/ROADMAP/BL-17.md` U10.

The change adds a keyword-only `confident_loss_disables: bool = True` parameter to
`_is_genuine_collision` (`audio-adapter/src/rule_patterns.py`). Rule x rule
(`_rules_collide`) keeps the old default (`True`): a confident loss on a perturbed sample still
disables both rules. Rule x legacy (`_collides_with_legacy`) now passes `confident_loss_disables
=False`: a confident loss there no longer disables the rule — only an exact tie on the clean
wording (`own_ratio == other_ratio == 1.0`) still rejects it, unchanged. This exactly matches the
stated intent and U10's own text ("two rules claiming the same wording: both disabled" — a rule x
*rule* clause only).

**Correctness of the underlying claim, verified independently, not just trusted:** read
`command_matcher.match_transcript`'s rule/legacy merge (`src/command_matcher.py:1166-1182`) — when
a rule is active and the legacy pipeline also resolves, the branch with the higher `match_ratio`
wins outright once the gap clears `SEPARATION_MIN`; a rule's mere existence never suppresses a
confident legacy resolution. So disabling the rule at load time bought nothing at runtime for this
collision case: the mis-hearing still goes to legacy with or without the rule, and keeping the
rule only restores correct recognition on the *clean* wording. The fix's premise holds.

**Real-world anchor, verified:** the two probed patterns in the new API test
(`test_a_mis_hearing_that_only_reaches_a_legacy_command_keeps_the_rule`) — `"align"` and
`"break turn <direction:left|right>"` — are exact copies of `cbtm_align`/`cbtm_break`'s real
patterns in `body-layer/config/rules/flight.lua:202-235`. This is not a synthetic example; it is
the actual shipped collision, exercised through the real `_legacy_probe`/`command_matcher`
pipeline (`running_server` fixture, no stub legacy matcher).

**No hazard caught by the old clause is missed.** The only genuine hazard U10 names — two
competing claims on the *same* wording — is the exact-tie case, and that path is untouched and
still tested (`test_legacy_exact_tie_on_the_clean_wording_is_still_rejected`, new, and the
unmodified `test_rule_x_rule` suite for the rule x rule side). The near-tie (ambiguous) band is
also untouched — it still returns `False` with an `INFO` log, deferring to the runtime confirm
band exactly as before.

**Test adequacy.** The renamed unit test
(`test_legacy_probe_confidently_beating_a_perturbed_sample_keeps_the_rule`) correctly flips its
assertion to match the new behaviour and its docstring points at the rule x rule counterpart that
still enforces the stricter rule. A new unit test covers the exact-tie case explicitly (previously
only implicit in the renamed test). A new `test_rules_api.py` test exercises the fix end-to-end
through the real `PUT /rules` handler and the real legacy pipeline, anchored to the two rules that
motivated the fix. Full audio-adapter suite passes (566 passed, 2 skipped) — this is stronger
evidence than `fast-tests.sh` alone, and was run in addition to it.

**Docstring accuracy.** `_is_genuine_collision`'s and `_collides_with_legacy`'s docstrings were
both updated to state the new split precisely, including the 2026-11-19 date, the user-approval
note, and the concrete measured cases (`cbtm_align`/`cbtm_break`). No durable line (dated note,
verbatim quote, measurement) was deleted — the only text removed was the now-inaccurate single
sentence describing the pre-fix behaviour, replaced by a more precise one; the pre-fix behaviour
is still recorded as a "(Until 2026-11-19 also when it beat it...)" parenthetical in
`_collides_with_legacy`'s docstring, so nothing is silently lost.

One minor documentation gap found (noted below, optional): `plans/speech-rules/plan.md`'s own D9
text (the "Recalibrated 2026-11-17" paragraph) still describes the rule x legacy and rule x rule
passes as sharing one check with no mention of today's split. Since this fix has no plan directory
of its own, that paragraph is now slightly stale against the shipped code. Not required to fix
here (the dispatch explicitly scoped this as code+tests, not a plan update), but worth a line
whenever `plans/speech-rules/plan.md` is next touched.

### Required Fixes

None.

### Optional Refinements

- `plans/speech-rules/plan.md`'s D9 "Recalibrated 2026-11-17" paragraph describes one shared
  criterion for both rule x rule and rule x legacy; it's now inaccurate for rule x legacy after
  this 2026-11-19 change. Worth a short addendum there next time that file is edited, so a future
  reader of the plan isn't misled about current behaviour (optional — this fix correctly scoped
  itself to code/tests only, per the dispatch).
- The rule x legacy confident-loss-but-kept path (`confident_loss_disables=False`, gap >=
  `SEPARATION_MIN`) now returns silently with no log line, unlike the near-tie branch which logs
  at `INFO`. A one-line `DEBUG` (or `INFO`) log naming the rule/legacy pair on this path would make
  a future "why didn't X get flagged" investigation easier, mirroring the near-tie log already
  there. Not required — this is deliberately silent-by-design per the fix's own reasoning (the
  rule's existence changes nothing observable at runtime for this case), but it's the one place a
  future reader loses visibility into which known mis-hearings exist.

### Verdict
APPROVED

### Review Confidence
Full read — diff is small (3 files, single mechanism change plus three tests), and verified
against the plan text, the roadmap decision (U10), the real `command_matcher` merge logic, and the
real `flight.lua` rule definitions, not just the stated intent. Ran `ruff format --check`,
`ruff check`, `mypy --strict` (all clean), and the full `pytest` suite (566 passed, 2 skipped) from
the correct venv (`/Users/sg/Code/DCS-petrobrain/audio-adapter/.venv`), in addition to what
`fast-tests.sh` would cover.
