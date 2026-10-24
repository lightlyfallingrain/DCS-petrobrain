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

  ## `/explore`d 2026-10-16 — measure the no-verdict case before designing for it

  Two answers, both narrowing this further.

  **On whether the word earns its place at all:**

  > *"Terrain blocked LOS can happen if in mountainous region. Airframe blocking is more common."*

  So `", obstructed"` stays — it is real, just not on the flat desert both 2026-10-15 sorties were
  flown over. The acceptance sortie for this should be **mountainous**, not a repeat of that
  terrain, or it will again measure a case that barely fires. The common case is the airframe,
  which §2 already resolves with silence.

  **On the no-fresh-verdict case (`live_los_clear is None`, ~8% of gate-4 evaluations in the 16:44
  sortie), which §9 left open as the one thing neither silence nor `", obstructed"` answers:**

  > *"Before acting on LOS none, we should know how often that happens. As it stands now, log it
  > and then ignore in cockpit behaviour."*

  **So §9's third sub-question is answered for now: no cockpit behaviour, log only.** The current
  fail-open `"unknown"` arm (speak the guidance, no qualifier) is correct as it stands and must not
  be given a word of its own until the rate is known for the attack target specifically.

  ### The instrument that exists does not answer this, and the gap is one line

  `belief_truth_log._write_attack_run_tripwire` already writes one
  `kind: "attack_run_los_tripwire"` row per poll for the attack target, carrying
  `present_in_snapshot`, `join_skew_s` and `live_los_clear` — built by `[[BL-B70]]` for exactly this
  §9 measurement. **But its loop skips every entry whose outcome is not `ADMITTED`:**

  ```python
  if entry.outcome is not GateOutcome.ADMITTED or entry.observation_id is None:
      continue
  ```

  A target rejected *at gate 4* is therefore recorded as `present_in_snapshot: false`, which is the
  same value it gets when the target was simply outside the pushed wedge that poll. **The two cases
  the user wants counted — "blocked" versus "no answer yet" — are indistinguishable in the one log
  built to count them**, because both land in the rejected set that this loop never reads.

  The detection trace itself does record `GateOutcome.TERRAIN_LOS` for rejected candidates, and
  `live_los_coverage` counts `evaluated`/`no_verdict` across *all* candidates — so the theatre-wide
  rate is already measurable. What is missing is the target-specific split, which is what the
  direction asks for.

  **Scope for this entry, as it now stands:** widen the tripwire to read the target's rejected entry
  too and record its `GateOutcome` and `live_los_clear` (`False` versus `None`). That is a logging
  change in `belief_truth_log.py` only — no change to admission, no change to what belief holds, no
  new word in the cockpit. Then fly it mountainous and read the rate before deciding anything else.

  ### Step 1 — `[x]` DONE 2026-10-16, `9616235a` (`feature/bl-b76-tripwire-rejected`) #needs-flight

  **The entry's own box stays `[ ]`**: this is one of three steps, and steps 2 (fly it mountainous,
  read the rate) and 3 (decide whether the attack run should read the live gate outcome rather than
  the stored contact) are both outstanding.

  Shipped exactly the scope above — `outcome` (`"admitted"`/`"rejected"`/`"absent"`) and, for a
  rejection, `gate_outcome` and `live_los_clear` (`False` versus `None`), for the attack-run target
  specifically. Reviewer APPROVED after one required fix, Security APPROVED, Performance
  APPROVED-MONITOR, DoD PASSED on fixtures. Nothing in the cockpit changed, confirmed by diff.

  **One caveat the Step 2 reading has to account for, and it is the reason this paragraph is here
  rather than only in a docstring.** `Contact` carries no DCS `object_id` — the no-omniscience
  boundary — so the join from the attack target to its *rejected* trace rows had to be invented: an
  `object_id -> contact_id` cache inside the log writer, populated only from **admitted** rows. If
  the target's perception cluster splits and the minority child is rejected on the same poll the
  split would have resolved, the cache never sees the split and credits that rejection to the
  target. **This can only inflate the `"rejected"` count, never deflate it**, and it fires exactly
  when a group scatters under fire — which is an attack run. So read the Step 2 rate as an **upper
  bound** on true LOS-blocked, and watch for group-scatter moments near the target when reading it.

  **Step 2 is a mountainous sortie, deliberately.** Both 2026-10-15 sorties were flat desert, where
  terrain blocking barely fires — which is structurally why the rate is unknown and why a repeat
  over the same terrain would measure nothing.

  Related: `[[BL-B70]]` (implements §8 against this dead input), `[[BL-14]]`, `[[X-B29]]` (the live
  LOS feed), `[[AC-8]]`/`[[WM-W2]]` (its availability).

  ### 2026-10-24 — `plans/attack-run-los/plan.md` answers the register half of step 3, narrower than framed

  Step 3 asked whether the attack run should read the live gate outcome rather than the stored
  contact. `plans/attack-run-los/plan.md`'s F2 fix does **not** change that — still `Contact.
  live_los_clear` via `_no_look_cause`, unchanged. What it changes is a different, adjacent defect
  found while fixing the sortie-reported "eyes on" bug: the loss/regain *register*
  (`AttackRunState.last_spoken_unresolved`) was keyed on `cause == "too_far"`, so a stale
  `"obstructed"` verdict decaying to `"unknown"` once `ATTACK_TARGET_LOS_MAX_AGE_S` elapsed read as
  "regained sight" with no fresh look at all. Re-keyed on `tier != 1` instead.

  **Decision 2 adds a further mitigation, not a resolution, to this entry's own open question.** A
  new `AttackRunState.terrain_blocked_held` flag holds a fresh `"obstructed"` verdict's consequence
  (the `", obstructed"` qualifier, and the new `"Behind the ridge, ..."` losing-sight line) across
  that verdict's own freshness window ageing out, until a genuine tier-1 look supersedes it. This
  narrows but does not close the risk this entry's Step 2 exists to measure: if `Contact.
  live_los_clear` never actually reads `False` in live play (this entry's own open question —
  rejected at admission, never updating the stored contact), the hold has nothing to latch onto and
  the `"unknown"` fail-open path still dominates exactly as before. **Step 2's mountainous-sortie
  measurement is unchanged and still the thing that answers this.**
