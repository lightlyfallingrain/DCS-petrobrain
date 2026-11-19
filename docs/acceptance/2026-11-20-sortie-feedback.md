# BL-16 sortie feedback (2026-11-20)

Flown on `main` at `98174b54` (after the handover-ack / wire-format fix), card
`docs/acceptance/2026-11-20-bl16-handover-ack-sortie.md`. User's words, verbatim:

> 1 - in mode 1 if not turning (=maintaining heading) bank angle should be ~0
>
> 2 - mode 2 first a small turn worked then left break worked, then any turn after that was
> acknowledged but nothing happened. on command to turn right 30, overlay stayed in CMBT when
> should have changed to FLT. Possible reason, if completion waits to reach *exact* desired
> value, that may never happen. Everyhing is imprecice.

Not yet explored with the user. Main-loop reading only:

- Item 1 implies that while holding a heading in mode 1, Petrovich flies with a standing bank,
  not wings level.
- Item 2: after a break, the AI wheel stays in CMBT, and every later goal is acknowledged and then
  never flown. The user's hypothesis: the break's completion test waits for an exact value that the
  imprecise sim never reaches, so the overlay never returns to FLT and the goal dispatcher stays
  blocked.

## Explore, 2026-11-20

- User rechecked in the cockpit: the overlay text is **"CBTM"** (the code's spelling). Rules out a
  mode-text mismatch as the cause of item 2.
- Code reading: the break's completion does not wait for a value (it finishes when its press
  releases). A later goal sees the mode is not FLT/HVR and taps short-left to cycle, up to 3 tries,
  then a 3 s cooldown, repeated. Open hypothesis: ED holds CBTM while the player is in the CPG/sight
  view (user's own note, `plans/flight-control/explore-notes.md`), so the cycle never wins.
- Item 1, code reading: there is no slip-ball term on the pedal (never probed), and a break's pedal
  bias is integrated into `t_y` and never unwound, so the heading hold can end up corrected by bank
  with crossed controls.
