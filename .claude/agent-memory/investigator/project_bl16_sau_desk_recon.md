---
name: project_bl16_sau_desk_recon
description: BL-16 (Petrovich flies the helicopter) desk-recon findings on the Mi-24P SAU channel mapping, Trimmer contradiction, and what remains genuinely unresearched (not just unread) for the stage-0 Windows probe
metadata:
  type: project
---

2026-10-26, desk session (Mac, no DCS install reachable) narrowing BL-16's own stage-0 probe
(`body-layer/ROADMAP/BL-16.md`). Full writeup:
`aircraft-layer/research/2026-10-26-bl16-flight-control-desk-recon.md`.

**K/H/T/B channel mapping, resolved (forum-claim-unverified but three independent snippets
agree):** `H`=yaw (Направление), `K`=roll (Крен), `T`=pitch (Тангаж), `B`=altitude (Высота).
Matches `autopilot_commands`' `ButtonK/H/T/B*` pairs in `mi24p-command-surface.md` §10. Use this
as the stage-0 probe's working assumption, confirmed against in-cockpit labels, not hardcoded
blind.

**Trimmer-vs-attitude-hold is a genuine, unresolved contradiction in community material, not a
reading gap** — one claim says holding `Trimmer` suspends the K/H/T hold and releasing it
re-references to the attitude at release; another says the trim hat only moves the force-trim
spring center and never touches the attitude-hold target. **Only a live probe settles this** —
don't spend more websearch budget on it next time.

**Chuck's Guide (`chucksguides.com/aircraft/dcs/mi-24p/`) names Altitude Hold Mode and Speed Hold
Mode as real section headings**, which raises the prior above the user's own recollected "possibly
not implemented (older DCS doc)" — but the page gates body text behind a PDF download; only the
table of contents was read. If BL-16 planning wants the actual mode description before flying,
fetch/paginate that PDF rather than re-searching — the ToC alone already says the content exists.

**Genuinely absent from both this project's files and the web (not merely hard to find), as of
this session:**
- Whether a `LoSetCommand` write to a global flight-axis iCommand (2001-2004) is absolute or
  trim-relative, and what the "central position trimmer" DCS option does to that relationship.
- What happens to such an axis once script writes stop (snap to physical stick, hold last value,
  or other).
- Return shapes/units for `LoGetVerticalVelocity`, `LoGetAngularVelocity`,
  `LoGetAccelerationUnits`, `LoGetVectorVelocity`, `LoGetSlipBallPosition`, `LoGetMagneticYaw`,
  `LoGetMechInfo` — `Sim_ControlAPI.md` names them with zero signature detail (confirmed by direct
  grep, not assumed) and no community source fills the gap either.
- Any numbered draw-argument for the Mi-24P's cyclic stick or pedals (collective/throttle's two
  args, 0/0, are known but suspiciously placeholder-shaped — see the main note).
- Mi-24P-specific radar-altimeter (RV-5) range/bank-validity envelope — other modules' numbers
  (A-10C, AV-8B) exist but are explicitly non-transferable; A-10C's own DCS implementation is
  ED-acknowledged to deviate from its manual on exactly this dimension.

**Don't re-run the same 9K113-axis-contention generalisation without testing it.** This project's
own [[project_9k113_ai_axis_native_contention_hypothesis]] (frame-order win on a *cockpit device
command* channel, device 7) is evidence of a *shape* of problem, not proof the *global iCommand*
flight-axis channel behaves the same way — the two channels are documented as structurally
different dispatch paths (`mi24p-command-surface.md` §1). Treat any carryover as a hypothesis for
the probe to test, not a transferable fact.
