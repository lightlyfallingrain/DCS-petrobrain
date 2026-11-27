## Security Deep Analysis: BL-16 mode 1 lift-vector law (LV-0..LV-2) + BL-B139/BL-B140

Mode 2 (per `AGENTS.md` "Recommended Role Sequences" / root `CLAUDE.md` "Agents" — once per
batch of stages actually built together, after Reviewer, before DoD).

Base: `bbddd80b` on `fix/bl16-flight-epoch-bound` (checked out as `bl16-sec` in this worktree,
since this worktree's prior HEAD, `f9864b45` on `worktree-agent-a8b34312a04624afb`, was not an
ancestor of it). Scope: `git diff $(git merge-base main bbddd80b) bbddd80b -- aircraft-layer body-layer`
(61 files, +14575/-3360).

### Dependency Status

No dependency change. No new package in any `pyproject.toml`/requirements file on either
touched subproject.

### Scope read

This batch replaces BL-16 mode 1's old `flight_control` op with `flight_desired`'s one numbered
`flight` channel (`POST /command/flight`, `POST /command/flight_lease`), rewrites the mode-1
control law (lift-vector law LV-0..LV-2, `flight_profile.lua` new), and adds BL-B139 (recovery
wake-kick, a `wake` bool on `ai_pilot_goal`) and BL-B140 (speed-250 default change). Read the
full diff; traced every inbound command surface (`POST /command/flight`, `/command/flight_lease`,
`/command/ai_pilot_goal`'s new `wake` field), the Lua-side listener on loopback UDP 7793
(`commands.lua`/`flight_desired.lua`/`flight_control.lua`), the bounds tables on both sides
(`_FLIGHT_FIELD_BOUNDS`/`_FLIGHT_EPOCH_MAX`/`_FLIGHT_SEQ_MAX` in `api/server.py`,
`FC_LIMIT_BOUNDS`/`validate_flight_fields` in the Lua), and every new numeric conversion at a
boundary this codebase did not itself construct (this project's own recurring-finding category,
`.claude/agent-memory/dod/project_recurring_unguarded_nonfinite_float_before_conversion.md`).

**What this batch gets right, worth recording so it isn't re-derived:** `POST /command/flight`'s
new validation (`epoch`/`seq`/`until`/every numeric field) is `isinstance(..., bool)`-excluding
and `math.isfinite`-checking at every site — the exact shape the recurring-NaN memory prescribes
— and `flight_desired.lua`'s `validate_flight_fields` re-checks the same bounds Lua-side
(`AC-B14`'s own lesson, cited in both the API docstring and the Lua comment), whole-message
reject on any violation. The Lua-side wire *encode* (`push_flight_desired_state`) uses
`fmt_num_or_null`/`fmt_int_or_null`, both of which already carry the `is_finite_number` guard
(`core.lua`, pre-existing, fixed on `fix/handover-ack-seq` before this batch) — so under normal
operation `Export.lua` can never put a literal `NaN`/`Infinity` onto the wire.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/flight_authority.py:294-316` (`decide_carried_value_speech`) | Unguarded `int()` on a value derived from a LAN-HTTP-sourced float with no finiteness check upstream | **Confirmed reachable crash.** `new.alt_m` is `_as_optional_float(sample.get("fd_alt"))` (line 169) — `isinstance`-checked only, no `math.isfinite`. `clamp_altitude(NaN, "agl")` (and `"baro"`) both return `NaN` unchanged, because `NaN < FLOOR_AGL_M` is `False` — the same "incidental NaN-comparison safety" this project's memory already documents, except here it does *not* save the call site: `flown_alt != new.alt_m` is `True` for `NaN != NaN`, so the branch is entered, and `int(flown_alt)` raises `ValueError: cannot convert float NaN to integer`. Verified live in a Python shell against this exact clamp/compare sequence. Caught only by `body.py`'s poll-cycle-wide `except Exception` (`body.py:6379`), so the process survives, but the whole remainder of that poll's processing (including the "You have controls!"/SAU-channel speech ordered immediately after it, `body.py:5600-5635`) is skipped and logged as an unhandled exception — a real defect, not a tolerated one, by this project's own standard (the handler's own comment: "a dead collector is not a defect" implies a *genuine* exception still is). Under the stated threat model the normal producer (`Export.lua`) never emits `NaN` (the encode-side guard above prevents it), but `aircraft_client._get_json`'s `json.loads` accepts the non-standard `NaN`/`Infinity` literals by default, so a LAN actor able to answer this poll's `GET /flight_desired/latest` (the project's own stated attack class: "infected computer in LAN scanning ports"/impersonating an unauthenticated LAN HTTP peer) can trigger this deterministically by including `"fd_alt": NaN` in the response — the exact shape of `BL-B104`'s precedent finding at this project's `GET /world_objects/latest` boundary. | **Fix before DoD.** Guard `new.alt_m`/`new.ias_kmh` with `math.isfinite` before the clamp-and-compare in `decide_carried_value_speech` (or push the guard one layer up, into `_as_optional_float` in `flight_authority.py`, which is the cheaper fix per-boundary and matches the memory's own recommended remedy — a value that fails the finiteness check becomes `None`, the same "nothing received this part yet" state every other field in this mirror already uses for a missing field). `clamp_speed`'s own accidental NaN-safety (argument order happens to keep `MAX_IAS_KMH` rather than propagate `NaN`) is fragile and should not be relied on either — the same guard covers both fields with one change. |
| `aircraft-layer/src/api/server.py` `_handle_command_flight`/`_handle_command_flight_lease` | New `POST` bodies | Reviewed in full — every numeric field is `isinstance(..., bool)`-excluded, `math.isfinite`-checked, and range-bounded (`_FLIGHT_FIELD_BOUNDS`, `_FLIGHT_EPOCH_MAX = 2**53-1`, `_FLIGHT_SEQ_MAX = 2**31-1`); closed-vocabulary fields (`kind`, `turn_style`, `alt_ref`) checked against fixed tuples; `turn` against a closed 3-way int set. No gap. | None. |
| `aircraft-layer/dcs-export/Petrobrain/flight_desired.lua` `handle_flight_command`/`validate_flight_fields` | Lua-side re-validation | Mirrors the API-layer bounds exactly (`AC-B14` posture), whole-message reject (`push_ack(seq, "r", "bounds")`) rather than partial apply; epoch/seq dedup (`epoch ~= fd_epoch` / `seq <= fd_last_seq`) is UDP-safe (silent drop on stale/duplicate, no ack storm). No gap. | None. |
| `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:2762` `handle_flight_lease_command`/`apply_limits_bounds_checked` | Lease bounds check | Whole-message reject on any out-of-bounds `limits` field, including the freshness refresh (`fc_arm_last_t`) — a malformed lease cannot keep the self-arm window open. No gap. | None. |
| `aircraft-layer/src/api/server.py` new `wake` field (`BL-B139`) / `ai_pilot_wheel.lua`'s `extract_json_bool_field(data, "wake")` | Local-actor validation gap, `AC-B14` lineage | API layer type-checks `wake` as strict bool (400 on anything else); Lua side uses the existing `extract_json_bool_field` helper, which returns `nil` (defaulted to `false`) for any non-boolean value rather than crashing or misinterpreting it — no new gap introduced by this field. The pre-existing, already-filed `[[AC-B14]]` gap on this handler's *other* fields (`param`/numeric targets, no Lua-side bound) is unchanged by this batch and was already assessed non-blocking (`.claude/agent-memory/security/project_ai_pilot_goal_lua_dispatch_missing_validation.md` — the local actor already has strictly broader `cockpit_switch` access). | None (no new exposure; `AC-B14` stands as previously filed, not reopened). |
| Command sockets (`commands.lua` COMMAND_PORT 7793, `POST /command/flight`/`/command/flight_lease` forwarding via `command_sender.py`) | Loopback binding | Unchanged from the established architecture — `Export.lua`'s inbound command listener binds loopback-only (`aircraft-layer/CLAUDE.md`); the LAN-facing surface is the read/write HTTP API, not this UDP socket. No gap. | None. |
| `net.dostring_in` / `eval`/`exec`/`loadstring`/`dofile` | Dynamic code execution sweep | None in the diff. The only `dofile`/`loadstring` mentions in touched files are documentation referring to the pre-existing, fixed-string `AC-B12` Export-module loader (`dofile("Scripts\\Petrobrain\\<module>.lua")`, a fixed set of this project's own files, not built from external input). | None. |
| `flight_control.lua:2231,2247` (`io.open(...aircraft_layer_flight_debug.flag...)`, `...aircraft_layer_flight_trace.log...`) | File writes | Fixed paths under DCS's own `lfs.writedir()`, flag-gated debug logging (established project pattern) — never built from external/wire data. No gap. | None. |

### Passed to Reviewer

- The `BL-B140` default-constant change (`retreating_blade_stall_ias_kmh` 250→335 km/h) is within
  its own declared bound (`0.0, 500.0` on both sides) and is a behaviour/calibration question
  (what the aircraft should do), not a security question — no verdict given here.

### Verdict

**NEEDS FIXES**

### Required Fixes

1. `body-layer/src/belief/flight_authority.py` — a non-finite `fd_alt`/`fd_ias` value reaching
   `decide_carried_value_speech` crashes that poll's processing via an unguarded `int()` call
   (lines 294-316, via `clamp_altitude`/`clamp_speed`). Add a `math.isfinite` guard — cheapest
   fix is inside `_as_optional_float`/`_as_optional_degrees_0_360` (lines 65-98) so every numeric
   field on this mirror degrades to `None` ("nothing received yet") rather than carrying a
   non-finite value forward, matching this project's own established remedy for this recurring
   category. Re-entry path per `AGENTS.md`: Implementer → Reviewer (fix review) → DoD.

This finding is a Required Fix, addressed before DoD rather than deferred — no backlog ID filed
per the closing-step rule (only deferred/accepted-risk findings need one; this one blocks).
