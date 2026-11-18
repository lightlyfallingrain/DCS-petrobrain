# BL-16 mode 1 (unparked, raw axes), Stages M1+M2: Flight M-A acceptance sortie

**Artifact (cockpit-readable card):** https://claude.ai/artifact/C4TTm4bK2eJLpGqsZ54Qp5
**Card source:** this file.
**Branch to fly:** `main`, after this DoD pass's auto-merge.

What is under test, from `plans/flight-control/plan.md` ("Revised 2026-11-18 — mode 1 (unparked,
raw axes) re-cut", "Flight M-A") and `body-layer/ROADMAP/BL-16.md`'s "Mode 1, Stages M1+M2 — DoD
pass" entry:

- Taking the controls on "you have controls," holding the aircraft's current state (heading or
  turn, altitude trend, IAS) with no jump, and ignoring the physical stick/collective/pedals.
- The five shipped BL-17 flight commands, dispatched to the new raw-axis controller instead of
  the AI overlay: `turn heading`, `turn left/right [NN]` (with no degrees, a continuous turn),
  `alt`/`altitude`, `speed`, `level off`/`stop turn`.
- Giving the controls back with "I have controls," at once, never gated on confidence below the
  confirm floor.
- The silent mode switch under Request Aircraft Control (U5, Decision 24): Petrovich keeps
  flying across a park/unpark, switching silently between mode 1 (axes) and mode 2 (the AI
  overlay) — only "I have controls" (or a forced handover) gives the player the stick back.
- The seat rule (Decision 25): identical behaviour from either seat, including the operator seat
  with the copilot controls unparked.
- The two forced-handover cases: an unpark mode 1 physically cannot fly (hover, below ~80 km/h),
  and U9's "I have controls" said while flying through the overlay.

**Known limits to expect, named up front:**

- **Every control-law gain is a first-cut placeholder.** M0-E (the per-axis step-response
  measurement) was never flown. Expect the response to be gentle, possibly sluggish, and to need
  at least one retune flight — that is what this flight is partly *for*, not evidence of a defect
  by itself.
- **No slip-ball feedback in the pedal channel.** It runs on collective-coupling feedforward
  alone. A yaw wander during a collective change that does not fully coordinate is expected.
- **The terrain floor (M3) and SAU interaction (M4) are not built.** Nothing holds you off rising
  ground yet, and the SAU's own attitude hold is not disabled on take — if K/H/T are on, expect
  possible fighting between the SAU and the new writes (M0-H informs M4, not flown as part of
  this).
- **What would be a real bug, not an expected rough edge:** the physical stick, collective or
  pedals doing *anything* felt while mode 1 holds the controls (E3 — M0-D measured no felt twitch
  on the Mac-side wobble, but not against the merged law's own real output cadence in the actual
  cockpit); any sudden jump at takeover, park, or unpark; a readback that names a value Petrovich
  is not actually flying toward.

**Already verified without a flight** (this DoD pass, from the Mac, no DCS needed): the full
test suites (953 aircraft-layer, 3619 body-layer), `mypy --strict`, `ruff`, and `luac5.1 -p` on
every touched Lua file all pass; the toy-plant control-law suite converges into band with no
ringing for heading/altitude/speed against a first-order toy plant; the bit-exact-at-take and
pause/freeze rows are pinned by Lua-interpreter tests, not reasoned about.

## Do / Expect / Record

1. **Do:** Fly straight and level, ~150 km/h, ~200 m AGL. Say "you have controls." Stir the
   stick, pedals and collective for 60 s.
   **Expect:** "I have controls." spoken once the take lands; the aircraft holds heading,
   altitude trend and IAS; your physical inputs do nothing.
   **Record:** did the readback land immediately or lag; any felt twitch from the controls; any
   drift outside a loose band.

2. **Do:** Say "I have controls."
   **Expect:** "You have controls." at once; the stick is live again immediately.
   **Record:** any delay; whether the aircraft's attitude at handback matches what you felt it
   was doing.

