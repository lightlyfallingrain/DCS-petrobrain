# BL-16: one desired flight state, one mode authority — explore notes

Started 2026-11-20 from the sortie feedback (`docs/acceptance/2026-11-20-sortie-feedback.md`, last
section; `body-layer/ROADMAP/BL-16.md` open item "one desired flight state shared by both modes").

## User direction, 2026-11-20, verbatim

> # desired state and active mode
>
> There should be a single place of truth for the desired flight params. Be it body layer of
> aircraft layer. All places that need them, get the params from there. It depends on where the
> actual control value logic sits, the desired values should be in that service as well.
>
> Mode 1/2/off state must come from Export.lua, since it may at any moment change by AI overlay
> activation. A state that body layer would hold, could become out of sync and then flight mode
> would error. Single place of truth in aircaft layer of export.lua. Body layer then is notified of
> change and acts accordingly. If mode 1/2 is ON in aircraft layer, body must use that state and
> not be in some other state like off. Similarly of Mode is offin aircraft layer/lua body must know
> that.
>
> Mode 1/2 must both be driven by the same desired flight params, those modes are simply different
> ways of manipulating the aircraft to reach them. In that sense, flight guidance logic would simply
> set the desired values, and control logic would use whatever mode is active to reach them. If
> mode 2 is active and something it cannot do is commanded, that'd get a response back saying so,
> on which body layer would act by informing player with unable.
>
> Desired flight param single source of thruth can be body or aircraft layer, whichever makes more
> sense for the control axis calculation logic. The other service then uses getters (or they are
> part of the normal polled data) to ask the values whenever it needs them. This also helps with
> the mode 1/2 transitions, the desired state is already known and mode change simply keeps flying
> to it (as much as mode 2 allows, of course).
>
> Where the control axis logic lives, that I leave up to you. Having it in aircraft layer would have
> it sit right next to/in lua and not be dependent on network traffic to body layer. Having it in
> body layer would allow more logic based on params that body layer knows. My thinking is that body
> layer sets the desired param values and aircraft layer calculates needed axis value changes (and
> other effectors) to reach them, but I leave the actual architechtural decision to you.

Earlier the same night, verbatim, on the same subject:

> Mode 2 > 1 change: Mode 1 to pick what player has commanded. The AI wheel probably shows it, but
> if mode transition is mid param adjust on AI wheel then AI wheel ha incorrect value. There should
> be a unified state of desired params that both modes use, mode 2 just has more limitations.

> handle the reset. having individual channels and their numbers sounds error prone. I'd still
> prefer single running number. Not critical immediately, but should be done in BL-16

## Main-loop architecture call (2026-11-20), the user left it to us

**Both the desired state and the active mode live in Export.lua (aircraft layer).** Reasons:

- Both controllers already sit there: mode 1's control law (`Petrobrain/flight_control.lua`) and
  mode 2's wheel press loops (`Petrobrain/ai_pilot_wheel.lua`). Putting the desired state next to
  them means the per-frame controller and an unpark take (which happens inside Lua, within one
  frame) never wait on the LAN.
- The mode is already physically decided there (park/unpark, the overlay), as the user says.
- Body-layer stays the *guidance* side: it turns player commands and its own manoeuvre logic
  (align, align-for-launch, break, recovery, latest-wins) into desired-value writes, and reads back
  desired state, active mode, and per-request accept/refuse on the normal polled status.

This also delivers the single running number: one `desired` command channel with one seq replaces
the separate goal / CBTM / flight_control goal seqs.

Open for the plan: what is a "desired value" versus a manoeuvre (break, align, HVRT translate are
not plain heading/alt/speed targets); what mode 2 refuses and how the refusal reaches the player;
what "off" means for desired state (kept or cleared); the transition rules (Decision 24) restated
over one state; migration of today's two goal channels and the body-layer mirrors.

## Answers to the goal check (`alignment.md` C1–C3, Q1–Q6), user, 2026-11-20, verbatim

Asked: C1 (a player take/hand-back reseeds from the aircraft, no stale target) and C3 (a break
replaces the older heading; align sets it to where it ends) as defaults unless objected; Q1–Q6 as
numbered in `alignment.md`.

