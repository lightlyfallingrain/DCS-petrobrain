## Security Deep Analysis: fix-ai-wheel-pilot-seat-gate

Mode 2, batch of one (single bug-fix commit). Branch `fix/ai-wheel-pilot-seat-gate`,
`53104a49` on top of `main` `11e40eb4`. Scope: `git diff main...53104a49`.

### Dependency Status

No dependency change.

### What changed, in security terms

`Export.lua`'s `ai_pilot_wheel.lua` now calls `LoGetCameraPosition`/`LoGetSelfData`/
`LoGetADIPitchBankYaw` each frame to decide which seat the player occupies, and gates
driving DCS device 30 (the AI-pilot wheel) on the player being in the operator seat. Two
diagnostic fields, `apw_seat` (string) and `apw_cam_fwd_m` (number), are added to the
existing 5 Hz status push over the existing loopback socket to the collector, carried
through `aircraft-layer/src/schema/ai_pilot_wheel.py` and served on the existing LAN
`GET /ai_pilot_wheel/latest`. Export version pair bumped (`2026-11-16b` → `...16c`) in
both `Export.lua` and `collector/server.py`, consistent with the project's version-match
convention.

This is a correctness/safety fix to prevent Petrovich from pressing cockpit buttons that
belong to a wheel the game is not currently showing to this seat — not a new capability,
and not a new write path. Confirmed no new inbound surface:

- No new socket, listener, or command channel. The only DCS-side additions are **reads**
  (`LoGetCameraPosition`, `LoGetSelfData`, `LoGetADIPitchBankYaw`) of local, non-player-
  controllable sim state — not inputs an external actor on the LAN or a malicious
  dependency could feed.
- The only change to the write side (`GetDevice(30):performClickableAction`) is a new
  **gate that reduces** when it fires (adds `in_operator_seat` to the existing park
  condition) — it narrows the existing capability, never widens it.
- The only wire-format change is two more optional fields on an **existing** unauthenticated
  LAN GET endpoint, in a project whose threat model already accepts that posture
  (single-user, LAN-only; root `CLAUDE.md`). Both new fields are scalar diagnostics
  (a seat label, a forward offset in metres) with no path/identifier/credential content.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua:362-379` (`ai_pilot_update_seat`) | New DCS-API reads driving a security-relevant gate | `safe_call` (`pcall`-wrapped) around every new engine call; every field is `type(...)`-checked before being indexed or compared (`ai_pilot_seat_from_camera`'s guards at lines 335-344). An error, a `nil` return, or an unexpected shape from any of the three new calls degrades to "no reading" (seat holds its last known value), never a crash of the per-frame poll loop and never a Lua error propagating out of `run_ai_pilot_wheel`. Matches the project's existing posture for every other `safe_call`-wrapped engine read in this file. | None. |
| `aircraft-layer/src/schema/ai_pilot_wheel.py:96,110-122` (`apw_seat`/`apw_cam_fwd_m` parsing) | Wire boundary number/string parsing from an untrusted-by-posture LAN-facing feed | Both new fields follow the existing `isinstance`-checked, `None`-on-absence pattern already used for the other eight optional fields in this schema. `apw_cam_fwd_m` goes through `float(raw_number)` only — **not** `int(...)` — after an `isinstance(raw_number, (int, float))` check that explicitly excludes `bool`. This is the same wire-boundary shape flagged project-wide in `.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lan_boundary.md` (an `int()` conversion on a JSON-parsed NaN/Infinity raises `ValueError`/`OverflowError` outside the module's own `*ParseError`), but that failure mode requires an `int()` call; `float()` never raises on NaN/Infinity, so this specific instance is not exploitable. Checked for completeness against the recurring pattern, not because this diff repeats it. | None — false positive against the recurring pattern (confirmed: no `int()` conversion on this field). |
| `body-layer/src/belief/ai_pilot_wheel.py` | Downstream consumption | `advance_parked_flight_state` does not read `apw_seat`/`apw_cam_fwd_m` at all yet — they are diagnostic-only on the wire and in the schema, with no consumer. Nothing to assess on the consuming side. | None. |
| Full-tree `security-grep` sweep (type/lint suppression, error suppression, hardcoded credentials, `eval`/`exec`/`loadstring`/`dofile`, `net.dostring_in`, subprocess/`os.execute`, network APIs, unbounded reads, file writes, `raise`/`assert`) | Pattern sweep across every changed file | No hits in any changed line of this diff for any category. | None. |

### Passed to Reviewer

(Nothing — the seat-boundary geometry, `Views.lua` eye-point constants, and the behaviour of
the takeover state machine across a seat switch are player-experience correctness, already
covered by the plan's own test suite (`TestSeatFromCamera`, `TestSeatGate` in
`test_ai_pilot_wheel_lua.py`) and this project's Reviewer role, not security.)

### Verdict

APPROVED

### Required Fixes (if any)

None.
