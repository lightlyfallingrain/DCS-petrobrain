---
name: project_bl_b67_batch_a_deep_analysis
description: BL-B67 (ATGM run) Mode 2 deep analysis, batch A (Stages 1-4 + Stage 0 probes) — APPROVED clean; Stage 5's own-weapon parser bound confirmed not reachable from this diff
metadata:
  type: project
---

`plans/bl-b67-atgm-run/security-review.md`, tip `f2c8c25cd2932d794c9aa6d008e691df20a21e0c`.
**APPROVED**, no required fixes for this batch.

**Why worth remembering**: confirms, by reading the actual diff rather than trusting the plan
review's account, that the two new aircraft-layer endpoints (`GET /payload/latest`) are read-only
GETs and `AC-B11`'s unbounded-`Content-Length` category (5 POST handlers) is genuinely unchanged —
`perception/own_weapons.py` does not exist in this batch (`belief/atgm_run.py`'s own docstring says
"Stage 5, not built"), so the firing-events wire the plan re-review flagged a parser-bound gap on
is simply not reachable from this diff. **That carried-forward finding (own-weapon `<type>` field
needs an independent length/charset bound in `schema/firing.py`, not just the Hook-side
truncation) stays tracked in the plan's own "Required Plan Changes" — do not file a fresh backlog
ID for it and do not re-raise it as a Stage 1-4 finding.** Flag it for whoever runs the deep
analysis on the batch that actually implements Stage 5.

**Mechanically verified rather than taken on the plan's word**: ran the `GETGLOBAL` bytecode
no-hoisting check on `Export.lua` (clean — `push_payload_state` defined below its locals, no own-
helper read as a global), on `Export.probe-weapons.lua` (clean), and — per the "extract the
dostring_in literal" procedure (`aircraft-layer/CLAUDE.md`) — on `petrobrain-damage-events-probe-
hook.lua`'s `EVENT_REGISTER_CODE`/`WEAPON_EXIST_POLL_CODE` literals extracted to their own files
(clean; the only non-stdlib/non-DCS-API globals are deliberate cross-dostring-call state
(`PB_PROBE_KEPT_WEAPON` etc.), same pattern `PB_ACTIVE_FIRING_UNITS` already uses). Also ran a full
`security-grep` sweep (both subprojects + 57 Lua files): zero `eval`/`exec`/`pickle.loads`/
`yaml.load`/`loadstring`/`dofile` hits anywhere; all `net.dostring_in` hits are the expected
`aircraft-layer/dcs-export/` bridge files with fixed string literals, none built from external
input.

**Confirmed `family_of` (`belief/atgm_run.py`) is strictly bounded**: lowercases and substring-
matches a DCS store/type name against a fixed 4-entry dict, returns only `"shturm"`/`"ataka"`/
`None` — no raw DCS text ever reaches `belief/speech.py`'s `render_atgm_launch`, confirming the
plan review's "no prompt-injection surface" claim (also: no LLM/brain-layer call anywhere in this
batch's diff).

See [[project_bl_b67_atgm_run_plan_review]] and [[bl-b67-own-weapon-wire-rereview]] for the
plan-review side of this same entry's story.
