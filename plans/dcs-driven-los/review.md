## Review: X-B29 — DCS-driven batched line of sight, Stages 1-3

Reviewed `feature/dcs-driven-los`, tip `0200e07f7e920e17d377fde93282480cfc2bafc4` (confirmed via
`git rev-parse feature/dcs-driven-los`; the task's worktree landed on `main`'s tip `01d84d0`, as
expected, so all reading and mechanical checks below ran against an isolated snapshot:
`git archive feature/dcs-driven-los | tar -x -C <scratch>`, with every command's `cwd` inside
`<scratch>/<subproject>` and the **main checkout's** `<subproject>/.venv/bin/{ruff,mypy,pytest}`
invoked by absolute path (confirmed the venv's import resolution picks up the snapshot's source,
not the main checkout's, by checking each subproject's own test/source count matched the
implementer's claim exactly — see Mechanical checks below).

`plans/dcs-driven-los/plan.md` exists on `main` already (pre-dates this branch's §7-§17 revisions,
confirmed by diffing). `plans/dcs-driven-los/security-plan-review.md` and
`plans/dcs-driven-los/implementation.md` exist **only on the feature branch**, not on `main` — both
were read from the snapshot only, consistent with the branch's own history (noted here because five
cherry-picks have conflicted on this exact file set today).

### Required Fixes

None.

### Optional Refinements

- **The Security-requested execution test of `_safeClampInt` against hostile inputs was not built;
  only text-presence checks exist** (`test_lua_file_contains_the_nan_and_infinity_guards` greps for
  the string `"value ~= value"` etc., never executes the function). I independently extracted
  `_safeClampInt` and ran it under a local Lua interpreter against `0/0`, `math.huge`, `-math.huge`,
  `nil`, a string, a table, and `1e300`/`-1e300` — all ten cases produced the correct clamped
  integer, and the naive `math.max(lo, math.min(hi, x))` the Security review warned about really
  does pass NaN through unchanged (confirmed empirically, not just asserted). So the code is
  correct; the gap is that CI itself never proves it, and a future edit to `_safeClampInt` could
  silently reintroduce the NaN-passthrough bug with the current test suite staying green. This is
  consistent with this project's own stated convention (`aircraft-layer/CLAUDE.md`'s Testing
  section: Hook scripts get `luac5.1 -p` syntax-only checks, "and nothing more" — no execution
  tests exist anywhere in this codebase for Lua, DCS-dependent or not), so I'm not treating it as a
  required fix. But `_safeClampInt` itself touches no DCS global and is a pure function — a small
  `lua5.1 -e` (or even `lua` 5.4/5.5, since the function uses nothing version-specific) invocation
  inside the test file would close exactly the gap Security's Finding 1 asked for ("assert the
  produced snippet against an expected string rather than only checking it parses"). Worth doing
  next time this file is touched; not worth blocking this feature on.
- **`MAX_SIGHTLINES_PER_CALL` is duplicated as two independent literals** — the outer Lua
  `local MAX_SIGHTLINES_PER_CALL = 128` and the hardcoded `128` inside the `LOS_CODE` string literal
  (`sightlinesComputed >= 128`) — with no mechanical guard tying them together, unlike the `%d`-count
  test that guards the splice. The implementer flagged this themselves in
  `plans/dcs-driven-los/implementation.md`'s "Notable Discoveries" rather than silently leaving it,
  and it is forced by the same `dostring_in`-literal rule as everything else in this file. A test
  mirroring `test_set_look_template_has_exactly_two_percent_d_and_nothing_else`'s pattern (grep both
  occurrences, assert equal) would be cheap. Optional.

### What I verified and how

**Both Security required fixes, read against the built code and independently exercised:**
- The clamp (`_safeClampInt`, `petrobrain-line-of-sight-hook.lua:368`) checks `type ~= "number"`,
  then NaN self-inequality, then `+math.huge`/`-math.huge`, all *before* the ordinary min/max —
  exactly the order Security required. I ran it under a standalone Lua interpreter with the hostile
  inputs from the review and it degrades correctly every time (see Optional Refinements for detail).
  The whole decode-clamp-format-`dostring_in` sequence is wrapped in `pcall` (`onSimulationFrame`'s
  `pcall(pollLookDirection)`), and a failure leaves `lastSentHour`/`lastSentFovHalfDeg` untouched
  because the only mutation point is the single `dostring("scripting", snippet)` call inside
  `_applyLookDirection`, which only runs after both clamps succeed.
