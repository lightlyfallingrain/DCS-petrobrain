## Security Deep Analysis: 9k113-sight-pointing (BL-B80, Stages 1-3)

Batch scope: Stages 1-3 (body-layer elevation calibration/gyro-alignment, the Export.lua per-frame
sight owner and `sight_target` wire op, the body-layer write-through), per the plan's own "Batching"
coordinator amendment. Stage 4 is the live sortie, not implemented.

### Dependency Status

No dependency change. Confirmed: no `pyproject.toml`/lockfile diff in `edc8dd73..157b78b1`; every
new symbol (`CommandSender.send_sight_target`, the `sight_target` Export.lua op,
`AircraftLayerClient.write_sight_target`, `sight_effector`'s new conversion functions) is stdlib
Python / hand-rolled Lua, matching the security-plan-review's finding.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py:701-772` (`_handle_command_sight_target`) | New write endpoint, finite-float + bound check | Implements the plan review's own non-blocking recommendation: both `az_cmd`/`elev_cmd` rejected unless finite and `abs(x) <= _SIGHT_TARGET_CMD_BOUND = 1.5` (±90deg-equivalent). Bool explicitly excluded (`isinstance(x, bool)` checked before the numeric check, matching `cockpit_switch`'s convention). `test_sight_target.py` exercises valid/at-bound/beyond-bound/missing/bool/NaN/non-JSON/503/500 — all pass. | None. |
| `aircraft-layer/src/api/server.py:716` | `Content-Length` read, no upper bound | Reproduces the pre-existing shape every POST handler on this server has (`int(Content-Length) -> rfile.read(length)`, no cap). Already filed and tracked as `AC-B11` (low/low, not blocking). This is the sixth handler sharing the shape, as the plan review anticipated. | None — already tracked under `AC-B11`. One housekeeping note: `AC-B11.md`'s text still reads "five... eventually six, once BL-B67 lands" — `sight_target` is in fact the sixth, landing before `BL-B67`. Cosmetic; see Housekeeping below. |
| `aircraft-layer/src/collector/command_sender.py:153-187` (`send_sight_target`) | UDP send, no validation at this layer | Matches `send_cockpit_switch`'s documented division of labour (validation happens at the API layer, this method is a pure transport). Loopback-only (`127.0.0.1:7790`, confirmed unchanged `HOST`/`COMMAND_HOST`). | None. |
| `aircraft-layer/dcs-export/Export.lua:959-964` (`extract_json_number_field`) | Regex-based field extraction (`"field"%s*:%s*(-?%d+%.?%d*)`) | Cannot match `NaN`/`Infinity`/non-numeric text — the pattern is digits-only, so a malformed or hostile datagram on this field yields `nil`, not a crash or a non-finite value. Unchanged by this plan; the new `az_cmd`/`elev_cmd` fields reuse it identically to `device`/`cmd`/`value`. | None. |
| `aircraft-layer/dcs-export/Export.lua:1096-1105` (`handle_sight_target_command`) | New inbound op handler | Only checks `az_cmd == nil or elev_cmd == nil` (missing-field), not NaN/Inf explicitly — unlike `handle_cockpit_switch_command`'s belt-and-suspenders `value ~= value`/`math.huge` check. **Not exploitable**: `extract_json_number_field`'s regex cannot produce NaN/Inf/non-numeric in the first place (see row above), so the extra check in `cockpit_switch`'s handler is defensive redundancy, not a closed gap this handler lacks. No bound/clamp on the Lua side either (unlike the API layer's `_SIGHT_TARGET_CMD_BOUND`) — mitigated structurally exactly as the plan review accepted: `run_sight_pointing`'s rate limiter only ever *approaches* `target_az_cmd`/`target_elev_cmd` at a fixed raw/s rate, never jumps, and this socket is loopback-only (not reachable from the stated LAN-attacker threat model at all, only from a process on this same machine). | None — matches the accepted precedent; noting for completeness, not filing (loopback-only + unreachable-input combination makes this non-exploitable, not merely low-risk). |
| `aircraft-layer/dcs-export/Export.lua:1061-1073` (`sight_point_quiet`) | Fixed `SetCommand` targets | `DEV_I9K113`/`CMD_AI_AZ`/`CMD_AI_ELEV` are compile-time constants (device 7, cmd 3060/3061); the caller only ever supplies the two numeric values, never the device/cmd pair. This is the fixed-device/cmd shape the plan review's own memory note (`project_bl_b80_sight_target_op_narrower_than_cockpit_switch`) checked against the cockpit-write-vocabulary invariant — confirmed as implemented: no new free-form surface. | None. |
| `aircraft-layer/dcs-export/Export.lua:1087-1240` (`run_sight_pointing`, the AI-on/off detector + ShowMenu press) | Internally-triggered `performClickableAction(WHEEL_MENU_BUTTON, ...)` | A LAN caller cannot force a `ShowMenu` press through `sight_target` directly — the press only fires from Export.lua's own per-frame comparison of the readback (`ARG_SIGHT_AZ`/`ARG_SIGHT_ELEV`) against the commanded value, gated by `GYRO_ALIGNMENT_S`, `AI_OFF_DETECT_TIMEOUT_S`, and `AI_OFF_REPRESS_INTERVAL_S` (0.5s / 2.5s placeholders). An attacker repeatedly sending `sight_target` values that never match the readback could cause repeated presses no faster than once per `AI_OFF_REPRESS_INTERVAL_S` (2.5s) — this is a cockpit-visible nuisance, not a new exposure class: `cockpit_switch` already lets any LAN caller press `ShowMenu` directly and immediately, with no rate limit at all. `sight_target` is strictly less capable here. The self-correction property (never latches, `ai_off_since` reset only on an actual press per the Reviewer-required fix) bounds press frequency; confirmed present in the diff (fix 1 in `implementation.md`). | None — subsumed by the already-accepted `cockpit_switch` exposure, per the plan review's own reasoning. |
| `aircraft-layer/dcs-export/Export.lua:1299-1314` (`LuaExportStop` reset) | New sight-pointing state cleared on mission stop | `target_az_cmd`/`target_elev_cmd`/`commanded_*`/`observ_on_since`/`ai_off_since`/`last_showmenu_press_t`/`ai_believed_on`/`sight_last_frame_t` all reset to `nil`/`false`. Prevents stale cross-mission state carrying a target or detector timer into a new mission — same reasoning as `pending_release_t`'s existing reset. | None. |
| `aircraft-layer/dcs-export/Export.lua:1076` (`sight_point_quiet`'s `GetDevice(DEV_I9K113)`) | `safe_call` wrapping | Reviewer's required fix 4 applied — matches every other `GetDevice` call site's convention in this file (a missing/invalid device handle degrades to a no-op rather than an unhandled error aborting the per-frame export hook). | None. |
| `body-layer/src/aircraft_client.py:275-284` (`write_sight_target`) | Pure pass-through, no validation | Matches `write_cockpit_switch`'s documented posture — raises `AircraftLayerError` on failure, validates nothing (the one caller, `belief.sight_effector.write_sight_target`, computes the values from Petrovich's own belief state, not from untrusted external input). | None. |
| No LLM/prompt-injection surface | — | This batch touches no text the brain layer or any model reads (pure control-loop/effector addition). Confirmed unchanged from the plan review's own finding. | None. |
| No secrets/credentials | — | None introduced. | None. |

### Housekeeping (not a security gate)

`aircraft-layer/ROADMAP/AC-B11.md` still reads "five... eventually six, once `BL-B67` lands" —
`sight_target` is in fact the sixth `Content-Length`-unbounded handler, landing before `BL-B67`.
The plan review already flagged this as a one-line update owed on ship, not a blocker. **Not
filed as a new backlog item** — it is a one-line edit to an existing, already-filed item
(`AC-B11`), not a new finding.

### Verdict

APPROVED

No dependency change, no new attack-surface category, the one place the implementation departs
from the Lua `cockpit_switch` handler's defensive NaN/Inf re-check is provably unreachable (the
wire-format extractor cannot produce a non-finite value), the API-layer bound requested in the
plan review is implemented and tested, the `ShowMenu` auto-press path is internally triggered and
strictly less exposed than the already-accepted `cockpit_switch` precedent, and the Reviewer's five
required fixes (including the `safe_call` wrap and the `ai_off_since` reset correction) are present
in the diff. Proceed to DoD.
