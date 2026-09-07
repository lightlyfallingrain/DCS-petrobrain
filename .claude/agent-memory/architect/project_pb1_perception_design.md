---
name: pb1-perception-design
description: PB-1 (Petrobrain Runtime first perception milestone) design — spike-before-tier-commitment, PerceptionSource abstraction, omniscience-avoidance mechanism
metadata:
  type: project
---

Plan: `plans/pb1-perception-logger/plan.md` (2026-09-07, final version after 3 investigator
sessions same day). Builds on `aircraft-layer/research/2026-09-07-petrovich-perception-export.md`.

**Process note worth repeating**: my first pass at this plan committed to Tier 3
(`LoGetWorldObjects` + heuristic proxy) as the build target without running a live-DCS spike
first. The coordinating agent corrected this — plan around a proof-of-concept before locking in
an architecture, not just a plausible desk-research design. I unstaged/held that draft and
launched Investigator for an actual POC pass instead of proceeding. Two more investigator
sessions that same day materially changed the picture (see below) and the final plan reflects a
different sequencing than my first draft would have. **Lesson: when a design decision hinges on
an empirically-testable unknown, get an agent to test it (or hand the user a cheap test) before
committing resources to the more expensive of two branches — don't design around the
untested assumption.**

**Investigation arc (same day)**:
- Session 1: falsified `get_param_handle` for HelperAI; found named `controllers`
  (`middle_list_text`, `az_text`, etc.) architecturally matching `list_indication`; confirmed no
  `range_m` field exists anywhere in Petrovich's UI (any tier needs external range derivation).
- Session 2 (first POC attempt, still no live DCS access): found real production code
  (`asherao/DCS-ExportScripts`, LGPL-3.0) calling `list_indication(8)` from Export.lua on the
  Mi-24P for a different indicator (kneeboard) — confirms the *mechanism* works from Export.lua
  for this aircraft, and gave the exact wire format (`-----...-----\n<Key>\n<Value>\n` repeating
  string blocks). This materially de-risked Tier 1 (down to one unknown fact — HelperAI's device
  ID — plus one behavioral unknown), which is why the final plan sequences a cheap live spike
  before committing to either tier, rather than building Tier 3 outright.
- Session 3 (user pasted a previously-403'd forum thread): confirmed `LoGetWorldObjects` returns
  **global, unfiltered multiplayer ground truth by default**, no built-in own-aircraft filter.
  This raises the stakes on Tier 3's detectability gate if that tier ends up shipping — it's the
  *only* thing preventing omniscience, not a refinement.

**Final plan structure**: build the `PerceptionSource` protocol, the aircraft-layer HTTP client,
BL-0 replay harness, and the range-derivation geometry helper (shared by every tier — none has a
range field) tier-independently first. Then run one cheap live spike (retrieve HelperAI's device
ID from the Windows box, probe `list_indication` against it with a real tracked target) to decide
which concrete `PerceptionSource` gets built: `petrovich_feed.py` (Tier 1) if the spike succeeds,
`proxy.py` (Tier 3, LOS-detectability-gate + separate degradation step) if it doesn't. A
throwaway fake-other-tier smoke test proves the interface is genuinely tier-agnostic before
calling PB-1 done.

**Key structural point carried from the first draft**: omniscience avoidance for Tier 3 needs
two separate steps, not one filter — a detectability gate (whether an object appears at all) and
a degradation step (what gets reported once detected: category-level classification, confidence
scaled by range, position re-derived noisily rather than copied from ground truth). Without the
second step, LOS-filtering alone is still omniscience in spirit.

**Licensing note**: recommend reimplementing DCS-ExportScripts' small wire-format-parsing
pattern rather than adopting the LGPL-3.0 framework, consistent with `aircraft-layer/CLAUDE.md`'s
existing stdlib-only/"deliberately dumb" Export.lua policy — flagged as a decision, not asserted
as settled.

Open decisions carried into the plan: body-layer subproject creation now (assumed yes per
`plans/body-layer/plan.md` §10 but never confirmed), bearing reference (true vs. magnetic,
project-wide deferred decision that can't be deferred further here), which box runs body-layer,
fixture gitignore boundary.

Related: [[project_body_layer_api_decisions]], [[project_aircraft_layer_architecture]].
