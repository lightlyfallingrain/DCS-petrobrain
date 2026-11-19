# BL-16 mode-1 batch — break turn/away, rotor envelope, VRS, rates-as-goals

**Branch to fly: `main`, after merge.** `git checkout main && git pull` in the repo root.

DoD passed on `feature/bl16-mode1-break`, tip `fd40f7ea` (Security PASS). Decisions 27–32 built:
break turn/away flown as a fast heading goal (no new state machine), the rotor-RPM/retreating-
blade-stall/VRS envelope active in every mode-1 state, `MAX_BANK_DEG` removed (no standing bank
limit — the rotor envelope is the only protection now), and a mode-1 take seeded from a mode-2
break's own target heading.

## Known gap — read this before flying

**The plan promised a break reaches roughly 60–80° of bank at cruise speed. The offline toy-plant
measurement says ~43° at 150 km/h and ~54° at 220 km/h** — the heading shaper's gain
(`OMEGA_HEADING`, an unmeasured placeholder) caps the achieved turn rate well below the commanded
ceiling, so raising the rate ceiling does not by itself drive the bank up to the promised figure.
This is a known, flagged shortfall (owed to Flight M-A's retune), not a defect to chase in flight —
but it means **do not be surprised if the break looks gentler than the plan's own text describes.**
Recording the real bank you see at each speed is this card's single most useful number.

**No standing bank limit exists in mode 1 any more, in any state** (removed, user direction). If
the aircraft rolls further than expected on a break or a hard turn, that is the removed limit
doing nothing — not a bug, but worth recording how far it actually goes.

## Setup

```sh
git checkout main
```

Air start, straight and level, mode 1 (unparked). Rotor RPM ships as a fixed dummy value
(`ROTOR_RPM_SOURCE = "dummy"`, 90%) this batch — **the RPM floor and stall-trade mechanism cannot
be exercised by a real low-RPM event**; they only engage if you deliberately lower the dummy value
for a test run (not expected of you — this is a code-path note, not an ask).

## Test blocks

### 1. Break turn, 150 km/h — **the prize**

**Do:** steady level flight at 150 km/h, "break left."
**Expect:** a fast heading change toward current heading − 90°, steeper bank than an ordinary
turn, settles and levels on the new heading.
**Record:** peak bank angle, height lost during the break, how long it takes to settle, whether it
overshoots the target heading before settling (integrator windup — see block 5).

### 2. Break turn, 220 km/h

**Do:** same, at 220 km/h, "break right."
**Record:** same four numbers as block 1. Compare the two — does the higher speed give noticeably
more bank, as the plan's kinematics predict (steeper bank at higher IAS for the same rate)?

### 3. Break away

**Do:** steady flight, "break away."
**Expect:** a continuous turn to current heading − 180°, same mechanism as break turn (always
turns the aircraft's faster direction).
**Record:** does it feel different from a plain break turn, or just twice the heading change?

### 4. Low and slow break

**Do:** slow to somewhere around 60–80 km/h, low altitude, "break left" or "break right."
**Expect:** per the user's own answer, if rotor RPM drops under load the aircraft should
*accelerate* (pitch forward for speed, which helps RPM recover) rather than let RPM droop
unchecked. With the dummy RPM source active this mechanism is not really exercised — **record
what you actually see the aircraft do**, since this is the one case where seeing "nothing special
happens" is itself useful information (it would mean the dummy value never approached the 85%
floor).

### 5. Integrator windup

**Do:** after any of the breaks above, especially a sustained hard one, watch what happens as the
aircraft approaches the target heading.
**Expect from the known gap above:** some overshoot past the target heading before it settles,
more than an ordinary turn would show, because the roll-rate integrator is no longer clamped by
any bank limit.
**Record:** how much overshoot, in degrees of heading, and whether it damps out or oscillates.

### 6. VRS — vortex ring state

**Do:** below 50 km/h, command a descent (e.g. "descend 100").
**Expect:** descent rate capped at 4 m/s regardless of how large the altitude error is.
**Record:** the actual descent rate you observe — does it hold near 4 m/s, or something else?

### 7. Take during an active mode-2 break (Decision 32)

**Do:** in mode 2 (parked), start a break (or break away) via the AI wheel command, then take the
controls mid-break.
**Expect:** mode 1 picks up the break's own target heading (held heading at the press, ±90° —
or ±180° for break away) as its heading goal — not whatever continuous turn the AI wheel was
flying at that instant.
**Record:** does the aircraft visibly continue toward the same heading it was breaking to, or does
it jump to something else at the handover?

### 8. Rotor RPM gauge check

**Do:** in the cockpit, watch the rotor RPM needle during normal flight and during a hard
collective pull.
**Record:** does cockpit draw arg 42 (if you have any way to probe it) track the needle? What is
the needle's maximum — does the dial go past 100%, or top out at 100%? (This settles
`ROTOR_RPM_ARG_SCALE_MAX_PCT`, currently assumed to be `raw * 100`.)

### 9. Engine vs. rotor RPM under a hard collective pull

**Do:** a hard, sustained collective pull (climb demand) at low-ish speed.
**Record:** do engine RPM and rotor RPM needles move together or separately? This is the
information that will let the dummy/engine-proxy RPM source be replaced with something closer to
the real rotor reading.

## Bring back

- Peak bank at 150 km/h vs. 220 km/h, and height lost, for both break turn and break away.
- Whether the low-and-slow break shows any visible acceleration behaviour.
- Overshoot (if any) after a hard break — degrees, damped or not.
- VRS descent rate actually observed below 50 km/h.
- Whether a take mid-break continued toward the break's own target heading.
- Rotor RPM gauge's maximum value and whether arg 42 tracks it.
- **Anything that surprises you is worth more than anything on this list.**
