# WB-8 — Radio layer: simulated frequencies, transmissions with speech and data

- [ ] **WB-8 — A simulated radio, not DCS's: each flight member is on a frequency, a transmission
  reaches everyone on that frequency and no one else, and it carries spoken text for the player and
  a data payload for the wingbrains. The player's frequency is read from the cockpit.**
  #status/open Filed 2026-11-19 from `docs/concept/wingbrain.md`, "Radio interface". Needs
  `[[WB-4]]`.

  > *"Radio interface will need to be it's own layer. It acts as the medium for all intra-flight
  > communications. Wingbrain will simulate radio, not use the DCS radio."*
  >
  > *"Each flight member will be on a specific frequency (possibly multiple simultanous frequencies
  > in future). In player aircraft player control radio settings. Read the set values from
  > aircfart: SPU-8 radio selector, R-8?? active channel and it's frequency. For wingbrains,
  > frequency is internal state. They share the same R-8xx channels and frequencies as player
  > aircraft. Initially winbrains start on R-863 channel 0."*
  >
  > *"Wingbrain listens on the channel (frequency) they are on. Other frequencies are not heard.
  > Wingbrain transmits on the channel (frequency) they are on."*
  >
  > *"Radio interface will simulate radio channels. When someone (player, wingbrain) transmits,
  > those who are on the same frequency will hear it. Each wingbrain probably need to register with
  > radio layer what frequency they are on. Then radio layer will relay trasmissions to listeners
  > of that frequency."*
  >
  > *"Radio transmission will need a payload of two kinds: spoken text and data payload.*
  > *- For wingbrain transmits spoken text will be TTS'd and played via audio adapter if and only if
  >   player is listening on the transmission frequency*
  > *- Data payload is so that each wingbrain does not need to handle spoken text transmission, but
  >   instead acts on the data payload. -> spoken text is for player's benefit only."*

  The concept's worked example: the player says *"2, turn right 30"* on R-863 channel 0; the speech
  is turned into `{ from: 1, to: 2, command: "heading_increment", value: 30 }`; wingman 2, if on
  that channel, reads back and acts, transmitting `{ speech: "2, turn right 30", data: { from: 2,
  to: 1, command: "acknowledge" } }`.

  **Decision D2 is settled here** (index, "Open decisions"): whether the radio layer is its own
  subproject. Petrovich transmits on it too (`[[WB-12]]`).

  **Known from the cockpit already:** the radio source selector is arg 455, six positions, R-863 /
  NF / R-828 / JADRO-1A / ARC-15 / ARC-U2, pilot side
  (`aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`). How to read the
  active channel and its frequency is not yet known.

  **Open for the plan:** which layer turns the player's speech into the data payload — the concept
  says *"Radio layer (or some layer)"*.
