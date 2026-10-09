# BL-B6 — `OP_LRSAM` folded into the air-defence command classes

- [x] **BL-B6 — `OP_LRSAM` folded into the air-defence command classes — merged 2026-09-24
  (`fix/lrsam-air-defence`).** #status/done "Watch nearest air defence" could not select an S-300:
  `crew_console._AIR_DEFENCE_OP_CLASSES` held the two gun systems and the short/medium SAM tiers
  and nothing else. The excluded contact was the worst possible one to miss — at the calibrated
  8.89 km detection range the S-300's tracking-radar mast is the furthest-detectable thing in the
  profile table, so it is both the most dangerous thing the command exists to find and the one
  most likely to be the *only* air-defence contact held at all.

  **Drift, not a decision.** The set was enumerated by hand against `perception.object_model`'s
  profile table when that table genuinely had no long-range SAM entry, and its own comment
  ("exactly the air-defence entries in `object_model`") stayed true only until the table gained
  one. Nothing connected the two. So the fix ships a guard test that recomputes the air-defence
  classes present in the profile table and asserts the command set covers them — verified to fail
  against the pre-fix set rather than assumed to — alongside the S-300 regression itself.
  `object_model` carries no structural air-defence marker to derive the set from, so the guard
  matches on `OP_*` naming and says in its own docstring that a class escaping that pattern is a
  signal to give `object_model` a real marker, not to loosen the assertion.

  Found while reading `plans/watch-reporting/plan.md`, which flagged it and deliberately left it
  unfixed; fixed on user direction ("it is air defence"). Merged as a small fix, no DoD pass.
