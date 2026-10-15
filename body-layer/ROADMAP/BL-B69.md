# BL-B69 — The object-permanence shortcut skips the spatial gate with no distance check of its own

- [ ] **`_resolve_continuity`'s object-permanence shortcut (`belief/contacts.py:1257-1280`) bypasses
  the spatial/class gate entirely, so two genuinely different objects could be folded into one
  contact with no distance check anywhere in the path.** #status/open Found 2026-10-15 while
  diagnosing [[BL-B68]] (`plans/position-belief-runaway/debug-2026-10-15.md`, "Related, found but
  not fixed here"). **No confirmed live trigger** — filed on its own merits, not because it fired.

  **The mechanism.** The shortcut skips the spatial/class gate whenever a percept's
  `continues_observation_id` resolves to an existing contact and both `object_id_continuity_valid`
  and `class_compatibility != "incompatible"` hold. **The second check passes on an *unknown*
  compatibility** — two unclassified `PRESENCE`-level percepts are not "incompatible", they are
  simply unjudged. So two real objects that each read as "something, unclassified" can satisfy both
  conditions, and nothing downstream applies a distance bound.

  **What it needs in order to fire: an `object_id` reused *within* one continuous mission.** That is
  the residual risk `contacts.py`'s own docstring already names — DCS reusing an id across a real
  kill/respawn boundary.

  **Why this is filed as open rather than deferred, unlike [[BL-B68]].** The 2026-10-15
  investigation confirmed the mechanism precisely by reading the code, and separately confirmed that
  the `object_id` reuse actually observed in the logs was **across missions**, which is expected,
  harmless, and a different thing entirely. So the gap is real and the evidence for it firing is
  absent — exactly the shape that stays invisible until a unit dies and respawns at the wrong moment
  in a long sortie.

  **Worth knowing before picking this up:** the previous investigation spent real effort on an
  `object_id`-collision hypothesis that turned out to be cross-mission reassignment misread as
  in-mission collision. The distinction is the whole of this item — **an id reused between missions
  is normal; an id reused inside one mission is the trigger.** Any fix or test must be built on the
  second, and a reproduction has to construct it deliberately rather than hope to observe it.

  A distance bound on the shortcut is the obvious candidate fix, but the threshold is a judgement
  call against how far a real contact can legitimately move between polls, so it is not a one-liner.

  Related: `[[BL-B68]]` (the same investigation; its per-source dedup maps feed this shortcut, so a
  mission-reset that clears them also narrows this gap's exposure).
