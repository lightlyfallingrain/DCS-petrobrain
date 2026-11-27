---
name: project_effector_engine_zero_step_delay_same_poll_fallthrough
description: SequenceFile step-delay-s:0 (BL-16 M4 SAU triggers) makes effector_engine.advance's due-time check (now_sim < next_due_sim) fail to break after a write, so all rows of that sequence fire as synchronous HTTP writes within one poll instead of one write per trigger per poll
metadata:
  type: project
---

`effector_engine.advance`'s per-row loop normally enforces "one write per trigger per poll" as a
side effect of `next_due_sim = now_sim + EFFECTOR_SEQUENCE_STEP_DELAY_S` (default 1.0s) landing in
the future, which the next iteration's `if now_sim < cursor.next_due_sim: break` catches. `[[BL-16]]`
M4 (`03b67fcb`) added a per-sequence-file `step-delay-s` header override, and set it to `0` for
both `controls-to-player.md` and `controls-to-petrovich.md` (4 `SwitchRow`s each, the SAU H/K/T/B
channels). With `step_delay_s = 0.0`, `next_due_sim == now_sim` after a write, so the strict `<`
does **not** break — the loop falls through and processes the next row in the **same** `advance()`
call, same poll. Each row's write is a real synchronous LAN HTTP round trip
(`AircraftLayerClient.write_cockpit_switch`), so up to 4 sequential blocking writes can land inside
one poll where previously at most 1 did.

This was deliberate (user direction 2026-11-28: "do not wait between them, just turn all on right
away ... this case is an exception") and is bounded — 2 triggers, 4 rows each, both one-shot
mode-transition edges, never a steady per-poll cost — and `body.py`'s own `_wait_for_next_tick`
already treats an over-budget poll as tick debt rather than a hang, so this was rated MONITOR, not
NOW, in `plans/bl-b141-single-command-seq/performance.md`.

**Reusable lesson for this role**: a `step-delay-s`/spacing override is not just "how often this
row group runs" — check whether the due-time check it feeds is a strict or non-strict comparison,
because a `0` value can silently convert a "spread over N polls" design into "all N writes this
poll." Re-check if a future sequence file reuses `step-delay-s: 0` with a materially longer row
count, or if a flown sortie's slew/effector trace shows a stall on a mode-1 take.
