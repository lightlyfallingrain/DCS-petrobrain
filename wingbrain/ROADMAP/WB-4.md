# WB-4 — Player commands, stage 1: speed, heading, altitude over the radio PTT

- [ ] **WB-4 — The player commands wingmen by voice on the radio PTT: "speed <value>", "heading
  <value>", "altitude <value>". The audio adapter records the whole radio press, tags it RADIO or
  ICS, and sends RADIO to the wingbrains and ICS to Petrovich.** #status/open Filed 2026-11-19 from
  `docs/concept/wingbrain.md`, "Commands from player", stage 1. Needs `[[WB-3]]` and `[[BL-17]]`'s
  rule engine. Cross-subproject: audio-adapter (capture, routing) and wingbrain (rules).

  > *"Wingbrain gets commands not from ICS, but radio. Therefore audio capture needs to listen to
  > full radio trigger (VOIP) press and record. Attach metadata to recording that tells*
  > *- ICS/RADIO*
  > *- if radio, then frequency of radio channel. SPU-8 selector tells us which radio is selected
  >   (R-8xx) and from that radio we get active channel and from that the frequence that channel is
  >   set to.*
  > *In audio-adapter route RADIO commands to wingbrain, ICS commands to Petrovich. Before radio
  > interface is built, simply ignore the frequency and send all commands to wingbrain(s)."*
  >
  > *"Stage 1:*
  > *- simple player commands:*
  >     *- "speed <value>"*
  >     *- "heading <value>"*
  >     *- "altitude <value>""*

  Commands are `[[BL-17]]` rules: fixed wording, typed slots, a handler that calls `[[WB-3]]`'s
  actions. BL-17 is parked (2026-11-18), but its rule engine is merged on `main`; this milestone
  needs only what is there.

  **Open for the plan:**

  - With two or more wingmen and no addressing yet (that is `[[WB-9]]`), every command goes to
    every wingbrain. Acceptable for stage 1, or address by number from the start?
  - How a wingbrain answers before the radio layer exists — a readback through the audio adapter
    the way Petrovich speaks, or no answer yet.
  - Today a capture that reaches the trigger's radio position is discarded
    (`DcsPTT.discard_requested`, `audio-adapter/tests/test_dcs_ptt.py`); this milestone is what
    changes it.
