---
name: reference_sim_controlapi_doc_naming
description: Sim_ControlAPI.md documents Hook-state functions under the name "Sim.*"; every deployed Hook script in this repo calls the real global as "DCS.*" (require("DCS")). Same table, doc uses the old/generic name.
metadata:
  type: reference
---

**Fact (confirmed by cross-reading, 2026-10-19):** `aircraft-layer/research/reference/Sim_ControlAPI.md`
documents the Hook-state simulation-control API entirely under the prefix `Sim.*`
(`Sim.setUserCallbacks`, `Sim.getRealTime`, `Sim.getMissionName`, `Sim.getCurrentMission`, etc.),
including in its own worked example (`test.onSimulationStart()` calling `Sim.getMissionName()`).

Every Hook script actually shipped in this project (`petrobrain-f10-commands-hook.lua`,
`petrobrain-line-of-sight-hook.lua`, `petrobrain-api-surface-probe-hook.lua`, and six others) does
`local DCS = require("DCS")` and calls members as `DCS.getRealTime()`, `DCS.setUserCallbacks(...)`.
This has never failed in production across nine scripts — `DCS.getRealTime()` and
`DCS.setUserCallbacks()` are both live-confirmed many times over.

**Why:** the doc's `Sim.*` prefix is almost certainly the table's documentation-era/internal name;
the real global this build's Hook state binds it to is `DCS`. Not two different objects — one
renamed between doc and shipped build (or the doc never used the shipped name to begin with).

**How to apply:** when `Sim_ControlAPI.md` documents a Hook-state function under `Sim.*` that this
project has not yet called (e.g. `Sim.getCurrentMission()`, `Sim.getMissionFilename()`,
`Sim.getMissionResult()`), treat its *existence* and *signature* as doc-level evidence only — write
the real call as `DCS.<name>()` by the naming convention above, but still mark "does it actually
return what the doc says" as unverified until a live probe confirms it, per
`aircraft-layer/research/2026-10-19-theatre-detection-at-mission-start.md`. The convention is strong
evidence, not proof, for any specific function the doc lists but this project hasn't yet called.
