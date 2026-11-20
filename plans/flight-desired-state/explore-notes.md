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
