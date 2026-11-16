## Security Deep Analysis: BL-16 takeover and stabilisation (Stage P1 revision)

Diff `993be9a5..306af5f0` (`d3bfe9df`, `72bac70e`, `306af5f0`; the two `main` merges in that range
are unrelated and excluded). Reviewer verdict: APPROVED, both rounds
(`plans/flight-control/review-takeover.md`). Scope per root `CLAUDE.md`/this role's own scoping
note: internet/LAN security only (code execution, cockpit-write surface, LAN reachability, prompt
injection, dependency/supply-chain, secrets) — player-experience correctness (whether the takeover
sequence actually lands the handover the pilot wants) is the Reviewer's territory.

**Worktree note**: started at `6a7e853f` (clean, strict ancestor of the task's tip
`f5700914`). Fast-forwarded with `git merge --ff-only f57009142de539863b24bfd20407b9f9f72158be`
before doing anything else.

### Dependency Status

No dependency change. `aircraft-layer` stays stdlib-only, `body-layer`'s touched file imports
nothing new. `git diff --name-only` for this diff's three commits touches only `Export.lua`,
`collector/server.py`, `schema/ai_pilot_wheel.py`, `belief/ai_pilot_wheel.py`, and their tests —
confirmed by listing each commit's own files (`git show --name-only`); the `raster-chart-viewer/
pyproject.toml` hit from a wider `993be9a5..306af5f0` diff belongs to the unrelated `main` merge, not
this feature.

### What can make `Export.lua` press anything — the one question this batch is built around

Traced every `GetDevice(30):performClickableAction` call site reachable from the new code:

- `ai_pilot_tap30(cmd)` (new) — called only with `WHEEL_CENTER_BUTTON` or `WHEEL_MENU_BUTTON`,
  both fixed pre-existing wheel-menu constants, never a direction.
- `ai_pilot_open_hold(cmd, t)` (new) — called only from `ai_pilot_begin_hold_phase`, whose `cmd`
  comes from `ai_pilot_correction_direction`, which returns only `AI_WHEEL_DOWN`, `AI_WHEEL_UP`, or
  `nil`. No other caller.
- `ai_wheel_pending_cmd`'s two release sites (`run_ai_pilot_wheel`, lines ~2442/2472) only ever
  release whatever was already opened through one of the two paths above.
- `AI_WHEEL_RIGHT`/`AI_WHEEL_LEFT` (3002/3003, the forbidden short-right "HDG LOS" command and its
  sibling) are **not declared anywhere in this file any more** — this revision removed the
  declarations that existed before (`grep -c AI_WHEEL_RIGHT Export.lua` → 0). E-P6 holds, now by
  construction (nothing to reference) rather than by discipline (declared but unused).
- No generic `press(direction, duration)` entry point exists. The two new press helpers
  (`ai_pilot_tap30`, `ai_pilot_open_hold`) are each restricted to a fixed small set of callers with
  fixed or provably-restricted arguments, same shape the plan's own Implementer note (E-P6)
  requires, and the Reviewer's own grep (`review-takeover.md`) is independently reproduced here.
- Every decision that drives a press traces to **local-only** inputs: `GetDevice(0):get_argument_value`
  on args 852/952 (cockpit animation state), `LoGetAltitudeAboveGroundLevel`/
  `LoGetAltitudeAboveSeaLevel`, `list_indication(HELPERAI_DEVICE_ID)` overlay text, and the model
  clock `t`. **No network, wire, or collector-derived value reaches `ai_pilot_takeover` or either
  press helper** — confirmed by grepping `poll_command_socket`'s own `op` dispatch (`petrovich_search`,
  `cockpit_switch`, `sight_target`, `watch_args`, `read_args`): none of the five branches touches
  `ai_wheel`/`ai_pilot`/`AI_WHEEL` state. The takeover sequence is exactly as self-contained as the
  task's framing assumes.

**Cross-check against the project's one deliberately-unrestricted write channel** (per this role's
own memory, `generic-write-channel-bypasses-narrow-guard`: a narrow guarantee on one call site can be
bypassed by a different, already-open channel to the same device). `cockpit_switch`
(`BL-B66`, user direction 2026-10-21 — "allow any cockpit switch... this is LAN only") forwards
`POST /command/cockpit_switch {"device":30,"cmd":3002,"value":1}` straight to
`performClickableAction(30, 3002, 1)` with no device/cmd allow-list, so it **could** press
AI_WHEEL_RIGHT directly — a LAN peer using that pre-existing, separately-scoped channel is not
bound by E-P6 at all. This is not a new finding: it is the same accepted, documented exception
(`aircraft-layer/CLAUDE.md`, "One deliberate exception") that predates this diff and is unchanged by
it — this batch did not touch `cockpit_switch`, did not narrow or widen it, and the plan's E-P6
guarantee has only ever been a claim about this module's own code, not a system-wide lock on device
30. Noted for completeness, not escalated.

### Every held press released — unpark, convergence/ceiling, confirmed; Export stop, not new

- **Unpark** (`run_ai_pilot_wheel`'s `if not now_parked then` branch): releases any open
  `ai_wheel_pending_cmd`, closes the command menu if this sequence opened it, and clears every
  `ai_pilot_takeover` field, same frame. Matches the plan's Co-moving Fields table exactly.
- **Convergence**: `ai_pilot_check_hold_convergence` releases the instant the readback is within
  tolerance, clearing `correction_hold_cmd`/`ai_wheel_pending_release_t`/`ai_wheel_pending_cmd`
  together.
- **60 s ceiling** (`AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S`): the per-frame deadline check at the
  top of `run_ai_pilot_wheel` releases unconditionally at `t >= ai_wheel_pending_release_t`, and — new
  in this revision — correctly distinguishes a hold release from a pulse release
  (`was_hold = ai_wheel_pending_cmd == AI_WHEEL_UP or AI_WHEEL_DOWN`) so only a hold's own
  `correction_hold_cmd`/`correction_phase`/`stage` get cleared, not a quick-pulse's unrelated state.
  Verified this still fires even if the overlay stops updating (it only reads `t` and the pending
  slot, no `list_indication` dependency) — the safety ceiling does not depend on the same feed whose
  absence it is meant to guard against.
- **`LuaExportStop` (mission end/restart) does *not* reset `ai_wheel_pending_release_t`,
  `ai_wheel_pending_cmd`, or any `ai_pilot_takeover` field** — confirmed by reading the full function
  body (`Export.lua:2835-2926`): it resets the *search wheel's* own `pending_release_t`, plus
  `sight_*`, `watched_*`, `mission_start_model_t`, following this file's own stated convention ("a
  stale X must never survive"), but the AI-pilot-wheel state added in the prior batch and extended
  here is absent from that list. **Pre-existing, not introduced by this diff** — confirmed against
  `993be9a5` (the state before this batch): the same gap existed there for the single-shot nudge.
  This batch does widen the exposure window the gap could matter during, from a single ≤0.7 s
  long-press to up to the full 60 s correction hold, and the plan's own Co-moving Fields table
  (`plans/flight-control/plan.md`, "Revised 2026-11-16") lists only "falling edge (unpark)" and
  "correction converges, or ceiling elapses" as this mechanism's release triggers — `LuaExportStop`
  is deliberately not one of them here, unlike the later `flight_control` stick-effector design
  elsewhere in the same plan file, which explicitly lists "Mission restart / `LuaExportStop` /
  ownship dead → release and reset" for a different mechanism. Assessed, not escalated as a blocker:
  `LuaExportStop` fires only at mission end/restart/DCS exit, every one of which also discards the
  aircraft instance the held press was acting on — there is no observed DCS scenario in a
  single-player session where the export environment tears down while the same aircraft remains
  player-controlled. Surfaced below per the Risk Communication Format rather than silently accepted,
  since the project's own file-wide convention argues the other way and the exposure window grew.

### What a LAN port scanner reaches — no new write surface

No new endpoint in this diff. The pre-existing `GET /ai_pilot_wheel/latest` (batch A) now serves
four more optional fields (`apw_arg852`/`apw_arg952`/`apw_takeover_stage`/`apw_correction_path`),
still read-only, no query-string parsing, same risk class as every sibling `/latest` endpoint. No
`POST` counterpart exists for this feed. `EXPECTED_EXPORT_VERSION` bumped to `"2026-11-16"` and the
comparison (`collector/server.py:385-398`) behaves as intended: a stale deployed `Export.lua`
produces a logged warning, never a crash or a dropped line, and resets `_watched_args_cache` the
same as every prior bump — purely diagnostic, not a gate.

### Arbitrary code execution / deserialization

No `eval`/`exec`/`loadstring`/`dostring`/`pickle.loads` anywhere in this diff (`security-grep` run
against the full tree: no hit under `aircraft-layer/src` or the touched `body-layer` file; the
project's one expected `net.dostring_in` bridge is untouched by this diff's file list).
`fmt_num_or_null`/`text_or_null` (both pre-existing, unchanged) are the only Lua→JSON encoders used
for the four new wire fields.

### The four new wire fields — parsing and validation

- **`aircraft-layer/src/schema/ai_pilot_wheel.py`**: `apw_arg852`/`apw_arg952` go through
  `isinstance(raw_number, bool) or not isinstance(raw_number, (int, float))` → `AiPilotWheelParseError`
  on anything else, then `float(raw_number)` — the **safe** side of the NaN/Infinity-at-LAN-boundary
  pattern this role has flagged before (`.claude/agent-memory/security/
  project_nan_infinity_int_conversion_at_lan_boundary.md`): `float()` never raises on `NaN`/
  `Infinity`/`-Infinity`, unlike `int()`. No `int()` conversion exists anywhere in this diff's new
  code. `apw_takeover_stage`/`apw_correction_path` go through the same `optional_strings` loop every
  other opaque status string here already uses (`apw_mode_text` etc.) — type-checked, not
  enum/length-validated, consistent with the existing pattern and not escalated for the same reason
  that pattern was accepted before: this collector-side boundary's realistic adversary is a malformed
  or stale *local* `Export.lua` process on the same machine, not a LAN peer (the LAN-reachable side
  is the read-only `GET` endpoint downstream of this parse, not the ingest socket).
- **`body-layer/src/belief/ai_pilot_wheel.py`**: `_as_optional_float` mirrors the same
  bool-exclusion + `isinstance` + `float()` shape; `takeover_stage`/`correction_path` are passed
  through via plain `sample.get(...)`, untyped at this layer but already typed/validated one hop
  upstream by the aircraft-layer schema it reads through `AircraftLayerClient`. Both are documented
  as diagnostic-only, read-only mirrors — "nothing in this stage decides from them" — confirmed by
  grep: neither field is referenced in any conditional anywhere in `advance_parked_flight_state` or
  its tests beyond the straight assignment.
- Malformed/hostile values (wrong type, missing field) raise `AiPilotWheelParseError` at the
  aircraft-layer boundary, which the collector already handles the same way every other schema's
  parse error is handled (logged, line dropped) — confirmed this is unchanged plumbing, not part of
  this diff.

### LLM prompt injection

No new text reaches a model prompt. `takeover_stage`/`correction_path` are fixed-vocabulary Lua
string literals (`"toggling_reference"`, `"opening_menu"`, `"correcting_altitude"`, `"quick"`,
`"hold"`, `"none"`) chosen entirely by `Export.lua`'s own code — never built from DCS-provided text,
let alone network or player input — so even if a stage wired these to speech later, they could not
carry injected instructions; they are a closed enum written by this project's own source, not
free-text relayed from an external observer. `apw_mode_text`/`apw_course_text`/etc. (the pre-existing
free-text overlay fields this batch does not add) remain the only text in this feed with any
external provenance (DCS's own HELPER_AI overlay), unchanged and already assessed by batch A's
analysis — still not wired to any LLM call as of this diff.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/dcs-export/Export.lua` (no `AI_WHEEL_RIGHT`/`AI_WHEEL_LEFT` declaration) | Cockpit-write command selection, E-P6 | Confirmed by grep: forbidden commands are not even declared, let alone pressed; no generic press entry point | None — holds, strengthened from prior batch |
| `aircraft-layer/dcs-export/Export.lua:2835-2926` (`LuaExportStop`) | Held-press cleanup on Export stop | `ai_wheel_pending_release_t`/`ai_wheel_pending_cmd`/`ai_pilot_takeover.*` not reset, unlike every sibling per-session state in the same function; pre-existing (not introduced here), window widened by this revision's up-to-60s hold | See Risk Communication below — not blocking |
| `aircraft-layer/src/schema/ai_pilot_wheel.py:91-106` (`apw_arg852`/`apw_arg952`) | `float()` on an `isinstance(x, int\|float)`-checked wire value | Safe side of the NaN/Infinity pattern — `float()` does not raise | None |
| `body-layer/src/belief/ai_pilot_wheel.py:111-116` (`_as_optional_float`) | Same shape, mirrored | Same assessment | None |
| `aircraft-layer/src/collector/server.py:385-398` (`EXPECTED_EXPORT_VERSION` check) | Stale-deploy detection | Logs and continues, never blocks or crashes on mismatch — behaves as intended | None |
| Inbound command socket `op` dispatch (`Export.lua`, `poll_command_socket`) | New input path check | No branch reaches `ai_wheel`/`ai_pilot` state; confirmed the five existing ops (`petrovich_search`/`cockpit_switch`/`sight_target`/`watch_args`/`read_args`) are untouched by this diff | None |
| `cockpit_switch` op (pre-existing, `BL-B66`) | Sibling unrestricted write channel to the same device | Could press `AI_WHEEL_RIGHT` directly; deliberate, user-accepted, unchanged by this diff | None — accepted risk, noted for completeness |
| All new Lua/Python in this diff | secrets/credentials grep | None found | None |
| All new Lua/Python in this diff | `eval`/`exec`/`loadstring`/`dostring`/`pickle` grep | None found | None |

