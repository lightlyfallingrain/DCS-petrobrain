# 2026-11-16 — AI wheel operated while the player is in the pilot seat (flight feedback)

Branch fixed on: `fix/ai-wheel-pilot-seat-gate`. User said "Fix now", so capture → fix directly,
no `/explore` round (root `CLAUDE.md`, "Direction before speed": proceed when told to, and say so).

## The user's words (verbatim)

> bug:
>
> * start mission
> * player selects copilot seat
> * player selects pilot seat
>    * this apparently parks copilot controls, but does not hand over to AI for flight
>    * observed: Petrobrain keeps toggling AI overlay on and off and pressing center action
>
> What must happen: Petrobrain must not operate AI wheel when AI is not flying.
>
> AI never flies when player is in pilot seat.
> When Player is in copilot seat, AI flight is toggled by the 'Request Aircraft Control' DCS action.
> Player switching to pilot seat automatically ends AI flight mode.
>
> Fix now.

Follow-up: *"DCS Control options have 'Occupy the Pilot's Seat' / 'Occupy the Copilot/Operator's
seat' in View Cockpit category"* — key bindings; `Export.lua` cannot observe a key press, only its
effect (the camera moves to that seat's eye point).

## Reading

- Arg 852 is `StickStowingOp` (`mainpanel_init.lua:193-198`) — the **operator's** cyclic stow. It
  reads stowed whenever the operator seat is not being flown by a human: AI flying from the
  operator seat **or** the player sitting in the pilot seat. P1 treated it as "AI flying".
- In the pilot seat the AI-pilot overlay never populates, so after the blind centre tap and the
  menu tap, the keep-open check re-toggled the menu every ~1 s forever — the observed flapping.
- Fix: AI flying = 852 stowed **and** the player's camera is in the operator seat. Seat from
  `LoGetCameraPosition` projected on the airframe's forward axis: `Views.lua` puts the pilot's eye at
  x = 3.15 m and the operator's at 4.65 m, head travel limited to −0.1…+0.5 m, so a 4.1 m boundary
  has ≥ 0.45 m margin each side. Camera outside the cockpit (external/map views) keeps the last
  known seat; no seat known yet = not flying. Leaving the operator seat drops the takeover state
  without the menu-close tap (that tap would land on the pilot seat's own wheel).
- **Unverified live:** that `LoGetSelfData().Position` is the model origin `Views.lua` measures
  from, and where the 9K113 sight view puts the camera. The status push carries `apw_seat` and
  `apw_cam_fwd_m` so one sortie settles both.
