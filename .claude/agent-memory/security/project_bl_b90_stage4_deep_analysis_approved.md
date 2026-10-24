---
name: project-bl-b90-stage4-deep-analysis-approved
description: BL-B90 Stage 4 (readback by need) deep security analysis -- the one required plan-review change (isfinite/non-bool guard on the one-shot read_args response) was implemented and tested on both the collector and body-layer sides, with a real mutation test (E9); everything else held up directly against code. APPROVED.
metadata:
  type: project
---

Deep analysis at `2b742cf3`, following [[project_bl_b90_stage4_readback_by_need]]'s plan review
(required change: finiteness/non-bool guard on `AircraftLayerClient.read_args`'s response before
it reaches `cursor.snapshot`).

**Verified fixed on both sides, not just the one the plan review named:**
- Collector (`arg_read_broker.handle_reply_line`) validates `"values"` via
  `schema.parse_arg_values` -- the **same** function the continuous feed's `WatchedArgsState.
  from_dict` already used, now shared rather than duplicated.
- Body-layer (`aircraft_client.read_args`) independently re-validates the HTTP response: finite,
  non-bool, key range, ≤64, **and** (stricter than asked) every key must be a member of the `args`
  actually requested -- rejects an unrequested/extra key too.
- `test_aircraft_client.py::test_read_args_rejects_a_malformed_response` is a real mutation test
  (named "security plan review, E9" in its own docstring), parametrized over nan/inf/bool/bad
  key/out-of-range key/unrequested key -- each asserts `AircraftLayerError`. Worth checking this
  exists and is parametrized, not just present, next time a plan review's required change is
  verified at deep-analysis stage.

**What else held up directly against code** (confirming [[project_bl_b90_stage4_readback_by_need]]'s
design-soundness claims rather than re-trusting them):
- `Export.lua`'s `parse_arg_list`/`MAX_READS_PER_FRAME` admission -- whole-op reject, per-frame cap
  drops excess at `debug_log` without blocking the drain loop, `watch_args` left deliberately
  uncapped per-frame (O(1), no device read).
- `load_polled_config` (local TOML, not network input) -- D5 non-fatal on bad/missing file,
  required args never dropped on the 64-arg cap, overflow config entries dropped from the end with
  a logged error.
- `/cockpit_switch/latest` removal is clean -- grepped the full tree, no live route/handler
  remains, only docstrings/tests noting its removal.
- `send_watch_args`/`send_read_args`'s f-string JSON construction is safe because both
  interpolated ids are pre-validated to `[A-Za-z0-9_]{1,16}`/hex-only before reaching this method --
  worth checking the *validator*, not the interpolation site, whenever a hand-rolled JSON builder
  shows up in this codebase (Export.lua does the same thing for the same reason).

**Nothing new filed.** The plan-review required change was a blocker, now resolved in code, not a
backlog item. The one pre-existing low/low finding this stage touches (`AC-B11`, unbounded
`Content-Length` on all POST handlers) already named both new endpoints before this stage existed
-- no new filing needed.
