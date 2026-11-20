# BL-16 desired state, Stages 1-2 — test card (2026-11-20)

**Branch to fly: `main`**, once this batch is merged. `git pull` in the repo root. No deploy
steps beyond the usual: your redeploy script copies `Export.lua` plus the whole `Petrobrain/`
folder, and body-layer's own code from this batch.

**What this checks:** Stage 1, the shadow authority/desired state Lua now reports (`fd_mode`,
`fd_mode_cause`, the desired heading/altitude/speed) against what the cockpit actually shows, and
which heading reference the AI-pilot wheel uses (true or magnetic) — the owed HSI check from BL-16
M0. Stage 2, that `fd_mode` is now the one live mode authority body-layer reads (`flight_mode()`,
"has controls", the readback values) and that losing the stick unexpectedly still gets the urgent
"You have controls!" line. Petrovich does not fly from the desired state yet (that's Stage 3) —
every manoeuvre tonight flies exactly as before; only the *reporting* and *who's declared to be in
charge* changed.

## Setup

Air start, straight and level, safe height (per the operating envelope: 50–800 m AGL). Readout from
the Mac terminal, one line every half second. The collector address comes from
`run-scripts/petrobrain.env`:

```sh
source run-scripts/petrobrain.env
while true; do curl -s http://$DCS_COLLECTOR_IP:7791/flight_desired/latest | python3 -c "import sys,json; d=json.load(sys.stdin) or {}; print(d.get('t'), d.get('fd_mode'), d.get('fd_mode_cause'), d.get('fd_mode_n'), d.get('fd_hdg_mode'), d.get('fd_heading'), d.get('fd_hdg_ref'), d.get('fd_alt'), d.get('fd_alt_ref'), d.get('fd_ias'), d.get('fd_hdg_true_deg'), d.get('fd_hdg_mag_deg'), d.get('fd_overlay_course'))"; sleep 0.5; done
```

Columns: sim time, mode, cause, mode-change counter, heading-mode, desired heading, heading
reference tag, desired altitude, altitude reference, desired speed, measured true heading,
measured magnetic heading, the AI wheel's own overlay course.

## Steps — heading reference (owed since M0)

1. **Steady on heading ~000.** Wings level, no turn, hold a few seconds. Note the **HSI reading**
   and the **time**. Compare against both `fd_hdg_true_deg` and `fd_hdg_mag_deg` at that same time.
2. **Steady on heading ~090.** Same note.
3. **Steady on heading ~180.** Same note.
4. **Park** (hand him the overlay). Once the overlay shows a course, compare **its own displayed
   course** against both `fd_hdg_true_deg`/`fd_hdg_mag_deg` logged at that moment, and note
   `fd_overlay_course` too.
5. *(Optional)* With the 9K113 pointed off the nose, press **align** once while parked. Note the
   time you pressed it and the time `apw_course_text` (or the overlay display) actually changes —
   this is the owed check on the plan's assumed 1.0 s align read delay.

## Steps — handover table (section 2 of the plan)

For each row, read off `fd_mode`/`fd_mode_cause`/`fd_mode_n` and what Petrovich actually says
(if anything):

6. **"You have controls" from the ground/off.** Expect `fd_mode` off → taking → m1, cause `take`
   on each move, silent in between, no urgent line.
7. **Park while flying mode 1.** Expect `fd_mode` m1 → m2, cause `park`, **silent** (U5).
8. **Unpark, normal.** Expect `fd_mode` m2 → m1, cause `unpark`, **silent**.
9. **Unpark too soon after a body-layer restart** (stop body-layer while parked, restart it, then
   unpark before ~3 s). Expect the unpark **refused** — `fd_mode` stays m2 (or goes m2 → off,
   check which), cause `unpark_unarmed`, and the **urgent** "You have controls!" if it does go to
   off.
10. **"I have controls" while flying mode 1.** Expect `fd_mode` m1 → off, cause `release`,
    **silent** (this is the player's own request, not a forced handover).
11. **Seat swap to the pilot seat while parked.** Expect an unpark edge (`fd_mode` m2 → m1 or m2 →
    off per whether armed), same causes as rows 8/9.
12. **A body-layer restart while parked, then unpark.** Expect `fd_mode` to stay `m2` through the
    restart (ED keeps flying), then the unpark hands you the stick with the **urgent** line
    ("you get the stick" per the explore-notes Q6 answer) — check whether the mode-authority
    mirror reports this as `unpark_unarmed` or stays silent; say which you saw.
13. **The second-handover "unable, not ready while holding" case from the 2026-11-20 sortie** —
    take controls, then immediately try a command before the take confirms. It must **not**
    recur: there should be no moment where Petrovich claims "not ready" while he is in fact
    already holding the controls.

## Report back

- For each heading step (1–4): HSI reading, time, `fd_hdg_true_deg`, `fd_hdg_mag_deg`,
  `fd_overlay_course` where applicable. Which one matches the HSI?
- Step 5 (if flown): the align-press time and the readback-change time, and the gap between them.
- For each handover row (6–13): the `fd_mode`/`fd_mode_cause`/`fd_mode_n` sequence you saw, and
  what (if anything) was said, flagged against what the row expects.
- Anything that doesn't match this card, including a silent line where an urgent one was expected
  or vice versa.
