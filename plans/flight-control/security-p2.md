## Security Deep Analysis: BL-16 Stage P2a/P2b (voice goals + HVRT translate)

Diff `370f37c0..09d25186` (merge of `feature/bl16-p2-voice-goals`, including the fix round against
`review-p2.md`'s three required fixes). Reviewer verdict: APPROVED, including the re-review
(`plans/flight-control/review-p2.md`). Scope per root `CLAUDE.md`/this role's own scoping note:
internet/LAN security only (code execution, cockpit-write surface, LAN reachability, prompt
injection, dependency/supply-chain, secrets) — player-experience correctness is the Reviewer's
territory.

**Worktree note**: started at `370f37c0` (clean, strict ancestor of the task's tip `09d25186`).
Fast-forwarded with `git merge --ff-only 09d25186cc1b240153d3b81d1248f575987e2a5d` before doing
anything else.

### Dependency Status

No dependency change. Diff touches only `*.py`, `*.lua`, `*.md`, `*.toml` (the generated
`config/defaults.toml`, four new tuning entries). No `pyproject.toml`/lock file in the diff
(`git diff --stat` for the full range, confirmed) — `aircraft-layer` stays stdlib-only, `audio-
adapter`/`body-layer` add no new imports for this feature.

### The write path: `POST /command/ai_pilot_goal` → collector → loopback UDP → `Export.lua`

**The LAN-facing boundary (`api/server.py`'s `_handle_command_ai_pilot_goal`, `TelemetryAPIServer`
binding `0.0.0.0` by design) is fully validated** — read, not assumed:
- `goal_seq`: whole number, bool excluded, `0 <= x <= 2**31-1`.
- `param`/`altitude_target_ref`/`hvrt_direction`/`hvrt_step`: each `None` or one of a closed
  tuple (`_AI_PILOT_GOAL_VALID_PARAMS`/`_VALID_ALTITUDE_REFS`/`_VALID_HVRT_DIRECTIONS`/
  `_VALID_HVRT_STEPS`).
- `heading_target_deg`/`altitude_target_m`/`speed_target_kmh`: `_optional_bounded_field` rejects
  bool, non-`(int, float)`, **non-finite** (`math.isfinite`), and out-of-range in one shared
  helper — this is exactly the recurring `[[project_nan_infinity_int_conversion_at_lan_boundary]]`
  bug class (NaN/Infinity surviving an `isinstance` check then blowing up a bare `int()`), and this
  handler does not have it: every numeric field is checked with `math.isfinite` before being
  accepted, and none of them is ever passed through `int()` — `goal_seq` is the only field that is,
  and it is checked `isinstance(..., int)` directly off the JSON value, never float-converted.
  Confirmed clean, not assumed from the pattern's name alone.
- A malformed/oversized/wrong-typed body gets a `400` with no side effect; `command_sender is None`
  (channel unconfigured) gets `503`. No path reaches `CommandSender.send_ai_pilot_goal` with an
  unvalidated value.

**The loopback hop (collector → `Export.lua`, UDP, `COMMAND_HOST = "127.0.0.1"` confirmed by
reading `commands.lua` directly) does not re-validate enums or numeric bounds** —
`handle_ai_pilot_goal_command` extracts `param`/`altitude_target_ref`/`hvrt_direction`/`hvrt_step`/
the three numeric targets and assigns them straight into `ai_pilot_goal`, with no enum check and no
range check. This is a genuine gap against this file's own sibling handlers:
`handle_petrovich_search_command` checks `mode` against exactly `{"forward","boresight"}`;
`handle_sight_target_command` checks every numeric field against `SIGHT_GOAL_AZ_BOUND`/
`_EL_BOUND`/`_RATE_BOUND`/`t_sim >= 0` (itself a required fix from BL-B80's own security plan
review). `command_sender.py`'s `send_ai_pilot_goal` docstring claims "`Export.lua`'s own dispatch
... validates a third time" — **not true for this handler**, confirmed by reading the actual code,
not the comment.

**Why this does not block APPROVED**: the command socket is loopback-only, so this gap is reachable
only by a process already running on the box DCS runs on — this project's own stated threat model
names that actor ("malicious code in a dependency"), not a LAN attacker; a hostile *LAN* body
cannot reach it at all, since the one LAN-facing hop is the fully-validated HTTP boundary above.
That same local actor already has `cockpit_switch` (`POST /command/cockpit_switch` →
`GetDevice(device):performClickableAction(cmd, value)` for **any** device/cmd/value, no allow-list
— user-accepted 2026-10-21, `aircraft-layer/CLAUDE.md`'s "What this is" section,
`[[project_cockpit_write_vocabulary_invariant]]`). That is strictly more powerful than anything the
missing checks here could add: this channel can only ever press `GetDevice(30)`'s
`AI_WHEEL_UP`/`_DOWN`/`_LEFT`/`_RIGHT`/`WHEEL_CENTER_BUTTON` regardless of what garbage reaches
`ai_pilot_goal`'s fields (traced every call site; `ai_pilot_goal_hvrt_direction_cmd`/`ai_pilot_
goal_ref_letter` fail safe to `nil`/no-op for an unrecognised value; an unrecognised `param` falls
through to `ai_pilot_goal_tick_speed` rather than being ignored — a logic quirk, not an escalation,
same fixed button set either way). **No crash risk**: Lua's numeric comparisons never raise on
huge/non-finite-looking values the way Python's `int()` does (confirmed: `math.abs`, `%`, `<`/`>`
all just produce a result, including on `1e300`-class magnitudes). **No indefinite hold**: every
hold this module opens (`ai_pilot_goal_open_hold`) arms a fixed `ai_wheel_goal_pending_release_t =
t + AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` safety ceiling *unconditionally*, regardless of
whether the target that opened it was ever valid — the "hold a press indefinitely beyond the
designed bounds" question this review was dispatched to check is answered structurally, not by the
missing validation.

**Filed as `[[AC-B14]]`** rather than left in this report's prose (this role's own closing-step
rule) — low/low, not blocking, recommended fix is to mirror `handle_sight_target_command`'s
pattern (cheap, mechanical, matches the project's own stated "closed vocabularies at the Lua
dispatch layer" invariant) and either make the `send_ai_pilot_goal` docstring's claim true or
correct it to match the code.

### `apw_goal_progress`/`apw_goal_seq` (the read-back path, Export.lua → collector → LAN)

`schema/ai_pilot_wheel.py`'s `AiPilotWheelState.from_dict` parses the new `apw_goal_seq` field via
`isinstance(raw_goal_seq, int)` (bool excluded) and assigns it **directly, with no `int()`/`float()`
conversion** — the right shape per `[[project_seat_change_triggers_deep_analysis]]`'s "equality/
isinstance allow-list, never a conversion" pattern: there is no path here where a non-finite JSON
value (`NaN`/`Infinity`, which Python's `json.loads` accepts by default) could reach a raising
`int()` call, because there is no `int()` call on this field at all. `apw_goal_progress` is a
string, same `optional_strings` shape every other wire string on this record already uses. Clean.

### Voice-originated parameters (audio-adapter slot parsers → crew_console → the wire)

`audio-adapter/src/vocabulary.py`'s new slot parsers (`parse_heading_deg`, `parse_turn_relative`,
`parse_speed_value`, `parse_altitude_value`, `parse_altitude_step`) concatenate consecutive
digit-words with `_read_digits_after` with **no length cap** — a long enough spoken digit string
produces an arbitrarily large Python `int`. This cannot crash anything: Python ints never overflow,
and every one of these values is eventually range-checked at the one real boundary
(`api/server.py`'s `_optional_bounded_field`/the closed-vocabulary checks above) before it ever
reaches the wire. Traced the failure path for a rejected value: `AircraftLayerClient.
write_ai_pilot_goal` raises `AircraftLayerError` on the `400`; `body.py`'s `_apply_ai_pilot_wheel_
goal` catches exactly that exception around both call sites (`:3365`, `:3388`) with
`logger.warning(..., exc_info=True)` and continues the poll — confirmed by reading the except
clauses, not inferring them. A nonsense spoken number degrades to "nothing happened, logged",
never a crash. (One correctness-only quirk, not a security finding, noted for Reviewer below.)
`parse_heading_deg` itself does cap at `<= 359` before returning; the others rely entirely on the
downstream HTTP bound, which is sufficient given the above.

### The seat gate

Confirmed by reading `run_ai_pilot_wheel`/`update_ai_pilot_wheel_overlay` directly: the entire goal-
tick/HVRT-tick machinery (`ai_pilot_goal_tick`, `ai_pilot_goal_tick_hvrt`) is reachable only through
`update_ai_pilot_wheel_overlay`, which returns immediately `if not ai_pilot_parked_active`.
`ai_pilot_parked_active` is set in `run_ai_pilot_wheel` from `ai_pilot_park_rising(..., in_operator_
seat and stick_park or nil)` — `in_operator_seat` is the camera-derived seat gate, unchanged by this
feature. Leaving the operator seat (or never having been parked) clears every goal field the same
frame (`:1135-1149`) and presses nothing. A forged/hostile `ai_pilot_goal` command received while
unparked sets inert table fields that are discarded on the very next tick — no effector action
without the seat gate, confirmed structurally, not just by absence of a counterexample in testing.

### Dependencies

No new package anywhere in this diff (checked `git diff --stat 370f37c0...09d25186` for any
`pyproject.toml`/lock file — none). `audio-adapter/src/command_matcher.py` and `vocabulary.py`'s new
code is pure-stdlib `re`/string logic, no new import.

### Prompt injection

No LLM-facing surface in this diff — the goal channel is a closed, enumerated command/numeric wire
format end to end (HTTP JSON → UDP JSON → Lua dispatch table), never free text reaching a model
prompt. Not applicable to this feature.

### Verdict

**APPROVED.**

### Required Fixes

None blocking. `[[AC-B14]]` (filed, not blocking — see above) is the one real gap found, and it
does not expand this project's already-accepted local-actor trust boundary (`cockpit_switch`).
`[[AC-B11]]`'s unbounded-`Content-Length` pattern now also covers `/command/ai_pilot_goal` —
noted in that entry's own correction, not re-filed.

### Passed to Reviewer

- `body.py`'s `_apply_ai_pilot_wheel_goal` sets `runner.ai_pilot_goal_last_sent_seq = final_goal.
  goal_seq` even when `write_ai_pilot_goal` raised and was caught (`:3375-3377`) — a goal rejected
  by the HTTP boundary (e.g. an out-of-range spoken number) is marked "sent" and will not be
  retried on the next poll unless some other state change bumps `goal_seq` again. Correctness/
  player-experience question (does a rejected voice command silently never reach the aircraft
  again), not a security finding — no verdict given.
