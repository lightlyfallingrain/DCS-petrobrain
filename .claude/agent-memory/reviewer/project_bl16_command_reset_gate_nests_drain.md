---
name: bl16-command-reset-gate-nests-drain
description: body.py gates both sends and their own ack-drain calls behind command_reset_confirmed -- a resync gap delays pending take/release resolution, it does not lose it
metadata:
  type: project
---

In `body-layer/src/body.py`'s poll loop, `_apply_flight_requests`/`_apply_ai_pilot_wheel_goal`
*and* their matching `crew_console.drain_flight_control`/`drain_ai_pilot_wheel_speech` calls are
nested inside the same `if runner.command_reset_confirmed:` block, not two separate gates. This is
pre-existing (predates the 2026-11-23 epoch-resync fix, `_resolve_command_reset`) but only became
observable mid-sortie once that fix let `command_reset_confirmed` flip back to `False` after the
initial startup handshake (an Export.lua reload on mission restart re-nils the echoed epoch).

**Why it matters for review**: a pending `flight_pending_take`/`flight_pending_release` already
staged and waiting on an ack does *not* get resolved/spoken while unconfirmed, because the drain
call that would resolve it sits inside the same gate as the send. This is correct (the resolution
is delayed until reconfirmed, including a correct late timeout if `HANDOVER_ACK_TIMEOUT_S` has
since elapsed) rather than lost, but it is easy to misread as "nothing happens to in-flight
requests during a resync" when the real mechanism is "nothing *new* is resolved either, until
reconfirmed." Check both halves (send gate and drain/resolve gate) when reviewing any future change
to `command_reset_confirmed`'s own lifecycle, not just the send side the commit message usually
describes.

**Separately**, `rules.gates._require_controls`'s `commands_ready` check (mirrors
`command_reset_confirmed`) gives any *new* voice command dispatched during the same gap an honest
immediate "unable, not ready" rather than silent acceptance -- that is the half that does cover
new commands; it is the already-pending ack resolution that is the delayed, not lost, half.

See `plans/flight-lift-vector/review-resync-1123.md` for the worked review this was found in
(APPROVED, filed as an optional refinement -- a docstring completeness note on
`_resolve_command_reset`, not a required fix).
