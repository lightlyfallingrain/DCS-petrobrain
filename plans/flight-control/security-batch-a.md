## Security Deep Analysis: BL-16 mode 2, parked mode, batch A (Stage P-ICS, Stage P0 probe, Stage P1)

Diff `fde7398e..618ec14f` (24 files, includes the Reviewer's own `c0be1771..618ec14f`
required-fix follow-up). `review-batch-a.md` verdict: CHANGES REQUIRED → re-reviewed
`da553b42` → fixed at `618ec14f`. Scope per root `CLAUDE.md`/this role's own scoping
note: internet/LAN security only (code execution, cockpit-write surface, LAN
reachability, prompt injection, dependency/supply-chain, secrets) — player-experience
correctness (E-P1/E-P6/E-P10, the park-sink nudge logic itself) is the Reviewer's
territory and was independently spot-checked below only because it is also the one
behavioural invariant ("never press short-right") that doubles as this layer's write
discipline.

**Worktree note**: this agent's worktree started at `0fa6c92f` (stale `origin/HEAD`,
not an ancestor of the task's tip). Moved with `git switch -C
worktree-agent-ac59a822fe45e91bd 618ec14f`, confirmed `HEAD == 618ec14f`, tree clean,
before doing anything else.

### Dependency Status

No dependency change. `aircraft-layer` stays stdlib-only; `body-layer`'s new file
(`belief/ai_pilot_wheel.py`) imports only `tuning` and `aircraft_client`, both already
in the codebase. No new package, no install-time script, nothing to search an
advisory database for.

### What a LAN port scanner reaches — new surface

One new endpoint: `GET /ai_pilot_wheel/latest` on `TelemetryAPIServer`, which binds
`0.0.0.0` (LAN-facing by design, `aircraft-layer/src/api/server.py:306`, pre-existing
posture — not introduced by this batch). Confirmed by reading `_make_handler`'s new
branch (`server.py:600-604`): no query-string parsing, no request body read, serves
`cache.latest()` or JSON `null`. Same shape and same risk class as every sibling
`/*/latest` endpoint already accepted in this project's threat model — a scanner
hitting it gets non-sensitive flight-status text (mode/course/altitude/speed overlay
strings), nothing it couldn't already get from `/petrovich_indication/latest` or
`/sight_servo/latest`. No new write/command path reaches it: grepped every
`_COMMAND_*_PATH`/`do_POST` branch in `api/server.py` and `collector/__main__.py` —
the AI-pilot wheel has no `POST` counterpart in this batch (Stage P2 adds the goal
channel later, per the plan). **Confirmed: no inbound press command exists yet.**

### Arbitrary code execution / cockpit-write surface — the E-P6 guarantee, re-verified independently

The task calls this out specifically because it is the one press in this batch that
acts on a received/derived value rather than a fixed sequence. Independently (not
taking Reviewer's grep on faith):

```
$ grep -n "AI_WHEEL_RIGHT" aircraft-layer/dcs-export/Export.lua
1993:local AI_WHEEL_RIGHT = 3002
$ grep -n "GetDevice(30)" aircraft-layer/dcs-export/Export.lua
...only AI_WHEEL_UP (3004) and WHEEL_MENU_BUTTON/WHEEL_CENTER_BUTTON appear as
performClickableAction's cmd argument...
$ grep -n "ai_wheel_pending_cmd" aircraft-layer/dcs-export/Export.lua
2037: local ai_wheel_pending_cmd = nil
2151:     ai_wheel_pending_cmd = AI_WHEEL_UP        <- the ONLY assignment
2167/2191: GetDevice(30):performClickableAction(ai_wheel_pending_cmd, 0)  <- release
```

`AI_WHEEL_RIGHT` (3002, the forbidden short-right/"HDG LOS" command) is declared but
never passed to `performClickableAction` anywhere in production `Export.lua` — the
only variable ever assigned to the pending-press slot is the literal `AI_WHEEL_UP`.
No generic `press(direction, duration)` entry point exists in production code; the
one press function (`ai_pilot_press_altitude_up_long_hold`) is hard-coded to
`AI_WHEEL_UP`. Holds under direct verification, not just reading.

The probe script (`Export.probe-ai-pilot-wheel.lua`) does have a generic `press(cmd,
value)` combinator (line 170), but `WHEEL_RIGHT` is referenced only once as a row
target (`P02_SEQ`, line 337) and only ever reached through `open_long_hold`, which
presses with `value=1` and schedules a 0.7s-later release — never a short pulse.
Verified: no call site anywhere in the probe passes `WHEEL_RIGHT` to a short-duration
path. The probe is not production code (manual-deploy-over-`Export.lua`, no collector,
not network-reachable, not voice-reachable) — Optional Refinement in
`review-batch-a.md` already flags this combinator as a shape not to carry into
production, which this analysis agrees with and does not escalate further.

No `eval`/`loadstring`/`dostring`/`dostring_in` of untrusted data anywhere in this
diff — the new Lua is all local function definitions and `performClickableAction`
calls with literal command constants; the new Python is all dataclass
parse/`to_api_dict` methods with no `exec`-shaped construct. `Export.lua`'s existing
`dostring_in` call sites are untouched by this diff (confirmed by diff stat: no Hook
script in the changed-file list).

### LLM prompt injection

No new text reaches a model prompt in this batch. `apw_mode_text`/`apw_course_text`/
`apw_alt_text`/`apw_alt_add_text`/`apw_speed_text`/`apw_last_press` are carried as
opaque strings through the schema and into `ParkedFlightState`, but this stage wires
no voice/speech output and no LLM call reads these fields yet (`belief/
ai_pilot_wheel.py`'s own docstring: "No actions wired to voice yet... No spoken line
on park or unpark"). Grepped for any `ai_mode`/`held_*`/`last_press` reference outside
`belief/ai_pilot_wheel.py`, `aircraft_client.py`, and `body.py`'s plumbing — none
found. Flag for whichever stage first surfaces these fields to Petrovich's speech:
`apw_mode_text` etc. originate from DCS's own `list_indication` overlay text (not
network/player-controlled), so the injection surface, if any, is "DCS's own HELPER_AI
overlay string" — same trust level as `petrovich_indication`'s existing feed, not a
new category.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/schema/ai_pilot_wheel.py:85` (`float(model_time)`) | `float()` on an `isinstance(x, int\|float)`-checked wire value | Matches the **safe** pattern (`float()`, not `int()`) — this is the NaN/Infinity-at-LAN-boundary gap's known-good side, not the known-bad side (`.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lan_boundary.md`). No `int()` conversion exists anywhere in this diff's new schema code. | None — false positive for the pattern, confirmed by absence |
| `aircraft-layer/dcs-export/Export.lua:1993-2151` (`AI_WHEEL_RIGHT`/`ai_wheel_pending_cmd`) | Cockpit-write command selection | E-P6 re-verified independently: only `AI_WHEEL_UP` ever reaches `performClickableAction` on device 30 from production Lua | None — holds |
| `aircraft-layer/src/api/server.py:600-604` (`GET /ai_pilot_wheel/latest`) | New LAN-reachable (`0.0.0.0`) endpoint | Read-only, no params parsed, same risk class as 8+ sibling `/latest` endpoints already accepted under this project's threat model | None |
| `body-layer/src/belief/ai_pilot_wheel.py:95-114` (`advance_parked_flight_state`) | Response from aircraft-layer's own API trusted without re-validating types beyond `dict`/`float()`-with-try | Same posture as every other `get_*`/`advance_*` pair in `aircraft_client.py` (pre-existing shape, not introduced here); the realistic attacker (an infected LAN peer) would have to spoof the aircraft-layer server's IP/port, a generic MITM risk against the whole polling architecture, not specific to this feature | None — not a new attack surface, no escalation beyond existing accepted posture |
| `Export.probe-ai-pilot-wheel.lua:170` (`press(cmd, value)`) | Generic combinator in a probe script | Not network-reachable, not production, manual-deploy-only testing aid; `WHEEL_RIGHT` only reached via long-hold in this probe | None (Optional Refinement already flagged by Reviewer) |
| All new Lua/Python in this diff | secrets/credentials grep | None found | None |

### Verdict

APPROVED

No REQUIRED FIX from this analysis. The one required fix identified by Reviewer
(missing aircraft-layer-side test tier) was addressed at `618ec14f` and independently
re-verified here (62 tests pass, `mypy --strict` clean for `aircraft-layer`). No new
dependency, no new code-execution surface, no new unauthenticated write-capable
endpoint, no prompt-injection surface actually wired yet, E-P6 (the one write-side
invariant with security-relevant shape) holds under independent grep/trace rather
than trust in the Reviewer's own grep.

### Passed to Reviewer

- The per-frame unthrottled `list_indication(6)` parse (`run_ai_pilot_wheel`,
  Export.lua) is already flagged to performance-reviewer in `review-batch-a.md` —
  not a security finding, no action here.
- `AI_PILOT_ALTITUDE_TOLERANCE_M`/`AI_PILOT_NUDGE_EPSILON_M` duplication across
  body-layer/Export.lua is a correctness/maintainability item already tracked in
  `review-batch-a.md`'s Optional Refinements — not security.

### Not filed (intentionally)

No new backlog-worthy finding was produced by this pass — everything checked either
held under independent verification or matched an already-accepted, already-reviewed
pattern (the LAN-facing `/latest` endpoint shape, the client-trusts-its-own-API-server
posture). Nothing here meets the bar for a `<prefix>-B<n>` entry.
