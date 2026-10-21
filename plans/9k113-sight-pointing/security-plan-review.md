## Security Plan Review: 9k113-sight-pointing (BL-B80)

### Dependencies Checked

No new dependency. Confirmed against the plan's "Affected Modules/Files" list and both subprojects'
stdlib-only posture (`aircraft-layer/CLAUDE.md`, `body-layer/CLAUDE.md` "Tech stack"): every new
symbol (`CommandSender.send_sight_target`, the `sight_target` Export.lua op,
`AircraftLayerClient.write_sight_target`, the `sight_effector` conversion functions) is stdlib
Python / hand-rolled Lua, same as every existing op on this channel.

### Design Findings

Threat model is single-user, LAN-only (root `CLAUDE.md` "Agents" / this role's own scoping
section). The realistic attackers are a malicious dependency (ruled out above — no new one) and an
infected LAN box reaching the aircraft-layer's HTTP API or its loopback sockets.

- **New surface is `POST /command/sight_target` (az_cmd, elev_cmd) → a third, narrow UDP op on
  `Export.lua`'s loopback command listener → fixed device 7 / cmd 3060/3061.** This is *narrower*
  than the `cockpit_switch` op this codebase already ships, which accepts **any**
  `(device, cmd, value)` triple with no allow-list — a deliberate exception on record (user
  direction 2026-10-21, `aircraft-layer/CLAUDE.md` "What this is": *"Allow any cockpit switch...
  This is LAN only and switch behaviour is limited to DCS"*). An infected LAN box reaching this API
  already has unrestricted cockpit-write capability through `cockpit_switch`, including the ability
  to press `ShowMenu` (device 30) directly. `sight_target` adds no new category of exposure — low
  risk, consistent with an already-accepted precedent. — **not filed, intentionally**: this is an
  observation that the new surface is subsumed by an already-reviewed, already-accepted broader
  one, not a new finding to track.
- **Validation posture matches the plan's own stated intent** ("same validation/shape posture as
  `/command/cockpit_switch`" — plan, Stage 2): finite-float checks on `az_cmd`/`elev_cmd`, no
  allow-list needed since there is nothing to allow-list (one fixed device/cmd pair). This is the
  right reuse — "do not reinvent the wheel" — of the pattern `_handle_command_cockpit_switch`
  already established (`aircraft-layer/src/api/server.py:607-665`): reject non-numeric/bool/NaN/Inf
  before forwarding. No numeric *bound* (e.g. clamping to the ±60°/+20°/−15° physical range) is
  specified at the API layer, but this is mitigated structurally by the design itself, not
  incidentally: Export.lua never writes the target directly — it rate-limits the commanded value
  toward it by at most `rate × dt` per frame (Stage 2), so an out-of-range or extreme target can
  only ever be *approached*, never jumped to, and DCS's own mechanical stops are what actually
  bound the head's real position (per the explore notes' own direction — "DCS will enforce it").
  An attacker sending `az_cmd=1e30` gets smooth, bounded, physically-limited motion toward a target
  it will never reach — a behavioral oddity at worst, not a safety or stability issue. **Low risk,
  not blocking.** Recommended, non-blocking improvement for the Implementer: clamp `az_cmd`/
  `elev_cmd` to a generous sane range (e.g. ±90° equivalent in raw units) alongside the finite
  check, purely to keep `ai_off_since`'s "commanded is non-trivial" comparison in Export.lua from
  ever reasoning about an absurd magnitude — cosmetic, not a blocker.
- **Loopback-only channel preserved.** The new `sight_target` op rides the existing
  `CommandSender`/`DEFAULT_PORT=7793` loopback UDP socket (`aircraft-layer/src/collector/
  command_sender.py`), not a new listener — consistent with every other op on this channel and with
  the "no new listening socket" posture a LAN port scanner would otherwise need flagging for.
- **Automatic `ShowMenu` press (the AI-on/off detector) is internally triggered, not
  externally commanded** — it fires from Export.lua's own per-frame comparison of the readback
  against the commanded value, not from a value an external caller supplies directly. Nothing in
  the wire protocol lets a LAN caller force a `ShowMenu` press through this new op beyond what
  `cockpit_switch` already permits directly. The self-correction property the coordinator
  amendments require (a false press corrects itself next interval, never latches) is a
  **correctness** property of the detector's behavior in the cockpit, not a security control —
  noted, not reviewed here (see "Passed to Reviewer" below).
- **Unbounded `Content-Length` read.** The new `_handle_command_sight_target` handler will
  reproduce the same `int(Content-Length) → rfile.read(length)` shape every existing POST handler
  on this server already has, with no upper bound. **Already filed and tracked**: `AC-B11`
  (`aircraft-layer/ROADMAP/AC-B11.md`), rated low/low on this project's threat model, not blocking
  any individual feature's merge — this plan would be the sixth endpoint sharing the shape (the
  file's text already anticipated a sixth before `BL-B67`). No new finding needed; worth a one-line
  update to `AC-B11.md`'s endpoint count when this ships, but that is housekeeping, not a security
  gate.
- **No LLM/prompt-injection surface.** This plan touches no text the brain layer or any model
  reads — it is a pure control-loop/effector addition (aim command → rate-limited cockpit write →
  position readback). Not applicable.
- **No secrets/credentials introduced.**

### Passed to Reviewer

The following are player-facing correctness concerns, not security findings — noted per this
role's scope, no verdict given:
- The derived (not independently measured) elevation degree↔raw conversion formula, to be verified
  live at the two mechanical stops (plan's own Risks section, Stage 4).
- The placeholder AI-off-detection timeout/re-press interval values, pending the 2026-10-22 latency
  probe (plan's own Risks section).
- The gyro-alignment window's effect on perception (no sight-tier optic during the ~10 s window)
  and the `home_phase` derivation moving from command-driven to observed-arg-886-driven — both are
  belief/perception-correctness properties for Reviewer to check against the plan's Co-moving
  Fields table.

### Verdict

APPROVED

No dependency change, no expansion of attack surface beyond an already-accepted precedent
(`cockpit_switch`), the one pre-existing pattern this plan reproduces (unbounded `Content-Length`)
is already filed and tracked under `AC-B11`, and the one place a numeric bound could be added is a
non-blocking, cosmetic recommendation given the rate-limiter's structural mitigation. Proceed to
Implementer.
