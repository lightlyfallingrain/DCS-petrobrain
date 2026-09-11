---
name: project_bl6_command_channel_design
description: BL-6 command/PendingIntent plan split into a mechanism-agnostic body-layer half and a probe-gated aircraft-layer half, since DCS command feasibility is unresolved.
metadata:
  type: project
---

BL-6 ("Commands and inspect-and-adapt") plan (2026-09-10, `plans/bl6-commands-inspect-adapt/plan.md`)
had to design around a genuinely unresolved question: whether Petrovich's scan behavior can be
influenced from outside DCS at all, and whether any outcome-verification signal exists if so. The
investigator agent (`aircraft-layer/research/2026-09-10-bl6-petrovich-command-feasibility.md`)
found real leads (`Export.LoSetCommand`, a shipped `AI_Wheel` command UI namespaced literally
"Petrovich") but confirmed only file *paths*, not contents — the live probe (reading ~7 Lua files,
testing `LoSetCommand` live) is still unrun as of this plan.

**Design pattern worth reusing**: when a milestone's premise depends on an unresolved DCS-internals
question that even the investigator can't fully close (no live-DCS access from this session), split
the plan into (a) a mechanism-agnostic core that's fully buildable and testable now, and (b) a
DCS-effector stage explicitly gated on a user-run live probe, with the core designed so it produces
real value even if the effector never materializes ("virtual scan": bias an `AttentionArea` +
verify task outcome from belief state, no DCS command required). This avoids blocking the whole
milestone on an answer only a live sortie can give, without silently assuming the answer either way.

**Why:** BL-6's own stated gate ("needs its own Security plan review") only applies to the new
aircraft-layer write channel — but the deeper problem was that the *feasibility* itself, not just
the security posture, was unknown. Resolving feasibility fully requires reading files not synced to
this repo and running a live DCS test; an agent session can't do either without the user.

**How to apply:** next time a plan forks on an unresolved live-DCS capability question, don't
default to "wait for investigator to fully resolve it" — check whether the plan can be restructured
so the uncertain part is a small, isolated, later-addable increment on top of a solid, testable
core. Also: this milestone's tool-set freeze point (BL-7 per `body-layer/ROADMAP.md`,
`scan_area`/`get_task_status`/`cancel_task`) can be satisfied by the body-layer-only half alone,
per the plan's Decisions section — flagged to the user as an open call, not assumed.
