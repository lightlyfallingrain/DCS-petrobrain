---
name: bl6-commands-inspect-adapt
description: BL-6 scan_area/get_task_status/cancel_task command lifecycle plus the aircraft-layer petrovich_search command channel
metadata:
  type: project
---

Implemented in full on `feature/bl6-commands-inspect-adapt` (3 commits: body-layer, aircraft-layer,
implementation.md), against the plan's locked 2026-09-11 rewrite (commit `2c98ff9`).

- `belief.tasks.PendingIntent`/`TaskStore`: success check is "any `Contact` inside `task.area` with
  `last_seen_sim > task.created_sim`" via `belief.attention.area_contains` — reuses BL-4's area
  machinery directly, no new geometry.
- `tools.scan_area`'s plan-listed signature omitted `now_sim`; added it anyway since
  `PendingIntent.created_sim`/`deadline_sim` are sim-time by this project's replay-determinism
  convention (never wall clock) — a caller-supplied `now_sim` is structurally required, not optional.
  If a future plan's function signature is missing a sim-time param that every sibling function has,
  treat it as an omission to fill, not a literal spec to follow blindly.
- `cancel_task` removes the registered `AttentionArea` too (plan Decision 3, resolved before
  implementation — no re-litigation needed).
- Live DCS effector trigger lives in `console.py`'s `scan-area` handler (try/except
  `AircraftLayerError`, degrades to "task registered, no live command fired"), never in `tools.py` —
  same split BL-2.5 established for the overlay push. `tools.scan_area` itself stays pure/DCS-I/O
  free.
- `CrewConsole` got a reserved, currently-unread `aircraft_client` field (plan asked for
  "Console.aircraft_client or CrewConsole's equivalent" wiring parity) — no player-facing
  `scan_area`-equivalent utterance exists yet, so nothing reads it. Documented as reserved in its own
  docstring, not dead code.
- `test_tool_api.py`'s "exactly twelve BL-5 tools" assertion was extended to the full BL-6 set — an
  anticipated update per `tool_api.py`'s own "expected to extend TOOL_SET" docstring, not an
  unrelated test rewrite requiring separate permission.
- aircraft-layer: `CommandSender` (mirrors `TextOverlaySender`) deliberately *raises*
  `CommandSendError` on a failed send — the plan's flagged asymmetry from `TextOverlaySender.
  send_line`'s never-raises posture, since a dropped search command is a real behavioral gap.
  `Export.lua`'s new UDP command listener (port 7793, third distinct loopback port) polls every
  frame ahead of the 5 Hz export throttle, so a queued command/pending long-press release is never
  delayed behind telemetry cadence.
- No live DCS session available in this environment — Export.lua changes verified with `luac -p`
  only (no lupa installed either). Stage 6 (live acceptance: real SRCH FWD firing, list_indication(10)
  state transition, task-status eventually succeeded) is the user's own follow-up per the
  execution-boundary rule.
