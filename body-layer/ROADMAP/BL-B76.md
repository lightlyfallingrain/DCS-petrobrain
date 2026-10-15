# BL-B76 — `", obstructed"` has no live caller: `Contact.live_los_clear` is never `False`

- [ ] **BL-B76 — The admission gate discards exactly the fact the attack run needs. A contact can only
  reach belief if its line of sight was *clear*, so `Contact.live_los_clear` is `True` or `None` in
  live play and never `False` — which makes `", obstructed"` structurally unreachable outside a test
  fixture.** #status/open Found 2026-10-15 during `[[BL-B70]]`'s review and confirmed by tracing the
  live path, not inferred.

  **This matters because it silently voids a direction the user gave the same day.** §8 of
  `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` settled what the qualifier means:

  > *"'...obstructed' for DCS LOS, be it terrain or buildings."*

  `[[BL-B70]]` implements exactly that, correctly, and the word can never be spoken against real DCS
  data. **The feature is not wrong; its input never arrives.**

  ## The mechanism, traced end to end

  | step | what happens |
  |---|---|
  | `visibility.py` gate 4 | **fail-closed** on `live_los_clear`, and the emitter bypass covers gates 3/5 only — so a blocked candidate is *rejected*, never admitted |
  | `naked_eye_source` | populates the field only from the `visible` list, i.e. candidates already admitted — every member is `True` |
  | per-cluster fold | `next(iter(member_los)) if len == 1 else None` over an all-`True` or empty set — can yield `True` or `None`, never `False` |
  | other sources | leave it at the `None` default; `source.py`'s own docstring says the hybrid channel *"never sets this"* |
  | `percept.py` → `contacts.py` | straight passthrough, unconditional overwrite |

  **So the information is discarded at admission.** Being blocked is not a property belief ever
  learns; it is a reason the observation did not exist.

  ## Why this is not simply "delete the word"

  **For an already-engaged target, "I cannot see it right now" is a fact the crewman has and the
  pilot wants.** It is not extra knowledge and does not touch the no-omniscience invariant — the
  crewman knows he is looking at a ridge rather than at the tank. The current design cannot express
  it because admission is all-or-nothing: either the contact updates, or nothing happened.

  Note how this rhymes with the direction's own §9 — *"during an attack run the current target is
  **the** thing to LOS and must take priority"*. Both point at the same gap: **the attack target
  needs a richer relationship with perception than an ordinary candidate**, one where a blocked look
  is reported rather than dropped.

  ## Shape of the options, for whoever plans this

  1. **Pass blocked observations through for an already-known contact**, carrying `live_los_clear =
     False` rather than rejecting. Honest, and makes §8 work as directed — but widens what reaches
     belief, so it needs the same care the emitter bypass got.
  2. **A separate, narrower channel for the attack target only** — the run already claims the gaze
     (2026-10-14 direction §15), so it could ask about its own target directly.
  3. **Accept that `", obstructed"` is terrain-only in principle and dead in practice**, and let §2's
     silence cover it. Cheapest, and loses the pilot's answer to *"why have you gone quiet?"*.

  **Do not pick one from this entry** — it is a perception-boundary change and wants an `/explore`
  with the user, who has already given three rounds of direction on what this word means.

  Related: `[[BL-B70]]` (implements §8 against this dead input), `[[BL-14]]`, `[[X-B29]]` (the live
  LOS feed), `[[AC-8]]`/`[[WM-W2]]` (its availability).
