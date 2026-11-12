# BL-B112 — motion-aware contact certainty: explore notes

Branch: `feature/motion-aware-certainty`. Entry: `body-layer/ROADMAP/BL-B112.md`.

## Origin (user, 2026-11-02, `plans/expected-area-check/explore-notes.md`)

> *"Tracking vs estimated. Again, the unit movement should be considered. Stationary unit can be
> expected to remain stationary. Therefore even if no one looked at it for 30s it's not likely to
> have moved."*

## What was shown (2026-11-11)

Today `belief.decay.certainty_of` is time-only for every contact: tracked ≤ 30 s
(`POSITION_HALF_LIFE_S`), estimated ≤ 120 s (`LOST_THRESHOLD_S`), then lost. Mock comparison of
how far a unit could have moved while unseen:

```
unseen for →        30 s        2 min        10 min        30 min
TODAY (all alike)   tracked→    estimated→   LOST          LOST
 SAM, entrenched    ~10 m       ~35 m        ~180 m        ~540 m
 parked column      ~10 m       ~35 m        ~180 m        ~540 m   (0.3 m/s drift)
 truck, seen moving ~450 m      ~1.8 km      ~9 km         —
```

Prior direction already in force: unseen motion is not stationary (2026-10-13); "observed stopped ⇒
zero" holds only over "a couple of minutes"; `UNOBSERVED_MOTION_GROWTH_RATE_MPS` = 0.3 for motion
`None` or `"stopped"` (2026-10-30, `BL-B104` Stage 8).

Questions asked:
1. A SAM site seen 10 min ago, not looked at since — stated as fact, or "last I saw it"? When does
   the wording change?
2. Should an unmoving unit ever go "lost" by time alone, or only by looking and finding the place
   empty (BL-B111's CONTACT_ABSENT)?
3. What counts as stationary — watched standing still, dug in by type, or never seen moving?

## User answers, verbatim (2026-11-12)

> *"1 - use "last I saw" if it is a mobile unit. Use when location inaccuracy grows to >= 0.5 km.*
>
> *2 - use current implementation*
>
> *3 - units that were seen and observed not moving. Dug-in units as they cannot move. A stationary
> truck may start moving, but that's by observation. A dug in unit cannot move. For all intents and
> purposes, in DCS, a SAM site that is not a mobile SAM unit itself, will not move. -> SA-2 is and
> remains stationary. OSA (SA-8?) can move, but does not necessarily."*

## Reading (to be confirmed by the goal check, not yet decided)

- **"Last I saw" trigger:** position uncertainty ≥ 0.5 km, not elapsed time — and only for a unit
  that can move. A unit that cannot move never gets "last I saw".
- **Two kinds of stationary:**
  - *Cannot move:* dug-in / installation components, and fixed (non-mobile) SAM sites — SA-2
    named. Stationary for good.
  - *Observed not moving:* a mobile unit seen and watched standing still (e.g. a parked truck, an
    OSA/SA-8 at a halt). Stays put until observed otherwise — "a stationary truck may start moving,
    but that's by observation."
  - Not seen moving and not seen stopped is neither.
- **Lost:** "use current implementation". Open whether that means keep today's 120 s time-to-lost
  for every contact (including an SA-2), or keep lost as the existing lifecycle with BL-B111's
  absence route added. Taken literally, an SA-2 would still go "lost" at 120 s while never reaching
  "last I saw" — for the goal check to raise with the user.
- **Tension with 2026-10-13:** "observed stopped ⇒ zero" was bounded to "a couple of minutes" and
  the 0.3 m/s drift applies to stopped units today. Answer 3's "may start moving, but that's by
  observation" reads as: a stopped mobile unit stays believed-stopped until seen moving — at
  0.3 m/s it would take ~28 min to reach 0.5 km. Whether the drift still applies to the label is
  for the goal check.
