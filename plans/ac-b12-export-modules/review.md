### Review Summary

Reviewed AC-B12 (split `Export.lua` into `dofile`-loaded modules under `dcs-export/Petrobrain/`)
with AC-B13 folded in (release an open AI-pilot-wheel press and clear takeover state on
`LuaExportStop`), against `plans/ac-b12-export-modules/plan.md` and `implementation.md`, on
`feature/ac-b12-export-modules` at `6d064b52` (fast-forwarded from this worktree's prior
`c7a5c8f0`, a strict ancestor; tree was clean).

**Behaviour preservation, the plan's central requirement, holds.** I traced the full original
`LuaExportStart`/`Stop`/`ActivityNextEvent`/`AfterNextFrame` bodies at `fab32110` line-by-line
against the new loader's composed callbacks and found:
- Every state reset in the original `LuaExportStart`/`Stop` lands in exactly the module the plan's
  state-relocation map names (`core`, `commands`, `petrovich`, `sight`, `ptt_ics`, `effectors`,
  `telemetry`), with no field dropped. AC-B13's new resets (`ai_wheel_pending_cmd`/
  `ai_wheel_pending_release_t`/every `ai_pilot_takeover` field except the `AI_PILOT_MENU_OPEN_
  DELAY_S` constant) are complete.
- The per-frame/5 Hz-gated call order in the new `LuaExportAfterNextFrame` is byte-for-byte the
  same sequence as the original (`commands.poll_command_socket` → `ptt_ics.push_ptt_state` →
  `push_spu8_state` → `sight.push_slew_trace` → `sight_servo_tick` →
  `petrovich.release_pending_search` → `ai_pilot_wheel.run_ai_pilot_wheel` → 5 Hz gate →
  `helperai_raw` read → `push_sight_servo_state` → `update_ai_pilot_wheel_overlay` →
  `push_ai_pilot_wheel_state` → `ensure_connected`/`force_resend` → `telemetry.send_ownship` (the
  gate) → `ptt_ics.on_mission_start_tick` → `effectors.push_watched_args_state` →
  `telemetry.push_payload_state` → `telemetry.send_world_objects` → `petrovich.push_indication` →
  `petrovich.push_wheel_state`) — correctly **not** the plan's own illustrative snippet, which the
  Implementer correctly identified as grouping ownship+world-objects together in a way that would
  have changed failure semantics. The implementation's own deviation from the illustrative snippet
  is right, and is called out in both the implementation log and a new architect-memory file.
- `handle_sight_target_command`'s field extraction/bounds-check logic, diffed verbatim against the
  original, is unchanged apart from the field extraction moving inside the function body (the
  `(data, t)` normalization the plan calls for). Spot-checked as the representative case for the
  other two normalized handlers (`handle_petrovich_search_command`, `handle_cockpit_switch_
  command`), which read the same way.
- `list_indication(6)` (HelperAI) is read exactly once per 5 Hz tick, in the loader, and passed as
  `helperai_raw` to both consumers — not re-read per module.
- `DUMPED_SELF_DATA`/`DUMPED_WORLD_OBJECTS`/`DUMPED_PETROVICH_INDICATION`/`DUMPED_PETROVICH_WHEEL`
  stay bare globals (no `local` declaration) in their new homes, as the plan required.
- AC-B13's own test (`test_ai_pilot_wheel_lua.py::TestOnStop`) extracts the real `on_stop`, and both
  cases (open press / no open press) assert every `ai_pilot_takeover` field clears, including
  `correction_hold_cmd`. Real, not decorative.

**Mechanical checks, all run in this worktree (no `.venv` existed; created one and installed
ruff/mypy/pytest fresh):**

```
luac5.1 -p  — Export.lua + all 8 Petrobrain/*.lua files: all pass
ruff format --check src tests   — 79 files already formatted
ruff check src tests            — All checks passed!
cd aircraft-layer && .venv/bin/mypy src   — Success: no issues found in 27 source files
pytest tests -q                 — 792 passed in 80.31s
pytest tests -v | grep -E " (SKIPPED|FAILED|ERROR)\b"   — no matches (confirms the 139
  Lua-interpreter-backed tests in the 7 affected files actually ran, not skipped)
```

Per-module `grep -cE '^local '` headroom, independently reproduced: core 29, telemetry 10,
petrovich 14, sight 84, ai_pilot_wheel 37, effectors 20, ptt_ics 24, commands 10, loader 14 — matches
`implementation.md` exactly, confirms the 200-local ceiling has wide headroom everywhere.

### Required Fixes

