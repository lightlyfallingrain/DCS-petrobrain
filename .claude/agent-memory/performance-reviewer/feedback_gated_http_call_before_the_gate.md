---
name: gated-http-call-before-the-gate
description: body-layer's poll loop pattern of fetching a readback unconditionally before checking the flag that decides whether it's needed -- found on BL-B90's GET /spu8/state call
metadata:
  type: feedback
---

A per-poll HTTP GET (`aircraft_client.get_*_latest()`) placed directly before a
`crew_console.drain_*` call that itself early-returns on a rarely-true flag still pays the
network round trip every poll, forever -- the early return inside the drain function does not
save the caller from the fetch that already happened.

Found on BL-B90 Stage 2 (`plans/effector-sequences/plan.md`): `get_spu8_state_latest()` was added
to `_run_crew_text_poll_loop` (`body-layer/src/logger.py`) to feed `CrewConsole.
drain_config_error`'s `intercom_open` argument, but `drain_config_error` itself early-returns on
`not self.config_error_pending` -- a flag that is `False` for the entire sortie in the common
case (no bad sequence file). The fetch ran every poll regardless.

**Why:** this is an easy shape to introduce because the natural code order is "compute the input,
then call the function that uses it" -- the guard belongs on the caller's side (`if flag:
fetch(); call(...)`), not only inside the callee, whenever the fetch itself has a cost (a
synchronous HTTP round trip) and the callee's own gate is the rare branch.

**How to apply:** when reviewing a new per-poll `aircraft_client.get_*_latest()` call, check
whether its only consumer is a `drain_*`/handler that itself gates on a flag that is normally
`False`/idle. If so, move the fetch inside that same guard in the caller, not just inside the
callee.

See also [[project_body_layer_poll_loop_diagnosis]] for the poll loop's general shape.
