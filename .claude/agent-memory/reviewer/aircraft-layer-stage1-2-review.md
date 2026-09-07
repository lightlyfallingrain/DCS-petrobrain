---
name: aircraft-layer-stage1-2-review
description: Review outcome for aircraft-layer stage 1-2 (Export.lua + collector) — approved w/ one minor fix
metadata:
  type: project
---

Reviewed `feature/aircraft-layer-telemetry` stages 1-2 (2026-09-06): scaffolding, Export.lua
push-only kinematic export, schema validation, TCP collector + cache, fixture tests. Verdict:
APPROVED WITH MINOR FIXES.

Plan fidelity was clean — no new deps, loopback-only binding, both DCS-model-time and
wall-clock timestamps present on every sample, no stage-4 API scaffolding built ahead of
schedule. The flagged `LoGetSelfData()` shape unknown was genuinely handled defensively
(pcall + nested-then-flat fallback + fail-to-skip), not scope creep or overkill.

One real bug found independent of the "needs live DCS" exemption: `CollectorServer`'s
accept loop (`src/collector/server.py`) doesn't catch `OSError` around per-connection
handling, so an abrupt disconnect (`ConnectionResetError`, common on Windows when DCS is
force-quit) crashes the whole long-running collector process rather than looping back to
`accept()` as the module's own docstring claims. This is a plain socket-programming gap,
reproducible with a socket pair, not something that needs a real DCS instance to catch —
worth specifically checking for on any future long-running accept-loop code in this
project (the LAN-facing HTTP API in stage 4 is the next place this class of bug could
recur, and that one *is* LAN-facing so the stakes are higher).

See [[feedback_check_agent_memory_staged]] — recurred again here (5th time): implementer's
own agent-memory file was left unstaged alongside the feature diff.