- **`commands.lua`'s dispatch table couples the fate of every inbound command op to every
  handler-owning module's load success, which contradicts the plan's own stated design goal**
  ("A module missing or erroring at load is caught by pcall and logged... the loader skips calling
  into it — one feature module failing does not take down telemetry or any other module",
  plan.md "Load mechanism"). `commands.lua`'s top-level `local handlers = {...}` table indexes
  `petrovich`/`effectors`/`sight` directly (`aircraft-layer/dcs-export/Petrobrain/commands.lua:62-68`).
  If any **one** of those three modules fails to load (a corrupted/missing file, a future syntax
  error introduced in one of them), indexing a `nil` global inside that table constructor raises a
  Lua error at `commands.lua`'s own top level, which `load_module`'s `pcall` catches — so
  `commands` itself fails to load, taking down **all five** command ops (`petrovich_search`,
  `cockpit_switch`, `sight_target`, `watch_args`, `read_args`), including the two
  (`cockpit_switch`/`watch_args`/`read_args`) owned by modules that loaded perfectly fine. Before
  the split, a corrupt file took down everything (a `luac`-level syntax error fails the single
  chunk); after the split, the loader's own `call_if` guards correctly isolate `telemetry`/`sight`/
  `ptt_ics`/`ai_pilot_wheel`'s own per-tick pushes from each other, but `commands.lua`'s handler
  table does not get the same isolation — so this is a narrower regression against the plan's own
  stated target than against the pre-split baseline, but it is still a real gap against what the
  plan says the design does, worth closing cheaply: guard each table entry (or each dispatch
  lookup) on the owning module being non-`nil`, the same `call_if`-style guard the loader already
  uses everywhere else. This also needs a guard at `commands.lua:93`'s `effectors.admit_read(...)`
  call, which has the identical hazard.

### Optional Refinements

- **`EXPORT_SCRIPT_VERSION` was not bumped, and this file's own established convention (the
  2026-10-22 "exponent-float fix" bump, documented in this same version-history comment block) is
  to bump even for a pure behaviour fix with no wire-format change, "so a collector talking to a
  pre-fix Export.lua is visibly flagged."** AC-B13 is exactly that shape of change. I don't treat
  this as a required fix: U1's answer and the plan's Deployment section both explicitly reasoned
  through this and decided not to bump ("nothing here for a collector to misread"), the risk is
  already named in the plan's own Risks section ("a missing feature module does not change
  `EXPORT_SCRIPT_VERSION`'s match/mismatch outcome"), and the version string was already at
  "2026-11-16" (same-day, from the BL-16 takeover revision) before this change — so even a bump
  would only have added a `b` suffix, a small gain. Worth a one-line mention to the user: a bump
  would let the collector's own "version match" live-check step (Verification step 1) actually
  distinguish "the split landed" from "it didn't," which it currently cannot (both report the
  identical string). Not required given the plan's explicit, examined decision.
- **`sight.lua` sits at 84 top-level locals against the plan's own ~60 soft target** (every other
  module is comfortably under: 10–37). Not a correctness risk — 116 locals of headroom remain
  against the hard 200 ceiling, and the separate 60-upvalue-per-closure limit (`run_sight_servo`,
  already at that ceiling per-function) is unaffected by file-level splitting either way. The
  Implementer correctly declined to re-split the 9K113 subsystem unilaterally (that would be a
  module-cut change outside an Implementer's authority) and flagged it transparently. No action
  needed now; worth a mental note if BL-16 Stage P2 or another sight-adjacent feature ever needs to
  add meaningfully more sight-module state.
- **Implementation-log accuracy, not code**: "Notable Discoveries" states 4 "must stay below
  `safe_call`/`fmt_num_or_null`" comments were pruned in `sight.lua`, with "the rest of each
  comment... kept." I traced all 4 occurrences against the original file: one is in
  `push_payload_state`, which moved to `telemetry.lua`, not `sight.lua`; and in the two `sight.lua`
  occurrences I checked (`push_slew_trace`, around the original's line ~1559), the **entire**
  ordering note was removed, not just the `safe_call`/`fmt_num_or_null` mentions — including the
  part naming the still-same-file locals (`SLEW_DEBUG`, `ASP17_FIELD_*`, `MARK_*`,
  `sight_mark_is_clipped`) that `push_slew_trace` must still stay below. I verified the actual
  ordering in the file is still correct (every one of those locals is declared above line 490,
  where `push_slew_trace` now sits), and `test_dcs_export_lua_local_order.py` mechanically re-proves
  this for every file on every run, so no correctness is at risk — this is a documentation-accuracy
  note about the log, not a code defect. No fix required; flagging so the log's claim isn't taken
  at face value by a later reader.
- Per this project's own comment-pruning rule: the specific dated incident this removed comment
  referenced (`push_ptt_state`/`push_slew_trace` called `nil` because they sat above their
  declarations, 2026-09-23/2026-10-21) remains documented in `aircraft-layer/CLAUDE.md` (unchanged
  by this diff), so nothing durable was actually lost — confirmed by reading that file's "no
  hoisting" section.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read of the loader, `core.lua`, `telemetry.lua`, `petrovich.lua`, `ptt_ics.lua`,
`effectors.lua`, `commands.lua`, and the `on_stop`/reset-relevant portions of `sight.lua` and
`ai_pilot_wheel.lua`, each diffed against the original file at `fab32110` line-by-line for the
state-relocation map and call order. `sight.lua`'s and `ai_pilot_wheel.lua`'s large non-reset
bodies (the 9K113 pointing/servo math and the takeover decision logic) were spot-checked rather
than diffed in full — the plan calls for pure relocation with no logic change there, the local-order
test and the full Lua-backed test suite (139 tests across the 7 affected files, confirmed running
rather than skipped) are the mechanical proof for exactly that claim, and the one normalized handler
I diffed in full (`handle_sight_target_command`) showed zero logic drift. Did not perform the live
check flight (Stage 8) — that is the user's own acceptance step per the plan, not the Reviewer's.
