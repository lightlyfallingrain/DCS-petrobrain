# BL-16 desired state, Stage 3 — test card (2026-11-20)

**Branch to fly: `feature/bl16-desired-state-s34`** (not yet on `main`). In the repo root:
`git checkout feature/bl16-desired-state-s34`, then your usual redeploy and restarts. Back to
`main` afterwards with `git checkout main`.

**What this checks:** Stage 3's one numbered channel (`POST /command/flight`, `epoch`/`seq`/
`until`/`kind`) replacing the old `flight_control` op; mode 1 now flies the desired state by
stamp (not a push-at-receipt goal); the heading-reference conversion (section 1); the unpark
seed carrying `desired` verbatim, including a standing break; and the voice-take handshake now
driven by `fd_acks` instead of polling `fc_take_seq`. Mode 2 is **unchanged this stage** — it
still flies through the old `ai_pilot_goal`/CBTM channel exactly as before; the numbered channel
only mirrors its exact commanded values into `desired` in parallel (for a later carry), which you
cannot observe from the cockpit directly.

**Known gap, flagged honestly:** the plan's own U1 ("wait for Lua before the readback") is **not**
built for ordinary heading/altitude/speed/turn/break commands in this stage — the rule file still
speaks the readback immediately, optimistically, the same timing as before this plan. Only the
two handover tokens ("you/I have controls") wait for `fd_acks` to confirm, as they already did in
Stage 2. If this card finds the readback latency distracting or wrong, that is `[[BL-16]]`'s own
backlog item to pick up, not a regression to chase here.

## Setup

Air start, straight and level, safe height (50–800 m AGL). Collector address from
`run-scripts/petrobrain.env`:

```sh
source run-scripts/petrobrain.env
while true; do curl -s http://$DCS_COLLECTOR_IP:7791/flight_desired/latest | python3 -c "import sys,json; d=json.load(sys.stdin) or {}; print(d.get('t'), d.get('fd_mode'), d.get('fd_hdg_mode'), d.get('fd_heading'), d.get('fd_hdg_ref'), d.get('fd_alt'), d.get('fd_alt_ref'), d.get('fd_ias'), d.get('fd_turn_rate'), d.get('fd_turn_style'), d.get('fd_epoch'), d.get('fd_last_seq'), d.get('fd_acks'))"; sleep 0.5; done
```

Columns: sim time, mode, heading-mode, desired heading, heading reference, desired altitude,
altitude reference, desired speed, turn-rate override, turn style, epoch, last accepted seq, the
ack ring.

## Steps — mode 1, ordinary commands

For each, say the command, watch `fd_*` update and the ack appear in `fd_acks` (accept, mode
letter `m1`), and compare the cockpit instrument against what was commanded:

1. **"You have controls."** `fd_mode` off → taking → m1; "I have controls." spoken only once the
   ack lands (about a second after the command, occasionally two — U5's own accepted latency).
2. **"Heading 090."** Flown to 090 on the HSI. If the HSI and the overlay turn out to read
   different references (the owed Stages 1-2 check), say what the aircraft actually flew the
   heading command *as* — this settles the one open risk the plan still carries on `HEADING_REF`.
3. **"Climb 50."** then immediately **"climb 50."** again, in one breath. Expect two readbacks in
   the order spoken (+100 total), not the order the acks happen to arrive.
4. **"Speed 200."** Flown smoothly to 200 km/h.
5. **"Turn left."** (no degrees) — a continuous turn; **"stop turn."** — rolls out and holds
   whatever heading it stopped at (watch `fd_heading` update to the roll-out value).
6. **"Break left."** then **"break away."** — latest-wins: the break-away target replaces the
   break's, the aircraft turns to the new target, not both.

## Steps — unpark carrying the desired state (the crash case this stage fixes)

7. **Mid-ramp unpark**: command "speed 200" (or any absolute value) through the AI overlay (mode
   2), then unpark **before** the overlay visibly reaches 200. Expect mode 1 to fly to 200, not
   whatever the overlay had actually reached at the moment of unpark.
8. **Unpark mid-break**: start a break in mode 1, park, then unpark again before it settles.
   Expect mode 1 to **finish** the break (continue turning at the same rate toward the same
   target), not snap straight to the target or hold the measured heading.
9. **"You have controls, heading 090" in one breath** — "I have controls." should be spoken
   first, then the heading readback, never the other order.

## Report back

- Step 2's own finding: which reference ("heading 090" flown to 090 on the HSI, or to 090 ± the
  theatre's variation) — this is the one thing the card still needs to settle.
- For each step: what was said, when (roughly), and whether the aircraft actually did it.
- The readback latency from step 1 (and generally) — does ~1 s feel acceptable, per U5's answer,
  or does it need the faster re-read U5 declined?
- Anything that doesn't match this card.
