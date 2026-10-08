---
name: los-hook-statics-round3-approved
description: fix/los-hook-statics security-fix review round 3 — APPROVED clean; log-only counter precedent check
metadata:
  type: project
---

Round 3 reviewed the fix answering Security's deep-analysis required fixes on
`fix/los-hook-statics` (commit `3395b4a`): a `;`-rejected mission-author object name now drops one
object instead of the whole poll, plus a mechanical guard test for `LOS_CODE`'s load-time splice
(the second code-generation site, alongside `SET_LOOK_TEMPLATE`).

**Technique that mattered here: when a rejection counter's placement looks suspicious (incremented
before vs. after a separate "survived" counter), check for an existing sibling pattern before
calling it a bug.** `nameRejects` is incremented and the function returns *before*
`objectsInBubble = objectsInBubble + 1` — so a rejected object silently shrinks the wire-level
`units_in_bubble` count with no accompanying wire signal. Looked like a candidate required fix.
But `staticEnumFailures`/`unitEnumFailures` already follow the identical shape: a per-side
enumeration failure stays `env.info`-log-only and never folds into the wire counts either — it's
an established project pattern for "this counter can't cross the `dostring_in` boundary, so it
goes to `dcs.log` directly," not an oversight. Ruled optional (one doc line in
`schema/line_of_sight.py`'s module docstring), not required.

**Mutation re-confirmed, not trusted:** the implementer's claimed `%.17g` → `%.17s` counterfactual
run was re-executed independently (edit the real Lua file, rerun pytest, see the exact
`['%.17s'] == ['%.17g']` mismatch, revert, confirm `git diff --stat` empty) rather than taken on
the implementation.md's word.

**The "two regexes for one job" smell (`_FORMAT_DIRECTIVE_RE` vs `_PRINTF_DIRECTIVE_RE`) resolved
in the fix's favor by mutation, not by reading.** The old regex mischaracterizes multi-char
directives (`%.17g` reads as `%.`) but for `SET_LOOK_TEMPLATE` (which only ever carries `%d`) no
constructible mutation both changes the splice and leaves `findall()` reading the exact expected
list — so the guard passes for the right reason despite its documented narrowness. Verified with
three hand-built mutations before concluding this, not from inspection alone. See also
[[every-guard-entry-needs-a-failing-counterfactual]] — same discipline, applied to a regex rather
than an except-tuple.

Verdict: APPROVED, ready for DoD. No required fixes; two optional refinements (one docstring line,
one regression-coverage parametrization in the existing `test_malformed_payloads_raise` table).
