## Security Deep Analysis: BL-16 mode 2 Stages P3+P4 (CBTM align/break/break-away)

Diff `3107a662..6e0421e3` (`aircraft-layer`/`body-layer` only, per task scope). Reviewer verdict:
APPROVED (review fix round for body/rule dispatch tests folded in at `6e0421e3`). Scope per root
`CLAUDE.md`/this role's own scoping note: internet/LAN security only (code execution, cockpit-write
surface, LAN reachability, prompt injection, dependency/supply-chain, secrets). Player-experience
correctness (CBTM mode gating, break-away timing, speech wording) is the Reviewer's territory and
is not re-litigated here.

**Worktree note**: this agent's worktree started at `59192cfa`, a strict ancestor of the task's tip
`6e0421e3` (confirmed via `git merge-base --is-ancestor`), tree clean. Fast-forwarded with
`git merge --ff-only 6e0421e3`. Confirmed `HEAD == 6e0421e3` before reading anything.

### Dependency Status

No dependency change. `git diff --stat 3107a662..6e0421e3 -- '*pyproject.toml' '*.lock'
'*requirements*.txt'` is empty; the diff touches only `*.py`/`*.lua`/`*.md`/`*.toml` (generated
`config/defaults.toml`) across `aircraft-layer`/`body-layer`.

### What a LAN port scanner reaches — new surface

`POST /command/ai_pilot_goal` gains two sibling one-shot fields, `cbtm_action` (closed five-value
vocabulary) and `cbtm_seq` (int). **Shape validation at the HTTP boundary matches the established
safe pattern**, confirmed by reading `_make_handler`'s new block directly: `cbtm_action` is checked
by membership against `_AI_PILOT_GOAL_VALID_CBTM_ACTIONS`, never converted; `cbtm_seq` is checked
`isinstance(..., int)` with bool excluded and range `[0, 2**31-1]`, never passed through a raising
`int()` — this is `[[project_nan_infinity_int_conversion_at_lan_boundary]]`'s known-good shape, not
the known-bad one. No new endpoint, no change to `TelemetryAPIServer`'s binding posture.

### Arbitrary code execution / Lua eval

No `eval`/`loadstring`/`dostring`/`dostring_in` anywhere in this diff. `handle_ai_pilot_goal_command`
extracts `cbtm_action`/`cbtm_seq` with the existing hand-rolled `extract_json_string_field`/
`extract_json_number_field` (string pattern matching, not a parser). The one effector table this
feature adds, `AI_PILOT_CBTM_PRESS_CMD`, is a fixed four-entry map (`align_for_launch`/`break_left`/
`break_right`/`break_away` → `AI_WHEEL_UP`/`_LEFT`/`_RIGHT`/`_LEFT`), indexed only by
`ai_pilot_cbtm.action`, which the Lua dispatcher assigns straight from the wire's `cbtm_action`
string with **no enum re-check on the Lua side**. If a value outside the five HTTP-validated ones
reached this code path (only possible via the loopback UDP hop directly, bypassing the HTTP
boundary — see next section), `AI_PILOT_CBTM_PRESS_CMD[action]` is `nil`, and
`GetDevice(30):performClickableAction(nil, 1)` runs inside `safe_call`, which catches the error;
`ai_wheel_cbtm_pending_cmd` is then set to `nil` and released the same safe way on the next tick.
No crash, no write outside the fixed device-30 button set — confirmed by reading `safe_call` and
every call site, not assumed. Same bounded-effector-table posture `[[project_cockpit_write_
vocabulary_invariant]]` already requires; this feature does not touch `cockpit_switch`'s any-device
exception.

### The loopback hop re-validation gap — pre-existing, now one field wider