### Risk Communication: `LuaExportStop` does not release an open AI-pilot-wheel press

**Finding:** `ai_wheel_pending_release_t`/`ai_wheel_pending_cmd` and the `ai_pilot_takeover` table's
`correction_hold_cmd` are not cleared in `LuaExportStop`, unlike every other per-session state this
function resets. If the export environment tears down while a correction hold is open (up to 60 s
window, widened from ≤0.7 s before this revision), the last-commanded `performClickableAction(30,
cmd, 1)` is never explicitly released by this code path.

**Location:** `aircraft-layer/dcs-export/Export.lua:2835-2926` (`LuaExportStop`), vs. the hold state
set by `ai_pilot_open_hold` (`Export.lua:2309-2316`).

**Probability:** low — `LuaExportStop` fires only at mission end/restart or DCS exit, and in every
observed single-player scenario (this project's whole scope) the aircraft instance the press was
acting on is discarded in the same event, which in practice already resets every cockpit control
state regardless of what Lua last commanded. No live DCS scenario has been found or tested where the
export environment restarts while the same aircraft remains player-controlled.

**Impact:** low if the probability holds (the press has nothing left to act on); the plan's own
design for this mechanism (unlike a separate, later `flight_control` stick-effector mechanism
elsewhere in the same plan file) does not list `LuaExportStop` as a release trigger at all, suggesting
this was a considered scope choice, not an oversight — but it is not explicitly stated as such, and
the file's own long-standing convention ("a stale X must never survive") argues for symmetry with
every other state this function resets.

**Recommended action:** add `ai_wheel_pending_release_t = nil; ai_wheel_pending_cmd = nil` plus a
reset of `ai_pilot_takeover`'s fields to `LuaExportStop`, mirroring `pending_release_t`'s existing
reset two lines above — a small, local, reversible change, cheap now and cheaper than re-deriving
the reasoning later once a third hold-shaped mechanism exists in this file.

Options:
  (A) Ignore — the teardown-coincides-with-reset reasoning above is accepted as sufficient
  (B) Add to todo.md — fix in a future session
  (C) Fix now — three-line addition to `LuaExportStop`
  (D) Stop — do not proceed until this is resolved

### Verdict

APPROVED

No REQUIRED FIX from this analysis — E-P6 holds (now more strongly, since the forbidden commands
are no longer even declared), no new network-reachable write surface, no code-execution surface, no
prompt-injection surface, no dependency change, the new wire fields are parsed safely (the `float()`,
not `int()`, side of this project's own known NaN/Infinity pattern), and the one gap found
(`LuaExportStop` not releasing an open hold) is pre-existing, assessed low/low, and presented to the
user above rather than silently accepted or used to block.

### Passed to Reviewer

- None beyond what `review-takeover.md` already covers — this pass's one correctness-adjacent
  observation (the `LuaExportStop` gap) is written up above with its own probability/impact
  because the task specifically asked this pass to check Export-stop cleanup; it is presented as a
  security-adjacent safety-ceiling gap, not handed off unassessed.

### Not filed (intentionally)

The `LuaExportStop` finding is not filed as a backlog item yet — it is presented via the Risk
Communication Format above for the user to choose (A)/(B)/(C)/(D). Once the user decides, (B) or (C)
determines whether it gets a `<prefix>-B<n>` entry; filing it now, ahead of that choice, would
pre-empt the decision this format exists to surface. Nothing else in this pass met the bar for a
backlog entry — every other checked item held under independent verification or matched an
already-accepted, already-reviewed pattern (the `cockpit_switch` sibling-channel posture, the
`/latest` endpoint shape, the diagnostic-field type-checking shape).