- `pollLookDirection` drains up to `MAX_LOOK_DIRECTION_DATAGRAMS_PER_FRAME` (20) queued datagrams in
  a loop but keeps only `latest`, calling `_applyLookDirection(latest)` exactly once after the loop
  — one `dostring_in` per frame regardless of burst size, matching required fix 2.

**The declared deviation (two `%d` instead of one).** Sound. Both substitution points
(`PB_LOOK_HOUR`, `PB_LOOK_FOV_DEG`) are independently passed through the same total `_safeClampInt`
before `string.format`, so each is "an already-integerised value in a known range" — exactly the
property the one-`%d` rule was protecting. `SET_LOOK_TEMPLATE` is a module-level constant with
`%d`/`%d` and nothing else, and `test_set_look_template_has_exactly_two_percent_d_and_nothing_else`
mechanically guards against a third substitution point landing unnoticed, which is the actual hinge
Security named.

**The 12 m tolerance boundary.** Verified in code, not accepted on the implementer's word.
`visibility.py:785-791`: `if candidate.live_los_clear is not None: ... elif not
line_of_sight_clear(...)`. The offline primitive is called **only** in the `elif` — i.e. only when
no live verdict exists. `world_model/src/query/line_of_sight.py`'s `_TERRAIN_TOLERANCE_M` comment
block was updated with an explicit "test-path-only — never a live-detection input" statement plus the
correct nuance that the fallback branch and fixtures are a real, permanent remaining use, not a
dead one. This matches the user's own quoted direction exactly and required no code change, as
claimed — the boundary was already correct by construction.

**No-omniscience.** `detection_trace_writer.py` has zero references to any LOS field (confirmed via
grep) — the new fields arrive on the ground-truth (perception) side only, never cross into belief as
a second truth channel. The chain is perception (`naked_eye_source._resolve_los_by_unit_name`, joins
the DCS-fed `GET /line_of_sight/latest` by `unit_name`) → `Observation.live_los_clear` →
`Percept.live_los_clear` (`percept_of`, unchanged pass-through) → `Contact.live_los_clear`
(overwritten, not folded, in `record()`/`from_percept()`). Belief never computes or sources this
value itself.

**The deletion.** `_threat_has_los`, `LOS_UNCERTAINTY_SAMPLES`, and `tick`'s `los_clear` parameter are
gone — grepped the whole of `body-layer/src/` for any remnant, found none. The rewritten engagement
term (`contacts.py:1359-1389`) implements exactly the three-part fail-open logic the plan's §11a
settled: out-of-envelope resets masking bookkeeping (load-bearing, not tidying — the reset prevents a
stale `los_masked_since_sim` from reading as instantly-masked on re-entry); no fresh verdict or a
verdict stale relative to `OBSERVED_WINDOW_S` fails open (`los_ok = True`); a fresh `False` verdict
only clears a danger state after `LOS_MASK_CONFIRM_S` of continuous masking. The four rewritten tests
in `test_contacts.py` set `Contact.live_los_clear`/`last_seen_sim` directly rather than patching a
fake callable, which is required by the deletion itself.

**Tests, disabled and rerun to confirm they're load-bearing, not decorative:**
- `test_live_los_clear_false_drops_a_candidate_without_consulting_the_offline_primitive` /
  `..._true_admits...` use a spy (`_fail_if_called`) on `line_of_sight_clear` that sets a flag if
  called — a real test of "never consulted", not just "result matches". Read the assertions directly;
  both fail if gate 4's live-verdict branch is removed.
- The clamp's NaN-passthrough failure mode is not hypothetical — I reproduced it: the naive
  `math.max(lo, math.min(hi, x))` on `0/0` returns `180` (the upper bound, garbage-in/garbage-through)
  under the real Lua semantics, exactly the bug Security named and exactly what `_safeClampInt`'s
  explicit guards prevent (verified: returns `45`, the documented default).
