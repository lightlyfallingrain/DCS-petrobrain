---
name: voice-command-completeness
description: Design decisions from the 2026-09-23 plan that wired up the 20 dead voice tokens — absolute-vs-relative frame rule, reply occupancy, and the F10 rename scoping
metadata:
  type: project
---

Voice is the primary command interface as of 2026-09-23; the F10 menu is allowed to go stale and
"F10 command" is retired as a *concept* name in body-layer while aircraft-layer's transport keeps
its F10 names until the menu is deleted.

**Why:** renaming `F10CommandQueue`/`GET /f10_commands/poll`/the Hook UDP vocabulary costs a
coordinated Windows+Mac redeploy with a stale-copy failure mode, on code scheduled for deletion.
The names are also accurate — they describe the radio-menu transport, which really exists.

**How to apply:** rename the concept in the layer that survives (`handle_f10_command` →
`handle_command`, `_F10_SCAN_REASON`), leave the transport alone, and delete it wholesale later.
The same "rename what survives, not what is being retired" split applies to any future transport
swap here.

---

**The frame rule, and it decides more than it looks like it does.** A spoken *bearing* is absolute;
an *o'clock* is ownship-relative. `AttentionArea` holds both (`sector` absolute, `relative_sector`
ownship-anchored and re-projected per tick), and only `relative_sector` reaches
`logger._active_gaze`/`perception.gaze.ScanPlan`.

**Why:** when the user directed "o'clock granularity is enough" for numeric bearings, the tempting
read was "quantise to the nearest o'clock". That is wrong — it would freeze a heading-dependent
bucket at command time, or follow the nose, both contrary to "scan bearing 320". Nearest *compass
sector* makes `scan_bearing_deg` reduce exactly to `scan_bearing_nw`, which already works.

**How to apply:** before mapping any new direction vocabulary onto existing machinery, ask which
frame the speaker meant, not which bucket is nearest in degrees.

---

**Measured gap worth remembering:** the eight compass scan tokens have never driven gaze.
`_active_gaze` only honours `task.area.relative_sector`, so `scan north` registers an area and a
readback while Petrovich keeps free-scanning. `_SECTOR_LEGS` in `perception/gaze.py` is the seam —
generalising `ScanPlan` to carry o'clock legs directly fixes both this and a future `scan <clock>`
family in one change. See [[project_cones_slice2_design]].

**Also measured:** `MatchResult.bearing_degrees` is parsed correctly in audio-adapter and then
dropped at `transcript_queue.TranscriptEvent`, which carries seven fields. Any "the number is
missing" symptom on a bearing command starts there, not in the matcher.

**Also measured:** contacts are never pruned from `ContactStore`; `certainty_of` reaches `"lost"`
past `LOST_THRESHOLD_S` (120 s) but the record stays forever. Any new aggregate query over
`store.contacts` must filter `"lost"` or it grows monotonically over a sortie.

---

**Command readbacks never budgeted speech occupancy.** `CalloutScheduler.busy_until_sim` is set by
`drain_events` and `note_urgent`, never by an ordinary `_print` — so routine callouts have always
queued immediately behind readbacks. The plan adds `note_reply` (extend via `max()`, never reset)
called from `_print`'s non-urgent path.

**Why:** a reply is an answer, not an alarm — preempting an in-flight contact callout to answer
"report" discards a detection the pilot has not heard.

**How to apply:** `_print` is now the single place that knows the channel is busy; anything that
produces speech outside it is a bug, and BL-10 barge-in will need that property.
