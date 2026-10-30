# DoD Check: 9k113-hands-off-switch (aircraft-layer)

Verdict scoped to tip **`02e32957c8a3ef04e501b2d7c55b88e085211204`** (branch
`feature/9k113-hands-off-switch`). DoD's own worktree HEAD (`8eced885`, strict ancestor, clean
tree) was fast-forwarded to this tip before any check ran; if the branch moves past this sha, this
verdict is stale and must be re-run.

## Scope (derived from the diff, not from memory)

```
git diff --name-only 8eced8857ebc48578859ae50e3dce92a1c32c69e HEAD
```

```
.claude/agent-memory/implementer/feedback_extract_lua_function_comment_false_positive.md
.claude/agent-memory/implementer/reference_lua51_60_upvalue_ceiling.md
.claude/agent-memory/reviewer/feedback_generic_write_channel_bypasses_narrow_guard.md
aircraft-layer/dcs-export/Export.lua
aircraft-layer/src/schema/sight_servo.py
aircraft-layer/tests/test_sight_servo_lua.py
plans/9k113-hands-off-switch/implementation.md
plans/9k113-hands-off-switch/review.md
```

**One subproject touched: `aircraft-layer/`.** `body-layer/` is untouched — confirmed by the diff
above, not taken on the task description's word. No `plan.md` exists for this feature by design
(small, directly-dispatched change, confirmed by `plan-summary`'s underlying check — only
`implementation.md`/`review.md` exist in `plans/9k113-hands-off-switch/`).

## Quality Gates (aircraft-layer, run from inside `aircraft-layer/`, tools from `body-layer/.venv/bin/` per `.claude/agent-memory/implementer/feedback_worktree_no_venv.md` — no venv of its own in this worktree)

| Check | Status | Notes |
|-------|--------|-------|
| Format (`ruff format --check src tests`) | ✓ PASS | 75 files already formatted |
| Lint (`ruff check src tests`) | ✓ PASS | All checks passed! |
| Types (`mypy --strict` via `cd aircraft-layer && python -m mypy src`) | ✓ PASS | Success: no issues found in 26 source files |
| Lua syntax (`luac5.1 -p dcs-export/Export.lua`) | ✓ PASS | — |
| Tests (`python -m pytest tests -q`) | ✓ PASS (with known pre-existing exception) | 649 passed, 2 failed, 181.30s |

