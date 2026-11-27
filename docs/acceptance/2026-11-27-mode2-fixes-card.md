# Mode 2 fixes — test card (2026-11-27)

**Branch to fly: `feature/bl16-lift-vector-law`** — `git checkout feature/bl16-lift-vector-law &&
git pull` on both machines, then your usual redeploy and restart of collector and body-layer. No
new deploy step. Items: `BL-B139`, `BL-B140`. Feedback:
`docs/acceptance/2026-11-27-mode2-recovery-feedback.md`.

## 1. "Speed 2 5 0" (BL-B140)

Do: in mode 2, "speed 2 5 0". Then "speed down" once.
Expect: readback and overlay **250**, not MAX. "Speed down" from 250 goes to **200**.
Record: what he read back; what the overlay showed.

## 2. Recovery from align-for-launch, the prize (BL-B139)

Do: note set altitude and speed on the overlay. "Align for launch", let it align, then let recovery
trigger (launch, or one of the recovery triggers) **without** changing set altitude or speed.
Expect: altitude first — set altitude dips a few metres (DOWN held ≤ 1.5 s), then back to exactly
the pre-align value; then speed — one DOWN tap, one UP tap, back to the pre-align value. DCS's AI
reacts: climbs/accelerates back. Heading untouched.
Record: did the AI react to each? Did the overlay end on exactly the pre-align values? Anything
pressed more than once?

## 3. Recovery when values already differ

Do: same, but change set speed during the align (so it no longer matches pre-align).
Expect: speed goes straight back to the pre-align value, no extra down-and-back step.

Bring back: the three answers above; anything surprising.
