# AC-B22 — `ai_pilot_cbtm_last_sent_seq` has no reconciliation against Lua's echoed `apw_cbtm_seq`

- [ ] **body-layer's CBTM dedup counter is not reconciled against `Export.lua`'s own echoed
  `apw_cbtm_seq` on startup/restart.** #status/in-progress — folded into `[[BL-B141]]` 2026-11-27
  (the single running number replaces this channel's own seq), on `feature/bl16-lift-vector-law`. Filed 2026-11-19 at the BL-16 mode 2 Stage
  P3+P4 security deep analysis (`plans/flight-control/security-p3p4.md`). `ai_pilot_cbtm.seq`
  persists in the long-lived Lua VM across a body-layer process restart; `body.py`'s
  `ai_pilot_cbtm_last_sent_seq` resets to `None` (next real send is `1`), with no read of
  `AiPilotWheelState.lua_cbtm_seq` feeding back into it. If Lua's stored value happens to
  coincide with a small number body-layer is about to send, that one real CBTM command (align/
  align-for-launch/break/break-away) is silently dropped as a duplicate — self-heals on the next
  distinct value. A LAN actor who can predict the small, sequential next value could also preempt
  it with a spurious bounded wheel press and/or cause the same drop, but this stays strictly
  bounded by the already-accepted no-auth `cockpit_switch` baseline (arbitrary device/cmd/value,
  no allow-list), which is more powerful. **Confirmed this does not reintroduce `[[AC-B19]]`'s
  "stuck forever" lockup shape** — the Lua-side guard (`cbtm_seq ~= ai_pilot_cbtm.seq`) is
  inequality-based, not ordering-based like `fc_last_cmd_seq`'s `<=`, so there is no ceiling value
  that jams the channel permanently.

  Single-user LAN, low probability, low impact (bounded, self-healing, no escape-hatch
  degradation) — not blocking.

  **Fix**: mirror the `[[AC-B19]]`/BL-16 mode 1 M1+M2 fix's shape — on reconnect/first sample
  after a restart, if `state.lua_cbtm_seq` is not `None` and differs from
  `ai_pilot_cbtm_last_sent_seq`, seed the local counter from it before the next bump, same
  reasoning `body.py:3699-3714`'s `flight_control` reconciliation already documents for the
  sibling channel.
