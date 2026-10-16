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

  ## NARROWED by user direction, 2026-10-16 — the admission gate is right, the lookup is wrong

  > *"on LOS false never arriving. That's correct since the LOS false means we don't see it. But
  > belief is there based on earlier observation. Like in real life, if a unit drives behind a
  > building, I cannot see it, nothing but my brain tells me it is there. But since I saw it, I saw
  > it moving behind the building, I can judge that it must be there. This is why memory and belief
  > are important. In real life a unit could for example drive into a building and hide there, in
  > which case it would effectively disappear. I would still know it's there somewhere, I just could
  > not see where exactly. DCS does not allow driving into a building, but the principle stands. No
  > LOS means no observation, but a LOS a moment ago means it's near where it was. In which case
  > memory and belief serve as guidance."*

  **So options 1 and 2 below are wrong and must not be built.** Blocked candidates *should* be
  rejected at admission — no line of sight means no observation, and admitting one would be
  inventing a sighting that did not happen. The existing fail-closed gate is correct and
  `Contact.live_los_clear` never being `False` is correct with it. **This entry is not about
  changing what reaches belief.**

  **What is actually wrong is where the attack run looks for the cause.** `Contact.live_los_clear`
  is the wrong source: by construction it only ever describes a look that *succeeded*. But the cause
  is computed every poll anyway — `check_visibility` decides, for the attack target specifically,
  whether this tick's failure was the mask, terrain LOS, range, or no verdict. **That verdict exists
  and is thrown away.** Reading it from the live gate outcome for the target, rather than from the
  stored contact, needs no change to admission, no widening of what belief holds, and no new
  channel.

  **And the guidance itself is already right**, which is why this is a wording defect rather than a
  behavioural one: `BL-14` continues guiding from the remembered or projected position precisely
  because the user's own earlier direction said to (2026-10-14 §7). The pilot keeps getting steered;
  the only open question is whether Petrovich can say *why* he has stopped seeing it.

  ## ~~Shape of the options, for whoever plans this~~ — superseded above

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
