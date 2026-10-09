# BL-B11 — Threat-based report prioritisation

- [>] **BL-B11 — Threat-based report prioritisation (`docs/concept/threat-levels.md`) — spec exists, mostly
  gated.** #status/deferred The user's own table: five priority bands (urgent / high / medium / low / ignore), what
  each does to reporting, and what counts as "dangerous to us". Raised 2026-09-20 asking where it
  fits; the answer is that it is **not one milestone** — it decomposes by what each row needs, and
  most rows are behind gates.

  **The dominant gate is coalition.** Roughly 15 of the 24 rows key on friendly/enemy/neutral/
  unknown, so they are downstream of the Coalition/IFF item below — which is itself deferred and
  needs terrain-control data `world-model` does not have. Today every contact is `UNKNOWN`, which
  collapses the table to its one unknown row.

  What the other rows need, none of which exists: unit **engagement envelopes** and "capable of
  firing at us" (also in the STATE_TRANSITIONS autonomous-behaviour backlog, with its 1.5 factor); a
  **behaviour-change channel** for "tracking us"/"engaging us" (there is none — the built event set
  is lifecycle, classification and cardinality); **terrain control** for the friendly-terrain /
  frontline / enemy-territory rows; **Mission Interpreter** output for "mission target" and escort
  targets; and a real **weapon detector** for the aimed-at-us rows, where `UrgentCall` already
  provides the mechanism and `!inject-urgent` is still the only trigger.

  **The buildable slice, and the recommended entry point: the bands themselves.** Urgent interrupts,
  high reports first, low gets the coarse form the spec writes out ("friendly ground 10 o'clock"),
  ignore is silent. This extends [[BL-7]]'s relevance scoring with a band output and gives
  `belief/speech.py` a coarse rendering path. Every contact would band as `medium` today — which
  sounds useless and is not: it builds the machinery so each row lights up as its own input lands,
  rather than arriving later as one large blocked milestone with a dozen prerequisites.

  **No-omniscience constraint — corrected 2026-09-20 by the user, and the correction matters.** An
  earlier version of this entry claimed that "unit well outside its engagement envelope" and "not
  tracking self/flight" require knowing things Petrovich cannot perceive. **Both were wrong**, for
  two different reasons worth keeping distinct:

  - **An engagement envelope is knowledge, not perception.** A crewman knows what a Shilka can
    reach; it is doctrine held in the head, not a fact sensed about the particular unit. The error
    was conflating "cannot perceive X" with "cannot know X" — only the first is an omniscience
    problem, and envelopes are the second.
  - **"Tracking us" is observable.** Guns or a radar dish slewed onto you is a visible fact at
    usable range, and radar lock is a real signal. (Simplification, user: only the pilot has RWR and
    it is poor, but model it as radar lock rather than building an RWR fidelity model.)

  What survives is narrower and still binding: **envelope knowledge is keyed on unit type, so it
  inherits the classification tier.** A contact held only as `lowres` presence has no type, so there
  is nothing to look the envelope up *for*, and it cannot band above unknown/medium. The band must
  be computed from **believed** classification and carry that belief's uncertainty. Computed from
  ground truth instead, it would be an omniscience backdoor wearing a prioritisation label — and an
  invisible one, since the output would merely be unaccountably well prioritised.

  **Open question for an Investigator pass** before the tracking-us rows are built: is turret or
  dish azimuth actually exportable from DCS? `LoGetWorldObjects` gives position and heading; whether
  a unit's *turret* bearing is reachable at all is unverified, and the rule depends on it.

  Also connects to two things already recorded: "urgent units must receive automatic tracking
  status" is the auto-watch-on-engaged rule in the STATE_TRANSITIONS autonomous half, and the
  group rule ("use the highest-capability threat to determine reporting") is the threat-based member
  selection that `clustering.py` deliberately does not do.

  **Do not start without the user's instruction**, same posture as the coalition item it depends on.
