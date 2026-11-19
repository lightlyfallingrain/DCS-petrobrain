# WB-9 — Radio procedure: addressing by number, readbacks, flight check-in, channel changes

- [ ] **WB-9 — Wingmen answer to their number in the flight, or to "flight" for all; each reads
  back and acts; a call to the flight is answered in number order with only the first giving the
  full readback; a member who stays silent is skipped. Wingmen change channel only on the player's
  command.** #status/open Filed 2026-11-19 from `docs/concept/wingbrain.md`, "Radio interface".
  Needs `[[WB-8]]`.

  > *"Wingmen have their number in flight: 1, 2, 3, 4. They respond to radio transmissions by their
  > number. "flight,..." means all wingbrains. Player: "2, fly heading 320" -> message is intended
  > for number two only. Two responds by readback "2, heading 320" and acts on it. On commands to
  > "flight" each wingbrain responds with their number, 2,3,4. Only first response does full
  > readback, rest just answer with their number.*
  > *- Player: "flight, speed 100" -> "2, speed 100" > 2s silence on frequency > "3" > 2s silence on
  >   frequnecy > "4"*
  > *- if a unit does not answer within some seconds (busy, destroyed, returning to base, not on
  >   frequency), the next one will.*
  >
  > *Plain command "flight" will have each flight member respond with their number: "2", "3",
  > "4"."*
  >
  > *"Wingbrain changes channel on player command only. "Set radio channel <value>
  > [shorthand-for-R-863/shorthand-for-R-828]""*
  >
  > *"Wingbrains can talk to player and to other wingbrains on the frequence when needed."*
  >
  > *"Wingbrains will transmit on radio to talk to flight lead (player). Very much like Petrovich
  > does."*

  The 2 s gap and the skip timeout change what the player hears, so they are tunables
  (root `CLAUDE.md`, "Behaviour-affecting constants are tunable").
