---
name: spu8_intercom_plan
description: SPU-8 intercom Slice 2 plan decisions — the wheel-feed misdirect, the two different "no SPU-8 data" defaults, and where each gate actually lives
metadata:
  type: project
---

Planned 2026-10-05 on `plans/spu8-intercom/plan.md` (branch `feature/spu8-intercom`, tip
`f75dab8`). Five stages: SPU-8 state telemetry (aircraft-layer), capture gating via `/ptt/state`
override, playback gating + PCM volume scaling, mission-start co-pilot ICS auto-ON (`Export.lua`
only), on-ground default silent mode (body-layer).

**The dispatch brief's "BL-6 added a wheel-state feed — check what it is" was a false lead.**
BL-6's wheel (`WHEEL_INDICATOR_ID = 10`) is Petrovich's AI-Wheel search-mode indicator, nothing to
do with landing gear/weight-on-wheels. The actual on-ground signal was already flowing the whole
time: `OwnshipState.alt_agl_m`, sourced from `LoGetAltitudeAboveGroundLevel()` via `Export.lua`'s
`alt_agl` field. **Lesson: a prompt's own causal framing ("X added Y, check what Y is") can be
wrong — verify the claim against the code before designing around it, don't just go find Y.**

**Capture gating lives entirely at the aircraft-layer collector, not audio-adapter.** Confirmed by
reading `audio-adapter/src/ptt_source.py`'s `DcsPTT.is_down()` — it reads `payload.get("intercom")`
verbatim off `GET /ptt/state`'s JSON. So overriding what the collector *serves* as `"intercom"`
(AND it with the SPU-8 gate) satisfies "gate capture in the collector, not downstream" with zero
audio-adapter changes. Worth checking this pattern (decided-booleans served pre-computed, consumer
reads them blind) before assuming a cross-subproject gate needs a change on both sides.

**Two deliberately different "no SPU-8 sample yet" defaults, easy to conflate:** `Spu8Cache` empty
→ gate **closed** (fail-safe, used by the real `/ptt/state` override and real `AudioPlaybackSender`
wiring in `__main__.py`). `AudioPlaybackSender`'s own constructor default when no gate provider is
injected at all → gate **always open** (backward-compat for every pre-existing test/call site that
predates this feature). Same codebase, same feature, opposite default — document which one you
mean, every time.

**SPU-8 args, confirmed live 2026-10-05** (`aircraft-layer/research/2026-10-05-spu8-intercom-
write-path-recon.md`): 377 = NET-1 = the spec's "pilot intercom 1 switch" (user-confirmed by
clicking it), not 456 as the roadmap's own table note had guessed. 664 = co-pilot/operator ICS
power, `crew_member_access = {1}`, and a cross-seat write from the pilot seat via
`GetDevice(55):performClickableAction(3015, 1)` **does** succeed — `crew_member_access` gates the
mouse-click registry, not `performClickableAction` dispatch. 457 = pilot SPU-8 volume, continuous
0..1. All three animate through intermediate values for ~0.1s on any transition (including a
code-driven write) — threshold at ≥0.5, never equality, same rule `PttSample` already uses for
arg 738.

See [[project_dcs_driven_los_design]] and [[project_dcs_driven_los_revision]] for the sibling
pattern of "a live cockpit/LOS value replacing a quantised/invented one lets belief carry a value
instead of computing one" — the SPU-8 gate is the same shape: read real cockpit state once, serve
a decided boolean, let every consumer trust it blindly.
