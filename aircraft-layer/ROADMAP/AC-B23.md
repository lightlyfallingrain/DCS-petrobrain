# AC-B23 — `POST /command/reset` is unauthenticated and forces an uncommanded control release

- [ ] **AC-B23 — Consider a sender check (or at least rate-limit/log) on `/command/reset`.** #status/open

Filed from the BL-16 sortie-1120 deep security analysis (`plans/flight-control/security-sortie-1120.md`,
2026-11-20).

`POST /command/reset` (`aircraft-layer/src/api/server.py:_handle_command_reset`, BL-16 sortie
2026-11-20) is shape-validated only (a non-negative whole `epoch`, same posture as every other
`/command/*` endpoint — no project departure here) and, like every endpoint on this API, carries
no sender check at all. Unlike the read-only feeds and the narrow-vocabulary writes
(`petrovich_search`, `watch_args`, `audio/*`), this one's *effect* is unconditional and immediate:
`commands.lua`'s `handle_reset_command` dispatches any accepted `epoch` to both
`flight_control.reset`/`ai_pilot_wheel.reset`, and each `reset()` calls `on_stop()` regardless of
the epoch's value — releasing mode 1's axes back to the player and dropping mode 2's open
goal/CBTM/HVRT state (ED's AI resumes flying), exactly the behaviour the user asked for on a
genuine body-layer restart (`docs/acceptance/2026-11-20-sortie-feedback.md`, "yes let go. A
service reset is error situation, that should not happen.").

Any device on the LAN that can reach this API (every `GET`/`POST` here already assumes that) can
therefore force that same release at will, repeatedly, mid-flight, with no confirmation the
sender is the real body-layer process. This is not a new category of risk on this project's
accepted threat model (root `CLAUDE.md`: single-user, LAN-only, realistic attacker is a
misbehaving/infected LAN box, not a remote adversary; `/command/flight_control`'s own `cmd:
"release"` and every other existing `/command/*` channel already have the same no-sender-check
shape) — but it is the first op whose own stated purpose is "unconditionally let go of whatever
Petrovich is doing," named and reachable on its own, rather than one outcome among several on an
existing channel.

**Probability:** low — requires another device on the same LAN to either guess this fixed
vocabulary or be already running something that probes it; no remote-internet exposure.
**Impact:** low/medium in this project's own terms (a dropped flight-control session, not data
loss or code execution) — bounded by the fact that `reset()`'s effect (hand the stick back,
ED's AI resumes) is itself the safe/accepted fallback the user already specified for a *real*
restart, so a spoofed one degrades to the same already-accepted state rather than a worse one.

**Not blocking this batch's merge** — shape validation is solid (tested: missing/negative/over-max
epoch, non-JSON body, `bool` excluded from the `int` check, 503 when unconfigured), and the
mechanism does exactly what Decision 13/the 2026-11-20 sortie asked for. Filed so the "should this
API have any sender check at all" question — which really applies to the whole `/command/*`
surface, not just this op — is schedulable rather than re-discovered piecemeal per endpoint.
