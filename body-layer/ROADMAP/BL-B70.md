# BL-B70 — Attack-run guidance: what to say and when

- [x] **Four defects and one new requirement from the 2026-10-15 attack-run sortie — the callout
  repeats with nothing audibly changed, guidance keeps talking while the target is behind the
  airframe, reaching the 12 o'clock sector is silent, and `", obstructed"` is spoken for every
  reason Petrovich is not looking at the target rather than only for the one it means.**
  #status/done #needs-flight Planned 2026-10-15, `plans/attack-run-sortie-fixes/plan.md`. Merged
  `feature/attack-run-fixes` (DoD pass, tip `3b69371`); mechanical checks green
  (ruff format/check, `mypy src` 60 files, `pytest` 2016 passed/4 xfailed), full
  Architect→Implementer→Reviewer(×2)→Performance→Security chain complete and APPROVED at every
  gate. **Not yet flown** — this is sortie-feedback work and §1/§2/§4/§8/§9 can only be validated
  in the air; see the Acceptance Testing Plan in `plans/attack-run-sortie-fixes/dod-check.md` for
  what the next sortie must confirm.

  **What shipped**, all inside `belief/attack_run.py`/`belief/speech.py`, pure functions, no optic
  involvement: a `_no_look_cause` taxonomy (`masked`/`obstructed`/`too_far`/`unknown`) computed in
  `check_visibility`'s real gate order; `_should_emit` reduced to a text-equality veto (§1), deleting
  the angular-change clause that was re-speaking unchanged text; a masked tick now returns silence
  while the run stays engaged (§2); a `"twelve o'clock"` marker on entry into the 12 o'clock sector
  from the o'clock register (§4); `", obstructed"` now fires only for a fresh DCS live-LOS `False`
  verdict, its one remaining meaning (§8); and a per-poll LOS-freshness tripwire for the attack
  target plus a dedicated `ATTACK_TARGET_LOS_MAX_AGE_S` (§9), as a measurement rather than a fix to
  LOS priority itself — the priority question stays open, scheduled by user decision rather than
  deferred by oversight (see below). The §5 fallback phrasing was superseded mid-task by direction
  §10/§11 (pulled in from `main`): a four-state losing-sight/regaining-sight register keyed on
  `cause == "too_far"` resolvability, not on tier and not on having been masked.

  **Two defects caught and fixed inside the loop, not shipped**: the first review found
  `_no_look_cause` checking `obstructed` before `too_far`, backwards from `check_visibility`'s real
  gate order (traced to source, not trusted from the function's own docstring claim) — mirrors this
  file's own `BL-B64` "trap that is one keystroke away" callout, same lesson, different site; and
  `where` built from a raw int rather than routed through `_ALIGNMENT_CLOCK_WORDS`, speaking the
  clock hour twice in one sentence. Both fixed in `571e898`, re-reviewed and approved in `review-2.md`.

  **Acceptance boundary, stated plainly**: everything above is verified against fixture logs and
  unit tests, which prove the code does what it says — they cannot prove it is the right thing to
  say at the controls. §1's suppression rate (38% of utterances were dead repeats) and §2's masked
  rate (68% of `obstructed` calls were rear-aspect) are measured from the *failing* sortie's own
  logs, not from a flight with the fix flying. Nothing here can tell whether the twelve-o'clock
  marker lands at the moment a pilot actually needs it, whether the four-state register sounds
  natural in the cockpit rather than merely correct on paper, or whether `", obstructed"`'s new
  narrower meaning still reads as informative rather than terse. That is exactly what the next
  sortie is for.

  **Downstream effect, per the Milestone Completion question**: `[[BL-B71]]` (the §6/§7 optic
  ladder) now has a real cause taxonomy to consume rather than a flat tier signal — the ladder can
  key its naked-eye/binoculars/9K113 choice on `too_far` specifically rather than re-deriving "no
  look" from scratch. `[[BL-B76]]` (filed on `main`, narrowed 2026-10-16) is the one place this
  milestone's own taxonomy is currently dead code in production: the `", obstructed"` branch is
  unreachable because `Contact.live_los_clear` cannot carry `False` through the live admission
  pipeline as currently gated — a pre-existing question this plan traced but correctly left alone,
  since it sits outside BL-B70's Affected Modules. Until `BL-B76` resolves, the `"obstructed"` arm
  of this taxonomy is unverified in practice even once flown, because the condition that would
  trigger it may never actually fire live.

  Source of truth is `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §1, §2, §4, §8, §9
  plus §5's fallback phrasing. The user's own words there outrank the plan.

  **All inside `belief/attack_run.py` and `belief/speech.py` — pure functions, no optic involvement,
  no attention cost.** Deliberately split from `[[BL-B71]]`, which carries the §6/§7 optic ladder:
  this entry is flyable on its own and its payoff is already measured, while the ladder changes what
  Petrovich can see of the rest of the world during a run and needs its own sortie. The cheap,
  measured win should not wait behind the risky one.

  **Measured payoff, from this sortie's own logs rather than estimated:**

  - **47 of 125** attack-run utterances in `dcs-belief-truth-20261015-164451.jsonl` were
    byte-identical to the one immediately before (38%).
  - **45 of 66** `obstructed` calls in the same sortie were rear-aspect, so the §2 silence rule alone
    removes two-thirds of the noise.

  **The one finding to read before starting, because it reverses the fix shape in the brief:**
  `_should_emit` **already** compares the rendered utterance — it is a *disjunction*, and the repeats
  come from the second clause (`> ATTACK_RUN_CHANGE_THRESHOLD_DEG` on either axis) firing while the
  text is unchanged. The emit threshold is 3.0° while the vocabulary's own quantisation is 10°
  (elevation gate), 30° (o'clock sector) and 7.5°/5.0° (azimuth rows), so **a 3° threshold on a 10°
  word gate cannot do anything except re-speak unchanged text.** The fix is to make text equality a
  *veto* and delete the angular clause, not to add a comparison that already exists.

  This is consistent with direction §10 rather than a reversal of it: §10 recorded the slow-drift
  guard as a risk *"recorded rather than designed around… whether that happens in the air is a sortie
  question."* The sortie answers it.

  **The three causes now split, each telling the pilot something actionable** (§8, user: *"'...
  obstructed' for DCS LOS, be it terrain or buildings"*):

  | cause | behaviour |
  |---|---|
  | live DCS LOS says blocked | `", obstructed"` — the word's only remaining caller |
  | cockpit mask | **silence**; the run stays active (*"keep attack run active until pilot commands otherwise"*) |
  | range/size | `", <age phrase>"` reusing `speech._spoken_age_phrase`; `[[BL-B71]]` tries a better optic first |
  | no verdict | tier 2, **no qualifier** — fail-open |

  `Contact.live_los_clear` is already a tri-state (`True`/`False`/`None`), and `ContactStore.tick`'s
  engagement term already decided the `None` case the same way (fail-open). **Reuse that predicate
  rather than minting a rule** — the admission gate stays fail-closed, the spoken word is fail-open,
  and they are different questions.

  **A trap that is one keystroke away** (`[[BL-B64]]` produced three of this class): `decide`'s emit
  path constructs a fresh `AttackRunState(...)` rather than `replace(...)`. It sets all six fields
  today, so nothing is dropped — but the `last_spoken_clock_hour` this entry adds for §4 would be
  silently reset on every spoken tick. Switch that site to `replace()`.

  **Escalation flagged in the plan:** several existing `test_attack_run.py` cadence tests pin
  `ATTACK_RUN_CHANGE_THRESHOLD_DEG` and must be *rewritten* rather than extended, because the
  constant they assert on ceases to exist.

  Related: `[[BL-14]]` (the milestone this fixes), `[[BL-B64]]` (made the sight a selectable optic;
  the bug class above), `[[BL-B71]]` (the optic ladder, which consumes this entry's cause taxonomy),
  `[[BL-B66]]`/`[[BL-B67]]` (will need that taxonomy to say anything honest about an ATGM run).

  **The attack-target LOS priority (§9) is scheduled here and not earlier — user decision,
  2026-10-15.** Asked whether the ~8% live-LOS no-verdict rate warranted pulling that fix forward,
  the answer was to observe rather than tune, because the cost is density-dependent: *"If it's very
  dense then there's a lot of units to LOS and that is a real cost. If just a few units inside the
  player bubble then it's nearly free. A very dense scene is on the rare side."* So this entry
  carries the priority fix on its own schedule, and nothing about the LOS feed is a prerequisite
  for starting it. See `[[AC-8]]`/`[[WM-W2]]` for the measurement that would reopen the wider
  question.