3. **Do:** Enter a 20° bank turn, hand over mid-turn, hold for a few seconds, then say "level
   off" (or "stop turn," whichever the card's rules show as current).
   **Expect:** the turn continues after the handover (not an immediate roll-out); on "level off"
   it rolls out smoothly and holds the heading it stops at — not the heading at the moment of
   handover.
   **Record:** whether the turn continued or was cut short at handover; overshoot/ringing on the
   roll-out.

4. **Do:** Enter a climb or descent, hand over mid-climb.
   **Expect:** the climb continues, then levels off at the altitude it naturally stops at — no
   reversal back toward the altitude at the moment of handover.
   **Record:** the altitude it actually leveled at vs. what you expected; any reversal.

5. **Do:** In sequence: "heading 3 1 5", "turn left 30", "alt 200", "speed 2 0 0", "turn right"
   (no degrees — continuous), then "level off"/"stop turn".
   **Expect:** each readback names the value actually commanded; smooth, non-ringing convergence
   into a loose band for each; the continuous turn holds a steady bank until stopped.
   **Record:** readback accuracy; time to band for each channel; whether the continuous turn's
   bank angle felt reasonable.

6. **Do:** Swap seats (pilot ↔ operator) while Petrovich flies in mode 1.
   **Expect:** no jump in attitude or heading at the swap.
   **Record:** anything felt at the swap.

7. **Do:** From the operator seat, with the copilot controls unparked, repeat steps 1, 2 and 5.
   **Expect:** identical behaviour to the pilot seat — mode 1 is never gated on seat.
   **Record:** any difference from the pilot-seat runs.

8. **Do:** While Petrovich flies in mode 1, press Request Aircraft Control. Wait 30 s. Press it
   again. Then say "I have controls."
   **Expect:** the first press silently switches him to the AI overlay (mode 2) — he keeps
   flying, nothing is said. The second press silently switches him back to mode 1, with no jump
   and the stick still ignored. "I have controls" then hands the player the stick.
   **Record:** anything spoken at either press (should be nothing); any jump at either edge.

9. **Do:** From "player flies," park (Request Aircraft Control). Unpark. Then say "I have
   controls."
   **Expect:** the park silently hands Petrovich the controls through the overlay; the unpark
   silently keeps him flying, now in mode 1, with no jump. "I have controls" then gives the
   player the stick back.
   **Record:** whether the stick is still dead right after the unpark (expected) and whether that
   matches your own intuition for how surprising this is in practice — U5 is a real behaviour
   change from the old mode-2 unpark (which used to give you the stick back).

10. **Do:** Park, then unpark below ~80 km/h (e.g. in a hover).
    **Expect:** an urgent "You have controls!" — mode 1 cannot fly below the minimum IAS, so this
    is a forced handover, not a choice.
    **Record:** whether the call came through clearly and at the right moment.

11. **Do:** While Petrovich flies through the overlay (parked), say "I have controls." Then
    unpark. Then say "I have controls" again.
    **Expect:** the first "I have controls" answers "Unable, AI overlay." and changes nothing.
    The unpark still leaves him flying in mode 1 (U9's case — unaffected by the refused request).
    The second "I have controls" (now unparked, in mode 1) takes the stick back for real.
    **Record:** the exact wording heard for the refusal; whether the unpark behaved as if the
    refused request had never happened.

12. **Do:** Pause the sim (or let DCS pause) while Petrovich holds the controls.
    **Expect:** nothing drifts or jumps when you unpause.
    **Record:** anything odd at the pause/unpause boundary.

## Pass criteria

The feature passes if every readback is spoken correctly and at the right moment, no handover or
mode switch produces a felt jump or stick fight, the physical controls are genuinely ignored
throughout mode 1 (step 1's own test), and the two forced-handover cases (step 10, and U9's "say
again" shape in step 11) behave exactly as described above. A rough, sluggish or lightly
overshooting response (not a jump, not a reversal, not ringing that fails to converge) is an
expected tuning gap, not a fail — note it for the retune flight M5 already anticipates.