`[[AC-B14]]` (filed at Stage P2a/P2b's security pass, `plans/flight-control/security-p2.md`) found
that `handle_ai_pilot_goal_command`'s Lua-side dispatch does not re-validate `hvrt_direction`/
`hvrt_step` against a closed set the way `handle_sight_target_command` does for its own fields, and
that `CommandSender.send_ai_pilot_goal`'s docstring's claim ("`Export.lua`'s own dispatch validates
a third time") is not true for this handler. **`cbtm_action` has the identical gap** — confirmed by
reading `handle_ai_pilot_goal_command`'s new block: no `if cbtm_action ~= nil and cbtm_action ~=
"align" and cbtm_action ~= ... then return end` guard, unlike `handle_sight_target_command`'s
pattern. This is the same local-actor-only exposure already assessed and filed as AC-B14 (the one
LAN-facing hop, the HTTP boundary, is fully validated; the gap is reachable only by a process
already running on the DCS box, loopback-only — this project's own stated threat model's other
named actor, "malicious code in a dependency," not a LAN attacker), and does not escalate beyond
`AI_PILOT_CBTM_PRESS_CMD`'s fixed four-entry table — strictly less powerful than `cockpit_switch`'s
already-accepted any-device exception. **Not a new finding; AC-B14's own recommended fix (mirror
`handle_sight_target_command`'s pattern) now additionally covers `cbtm_action`** — noted here so
AC-B14's eventual fix is scoped to pick this field up too, not re-filed as a separate entry.

### The handover/dedup channel itself — this is what the task was dispatched to check

**`cbtm_seq` does not reintroduce `[[AC-B19]]`'s "stuck at the ceiling" shape, by construction, not
by accident.** `flight_control.lua`'s `fc_last_cmd_seq` check is `if seq <= fc_last_cmd_seq then
return end` — monotonic, so a single message carrying the HTTP-layer maximum (`2**31-1`) jams the
channel permanently (that finding's own root cause, fixed in M1+M2 by `wire_seq` reconciliation
against `fc_last_cmd_seq` on startup, residual tracked as AC-B19). **The CBTM channel's own guard is
different**: `if cbtm_action ~= nil and cbtm_seq ~= ai_pilot_cbtm.seq then` — inequality, not
ordering. A message carrying any value different from the currently-stored one is accepted and
acted on, including a *smaller* value than what is currently stored. Walking `ai_pilot_cbtm.seq` to
`2**31-1` (deliberately or via a coincidental restart mismatch) does **not** jam the channel the way
`fc_last_cmd_seq` could: the very next real send (`body.py`'s `bumped_cbtm_seq = (runner.
ai_pilot_cbtm_last_sent_seq or 0) + 1`, a small number after any restart) is simply *different* from
`2**31-1` and is accepted. Confirmed by reading both guards side by side, not inferring from the
field's name alone.

**What this design trades the lockup risk for: the dedup counter is a small, predictable,
sequential integer with no reconciliation against Lua's own echoed `apw_cbtm_seq` on body-layer
restart (`runner.ai_pilot_cbtm_last_sent_seq` is a plain `None`-initialised field, grepped `body.py`
for any read of `lua_cbtm_seq` feeding back into it — none; same one-directional posture
`[[AC-B19]]`'s root cause had for `wire_seq` before that fix, just without that finding's lockup
consequence here).** Two residual, narrow effects, both bounded by the equality-not-ordering guard:

1. **A one-time coincidental duplicate-suppression after a body-layer restart.** `ai_pilot_cbtm.seq`
   persists in the long-lived Lua VM across a body-layer process restart (same as `fc_last_cmd_seq`
   did); `ai_pilot_cbtm_last_sent_seq` resets to `None` (so the next real send is `1`, `2`, ... from
   a fresh park). If Lua's stored value happens to already equal whatever small number body-layer
   next sends, that one real CBTM command is silently dropped (the existing `cbtm_seq ~=
   ai_pilot_cbtm.seq` check reads as "already seen," not "stale"). Self-healing on the very next
   distinct value — no permanent jam, unlike AC-B19's root cause.
2. **A LAN actor (or the local-actor hop above) can predict the next `cbtm_seq` value**, since it is
   a plain incrementing counter starting at `1` each park. Sending a crafted `{"cbtm_seq": N,
   "cbtm_action": "align"}` ahead of the real next command (1) fires one spurious, bounded wheel
   press from the fixed four-entry table, and (2) sets `ai_pilot_cbtm.seq = N`, so if the real
   command about to be sent also carries `N` (plausible, since body-layer's counter is independent
   and small), it is read as a duplicate and dropped.

**Why this does not block APPROVED.** Both effects are reachable only through the same LAN-facing
HTTP boundary `cockpit_switch` already exposes with no authentication at all
(`[[project_cockpit_write_vocabulary_invariant]]`, user-accepted 2026-10-21) — and `cockpit_switch`
gives that same actor an arbitrary device/cmd/value write, strictly more powerful than anything
reachable through this channel's fixed four-button table. Neither effect touches the physical
park-the-AI-wheel escape hatch (`security-m1-m2.md`'s own finding: arg 852, disjoint from the CBTM
button set, confirmed again here — `run_ai_pilot_wheel`'s park branch clears every CBTM field the
same frame, same as the goal/HVRT fields beside it). This project's threat model (root `CLAUDE.md`,
2026-10-21) names "an infected computer scanning/probing reachable ports" as the realistic LAN
actor, not a player deliberately racing sequence numbers against their own aircraft; probability is
low for both effects, impact is low (one dropped command that self-heals, or one spurious bounded
wheel press no more consequential than the player's own hand on the wheel).

### LLM prompt injection

No new text reaches a model prompt. `cbtm_action`'s five values are a closed Lua-side enum choice
from a fixed set (same `_AI_PILOT_GOAL_VALID_CBTM_ACTIONS` tuple enforced at the one validated LAN
hop); `apw_cbtm_status` echoed back on the wire is one of `"idle"`/`"running"`/`"done"`, assigned by
Lua itself from a fixed set, never built from parsed input. `config/rules/flight.lua`'s new CBTM
rules (`align`, `align for launch`, `break turn <direction:left|right>`, `break away`) are static,
sandboxed-Lua rule text, not reachable or influenced by anything a LAN peer sends. Not applicable.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py`'s `cbtm_action`/`cbtm_seq` validation | `isinstance`/membership checks, `seq` never passed through `int()` | Matches the established safe pattern | None |
| `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`, `handle_ai_pilot_goal_command` (`cbtm_action`) | No enum re-check on the loopback hop | Pre-existing `[[AC-B14]]` gap, now one field wider; local-actor-only, bounded by the fixed 4-entry press table | None — AC-B14's own fix will cover it; not re-filed |
| `ai_pilot_wheel.lua`'s `cbtm_seq ~= ai_pilot_cbtm.seq` guard | Inequality dedup, not ordering | Confirmed does **not** reintroduce `[[AC-B19]]`'s lockup shape | None |
| `body.py`'s `ai_pilot_cbtm_last_sent_seq` | No reconciliation against `lua_cbtm_seq` on restart | New finding — filed `[[AC-B22]]`, low/low, not blocking | Fix recommended, not blocking |
| `AI_PILOT_CBTM_PRESS_CMD` / `GetDevice(30):performClickableAction` | Fixed 4-entry button table, never wire-indexed beyond the enum | No generalization of the cockpit-write surface | None |
| All new Lua/Python in this diff | secrets/credentials grep | None found | None |

### Verdict

**APPROVED.**

### Required Fixes

None blocking. `[[AC-B22]]` (filed below) is the one new residual, low/low, consistent with this
project's own house style of surfacing rather than blocking on a no-auth-LAN-baseline-bounded,
self-healing gap.

**Finding:** `ai_pilot_cbtm_last_sent_seq` is not reconciled against Lua's own echoed `apw_cbtm_seq`
on body-layer startup/restart, so (a) a coincidental seq match after a routine restart silently
drops exactly one real CBTM command (self-healing on the next distinct value), and (b) a LAN actor
who can predict the small, sequential next value can preempt it with a spurious bounded wheel press
and/or cause the same one-command drop.
**Location:** `body-layer/src/body.py:565,3627,3645` (`ai_pilot_cbtm_last_sent_seq`, never read
against `AiPilotWheelState.lua_cbtm_seq`); `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`
(`ai_pilot_cbtm.seq`, the Lua-side value it would reconcile against).
**Probability:** low — single-user LAN, no attacker currently targets this; the self-inflicted
restart-coincidence variant needs the stored Lua value to land on the exact small integer
body-layer's fresh counter is about to produce, which is itself low odds for any single restart.
**Impact:** low — bounded by the already-accepted no-auth `cockpit_switch` baseline, which is
strictly more powerful; at most one dropped command (self-healing) or one spurious press from the
fixed four-button CBTM table, never a stuck channel (confirmed structurally distinct from
`[[AC-B19]]`'s ordering-based lockup) and never a degradation of the physical park escape hatch.
**Recommended action:** mirror the `[[AC-B19]]`/M1+M2 fix's shape — on reconnect/first sample after
a restart, if `state.lua_cbtm_seq` is not `None` and differs from `ai_pilot_cbtm_last_sent_seq`,
seed the local counter from it (`max(local, remote)`-style) before the next bump, same reasoning
`body.py:3699-3714`'s `flight_control` reconciliation already documents for the sibling channel.

Options:
  (A) Ignore — document acceptance of this risk for now (single-user LAN, low/low, self-healing).
  (B) Add to the aircraft-layer backlog — fix in a future session. **(Filed as `[[AC-B22]]`.)**
  (C) Fix now — apply the recommended reconciliation above.
  (D) Stop — do not proceed until resolved.

### Not filed (intentionally)

- `[[AC-B14]]`'s own recommended fix (mirror `handle_sight_target_command`'s enum-check pattern) now
  additionally covers `cbtm_action` — not re-filed as a separate entry; noted in that entry's own
  scope by this report.
- `[[AC-B11]]`'s unbounded-`Content-Length` pattern already covers every POST handler on this
  server, including the unchanged-shape `/command/ai_pilot_goal` handler this diff extends with two
  more fields — not re-filed.

### Passed to Reviewer

- Nothing new. `review-p3p4.md`'s own scope (body/rule dispatch tests for CBTM composition) is
  already the Reviewer's territory and was approved there.
