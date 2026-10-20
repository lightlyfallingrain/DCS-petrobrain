---
name: reference-debrief-log-for-firing-event-ground-truth
description: debrief.log's events table carries full initiator/target/weapon/object_id for every shooting/hit/kill event -- the cheapest, no-live-DCS-needed ground truth for "who shot at whom" questions
metadata:
  type: reference
---

`$DCS_SAVED_GAMES_PATH/Logs/debrief.log` is a post-mission Lua table (`events = { [1] = {...}, ... }`)
that DCS writes at mission end/exit. For any "who was X actually shooting at" question, it is a far
richer and cheaper source than either `dcs.log` (the Hook scripts in this codebase log only
per-poll *counts*, e.g. `firing events poll: n=3` — never per-event detail) or a live probe.

**Per shooting-type event it carries**: `type` ("start shooting"/"end shooting"/"hit"/"bda"/"kill"/
"dead"/"shot"), `t` (sim time), `initiatorPilotName`/`initiator_unit_type`/`initiator_object_id`/
`initiator_coalition`, and — critically — `target`/`targetPilotName`/`target_unit_type`/
`target_object_id` **populated on `start shooting` specifically**, not on `end shooting` (which
reads `target='-'`). `weapon` is also present and names the actual gun/round
(e.g. `M61_Vulcan`, `MG3`, `3OF26 (125mm HE)`, `20mm AP`/`20mm HE`, `7.62mm`) — enough to
distinguish which weapon system on a multi-weapon unit fired.

**Worked example, 2026-10-20** (`aircraft-layer/research/2026-10-20-aaa-firing-target-recon.md`):
parsing this file settled, in minutes and with zero DCS access required at query time, a question
("does an M163 Vulcan's `SHOOTING_START` ever carry a target, and does it ever name the player")
that the live collector API and a fresh sortie could have answered too, but far more expensively.
It also let this session distinguish *multiple simultaneous units of the same type* by
`initiator_object_id`/`target_object_id` even though `initiatorPilotName`/`initiator_unit_type` only
ever show the bare type name ("Vulcan"), never the numbered in-mission name ("Vulcan-2") that
`getName()`/the live Hook's `PB_ACTIVE_FIRING_UNITS` key on.

**Parsing recipe**: split on `r'\},\s*--\s*end of \[\d+\]'` to get one block per event, then regex
each field out of the block (`\bt\s*=\s*([\d.]+)`, `type\s*=\s*"([^"]+)"`, etc.) — this file is not
valid standalone Lua (no `return`, defines a bare `events` table), so loading it with a Lua parser
is more friction than block-splitting plus field regexes.

**Caveat, not yet resolved**: debrief.log is DCS's own end-of-mission recorder, a *separate*
implementation from the live `world.addEventHandler` channel this project's Hook scripts actually
subscribe to at runtime. The two are not guaranteed to agree event-for-event — see
[[project_emitter_tracker_watchdog_staleness]] for a case where that gap is the likely explanation
for an otherwise-puzzling live reading. Use debrief.log to establish what the *engine* did; it does
not by itself prove what the live Hook *received*.
