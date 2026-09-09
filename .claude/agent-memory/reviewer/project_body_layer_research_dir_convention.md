---
name: project_body_layer_research_dir_convention
description: DCS-internals verification findings for body-layer/aircraft-layer work are filed in aircraft-layer/research/, not world-model/research/
metadata:
  type: project
---

The root `CLAUDE.md` checklist item "No claim about DCS internals encoded as fact without a
corresponding entry in `world-model/research/`" is written from the World Model Builder's
perspective. In practice, each subproject that does DCS-internals recon keeps its own
`research/` directory following the same dated-findings convention — `aircraft-layer/research/`
is where Investigator has filed PB-1/PB-1.5 findings (`HelperAI`/`Export.lua`/ambient-detection
recon), not `world-model/research/`.

**Why**: `aircraft-layer/research/` findings are about DCS's live scripting/export surface
(HelperAI Lua files, `LoGetWorldObjects`, cockpit params), which is aircraft-layer's domain, not
world-model's (terrain/coordinate/geographic recon). world-model's checklist wording shouldn't be
read as "the only valid research/ directory in the repo."

**How to apply**: when a body-layer or aircraft-layer review surfaces a DCS-internals claim that
needs recording (e.g. a keyword-table coverage validation against a DCS file), point to
`aircraft-layer/research/` with a dated filename matching the existing pattern
(`YYYY-MM-DD-<topic>.md`), not `world-model/research/`.