**The 2 test failures, independently confirmed as pre-existing and unrelated to this diff:**
`test_collector_server_accept_errors.py::test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers`
and `::test_close_during_a_blocked_accept_ends_the_loop_cleanly`, both `OSError: [Errno 98] Address
already in use` — a port-binding collision on this machine. Verified against `main` in an isolated
scratch tree (`git archive main | tar -x -C <scratch>`, same venv-borrowed tools, run from inside
that tree's own `aircraft-layer/`):

```
FAILED tests/test_collector_server_accept_errors.py::test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers
FAILED tests/test_collector_server_accept_errors.py::test_close_during_a_blocked_accept_ends_the_loop_cleanly
2 failed in 0.06s
```

Same two tests, same error, on `main` — not introduced by this change. `collector/server.py` is
outside this diff entirely (confirmed by the file list above).

## Code Violation Scans (touched files only)

| Check | Status | Findings |
|-------|--------|---------|
| No debug output (`print(`/`pdb.set_trace`/`breakpoint()`) | ✓ PASS | 0 occurrences |
| No TODO/FIXME/HACK/XXX markers | ✓ PASS | 0 occurrences |
| No bare `except:` / error suppression | ✓ PASS | 0 occurrences |

## File Size

`aircraft-layer/src/schema/sight_servo.py` 164 lines, `aircraft-layer/tests/test_sight_servo_lua.py`
1379 lines (test file, not production `src/`), `aircraft-layer/dcs-export/Export.lua` 2460 lines
(canonical whole-file Export script, not a Python `src/` module the 400-line limit targets — a
single Export.lua has always been this project's structure for this file). No new oversized
Python `src/` file introduced.

## Staging / Agent-Memory Path

`git status --porcelain` clean at merge time; the only post-merge change was this DoD pass's own
edits (`review.md` Disposition section, `dod-check.md`, the `BL-B80.md` roadmap note, two `notes/`
files, the acceptance-card source doc), all staged below. Both agent-memory files from this
feature's own commits already sit at repo-root `.claude/agent-memory/<role>/` (not a
subproject-relative path).

## Security Sign-off

**No `security-plan-review.md`/`security-review.md` exists for this feature, and that is correct,
not a gap.** User direction, 2026-10-30, verbatim: *"is this a small change? If so, skip perf and
sec"* — recorded, not re-litigated, per root `CLAUDE.md`'s "Agents" section allowing the
once-per-batch cadence to be overridden by explicit user direction for a genuinely small change.
This change is one load-time flag, one early-return gate at the single existing write site, and a
thin wrapper function — no new dependency, no new network surface, no new write vocabulary (the
existing `cockpit_switch` channel's scope is unchanged by this feature; see Scope & Correctness
below for the one place that surface was discussed). Scope matches "small."

## Scope & Correctness

- **Implementation matches the stated intent** (`docs/acceptance/2026-10-30-sortie-feedback.md`,
  "Explored with the user" — *"I can point the 9K113 by hand - Petrovich must not write axis
  values then"*). Verified independently by the Reviewer, not just the implementation record: the
  one `SetCommand(CMD_AI_AZ/CMD_AI_ELEV)` call site is gated, `run_sight_servo`'s goal/mark/stall
  tracking is skipped entirely (not just its writes) via the new `sight_servo_tick` wrapper, and
  `push_slew_trace` (the diagnostic trace the calibration flight depends on) is independently
  confirmed to keep logging unconditionally.
- **No unplanned scope added silently** — the implementer's own "Notable Discoveries" section
  flags every judgment call made beyond the literal ask (the load-time confirmation log line, the
  decision not to invent new doc sections) rather than making them silently.
- **One Reviewer-required fix, declined by the user, not fixed**: closing the generic
  `cockpit_switch` write channel (`handle_cockpit_switch_command`) against the same AI-axis
  commands while hands-off is active. Confirmed still absent from `Export.lua` (lines 1128-1149,
  `handle_cockpit_switch_command`, no `SIGHT_HANDS_OFF` check) — matching the Reviewer's finding
  exactly. **Disposition recorded in `plans/9k113-hands-off-switch/review.md`** (appended this
  pass): user direction 2026-10-30, *"just let it be, this is testing aid"*, with the Reviewer's
  own grep-verified context (no device-7 clickable element bound to commands 3060/3061/3025/3026 in
  `body-layer/config/sequences/mi-24p/switch-reference.md` or `config/effectors-raw/mi-24p.toml`)
  carried forward as the basis for accepting the residual risk on a short-lived testing aid rather
  than a permanent safety boundary. This is accepted debt with no further Implementer/Reviewer loop
  owed, not an open NEEDS REVISION item.
- **No project invariants violated.** This is aircraft-layer-only; no DCS-authoritative-vs-GIS
  concern, no provenance/timestamp field added, no new write vocabulary beyond the existing
  `cockpit_switch`/`SetCommand` surfaces. The "behaviour-affecting constants are tunable" rule is
  scoped to body-layer's `tuning.py` mechanism and does not apply to this Lua-side load-time flag,
  which follows the file's own existing `SLEW_DEBUG` flag-file pattern.
- **All new/modified files staged** — confirmed via `git status --porcelain` (see above).

## Testing

Core logic covered by 5 new tests (`TestSightPointQuietHandsOffGuard` ×2,
`TestRunSightServoHandsOff` ×4 minus one duplicate counted in implementation.md's list — see that
file for the exact names), plus **counterfactual mutation testing actually run** (not just
asserted): removing `sight_point_quiet`'s own guard turned the write-blocking test red for the
stated reason; reducing `sight_servo_tick` to an unconditional `run_sight_servo(t)` call turned all
three "blocks" tests in `TestRunSightServoHandsOff` red; both reverted and checksum-verified
byte-identical. The Reviewer independently reproduced the upvalue-ceiling claim by the same
mutate/verify/revert method rather than trusting the implementation record. No existing tests
broken — full suite 649 passed (the 2 pre-existing failures addressed above).

## Documentation

- Reviewer's one required fix addressed via the Disposition section above — not an open item.
- Non-obvious behaviour explained via code comments (`Export.lua`'s own comments on the upvalue
  ceiling and the gating-site choice) and two `notes/` entries added this pass (see below).

## Notes Harvest

Two genuinely non-obvious, non-duplicate insights appended this pass (checked against
`notes/notes-index.md` and the relevant topic files' existing content first):

- `notes/the-9k113-sight-bl-b64.md` — the Lua 5.1 60-upvalue-per-closure ceiling on
  `run_sight_servo` (a hard constraint on all future edits to that function), and the
  scale-vs-boresight observational ambiguity that motivated this feature.
- `notes/fixture-management-and-test-infrastructure.md` — a second, independent latent bug in the
  shared `_extract_lua_function` test helper (bare-word comment matching, distinct from the
  already-documented loop-truncation bug in the same helper).

The two agent-memory files from this feature's own implementer/reviewer commits
(`feedback_extract_lua_function_comment_false_positive.md`,
`reference_lua51_60_upvalue_ceiling.md`, `feedback_generic_write_channel_bypasses_narrow_guard.md`)
are role-specific checklist/reference material and were left in agent-memory rather than
duplicated into `notes/`.

**Recurring-fix check (this role's own memory, `.claude/agent-memory/dod/`):** searched for a prior
"narrow guard vs. generic write channel" pattern — no match (`memory-search.py`, see transcript).
This is the first occurrence of this specific shape (a new narrow gate leaving a pre-existing,
deliberately-unrestricted write channel unexamined) surfacing at Reviewer; not (yet) a recurring
pattern warranting a DoD-level memory entry or an earlier-stage check. The Reviewer's own memory
file already captures the general checklist habit for next time.

## Milestone Completion

Answered in `body-layer/ROADMAP/BL-B80.md`'s new dated entry: this does not change what BL-B80's
next step should be (it is purely an enabler for the calibration flight already called for by the
2026-10-28 entry), but it does mean that flight's result is now the authoritative correction to
`MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL`, since it removes the one confound (Petrovich's own
servo write) that made every earlier single-point observation ambiguous.

## Acceptance Boundary

**What this feature's fixtures structurally cannot reach:** no automated test here drives a real
9K113 gimbal, a real ASP-17 mark, or DCS's own `SetCommand`/`performClickableAction` behaviour —
every test calls the extracted Lua function or the Python schema directly. The fixtures prove the
gate exists and blocks the write at the Lua-source level; they cannot prove the flag file is read
correctly by a real DCS process at mission load, that hand-slewing via the player axis is
unaffected, or that the two depression-angle readings the calibration flight depends on are
actually separable in practice. That is exactly what the live flight below is for.

## Acceptance Testing Plan: 9K113 Hands-Off Switch

**Goal:** confirm the hands-off flag actually suppresses Petrovich's servo write in a real DCS
session, and gather the two depression-angle readings the elevation-calibration correction needs.

**This is live acceptance — PENDING, not blocking.** Per root `CLAUDE.md`'s 2026-10-26 standing
direction, a live test the user has not flown yet does not gate the merge. Card published:
**https://claude.ai/artifact/X1waKvSQkUvDHciBc1AkN8** (source
`docs/acceptance/2026-10-30-9k113-hands-off-calibration.md`), branch to fly is `main`. Tagged
`#needs-flight` on `body-layer/ROADMAP/BL-B80.md`.

**Prerequisites**
- [x] Type-checked (`mypy --strict aircraft-layer/src`, confirmed above)
- [ ] `Saved Games\DCS\Scripts\aircraft_layer_sight_hands_off.flag` created before mission launch
- [ ] `aircraft_layer_slew_debug.flag` and `aircraft_layer_debug.flag` created for logging
- [ ] `body.py` launched with `--slew-trace <path>`

**Test Cases** (full detail in the card)
1. Mission start with the flag present — expect the `9K113 hands-off switch is ACTIVE` log line.
2. Hover and hand-slew the 9K113 onto a near target at a known depression angle — expect a steady
   hold, no fight from an invisible AI-axis write.
3. Hover and hand-slew onto a far target at a clearly different depression angle — same
   expectation.

**Edge Cases to Probe**
- Flag file missing/misnamed — the confirmation log line's absence is the tell; the card calls
  this out as the thing to check before trusting anything else.
- OBSERV toggled off/on mid-hold — not exercised by this card; outside this feature's scope
  (unrelated to the hands-off flag, which is load-time only).

**Pass Criteria** — the confirmation line appears, both holds are steady with no servo fight, and
the two (target, angle, time) readings come back clean enough to derive a corrected
`MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL`.

---

## Verdict: **PASS**

All mechanical checks pass (with the one pre-existing, independently-confirmed, out-of-scope test
failure). The one Reviewer required fix is accepted-by-user debt, recorded in `review.md`'s
Disposition section — not an open item. Performance/Security passes correctly skipped by explicit
user direction for a small change. Acceptance testing is **PENDING (live)** — card published,
`#needs-flight` tagged on `BL-B80`'s entry file, and per standing direction this does not block the
merge.
