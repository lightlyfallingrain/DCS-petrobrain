---
name: run-the-card-utterances-through-the-matcher
description: Every spoken form in an acceptance card goes through match_transcript first; on BL-13 that found three card-breaking facts no review document held
metadata:
  type: feedback
---

**Every utterance that goes into a voice acceptance card is run through
`command_matcher.match_transcript` first, on the branch under test, and the real result pasted.**

**Why:** this is now twice measured. The 2026-10-06 card nearly instructed the pilot to say
*"Petrovich, describe."*, which returns **no token at all** (a wake-word prefix routes to the brain
as free speech). On BL-13 (2026-10-10) the same ten minutes of probing found three more things no
review document contained, each of which would have read as the feature being broken:

| probed | result | why it matters to the card |
|---|---|---|
| `Petrovich, report left` | `token='report'`, **`slots=None`** | the wake word now loses a *filter* rather than the whole command — he gets the whole scene and thinks "left" was ignored |
| `report trucks near` / `report air defence near` / `report armour north` | the `descriptor` slot is **silently dropped** | the seven accepted *what* words are singular and do not include the user's own vocabulary |
| `report six o'clock` | `report_clock_8` | a silent wrong-direction match for the rear hours, on base *and* tip — the same shape as the bug the milestone fixed |

None of these is a code defect this branch introduced, and no review was wrong to omit them: a
review reasons about code, a card tells the pilot what to *say and hear*. They are only findable by
saying the words.

**How to apply.** For a card on any speech feature: write the utterance list first, run it through
the matcher in one script, and let the real output decide the card's wording — including the
negative cases worth warning about. Do the same for the output side: render the real strings from
the real renderer rather than quoting the plan's mock, and paste the word counts. On BL-13 the
renderer's own output confirmed the 28-word and 25-word scenes the review claimed, which is cheaper
than trusting them and makes the card's examples the system's own voice.
