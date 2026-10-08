# Review round 3 — security fix review, `fix/los-hook-statics`

**Commit under review:** `3395b4a34a48c357b0e3d24a04a67b87182f5b1a`
**Answers:** `plans/los-hook-statics/security-review.md`'s two required fixes
(60e5b07, verdict APPROVED WITH REQUIRED FIXES)

## Base-commit correction

Worktree landed on `main` (`2ddceff`), as predicted — `fix/los-hook-statics` is checked out in the
main checkout. `worktree-agent-a01c6bd9e0d5c78b1` carried no unique commits (just a ref onto
`main`'s tip), so moving the ref directly was safe and lossless, per the dispatching prompt's own
documented mechanism:

```
git checkout -B worktree-agent-a01c6bd9e0d5c78b1 3395b4a34a48c357b0e3d24a04a67b87182f5b1a
```

`git rev-parse HEAD` now returns `3395b4a34a48c357b0e3d24a04a67b87182f5b1a`, tree clean.

## What was verified (re-run, not inherited)

| check | result |
|---|---|
| `ruff check src tests` | pass |
| `mypy src` (cwd inside `aircraft-layer/`) | pass, 21 source files |
| `pytest tests -q` | **254 passed** |
| `luac5.1 -p` on the outer hook file | pass |
| `LOS_CODE` prefix reconstructed standalone (same literals, same `string.format` calls) and compiled with `luac5.1 -p` | pass, bytecode dump shows **LOADK/MOVE/RETURN only — no GETGLOBAL/SETGLOBAL at all** for the current `128`/`10000.0` literals |
| Mutation: `%.17g` → `%.17s` on the real splice, reran `test_line_of_sight_hook_lua.py` | **1 failed, 6 passed** — `test_los_code_prefix_has_exactly_one_percent_d_and_one_percent_17g` goes red with the exact mismatch (`['%.17s'] == ['%.17g']`), confirmed, then restored and confirmed `git diff --stat` is empty |
| Real parser (`LineOfSightSnapshot.from_wire`) against a post-fix-shaped payload (`;`-named object simply absent) | parses cleanly, `units_in_bubble=2`, both remaining verdicts intact |
| Real parser against a pre-fix-shaped payload (the `;`-name leaked onto the wire) | raises `LineOfSightParseError` on the fragment — reproduces exactly the hazard the fix removes |
| `grep` for every path that appends to `parts`/`candidates` | one write site (`candidates[#candidates+1] = {...}` inside `considerCandidate`), one read site (`parts[#parts+1] = c.name..":"..`) — both unit and static enumeration loops call the same `considerCandidate`, so the `;` guard covers both; no second path for a name to reach the wire |

## Ruling on the three flagged points

### (a) Two regexes, one job

**Not a hole.** Tested by mutation (table above): any widened/changed specifier on
`SET_LOOK_TEMPLATE` perturbs `_FORMAT_DIRECTIVE_RE`'s `findall()` away from the exact
`["%d", "%d"]` the test asserts, even though the regex mischaracterizes multi-char directives
(`%.17g` reads as `["%."]`, `%5d` reads as `["%5"]`). For `SET_LOOK_TEMPLATE` specifically — which
only ever carries `%d` — there is no constructible mutation that both changes what the splice emits
and leaves `findall()` reading exactly `["%d", "%d"]`. The old guard passes for the right reason,
not by coincidence; it just documents its own narrowness honestly.

**Optional refinement:** `_PRINTF_DIRECTIVE_RE` is a strict superset and verified to produce the
identical `["%d", "%d"]` against the real template. Two near-identical patterns for one concept is
exactly the drift risk this repo already flagged once (the duplicated `128` literal). Collapsing to
one regex, used by both guard tests, would remove that risk at zero cost — but the implementer's
own stated reason for not doing it (don't touch `SET_LOOK_TEMPLATE`'s established guard behaviour
on an unrelated fix) is a legitimate, conservative call. Not required.

### (b) `nameRejects` excluded from `objectsInBubble`

**Consistent with established precedent, not an oversight worth blocking on.** `objectsInBubble`/
`objectsInWedge` (wire-level `units_in_bubble`/`units_in_wedge`) now count only objects that survive
into the candidate pipeline — exactly how `staticEnumFailures`/`unitEnumFailures` already work: a
per-side enumeration failure stays in the `env.info` log line and is never folded into the wire
counts either. `name_rejects=` follows the same split: Lua-log-only, wire count reflects "objects a
sightline could actually be computed for." This also keeps the docstring's own stated purpose for
the triad (`sightlines_computed < units_in_wedge` as the cap-hit signal) trustworthy — a
name-rejected object can never produce a sightline, so counting it in the denominator would bias
that comparison toward a false cap signal.

Where this falls short: `name_rejects` **never reaches the wire** (confirmed —
`schema/line_of_sight.py`'s 7-field format is untouched by this commit), so a drop here is visible
only in `dcs.log`, not to body-layer or the API. That's the same limitation `static_enum_failures`/
`unit_enum_failures` already carry, so it is not a new gap this fix introduces — but combined with
(b), it means nothing at the API/body-layer level distinguishes "fewer objects were genuinely in
range this poll" from "N objects were silently dropped for having a `;` in their name." A one-line
addition to the module docstring in `schema/line_of_sight.py` (which currently states
`units_in_bubble`/`units_in_wedge` are "counts of *objects* (units + statics)" with no mention of
the exclusion) would close that gap cheaply. **Optional, not required** — it's a documentation
completeness note, not a behavioural defect, and it matches an already-accepted project pattern.

### (c) Does the guard close the hole end to end?

**Yes, verified by execution** (table above), both directions: the post-fix payload shape parses
cleanly with the rest of the poll intact, and feeding the pre-fix shape through the real parser
reproduces the original hazard, confirming the fix is what stands between them. Confirmed there is
exactly one path from an object's name to the wire (`considerCandidate` → `candidates` → `parts`),
shared by both the unit and static enumeration loops, so the guard cannot be bypassed by one
population and not the other.

## Other observations (optional)

- **No mechanical test exercises the `;` guard itself.** The implementer's own
  `implementation.md` states this plainly: the fix is Lua-only text with no new Python behaviour,
  and this codebase has no automated behavioural test for Hook scripts at all
  (`aircraft-layer/CLAUDE.md`'s own stated limitation). Consistent with that limitation, not a gap
  this commit introduces. A cheap, optional addition: `test_line_of_sight_schema.py`'s existing
  `test_malformed_payloads_raise` parametrization (`aircraft-layer/tests/test_line_of_sight_schema.py:55`)
  could gain one case with a `;` inside the name field, to keep the originally-demonstrated hazard
  under permanent regression coverage rather than only in `security-review.md`'s prose. Optional —
  the parser itself is unchanged, so this documents the motivation rather than tests new code.
- The `%.17g` comment narrowing is accurate and scoped correctly (only the comment touched, matching
  the review's "fix-before-public, taken while in the area" framing); re-verified the underlying
  claim (`inf`/`-inf`/`nan` are not valid Lua numeral syntax) is true and that the constant is
  grep-confirmed never reassigned.
- Live-sortie interaction check: the 2026-10-08 feedback (`docs/acceptance/2026-10-08-los-statics-sortie-feedback.md`)
  predates this fix and reports the Damascus `cap_hit=1` population issue. The `;` guard has no
  interaction with it — it only removes malformed-name objects from the candidate list, which does
  not change which objects bind the 128 cap over a dense city. Not this review's scope, not touched.

## Scope

Matches the security review's two required fixes exactly, plus the one named fix-before-public item
taken while in the area. No scope drift. Module boundaries unchanged (Lua hook + its own test file
+ `implementation.md`); no Python `src` behaviour changed.

## Verdict

**APPROVED.** No required fixes. Both of Security's required fixes are correctly implemented,
demonstrated end-to-end (not just reasoned about), and covered by a guard test that was confirmed
to go red for the stated reason. The three flagged points above resolve in the fix's favor, with
two low-cost optional refinements (one doc line, one test parametrization) that do not need to block
DoD.

Ready for DoD.

## Review Confidence

Full read. Every claim in this file was independently re-derived: ran all four checks myself
(ruff/mypy/pytest/luac), reconstructed and compiled the actual `LOS_CODE` splice standalone, ran the
real Python parser against both payload shapes, grepped for every write site into `parts`, and
mutated the real Lua file (`%.17g` → `%.17s`) to watch the new test go red before reverting it
cleanly.
