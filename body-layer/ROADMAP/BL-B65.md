# BL-B65 — Weapons safety circuit switch

- [x] **BL-B65 — Model the weapons safety circuit switch as its own cockpit action, before any ATGM
  attack run is built.** #status/done **FOLDED INTO `[[BL-B66]]` 2026-10-21** (user direction, *"ok"*): the safety bar (arg 673) is built there, pilot-commanded ARMED/SAFE — `plans/9k113-effectors/explore-notes.md`. Original text kept below. Asked for explicitly by the user in `docs/concept/9K113.md`'s
  closing line: *"Weapons safety circuit switch — This should be it's own roadmap item before ATGM
  attack run."*

  The ATGM sequence in that document has *"Turn weapons circuits switch to ARMED"* as one step among
  several, which is precisely why it earns separating: arming the aircraft's weapons is not a detail
  of a guidance loop. It is a discrete, consequential cockpit action with its own state — armed or
  not — that outlives any single attack run, and it needs its own answer to when Petrovich arms,
  whether he announces it, whether he ever *dis*arms, and what happens if the pilot commands an
  attack run while the circuit is safe.

  **Why it is filed now rather than with the ATGM work**: the same reason it is being separated. Left
  inside `[[BL-B64]]`'s sequence it would be implemented as a switch flip in the middle of a
  guidance routine, which is how a safety interlock turns into an implementation detail nobody
  reviews.

  Open, and not scoped: the switch's own device argument number (the same reconnaissance that found
  the push-to-talk trigger at arg 738 and the SPU-8 controls), and whether arming is Petrovich's
  decision at all or strictly pilot-commanded.

  Related: `[[BL-B64]]` (the 9K113 capability and its specification), `[[BL-14]]` (the naked-eye
  attack run, which arms nothing and needs no circuit state).
