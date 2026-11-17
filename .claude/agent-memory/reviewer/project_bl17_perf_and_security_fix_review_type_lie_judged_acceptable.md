---
name: project_bl17_perf_and_security_fix_review_type_lie_judged_acceptable
description: BL-17's two post-batch Required Fix commits (collision-check memoization, body.py union-slot dict filter) reviewed APPROVED -- worked example of judging a deliberately-scoped type lie against the Any-boundary rule, and of mutation-verifying a security fix's regression tests rather than trusting the implementer's counterfactual account.
metadata:
  type: project
---

`0ca6d715` (perf: `compile_rules` memoizes `_samples_with_perturbation` once per rule instead of
per pair) and `79d75af8` (security: `body.py`'s `_poll_transcripts` admits a bounded dict slot
value) both reviewed APPROVED, no required fixes, 2026-11-17
(`plans/speech-rules/review-perf-security-fixes.md`).

**Worked example for judging "the implementer deliberately left a type narrower than runtime
reality, is that acceptable":** `handle_command`/`_dispatch_rule`/`run_rule`/
`PendingRuleDispatch.slots` all stayed `dict[str, int | str]` even though a dict value (`set_speed`'s
`speed_target` tagged table) now genuinely flows through them at runtime. Judged acceptable because
(1) `AudioAdapterClient.get_transcripts() -> tuple[list[dict[str, Any]], ...]` means the value is
already `Any`-typed at the one point it enters `body.py` -- mypy never checked the narrower claim
anyway, confirmed by running `mypy --strict` and seeing it clean both conceptually and actually;
(2) the real invariant (no dict reaches an unrelated token handler) is enforced by
`handle_command`'s own token-based branching, not the type system; (3) widening the shared `slots`
param would cascade into ~10 unrelated handlers for zero safety gain. This matches
`.claude/agent-memory/implementer/feedback_scope_type_widen_to_the_any_boundary_not_the_whole_chain.md`
exactly -- that memory's reasoning is the test to apply, and it held up under independent
verification here, not just on the implementer's own say-so.

**The one real gap found, filed as optional (not a blocker):** none of the narrower-typed
functions on the rule-dispatch path (`run_rule`, `_dispatch_rule`, `PendingRuleDispatch.slots`,
`rule_runner`'s `Callable` type) carry a comment saying a dict value can reach them despite the
declared type. The explanation lives only at `body.py`'s own validator and in
`implementation.md` -- a future reader opening `run_rule` cold would reasonably (and wrongly)
assume scalar-only. Did not require it as a fix: no correctness/type-safety issue follows, the
real boundary is tested, and `CLAUDE.md`'s own comment-pruning guidance doesn't reach code nobody
touched this batch. **Worth watching**: if a future BL-17 stage adds a second union slot or a
Python-side consumer that actually reads a slot value's shape (not just handing it to Lua), revisit
whether this comment gap should become a required fix at that point -- the invariant it is
protecting gets a second, independent user then.

**Process note for future reviewers**: verified the security fix's regression tests by mutation
(reverted the fix in a throwaway edit, re-ran `test_body.py -k poll_transcripts`, confirmed the
two threading/e2e tests go red for the stated reason while the two rejection tests stay green
under both old and new code, then restored and shasum-matched) rather than trusting the
implementer's own "counterfactual run" writeup. Also independently re-measured `compile_rules`
timing at n=18/50/100 with a fresh standalone script rather than re-running the implementer's own
benchmark -- numbers differed in absolute value (different synthetic padding) but confirmed the
same order-of-magnitude fix, which is the actual question a performance Required Fix needs
answered. Both took under a few minutes and caught nothing wrong this time, but are the right
default for any review phrased as "is this fix real" rather than "is this file present."
