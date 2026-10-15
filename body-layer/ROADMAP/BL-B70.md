# BL-B70 — Attack-run guidance: what to say and when

- [ ] **Four defects and one new requirement from the 2026-10-15 attack-run sortie — the callout
  repeats with nothing audibly changed, guidance keeps talking while the target is behind the
  airframe, reaching the 12 o'clock sector is silent, and `", obstructed"` is spoken for every
  reason Petrovich is not looking at the target rather than only for the one it means.**
  #status/open Planned 2026-10-15, `plans/attack-run-sortie-fixes/plan.md`.

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
