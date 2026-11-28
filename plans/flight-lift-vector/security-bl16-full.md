## Security Deep Analysis: BL-16 (full feature, all stages, Mode 2)

Scope: the whole of BL-16 as merged onto `feature/bl16-lift-vector-law` — every stage from Stage
P-ICS/P0/P1 through mode 1 M1/M2, Stage 2 (flight-desired-state Stage 2), Stage 3
(flight-desired-state, flight_authority), lift-vector LV-0 through LV-3, M3 (terrain floor), and
M4 (SAU handover). Diff range `1561d3706220ca2c8d63fde496705772c27ccc3f..
cf03d63e7ce34f3f5f493ba05b263677047a2034` (~249 commits, ~28 source files, 8265/1895 lines in
`aircraft-layer/src`, `aircraft-layer/dcs-export`, `body-layer/src`). Branch verified at tip
`cf03d63e7ce34f3f5f493ba05b263677047a2034` (fast-forwarded cleanly from the dispatched worktree's
prior `a29eff71`; `git status --porcelain` clean before starting).

### Threat model applied (newer than this role's own file)

Per user direction 2026-11-28: a LAN peer sending Petrovich a false/malformed action, flight
lease, terrain point, or look direction is **not a finding** — this project's single-user,
LAN-only posture already accepts an unauthenticated LAN actor issuing commands. Only
OWASP-style network-security issues are in scope: code execution, unbounded/malformed input that
crashes or wedges a listener, resource exhaustion, unsafe deserialisation, listeners bound wider
than needed, secrets, dependency issues. **This retires no specific prior finding by name** — the
two BL-16-specific findings on record (`security-m1-m2.md`'s unbounded-`Content-Length`
non-finding and `security-m3.md`'s terrain-relay findings 1/2) were already filed under this same
lens, not the "false command" lens the new rule excludes. Nothing in the per-stage reports assumed
a false-command threat that this rule now removes.

### Method

1. Fast-forwarded the worktree to the expected tip and confirmed clean tree.
2. Read every prior security report touching this feature (`plans/flight-control/security-*.md`,
   `plans/flight-desired-state/` — none filed there, `plans/flight-lift-vector/security*.md`,
   `plans/bl-b141-single-command-seq/security.md`) and this role's own agent-memory for the
   branch (three files: the NaN/int crash, the LV-3 pure-Lua-internal non-finding, the terrain
   relay x/z/count gap).
3. Verified the two "owed before BL-16 DoD" items the roadmap names (terrain relay `x`/`z`
   magnitude bound, 32-point cap enforcement) are **fixed in the current tree** —
   `_terrain_relay_passes_bounds` in `aircraft-layer/src/api/server.py:485-519` now checks
   `math.isfinite` on `x`/`z`/`h`, bounds each to `_TERRAIN_POINTS_COORD_ABS_MAX` (2,000,000), and
   rejects `len(entries) > _TERRAIN_POINTS_MAX_POINTS` (32).
4. Verified the `flight_authority.py` NaN→`int()` crash (agent-memory
   `project_bl16_flight_authority_nan_int_crash.md`) is fixed — `_as_optional_float`/
   `_as_optional_degrees_0_360` (`body-layer/src/belief/flight_authority.py:66-105`) both call
   `math.isfinite` and degrade to `None`.
5. Read the full changed-code diff across `aircraft-layer/src/api/server.py` (616 lines),
   `aircraft-layer/src/collector/{command_sender,server,cache,__main__}.py`,
   `aircraft-layer/dcs-export/Petrobrain/{flight_control,flight_desired,flight_profile,
   ai_pilot_wheel,commands,core}.lua`, `aircraft-layer/dcs-export/Export.lua`,
   `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`,
   `aircraft-layer/src/schema/{flight_control,flight_desired,line_of_sight}.py`,
   `body-layer/src/{aircraft_client,body}.py`, `body-layer/src/belief/{crew_console,
   flight_authority,flight_control,terrain_ahead,effector_engine,effector_sequences,
   ai_pilot_wheel}.py`.
6. Grepped the whole diff for `eval(`/`exec(`/`pickle`/`subprocess`/`os.system`/`__import__`/
   `marshal`/`yaml.load(`/`shell=True`, and separately for secret-shaped strings
   (password/secret/api_key/token=/`BEGIN (RSA|PRIVATE)`) — no hits in either sweep.
7. Confirmed every Lua inbound command listener this feature touches (`commands.lua`'s existing
   UDP listener, the LOS Hook's existing 7797 listener) is bound to `127.0.0.1` only —
   `core.lua:36`, `commands.lua:40/53` — unchanged, and the new `terrain_points` op rides the same
   loopback-bound socket, not a new listener.
8. Traced the new `terrain_points` Hook-side splice (`petrobrain-line-of-sight-hook.lua`'s
   `_applyTerrainPoints`/`SET_TERRAIN_TEMPLATE`): fixed-arity `%d`-only template
   (`2 + 2*32 = 66` conversions, no other specifier), every spliced value through `_safeClampInt`
   (the same total, NaN/±Inf-guarded clamp already verified clean for `probe_points`) — not a new
   injection surface.
9. Traced every new/changed HTTP endpoint's request-body validation path end to end
   (`_handle_command_flight`, `_handle_command_flight_lease`, `_handle_command_terrain_points`,
   `_handle_command_ai_pilot_goal`'s new `wake` field): every numeric field checked for
   `isinstance`+`not bool`+`math.isfinite`+range before use; every string field against a closed
   vocabulary tuple; unknown/malformed → `400`, never a crash or silent pass-through.
10. Checked the one recurring pre-existing pattern this diff's new handlers reproduce —
    unbounded `Content-Length` read (`length = int(self.headers.get("Content-Length", "0"))`,
    `raw_body = self.rfile.read(length)`, no upper bound) — against the already-tracked backlog
    item `[[AC-B11]]`: confirmed by `security-m1-m2.md`'s own prior finding that this is the
    structural shape of **every** POST handler on this server, already filed and accepted as
    low/low, not specific to this feature.

### Dependency Status

No dependency change. No new package, no new install-time script, no new transitive import —
confirmed by `git diff --stat` showing no `pyproject.toml`/`requirements` touched in either
`aircraft-layer/` or `body-layer/`, and by this feature's own prior plan reviews
(`perf-plan-review.md`, the various `security-*.md` reports) recording none.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py` (every `_handle_command_*`, incl. the four new/changed in this feature) | Unbounded `Content-Length` read before `rfile.read` | Pre-existing structural shape of every POST handler on this server, not introduced or worsened by BL-16; already tracked as `[[AC-B11]]`, assessed low/low by `security-m1-m2.md` | None — not re-filed, matches this project's own "don't re-file a pre-existing instance" rule |
| `aircraft-layer/src/api/server.py:485-519` (`_terrain_relay_passes_bounds`) | Previously-flagged missing `x`/`z` magnitude bound and missing point-count cap on the `flight_lease`'s `terrain` relay field | **Fixed since the memory/roadmap note** — `math.isfinite` + `abs(x)/abs(z) <= 2_000_000` + `len(entries) <= 32`, confirmed read live | None — verified fixed, no further action |
| `body-layer/src/belief/flight_authority.py:66-105` | Previously-flagged non-finite-at-LAN-boundary crash (`fd_alt`/`fd_ias` NaN → `int()` `ValueError`) | **Fixed** — `_as_optional_float`/`_as_optional_degrees_0_360` both call `math.isfinite`, degrade to `None` | None — verified fixed |
| `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` (`_applyTerrainPoints`/`SET_TERRAIN_TEMPLATE`) | Third runtime-value splice into `net.dostring_in`'s mission-scripting state | Fixed-arity `%d`-only template, every value through `_safeClampInt` (total/correct NaN/Inf guard) — same already-approved shape as `probe_points` | None |
| `aircraft-layer/dcs-export/Petrobrain/commands.lua:40/53`, `core.lua:36` | Inbound command UDP listener binding | Still `127.0.0.1` only, unchanged by this feature | None |
| `aircraft-layer/src/api/server.py` `_handle_command_flight`/`_handle_command_flight_lease`/`_handle_command_terrain_points`/`_handle_command_ai_pilot_goal` (`wake`) | New/changed wire fields | Every numeric field: type+non-bool+`isfinite`+range; every string field: closed vocabulary; malformed → 400 | None |
| Whole diff (`aircraft-layer/src`, `aircraft-layer/dcs-export`, `body-layer/src`) | `eval`/`exec`/`pickle`/`subprocess`/`os.system`/`__import__`/`marshal`/`yaml.load`/`shell=True` grep | Zero hits | None |
| Whole diff | Secret/credential-shaped strings | Zero hits | None |
| `body-layer/src/belief/crew_console.py`, `body.py` | New brain/LLM/tool-call surface for BL-16 | None added — flight control is fully deterministic, no LLM path touches it; no new prompt-injection surface | None |
| `body-layer/config/rules/flight.lua`, `effector_sequences.py`'s new `step-delay-s` header | New sequence-file/rule-file parsing | Repo-committed config, not LAN-reachable; `step-delay-s` is `float()`+`isfinite`+`>=0` checked | None |

### Retired by the 2026-11-28 threat-model rule

None by name. The threat-model rule excludes "a LAN peer sends a false but well-formed command/
lease/terrain-point/goal and Petrovich acts on it" as a finding category; none of the prior
BL-16 security reports (`security-m1-m2.md`, `security-p2.md`, `security-p3p4.md`,
`security-sortie-1120.md`, `security-handover-ack.md`, `security-batch-a.md`, `security-lv3.md`,
`security-m3.md`, and `bl-b141-single-command-seq/security.md`) filed a finding of that shape —
every blocking/non-blocking finding across them was already an OWASP-style issue (unbounded
input, a missing magnitude/count bound, a non-finite-at-boundary crash). So this pass retires
nothing from the prior record; it confirms the record's own scope already matched the current
rule.

### Interaction check across stages (the reason for a whole-feature pass)

- The mode-1/mode-2 handover boundary (`fd_mode` transitions, `FlightAuthorityState`,
  `CrewConsole.flight_mode()`) is exercised from three different stages (Stage 3's
  `flight_authority`, LV-3's hover/forward blend, M4's SAU trigger wiring) and none of them opens
  a new wire field outside the already-bounded `_FLIGHT_FIELD_BOUNDS`/`_FLIGHT_VALID_KINDS`
  closed vocabularies — confirmed by re-reading `_handle_command_flight` against the full set of
  `kind` values the plan's six mode-2 kinds add; `Export.lua`'s own `handle_flight_command`
  refuses the five not-yet-wired kinds with `wrong_mode`, never executes them speculatively.
- The terrain-floor channel (M3) and the SAU handover channel (M4) are both new per-poll sends on
  the same `flight_lease`/effector-trigger seam; neither introduces a second listener or a second
  validation path — M3's `terrain` field and M4's `CONTROLS_TO_PETROVICH`/`CONTROLS_TO_PLAYER`
  triggers both route through the single existing effector-engine/command-sender seam this
  feature's earlier stages already hardened.
- No stage reintroduces the retired `flight_control` op or a raw-axis wire value — grepped for
  `LoSetCommand` call sites outside `flight_control.lua`'s own per-frame capture+wobble path:
  none found in `src/api`, `src/schema`, or `body-layer/src`, matching the standing invariant
  (`body-layer/CLAUDE.md`, "No LAN message to the aircraft layer ever carries a raw flight-axis
  value").

### Verdict

**APPROVED.** No new exploitable vulnerability across the full BL-16 diff. Both previously-open,
non-blocking findings (terrain relay `x`/`z` magnitude bound, terrain relay point-count cap) are
confirmed fixed in the current tree, and the previously-fixed `flight_authority` NaN/int crash
remains fixed. The one recurring pattern surfaced (`[[AC-B11]]`, unbounded `Content-Length`) is
pre-existing across the entire API surface, already tracked, and not worsened by this feature.

### Required Fixes (if any)

None.

### Passed to Reviewer

- Nothing new identified in this pass beyond what prior per-stage Reviewer rounds already
  covered (M3's `review-m3.md`, LV-3's `review-lv3.md`/`review-lv3-r2.md`, M4's
  `review-m4-sau.md`) — this pass found no correctness/player-experience issue of its own to
  hand off.