> Break heading is a heading set just as any other heading set. The difference is that a break is
> a rapid turn away from threat, not a gentle one.
>
> 1 - a
> 2 - drop anything that is unable
> 3 - default to radar in both modes. Barometric if player says so.
> 4 - yes, finish break
> 5 - on move to pilot seat always. In copilot seat, no.
> 6 - I get stick

Settled:
- **C1, C3:** not objected; they stand. A break is an ordinary desired-heading write with a fast
  turn rate (mode 1's Decision 27 shape: heading target plus rate override), so it replaces the
  older heading like any later heading command does.
- **Q1 (a):** mode 2 reads back what it will actually fly; the exact commanded value stays the
  desired value, for mode 1 to fly after an unpark.
- **Q2:** anything answered "unable" is dropped; "unable" means nothing changed.
- **Q3:** altitude defaults to radar (AGL) in both modes; barometric only when the player says so.
- **Q4:** an unpark mid-break finishes the break (mode 1 flies to the break's heading), then holds.
- **Q5:** the overlay switches off whenever the player moves to the pilot seat; in the copilot seat
  it does not switch off by itself.
- **Q6:** after a body-layer restart while parked, an unpark gives the player the stick.

## Mode 2 is Mi-24 only (user, 2026-11-20, verbatim)

> Note: mode 2 is mi-24 specific. When, eventually, we add other helicopters, they have no mode 2,
> only mode 1. Just build this so that it's easy to isolate mode 2 to the mi-24 only.

So the desired state, the mode authority and mode 1 are aircraft-generic; mode 2 (ED's AI-pilot
wheel) is one aircraft-specific consumer of the desired state, behind a seam that another module can
simply not have. Not a request to build other aircraft now.

## Heading reference, align and align-for-launch (user, 2026-11-20, verbatim)

Asked the plan's U1–U4 (`plan.md`); this answers U3 and refines the manoeuvre table.

> True vs magnetic - which ever the AI wheel uses should be used in both modes.
>
> Mode 2 Align is also a heading set, but a special case because it's heading set to align with
> 9K113 vector and AI overlay does that. In AI overlay align command sets heading to 9K113 azimuth,
> that is the align. It is single time heading set on command press. Read that into desired value
> heading (after a small delay so AI overlay updates first).
> Align for launch differs in two ways: it stays on and keeps aligning to current 9k113 azimuth
> constantly so 9K113 slew makes the AI fly the helicopter to keep it aligned. Also it tries to
> align pitch so that the missile launch parameters are met.
> In both of these, read the value from AI wheel that the AI is flying and update our desired
> heading value to match that so that that heading is kept when recovering from align.

Settled:
- **U3:** the desired heading uses the AI wheel's own reference (true or magnetic, whichever the
  overlay course is), in both modes; mode 1 converts if its own heading source differs. The
  Stage 1 card measures which reference the overlay uses.
- **Mode 2 align:** one-shot. ED's overlay sets its course to the 9K113 azimuth on the press; after
  a short delay (overlay updated), Lua reads that course into the desired heading.
- **Mode 2 align-for-launch:** continuous. The overlay keeps re-aligning to the current 9K113
  azimuth (slewing the 9K113 steers the helicopter) and also aligns pitch for launch parameters.
  While it is on, the desired heading keeps following the overlay course the AI is flying, so
  recovery and any later mode change hold the last aligned heading.

## U1, U2 and align in mode 1 (user, 2026-11-20, verbatim)

> 1 - Readback on acting on command -> wait for lua
> 2 - yes
> 4 - as I've said before, align is possible only in mode 2 -> unable

- **U1:** the readback waits for Lua's accept/refuse; Petrovich speaks only what Lua accepted (or
  "Unable, <reason>"). Not the plan's recommendation; the user's decision.
- **U2:** yes, when a carried value can't be flown exactly in the new mode, Petrovich says once,
  not urgent, the value now flown.
- **Align / align for launch in mode 1:** "unable" (align exists only in mode 2, as decided
  earlier in BL-16).
- **U4** (fly Stage 1 alone): asked what Stages 1 and 2 are; pending.
