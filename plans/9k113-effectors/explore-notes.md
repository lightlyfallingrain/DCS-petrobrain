# BL-B66 — explore notes, 2026-10-21

Short explore pass before the architect revision of `plan.md`. The plan predates the 2026-10-17
split (`[[BL-B80]]`) and the user's procedures
(`docs/acceptance/2026-10-17-9k113-procedures-direction.md`); this note records what was settled
on 2026-10-21 so the revision builds on it rather than re-asking.

## Settled — scope

1. **`[[BL-B65]]` folds into `BL-B66`.** User: *"ok"*. The weapon safety bar (arg 673) is built
   here; `BL-B65` closes with a pointer. Its own open questions are answered by the procedures
   direction §1 and by point 6 below.
2. **`CPLR DISTR` is built at arg 761, marked unverified**, and confirmed on the acceptance sortie
   by logging changed arguments while the user throws it by hand. User: *"ok, we can change the
   switch number easily"* — so a wrong 761 is a one-line fix, not a blocker; no read-probe before
   coding.
3. **The body-side slew model (old plan Stage 1 — rate-limited `actual` toward `desired`, 20°/s
   az, 10°/s el) moves to `[[BL-B80]]`.** User: *"yes"*. `advance_sight_aim` stays a pass-through
   in this entry.

## Settled — behaviour, in the user's words

> *"Guidance unit power up after takeoff, autonomously.*
>
> *"Guidance unit ready" is enough. No OBSERV while warming up.*
>
> *ARMED - from my spoken command for attack run. Or "weapons on/armed" command."*

4. **Power-up is autonomous, triggered by takeoff.** Petrovich throws the four switches (773 →
   761 → 885 → 955) himself after takeoff; no pilot command starts it. What "after takeoff"
   means in telemetry (weight-off-wheels, AGL, airspeed) is the architect's to propose against
   what body-layer already reads.
5. **One callout: *"Guidance unit ready"*** at the end of warm-up. No per-switch narration. With
   the zero-warm-up direction still standing (*"ignore until effectors built. Prepare code for it,
   but use no warmup time"*), it follows the sequence immediately; the readiness seam is where the
   measured ~5 min lands later.
6. **No OBSERV while warming up.** An OBSERV-on request before readiness is not acted on. How he
   answers it is not stated; the project's existing rule (memory `say-again-vs-unable`) gives
   *"unable <because>"* as the best form — proposed, to confirm on the plan.
7. **ARMED is pilot-commanded only**: on the spoken attack-run command (`BL-14`'s), or on a
   *"weapons on"* / *"weapons armed"* command. **Not** on any internal attack-run state. SAFE
   stays pilot-commanded only (procedures §1), so the new vocabulary is presumably a matching
   *"weapons off/safe"* — to confirm on the plan.

## Not settled — left to the plan

- Whether the power-up is re-run or skipped if the switches are already on (player set up by
  hand, or a hot start).
- What happens on landing — nothing in the direction powers the unit down.
- Voice and F10 vocabulary entries for the arm/safe commands (cross-subproject: `audio-adapter/src/vocabulary.py`, per the `BL-8` DoD finding that a body-layer token with no vocabulary entry is unreachable).
