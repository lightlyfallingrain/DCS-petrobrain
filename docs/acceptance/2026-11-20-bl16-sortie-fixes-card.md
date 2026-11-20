# BL-16 sortie-1120 fixes — test card (2026-11-20)

**Branch to fly: `main`**, once this batch merges. `git checkout main && git pull` in the repo
root.

DoD passed on `fix/bl16-sortie-1120` (tip `bf66cc80`, Reviewer/Performance/Security all APPROVED,
`plans/flight-control/dod-sortie-1120.md`). This batch is seven fixes from the 2026-11-20 sortie
feedback (`docs/acceptance/2026-11-20-sortie-feedback.md`), most of it already flying on `main`
since it was merged ahead of this gate for flight testing. This card is the first chance to check
all seven together, plus the two items this card doesn't cover: the slip-ball probe has its own
card (`docs/acceptance/2026-11-20-slip-ball-calibration-card.md`) and the mission-wide running
command number is still open work on `[[BL-16]]`, not built in this batch.

## Redeploy first

Copy the whole `aircraft-layer/dcs-export/Petrobrain/` folder **and** `Export.lua` to
`Saved Games\DCS\Scripts\` (`Petrobrain/` and `Export.lua` respectively) — standard practice here,
`aircraft-layer/WORKFLOW.md`. Restart DCS (a mission restart alone does not reload `Export.lua`).
Restart the collector and body-layer.

**Pre-flight check**, before takeoff:

```sh
curl -s http://<collector-host>:7791/flight_control/latest
curl -s http://<collector-host>:7791/ai_pilot_wheel/latest
```

Expect both to return a real JSON object, and the collector's startup log to show **no**
`Export.lua version mismatch` warning (`EXPECTED_EXPORT_VERSION = "2026-11-20"` — if this fires,
the deploy did not take and nothing below will mean anything). This is block 10 below, done early
because it gates everything else.

## Test blocks

### 1. Mode 1 take — no pedal kick, wings level

**Do:** unparked, straight and level, "you have controls."
**Expect:** no left-pedal kick on the take; once settled, holding a heading means wings level
(bank ~0°), not a standing bank held by crossed controls. (User's prior flight: left pedal
drifted, right bank compensated, heading held with unwanted yaw+bank.)
**Record:** bank angle a few seconds after the take; any pedal movement you didn't command.

### 2. Re-take

**Do:** "I have controls," then immediately "you have controls" again.
**Expect:** the second take confirms and flies cleanly — not "unable, not ready" while Petrovich
is, in fact, able to take. (User's prior flight: a second take ended in "unable, not ready" while
still taking controls — contradictory outcome.)
**Record:** did the re-take confirm normally, and was there any stray bank/pedal left over from
the first cycle.

### 3. "I have controls" actually frees the stick — open question

**Do:** while Petrovich holds mode 1, "I have controls," then move the stick yourself immediately.
**Expect:** the aircraft responds to your input right away, with nothing fighting you.
**Record:** this is flagged open from the user's own prior flight note — say plainly whether the
handback was clean or whether anything felt like it was still being held.

### 4. Mode 2 — turn after a break, and during a break (latest wins)

**Do (after):** "break turn left," let it finish, then "turn right 30."
**Do (during):** "break turn right," and before it finishes, "turn left 15."
**Expect:** both turns are flown — a heading goal always wins, whether it arrives after a
finished break or interrupts one still running (it ends the break's own press). This was the
batch's root-cause fix: before it, any goal after the first break was acknowledged but never
flown (`apw_goal_seq` stuck at 0).
**Record:** did both cases actually turn, and did the overlay visibly leave CBTM for FLT each
time.

### 5. "altitude 100" sets exactly 100

**Do:** "altitude 100 radar."
**Expect:** the AI-wheel's **set** value reads exactly 100, not a nearby number (the user's prior
flight saw 116 commanded as 100). The **flown** value may wander around it a bit — that's allowed
— but the set value itself must be exact. Watch for a few seconds for hunting (the wheel pressing
back and forth without settling).
**Record:** the set value shown, and whether it ever stopped moving/hunted.

### 6. Collective holding altitude in a break, mode 1

**Do:** mode 1, "break turn left" (or right).
**Expect:** collective is now written in mode 1 — altitude should hold noticeably better through
the break, with less speed lost, than a break flown with collective untouched.
**Record:** rough altitude loss and speed loss through the break, compared with what you've seen
before this batch if you remember it.

### 7. Pedal into turns, mode 1 — note direction

**Do:** mode 1, "turn right 30," then separately "turn left 30."
**Expect:** pedal now moves into the turn (a turn-coordination term, new this batch). Its sign is
an **unmeasured guess** pending the slip-ball calibration flight (separate card) — this block is
exactly how that guess gets checked.
**Record:** which pedal moved for which turn direction, and whether it looked like the right way
to coordinate the turn or the wrong way.

### 8. Unpark mid-turn carries on with mode 2's set targets

**Do:** mode 2 (parked), set speed to something away from current (e.g. "speed 200" while slow),
let the AI start accelerating, then unpark (switch off the AI-pilot wheel in the cockpit) while
still accelerating/turning.
**Expect:** mode 1 picks up flying immediately toward mode 2's **set** heading/speed/altitude —
not whatever the aircraft happened to be doing at the instant of the switch. (User's prior flight:
an unpark mid-maneuver left the controls fixed at their last values with no correction, and the
aircraft crashed as bank increased unchecked.)
**Record:** did mode 1 visibly correct toward the held targets right away, with no dead interval.

### 9. A body-layer restart lets go of the stick

**Do:** while Petrovich holds mode 1 (or mode 2), restart body-layer (Ctrl-C and relaunch, or
your usual restart). Do this somewhere safe — expect an unexpected release.
**Expect:** restarting body-layer makes Petrovich let go: mode 1 frees the axes back to you,
mode 2 drops its goal/CBTM/HVRT state back to ED's own AI. Confirmed by the collector log and
`GET /ai_pilot_wheel/latest` — `apw_goal_seq`/`apw_cbtm_seq` reset to the fresh process's values.
**Record:** did the stick/controls come back to you cleanly on the restart, with no stuck input.

### 10. The stale-Lua warning (optional, already checked pre-flight)

Covered above under "Pre-flight check" — if you skipped it, confirm now that the collector log
never showed an `Export.lua version mismatch` warning during this flight.

## Bring back

- Blocks 1–2: clean take/re-take, no pedal kick, no bank, no contradictory "unable, not ready."
- Block 3: did "I have controls" genuinely free the stick — the open question.
- Block 4: did both after-break and during-break turns fly.
- Block 5: did the set altitude land exactly on 100, no hunting.
- Blocks 6–7: collective's effect on the break, and which way the turn pedal moved.
- Block 8: did the unpark-mid-turn carry on mode 2's targets with no dead interval.
- Block 9: did a body-layer restart cleanly release the controls.
- **Anything that surprises you is worth more than anything on this list.**

## See also

- Slip-ball probe (you fly it, Petrovich doesn't use the reading yet):
  `docs/acceptance/2026-11-20-slip-ball-calibration-card.md`.
- The mission-wide running command number is recorded as open `[[BL-16]]` work, not in this batch.
