---
name: project_bl_b124_hybrid_channel_unaddressed
description: BL-B124 light-level plan threads light_factor through naked-eye/optic_policy only; body-layer runs a second always-on perception channel (HybridPerceptionSource/list_indication) every poll that the plan never touches or checks for light-sensitivity.
metadata:
  type: project
---

BL-B124 (light level falls off with sun elevation) traced cleanly for the channel it names:
`naked_eye_source.py`/`optic_policy.py`/`visibility.py` all get the new `light_factor` parameter,
and the anchors/end-points/smooth-blend/fail-loud assumptions all settle against the explore-notes
cleanly. E1-E3, E5-E8, E10 are solid.

E4 ("no optic sees an unlit unit in real darkness") is only half-delivered, and nothing in the
plan or its investigator pass noticed: `body-layer/CLAUDE.md` ("What this is") says production
runs **two** concrete `PerceptionSource`s every poll into one `ContactStore` —
`HybridPerceptionSource` (gated on HelperAI's `list_indication`, itself a read of ED's own
engine-native `wDetector`/`Detection.lua` detector per `BL-B22.md`) and `NakedEyePerceptionSource`
(the geometric model BL-B124 touches). The plan's "Affected modules" list and both of its mermaid
diagrams only mention the naked-eye/optic-policy path; `hybrid_source.py` never appears. Whether
ED's own engine detector already degrades with darkness on its own is genuinely unknown — no
investigator note checked it — so this went to the user as a question rather than a Finding
that blocks the verdict (CONCERNS, not MISALIGNED).

**Why this matters for future plan-aligner passes**: body-layer's architecture README describes
itself as a "hybrid design" with two always-on channels feeding one belief store. A plan that
names only one channel in its "Affected modules" is not automatically wrong, but **grep
`body-layer/CLAUDE.md`'s module map for every concrete `PerceptionSource` before accepting that a
perception-behaviour plan is complete** — a stage can deliver its own channel cleanly while a
second, equally-active channel quietly keeps the old (pre-feature) behaviour. This is the same
"easy proxy instead of the real thing" shape the procedure warns about, just at the channel level
rather than the stage level.

See [[project_bl16_vocabulary_grep_stopped_one_layer_short]] for the same "stopped one layer
short" shape in a different subsystem (new vocabulary reaching dispatch but not the recognition
layer's whisper-bias table).