- `test_run_once_pushes_look_direction_on_change_only` (`test_logger.py`) asserts exactly one push on
  the first call and no second push when the gaze/hour pair is unchanged — read the assertion
  directly, it would fail if push-on-change were replaced with push-every-poll.
- `annotate_los` (`detection_trace.py:271-279`) is a no-op when `_last_by_object_id.get(object_id)`
  returns `None`, mirroring `annotate_motion`'s established, already-tested pattern exactly; called
  unconditionally per candidate in `naked_eye_source.py:581` (not gated on gate outcome), confirmed by
  reading the loop directly — a `TERRAIN_LOS`-outcome row still carries `building_clear`/
  `terrain_clear` as claimed.

**Parallel-treatment check (the standing "grep for the call site, not the file list" rule).** Only
`naked_eye_source.py` constructs `WorldObjectCandidate` with the LOS join
(`grep -rln "WorldObjectCandidate(" body-layer/src/` → `association.py` only, the shared factory).
`HybridPerceptionSource` (`hybrid_source.py`) has zero LOS references — confirmed by grep, not
assumed from the plan's own §11 audit — consistent with that module's own docstring claim that it
never sourced LOS, so there is no sibling channel this plan claimed parallel treatment for and
silently missed.

**Collector-side validation (`aircraft-layer/src/api/server.py:442-496`).** Both `hour` and
`fov_half_deg` explicitly exclude `bool` (`isinstance(hour, bool) or not isinstance(hour, int) or
not (MIN <= hour <= MAX)`) before the range check — correctly defeats Python's `bool`-is-`int`
subtyping, which the test suite's own `@pytest.mark.parametrize("hour", [-1, 12, 1.5, "3", True])`
exercises and which I confirmed would otherwise silently admit `True` as `hour=1`.

**Things that genuinely cannot be verified without DCS**, flagged plainly rather than waved through:
the heading/bearing `atan2` convention inside `LOS_CODE`, and `tonumber("nan")`/`tonumber("inf")`
behaviour on DCS's bundled Lua/CRT. Both are named explicitly in the Lua file's own header and in
`implementation.md`'s "Notable Discoveries," with the correct consequence stated (a wrong heading
convention produces a coverage gap — a wedge that silently doesn't track where Petrovich is looking
— not a wrong detection, per the plan's own safety property). I have no way to add to that beyond
what's already said; Stage 4's sortie is the only thing that closes it, as the acceptance card says.

### Mechanical checks (run from inside the snapshot, each subproject's own venv)

| subproject | ruff format | ruff check | mypy --strict | pytest |
|---|---|---|---|---|
| aircraft-layer | pass | pass | pass (21 files) | **252 passed** |
| body-layer | pass | pass | pass (53 files) | **1457 passed, 4 xfailed** |
| world-model | pass | pass | pass (72 files) | **550 passed, 3 skipped** |

All three match the implementer's claimed counts exactly.

**Staging/commit state.** `git show --stat 0200e07` shows every file (code, tests, plan correction,
implementer's own agent-memory at the repo-root path) committed; nothing outstanding. All five
commits on this branch (`9bc8b74` through `0200e07`) are scoped to this feature — no side-quest
commits.

### Verdict

**APPROVED**

The two Security required fixes are both correctly implemented and independently verified (not just
read) against hostile inputs. The 12 m tolerance boundary claim holds exactly as stated. No-omniscience
is intact — LOS remains a perception-side fact joined onto belief, never computed there. The
engagement-term rewrite and the deletions are complete and consistent with the plan's settled §11a
reasoning. No parallel-channel gap. Mechanical checks all pass and match the implementer's reported
numbers exactly. The two items above are genuinely optional — closing them is cheap and would be
worth doing opportunistically, but neither is load-bearing for Stage 4's acceptance sortie, which
remains the only thing that can confirm the live path (heading convention, `tonumber` behaviour,
felt frame cost) rather than this review.

### Review Confidence

Full read. Every file in the "What to check" list was read directly, not sampled; the clamp and the
naive-clamp failure mode were independently executed under a local Lua interpreter rather than taken
on the plan/review's word; all three subprojects' mechanical checks were run against the snapshot and
cross-checked against the implementer's claimed numbers exactly, not merely re-trusted.
