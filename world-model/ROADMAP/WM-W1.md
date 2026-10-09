# WM-W1 — LOS elevation-tolerance fix

- [x] **LOS elevation-tolerance fix (no M-number — a bug fix, not a milestone; done, merged
  2026-09-29).** #status/done A real sortie (2026-09-28) flew close past an insurgent AAA position, boresight
  on an attack run, and Petrovich never called it out. Debugged and reproduced offline
  (`plans/missed-aaa-detection/debug.md`): `query.line_of_sight.line_of_sight_clear` treated its
  SRTM-sourced elevation grid as exact, so a unit sitting under a grid cell that overestimates
  ground height by as little as M7's own recorded error (mean −7.19 m, stddev 11.52 m) reads as
  permanently "underground" relative to the model at its own position — blocked from every
  angle, at every range, not a per-look coin flip. Fix (user-chosen option 1 of five laid out):
  `_TERRAIN_TOLERANCE_M = 12.0` (rounded up from the stddev) added to the terrain-blocking
  comparison in `world-model/src/query/line_of_sight.py` — terrain blocks only when it exceeds
  the sightline by more than that margin. A module constant, one comparison, one caller
  (body-layer's `perception.geometry.line_of_sight_clear`, an unchanged thin wrapper); no
  override surface. Two new regression tests pin the reproduction and the exact 12.0 m boundary
  in both directions. **Accepted cost, explicit and permanent, not a stopgap**: a unit genuinely
  masked by a real ridge clearing the sightline by less than 12 m now reads as visible — accepted
  because the Mi-24P attacks in a run rather than from a masked pop-up hover (user direction,
  2026-09-28); revisit if this primitive is ever asked to model a pop-up-and-shoot airframe
  (Ka-50, Apache). Reviewer: APPROVED, no required fixes (one optional boundary-test refinement,
  acted on in a follow-up commit). Security: APPROVED — confirmed the fix implements exactly the
  accepted no-omniscience trade and nothing wider. Both `world-model` (475 passed/3 skipped) and
  `body-layer` (1313 passed/4 xfailed, consumes the primitive via the unchanged wrapper) full
  check suites re-run clean. **Unflown — see "Live acceptance debt" above.** Next-milestone
  impact: none — a same-module constant change, no consumer contract change. Surfaces a broader
  gap worth tracking ([[WM-B3]] below): the elevation grid's own measured 11.52 m stddev sat in a
  research note for three weeks while a downstream gate consumed that data as if exact — the
  defect was in the gap between the measurement and its consumer, not in either one. See
  `plans/missed-aaa-detection/debug.md`, `.../implementation.md`, `.../review.md`,
  `.../security-review.md`.

Its live-acceptance-debt record follows. The two are records of the same piece of work: the Status
entry above is the original, 2026-09-29, and still closes with *"Unflown — see 'Live acceptance
debt' above"*, i.e. it points at the list it is paired with; the record below is dated 2026-10-09
and carries the acceptance that closed it. A time-ordered pair rather than a disagreement, so both
are kept verbatim and neither was edited.

- [x] **`fix/los-elevation-tolerance` — ACCEPTED 2026-10-09.** #status/done User, reviewing the status
  page: *"LOS tolerance / grid error buried a unit -> accepted"*. Note what has also happened
  underneath it since this entry was written: [[BL-11]] Stage 4 took world-model's primitive out
  of the live path entirely (merge `b961977`), so the 12 m tolerance is now **offline/test-path
  only by construction**, not merely narrowed. The acceptance closes the debt; the tolerance's
  remaining consumers are fixtures.

  Original entry, kept for the record:

  - [ ] **`fix/los-elevation-tolerance` — `_TERRAIN_TOLERANCE_M = 12.0` added to
  `query.line_of_sight.line_of_sight_clear` (merged 2026-09-29), unflown.** **Narrowed 2026-10-05 by
  [[X-B29]]'s DoD gate**: once `feature/dcs-driven-los` lands, gate 4 never calls this primitive at all
  once a live DCS verdict exists for a unit (`candidate.live_los_clear is not None` short-circuits
  it) — the tolerance is now test-path/fallback-only by construction, documented at its own
  definition site. The original two questions this entry tracked split accordingly:
  - **"Does Petrovich now detect the previously-missed AAA on a similar pass"** — this is now
    answered by the *live* path, not by this tolerance, and is covered by
    [[X-B29]]'s own Stage 4 acceptance card (`docs/acceptance/2026-10-05-dcs-driven-los-sortie.md`),
    not this one. Still unflown.
  - **"Does the 12 m tolerance start revealing units genuinely masked by a ridge"** — this is the
    one question still actually owned by this entry, and only for the narrower surface it now
    covers: gate 4's fallback branch (live feed absent/outside the wedge/stale) and [[WM-B8]]'s
    fixtures. Lower-stakes than originally framed, since the live path no longer depends on it for
    the common case. Still unflown; card `docs/acceptance/2026-09-29-los-tolerance-sortie.md` is
    stale in scope (it was written when this tolerance was the only LOS answer) and should be
    re-read against this narrower claim before being flown, not flown as originally written.
