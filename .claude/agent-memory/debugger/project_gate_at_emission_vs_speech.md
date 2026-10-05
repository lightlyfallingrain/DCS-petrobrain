---
name: gate-at-emission-vs-speech
description: body-layer gates placed at event emission (ContactStore.tick) structurally cannot cover group disclosure, which mints no Event — put a spoken-output gate in CalloutScheduler.tick instead
metadata:
  type: project
---

A gate on *what Petrovich says* belongs in `belief/callouts.py::CalloutScheduler.tick`, not in
`belief/contacts.py::ContactStore.tick`'s per-contact blocks.

**Why:** `plans/sortie-2026-09-26-fixes/plan.md` Stage 1 put the cockpit-mask observability gate at
emission, inside `ContactStore.tick`'s fifth and sixth blocks. That reached exactly two event kinds
(`CONTACT_MOTION_CHANGED`, `CONTACT_RANGE_CROSSED`) and nothing else. Nine days later the
2026-10-05 sortie spoke **17 unprompted** lines about 5/6/7 o'clock — body azimuths 150/180/150
against `_CO_PILOT_MASK.rear_cutoff_deg = 130.0` — every one of them either
`CONTACT_CLASSIFICATION_CHANGED` or **group disclosure**. Group disclosure was unreachable *in
principle*: `tick` reads `store.groups` as a second candidate source and mints no `Event` for a
group's trigger (`plans/group-reporting/plan.md` Stage 4), so there is no emission site to gate.
Fixed in `plans/callout-observability-gate/debug.md`.

**How to apply:**

- `CalloutScheduler.tick` is the single speech-time choke point for the **push** path, and
  `CrewConsole.drain_events` is its only caller. Two candidate sources feed it: events and groups.
  A gate must cover both loops or it covers neither.
- **Gate every kind, not a list.** The defect's shape *is* a per-kind list the next new kind
  silently fails to join.
- **Push and pull need opposite answers, and they do not share a chokepoint.** A pilot-initiated
  `report` goes `handle_line` → `_handle_report` → `belief.speech` and touches the scheduler only
  via `note_reply` (occupancy bookkeeping, gates nothing). Never filter the pull path by
  observability — belief survives the aircraft turning away and the pilot *asked*. There it bites
  as an absence claim (`render_no_view`) or freshness phrasing. Cross-plan constraint from
  `plans/crew-query-path/plan.md`. **`_handle_report` is a genuine third producer of masked-hour
  output and is correct** — 3 of the sortie's 20 masked-hour lines, all within 4.4 s of a `report`
  command (`plans/post-review-fixes/explore-notes.md` §9). When counting a push-path reporting
  defect from a speech log, **split by `acted_token` proximity first** or you will over-count it and
  then "fix" a documented decision. 20 vs. 17 here.
- **Deferred vs. lost is a real choice in `tick`.** Skipping *before* the `CALLOUT_MAX_AGE_S` check
  leaks the event forever (nothing ever consumes it); skipping *after* it defers with a bound. Gate
  after. Contrast `WATCH_REPORT_MIN_GAP_S`, which deliberately consumes ("lost, not deferred").
- **Gating at emission can silently *drop*, not defer**, because the `last_emitted_*` snapshot is
  assigned unconditionally after the emit block — so a suppressed event's state is marked as
  emitted and never re-fires. `CONTACT_RANGE_CROSSED` guards its field update for exactly this
  reason; `CONTACT_MOTION_CHANGED` does not. Another reason the speech layer is the better site.
- **Read the bookkeeping, do not recompute the geometry.** `_callout_may_speak` already stamps
  `Contact.last_observable_sim` for *every* contact once per `tick(ownship=...)` (the loop has no
  early `continue`), and `run_once` runs `store.tick` immediately before `drain_events`. So
  `ContactStore.callout_observable` is a pure read. It needs an `_observability_tracked` flag,
  though: without `ownship` the field stays `None` forever, and `None` otherwise means "confirmed
  never observable" — gating on it would silence every test and every ownship-less caller.

See [[project_naked_eye_gaze_gate_is_correct]] (the detection side is fine — this is a reporting
defect) and [[project_watch_report_sounds_live]] (same family: `plans/callout-outside-gaze/debug.md`
diagnosed the *wording* of a watch update, not a gate).
