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

**Stage 3b closes the gap the Stage 3 card flagged here**: U1 ("wait for Lua before the
readback") now covers every ordinary `flight_control*` command, in both modes, not only the two
handover tokens. Every heading/altitude/speed/turn/break/level readback — mode 1's own `axes_*`
commands and mode 2's ordinary voice goals (heading/altitude/speed/level flight) alike — now
waits for `fd_acks` to accept its own `seq` before speaking, about a second after the command
(occasionally two, same U5 latency the handover already had). A refusal speaks "Unable, <reason>."
instead of the readback; no ack inside the deadline speaks "Unable, not ready." **Mode 2's HVRT
and CBTM (align/align-for-launch/break) are not dual-written onto the numbered channel yet**
(Stage 4's own work) — their readbacks still speak immediately, unchanged, exactly as before this
plan.

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
2. **"Heading 090."** Flown to 090 on the HSI — both the AI overlay and the HSI read true heading
   (measured, 2026-11-20: `HEADING_REF = "true"` is confirmed, not a placeholder), so no
   conversion applies here.
3. **"Climb 50."** then immediately **"climb 50."** again, in one breath. Expect two readbacks in
   the order spoken (+100 total), not the order the acks happen to arrive.
4. **"Speed 200."** Flown smoothly to 200 km/h.
5. **"Turn left."** (no degrees) — a continuous turn; **"stop turn."** — rolls out and holds
   whatever heading it stopped at (watch `fd_heading` update to the roll-out value).
6. **"Break left."** then **"break away."** — latest-wins: the break-away target replaces the
   break's, the aircraft turns to the new target, not both.
7. **Readback timing**: time the gap between saying "Heading 090." and hearing "Heading 0 9 0."
   back — about one second, per U5's own answer (occasionally two, when a poll's work runs long).
   If it feels distracting rather than merely noticeable, say so in the report; U5 already
   declined the faster re-read for the handover, but this is the first time it is heard on every
   ordinary command, not only a take.
8. **Refusal check (best-effort — hard to force live)**: if a command happens to land right at a
   mode change (e.g. "heading 090" spoken the instant you unpark), you may see "Unable, not
   ready." instead of the heading readback — that is `wrong_mode`/`stale`/`precondition`
   resolving to the one shared wording (3a: "no new spoken wording"), not a bug. Nothing to do
   deliberately here beyond noting if it happens.
9. **Mode 2, same commands**: say "heading 090"/"speed 200"/"altitude 900" while parked (mode 2).
   Same ~1 s readback latency as mode 1. Then **"align"**/**"move left"** (CBTM/HVRT) — these two
   still speak immediately, with no perceptible delay, since they are not on the numbered channel
   yet (the one deliberate asymmetry this card should show).

## Steps — unpark carrying the desired state (the crash case this stage fixes)

7. **Mid-ramp unpark**: command "speed 200" (or any absolute value) through the AI overlay (mode
   2), then unpark **before** the overlay visibly reaches 200. Expect mode 1 to fly to 200, not
   whatever the overlay had actually reached at the moment of unpark.
8. **Unpark mid-break**: start a break in mode 1, park, then unpark again before it settles.
   Expect mode 1 to **finish** the break (continue turning at the same rate toward the same
   target), not snap straight to the target or hold the measured heading.
9. **"You have controls, heading 090" in one breath** — "I have controls." should be spoken
   first, then the heading readback, never the other order.
10. **"Speed 0" in m2 then unpark** (U2's one line). Through the AI overlay, command "speed 0",
    then unpark. Expect mode 1 to fly its own minimum speed, not 0, and to hear "Speed 8 0."
    once, not urgently, right after any mode-change speech (there should be none here — an
    ordinary unpark is silent). `fd_ias` itself should still read `0` (the exact commanded
    value never changes), only what is actually flown is clamped.

## Report back

- For each step: what was said, when (roughly), and whether the aircraft actually did it.
- The readback latency (step 7, and generally) — does ~1 s feel acceptable, per U5's answer, or
  does it need the faster re-read U5 declined?
- Whether a refusal ("Unable, ...") was ever heard in place of a readback (step 8), and what the
  command/situation was at that moment.
- Anything that doesn't match this card.
