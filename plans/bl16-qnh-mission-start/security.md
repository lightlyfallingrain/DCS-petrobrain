## Security Deep Analysis: BL-B118 (operator altimeter QNH sync at mission start)

Mode 2, after Reviewer's APPROVED (including the "Re-review" fix round), before DoD. Batch: this
feature's own 3 implementation stages (no other stage pending). Code scope:
commits `276fdce8`..`f9e084ad` against `5f57b54a` — merges of `main` in that range (the AC-B12
Export.lua module split) are unrelated and already have their own `plans/ac-b12-export-modules/
security.md`; not re-reviewed here.

### Dependency Status

No dependency change. `body-layer/pyproject.toml`'s only diff in this range is a `[tool.pytest.
ini_options] markers` entry for a `slow` test marker — test infrastructure, not a package.

### Threat model applied

Single-user, LAN-only. The two realistic attackers (per the project's security scope) are
malicious code in a dependency (ruled out above) and an infected LAN machine scanning ports / able
to intercept traffic. This feature introduces no LLM-reachable surface at all — no brain-layer
involvement, so prompt injection is not applicable here.

### What a LAN port scanner reaches, traced end to end

- `petrobrain-mission-start-hook.lua`'s `sendMissionStart` sends UDP to `127.0.0.1:7799` only —
  not LAN-reachable. `MissionStartReceiver` (`aircraft-layer/src/collector/mission_start_receiver.
  py`) also binds `127.0.0.1` — unchanged by this feature, confirmed still loopback-only. A LAN
  attacker cannot inject a `qnh`/`atmosphere_type` value at this hop.
- The actual LAN-facing surface is `GET /mission_start/latest` (`aircraft-layer/src/api/
  server.py`, `DEFAULT_HOST = "0.0.0.0"`, unchanged — confirmed, not newly exposed by this
  feature). It is read-only and serves whatever `MissionStartEvent` the loopback-only receiver
  already validated and cached — under normal operation an attacker reading this endpoint learns
  the mission QNH, nothing more. The only way a malicious `qnh` reaches body-layer through this
  hop is a LAN peer able to intercept/spoof that HTTP response (ARP spoofing or similar) — the
  same pre-existing MITM exposure every other `AircraftLayerClient` GET already has, not a new one
  this feature creates.
- `POST /command/cockpit_switch` (reused, not added) is device 42/cmd 3001 unlocked to the whole
  `cockpit_switch` op's pre-existing "deliberately broad" posture (`BL-B66`, user direction
  2026-10-21) — this feature writes through it but adds no new reachable op.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `petrobrain-mission-start-hook.lua` `resolveQnh`/`resolveAtmosphereType` | `net.dostring_in("scripting", "return env.mission.weather.qnh")` / `...atmosphere_type` | Fixed literal strings, confirmed by reading the file — no interpolation, no mission content or network input reaches the evaluated code. `type(result) == "number"` rejects non-number results (string, table, nil); a non-numeric or missing value correctly yields `nil`, sent as JSON `null`. Same shape as the existing `resolveTheatre()`. | None — clean |
| `aircraft-layer/src/schema/mission_start.py:97-109` | `qnh`/`atmosphere_type` field validation in `from_dict` | `qnh`: `isinstance(qnh, bool) or not isinstance(qnh, (int, float))` rejects strings/bools/etc., then `float(qnh)` — uses `float()`, not `int()`, so this does **not** hit the project's known `int()`-on-NaN/Infinity `ValueError`/`OverflowError` gap (`.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lan_boundary.md`). `atmosphere_type`: same bool-exclusion pattern, `isinstance(..., int)`, no `float()`/`int()` conversion at all since it's stored as given. A malformed value raises the module's own typed `MissionStartParseError`, caught by `mission_start_receiver.py`'s `_handle_datagram` and dropped/logged at debug — does not crash the receive loop. | None — clean, follows the known-safe pattern |
| `body-layer/src/aircraft_client.py:272-289` `get_mission_start_latest` | LAN-facing response parsing | Only checks the top-level JSON value is a dict or `None`; per-field types are not re-validated at this hop (same posture as the pre-existing `theatre`/`sequence` fields — not a regression this feature introduces). The actual field-level guard for the new fields lives in `body.py`'s `_maybe_start_altimeter_qnh_sync` (next row). | None — consistent with existing seam posture |
| `body-layer/src/body.py:3041-3072` `_maybe_start_altimeter_qnh_sync` | `isinstance(event_qnh, bool) or not isinstance(event_qnh, (int, float))` before `float(event_qnh)`; `event_atmosphere_type` only ever reaches a `logger.info("...%r...", ...)` call | A non-numeric/missing `qnh` clears the sync to `None` rather than raising — no crash path reaches the poll loop from a malformed `GET /mission_start/latest` response. `atmosphere_type` is never type-checked at this hop, but its only consumer is a `%r`-formatted log line, which is safe for any Python object (no eval/exec, no crash on an unexpected type/shape). | None — malformed input cannot crash the collector or body, confirmed |
| `body-layer/src/belief/altimeter_qnh_sync.py:158-212` `_clamp`/`start_altimeter_qnh_sync` | `target_mmhg = _clamp(qnh_mmhg, 670.0, 790.0)` where `_clamp = max(lo, min(hi, value))` | Verified by direct interpreter test: `+inf` clamps to 790.0, `-inf` clamps to 670.0, correctly by design. `NaN` also resolves to 790.0 and does not propagate — but only as an accident of `min`/`max` argument order (Python's NaN-comparison semantics), not a designed `math.isfinite` guard — same incidental-guard shape already on file for `position_belief.py` (`.claude/agent-memory/security/project_nan_comparison_incidental_guards.md`). A QNH outside 670-790 (finite or not) never drives the knob outside that window, confirmed. | Filed as **`[[BL-B120]]`** (low probability × low impact — not blocking) |
| `body-layer/src/belief/altimeter_qnh_sync.py:215-314` `advance_altimeter_qnh_sync` | the closed loop's write bound | Both write branches (gain-based and the `else` calibration-step probe) are clamped to `±ALTIMETER_QNH_MAX_STEP` — confirmed by reading the current code (the gap Reviewer's first pass found, where only the gain branch was clamped, is fixed and re-reviewed; `test_calibration_step_is_clamped_to_max_step_even_when_configured_larger` exercises exactly this). `ALTIMETER_QNH_MAX_ITERATIONS`/`ALTIMETER_QNH_MAX_DURATION_S` terminate the loop (`failed_timeout`) independent of each other, so a dead collector or a pathological knob response cannot hang or write forever. A transient `AircraftLayerError` on read or write is caught narrowly and skips the poll (retried next), bounded by the same wall-clock cap — matches `_check_for_new_mission`'s own transient-error posture. | None — clean, the plan's stated safety claim ("only device 42, command 3001, bounded by ±`ALTIMETER_QNH_MAX_STEP`... cannot write forever") holds in the current code |
| `body-layer/src/belief/crew_console.py:2078-2116` `drain_altimeter_qnh_failed`, `ALTIMETER_QNH_NO_RESPONSE_LINE`/`ALTIMETER_QNH_TIMEOUT_LINE` | speech lines | Both lines are fixed `Final[str]` constants, selected only by `phase` (a `Literal` type, not mission/network text) — no mission-derived or attacker-reachable text is ever spoken by this feature. | None — clean |

### Verdict

**APPROVED**

### Required Fixes

None.

### Findings filed, not fixed now

- **`[[BL-B120]]`** (`body-layer/ROADMAP/BL-B120.md`) — the NaN/Infinity clamp in
  `start_altimeter_qnh_sync` holds by accident of `min`/`max` argument order, not a documented
  `math.isfinite` guard. Not reachable under normal DCS operation (the mission editor does not
  offer a non-finite QNH, and the only untrusted-input path to it would require a LAN MITM of
  aircraft-layer's own HTTP response). Rated low probability × low impact per the Risk
  Communication Format below; filed as a backlog item rather than left in prose, per this role's
  own "every finding gets an ID" rule.

**Finding:** `start_altimeter_qnh_sync`'s clamp stays bounded for NaN/±Infinity only because of
`min`/`max`'s specific argument order, not a stated `math.isfinite` guard.
**Location:** `body-layer/src/belief/altimeter_qnh_sync.py:158-212`
**Probability:** low — requires a non-finite `qnh` to reach this function, which needs either a
hand-crafted mission file (the editor UI cannot produce one) or a LAN MITM of aircraft-layer's
read-only HTTP response.
**Impact:** low — even then, the clamp result and every subsequent write stay inside
`[670.0, 790.0]` / `±ALTIMETER_QNH_MAX_STEP`; no crash, no runaway write, no NaN reaching the
cockpit.
**Recommended action:** file it (done, `[[BL-B120]]`), fix opportunistically next time this module
is touched — not worth a dedicated change now.

Options: (A) Ignore (B) Add to todo.md — **(B) taken**, filed as `[[BL-B120]]` (C) Fix now (D) Stop.

### Passed to Reviewer

None — nothing found here is a player-experience/correctness question outside this role's scope;
everything above is squarely a security boundary (wire parsing, write bounding, speech content).
