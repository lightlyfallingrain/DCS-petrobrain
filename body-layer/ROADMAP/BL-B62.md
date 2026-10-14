# BL-B62 — The ownship-relative observation channel is general, and only `BL-14` uses it

- [ ] **BL-B62 — `BL-14`'s relative-direction channel answers *"where is it relative to me"*, which
  is a different and easier question than *"where is it on the map"*. Every other consumer that
  wants a relative quantity is currently paying the describing-error model. Generalising it needs its
  own plan, because `BL-14` fences it to a single consumer by test.** #status/open

  Filed at Architect stage during the `BL-14` attack-run amendment pass, 2026-10-14, from the user's
  own observation in `docs/acceptance/2026-10-14-attack-run-guidance-direction.md` §18: the
  two-mechanism distinction *"likely explains why Petrovich can point at things better than he can
  describe where they are"*.

  **Why that reading looks right, and it is checkable rather than rhetorical.**
  `perception/estimation.py`'s `BEARING_SIGMA_DEG = 3.0` docstring says in its own words that it is
  *"the crewman's own pointing precision, not anything DCS reports"*, bounded below by the optical
  resolution floor and above by the 15° clock half-bucket — a model of **stating** a bearing. It is
  the only bearing-error model in the codebase, so every consumer is charged it, including those that
  want a relative quantity a crewman tracks far better than he names.

  **Candidates, so they are not re-derived:**

  - **The 9K113/ATGM run** — a tracking task, not a describing one. It needs `BL-14`'s loop plus an
    optic that does not exist (`perception/optics.py` declares two), and should be built on the
    relative channel from the start rather than retrofitted.
  - **The deferred general advisory** (*"break right"*) — pure relative direction, no map content.
  - **Not** terrain or world-feature references. *"Edge of the forest"* is a map claim and the
    relative channel cannot answer it. Recorded explicitly because *"use the better channel
    everywhere"* is the wrong generalisation and is the likely mistake.

  **Why it is filed rather than built.** `BL-14`'s Decision 16 fences the field to exactly two files
  under `belief/` — `percept.py` (the projection) and `attack_run.py` (the consumer) — by a grep test
  modelled on `test_belief_source_never_references_derived_world_position`. **That fence is what
  makes the boundary widening safe**, since the datum is convertible to a world position when
  combined with ownship telemetry: the protection is structural, not informational. A second consumer
  breaks the fence, so generalising means replacing it with a considered rule, not deleting a test.

  **Also needed before a second consumer:** a non-zero `RELATIVE_DIRECTION_SIGMA_DEG`. `BL-14` ships
  it at `0.0` on the user's *"guide to it exactly because we look at it"* reading, which is defensible
  for a commanded, bounded manoeuvre and is **not** defensible for routine output.

  Related: `plans/attack-run/plan.md` Decisions 16/17 and its Second-order effect section;
  `plans/dcs-driven-los/plan.md`'s "why this is not a boundary violation" (the precedent, and the
  respect in which this datum goes further than it).
