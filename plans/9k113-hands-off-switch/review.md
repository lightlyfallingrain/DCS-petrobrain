### Review Summary

Reviewed `feature/9k113-hands-off-switch` (tip `f86861e6`, one commit on `main`@`8eced885`,
fast-forwarded into this worktree cleanly — `HEAD` was a strict ancestor of the named tip and the
tree was clean before merging). No Architect plan exists for this change by design; the decision
record is `plans/9k113-hands-off-switch/implementation.md`, cross-checked against
`docs/acceptance/2026-10-30-sortie-feedback.md` (read via `git show` on
`docs/2026-10-30-sortie-feedback`) for intent.

**What the change does.** A load-time flag (`aircraft_layer_sight_hands_off.flag`) sets
`SIGHT_HANDS_OFF`, gated once at `Export.lua` load (no mid-sortie toggle). The one call site that
issues `SetCommand(CMD_AI_AZ/CMD_AI_ELEV)` on the 9K113 (`sight_point_quiet`) returns immediately
when the flag is set. `run_sight_servo` itself is deliberately left ungated (it is already at Lua
5.1's 60-upvalue-per-closure ceiling — reproduced independently below) and is instead skipped
entirely by a new thin wrapper, `sight_servo_tick`, called from `LuaExportAfterNextFrame` in its
place; this also stops the goal/mark/stall tracking from running meaninglessly while hands-off,
and reports `sight_mode = "hands_off"`. `push_slew_trace` (the per-frame SLEW_DEBUG trace) is
untouched and independently verified still unconditional.

**Independently verified, not just read:**
- Fast-forward preconditions (`git rev-parse HEAD`, `git merge-base --is-ancestor`), then the merge
  itself.
- **The 60-upvalue ceiling claim, by mutation**: added `if SIGHT_HANDS_OFF then return end` at the
  top of `run_sight_servo` myself, ran `luac5.1 -p` — reproduced the exact reported failure
  (`function at line 1583 has more than 60 upvalues`) — then reverted and confirmed `luac5.1 -p`
  passes and the working tree is byte-identical (`git status --porcelain` empty). This is the
  reason `run_sight_servo` could not simply gain a fourth `if` at its own top, and it is real, not
  an unverified claim carried over from the implementation record.
- **Every module-level `sight_*` state variable `push_sight_servo_state` sends** (`sight_setpoint_
  body_*`, `sight_mark_body_*`, `sight_error_*`, `sight_field_target_body_*`, `sight_mark_clipped`,
  `sight_stalled`, `sight_stall_count`) is assigned only inside `run_sight_servo` or
  `LuaExportStop` (grepped every assignment site). Since `sight_servo_tick` skips calling
  `run_sight_servo` entirely while hands-off, and the flag never toggles mid-session, these stay at
  their declared `nil`/`false`/`0` initial values for the whole session — `fmt_num_or_null` renders
  `nil` as JSON `null`. So the feed body-layer reads is `servo_mode: "hands_off"` with every other
  field `null`/`false`/`0`, never a stale frozen snapshot from before the flag took effect. No
  staleness bug.
- **Body-layer parses `servo_mode` nowhere as an enum.** `sight_trace_writer.py`'s `_SERVO_KEYS`
  copies `mode` through verbatim as a `servo_<key>` trace column; `aircraft_client.get_sight_servo`
  only checks the JSON shape (object or null), never the string's value; `schema/sight_servo.py`'s
  `mode` field is a bare `str`, no `Literal`/enum. `"hands_off"` passes through exactly like any
  other mode string. Confirmed by reading all three files, not just the implementation record's
  claim.
- **`push_slew_trace` is independently called** at `Export.lua:2265`, before `sight_servo_tick` at
  `:2275`, inside the same unconditional block of `LuaExportAfterNextFrame` — reads only
  `GetDevice(0)` args and `SLEW_DEBUG`, no `sight_mode`/`SIGHT_HANDS_OFF` dependency. Confirmed it
  keeps logging raw 555/566 + gimbal args every frame regardless of the hands-off flag, as the
  sortie feedback required.
- **`debug_log`** is declared at line 295, well above its first use inside the new flag block at
  line ~377 — satisfies this file's own hoisting rule.
- Full command suite from `aircraft-layer/` (no venv in this worktree; ran via the main checkout's
  `body-layer/.venv` binaries per `.claude/agent-memory/implementer/feedback_worktree_no_venv.md`,
  `cwd` inside this worktree): `ruff format --check` (75 files already formatted), `ruff check`
  (all checks passed), `python -m mypy src` (strict, 26 files, no issues), `luac5.1 -p
  dcs-export/Export.lua` (pass), `python -m pytest tests -q` → **649 passed, 2 failed** — the 2
  failures are `test_collector_server_accept_errors.py`'s two tests, both `OSError: Address already
  in use`, a pre-existing environment port-binding collision this change does not touch
  (`collector/server.py` is untouched by this diff) and which the implementation record documents
  as pre-existing against a pre-change baseline. Consistent with that record.

### Required Fixes

- **The "no 9K113 AI-axis write of any kind" guarantee is not actually closed against the generic
  `cockpit_switch` channel.** `handle_cockpit_switch_command` (`Export.lua:1128`) writes *any*
  `GetDevice(device):performClickableAction(cmd, value)` with no allow-list — a deliberate,
  separately-decided departure from the per-switch safety net (user direction 2026-10-21,
  `BL-B66`). It is **not** gated by `SIGHT_HANDS_OFF` at all, and nothing about this change touches
  it. The implementation record's own verification ("confirmed by grep that this is the only place
  in the file that calls `SetCommand` on `CMD_AI_AZ`/`CMD_AI_ELEV`") is true but narrower than the
  stated goal — it rules out `SetCommand`, not `performClickableAction` on the same device/cmd pair
  through the other channel.
  - **What I found checking it**: grepping `body-layer/config/sequences/mi-24p/switch-reference.md`
    and the raw dump `body-layer/config/effectors-raw/mi-24p.toml` for every device-7 element shows
    no clickable element bound to commands 3060/3061 anywhere (device 7's elements are cmds
    3001–3029/3062–3064 only) — consistent with this project's own prior research
    (`aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`: the sibling player slew
    axis "has no clickable element... a raw `SetCommand` continuous axis," the kind of control that
    process would never surface). So in practice, today, no curated effector sequence can reach
    this, and `performClickableAction` for an unregistered command most likely no-ops rather than
    reaching the same device-internal write `SetCommand` does.
  - **That inference is not verified against DCS itself**, and the feature's entire value rests on
    this one guarantee holding during a live calibration flight whose corruption would be silent
    and undetectable after the fact (the whole point of flying hands-off is to trust that nothing
    else is writing the axis while the pilot reads off a known angle). Given the fix is three
    lines, close it defensively rather than resting on an unverified DCS-internals inference:
    reject `device == DEV_I9K113` (or specifically `cmd == CMD_AI_AZ or cmd == CMD_AI_ELEV`) inside
    `handle_cockpit_switch_command` while `SIGHT_HANDS_OFF` is set, mirroring the same guard
    `sight_point_quiet` already has. This does not reopen the `BL-B66` "allow any switch" decision
    — it only narrows what the already-separate hands-off mode permits, the same way `SIGHT_HANDS_OFF`
    already narrows `sight_point_quiet` without touching any other device.

### Optional Refinements

- `.claude/agent-memory/implementer/feedback_extract_lua_function_comment_false_positive.md`'s
  frontmatter uses a flat `type: feedback` key rather than the documented `metadata:\n  type:
  feedback` nesting (its sibling `reference_lua51_60_upvalue_ceiling.md` in the same commit uses
  the nested form correctly). Harmless to this feature, but worth fixing for
  `memory-search.py`/indexing consistency the next time either file is touched.
- Consider citing `aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md` directly
  in `handle_cockpit_switch_command`'s comment once the Required Fix above lands, so the "why" for
  a device-7 exception inside an otherwise-unrestricted channel is traceable without re-deriving it.

### Verdict

NEEDS REVISION

One required fix: close the generic `cockpit_switch` channel against the 9K113 AI axis while
`SIGHT_HANDS_OFF` is active (see above). Everything else checked — the gated write site, the
upvalue-ceiling workaround, the `_extract_lua_function` fix, test coverage (including the
counterfactual mutations the implementation record describes, which match what I'd expect this
guard to need), the slew-trace independence, and the full `aircraft-layer` check suite — is sound
and matches the user's stated intent. This is a small, cheap fix; expect a short loop back through
Implementer → Reviewer rather than a rework.

### Review Confidence

Full read. All checklist items were independently verified against the live file (not just the
implementation record's claims), including two mutation tests (the upvalue ceiling, confirmed and
reverted cleanly; the module-level state staleness question, confirmed by grepping every assignment
site) and the full `aircraft-layer` check suite re-run from this worktree.
