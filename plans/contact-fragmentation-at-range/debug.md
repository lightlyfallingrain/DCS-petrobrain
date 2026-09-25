# Contact fragmentation at range — an outpost becomes 18 contacts

**Status: diagnosed, not fixed.** Investigated 2026-09-25 from a real sortie's
`--belief-truth-log`. Not fixed in-session because `fix/scan-is-not-watch` was live against the
same files (`contacts.py`, `association_over_time.py`) and two agents editing them concurrently
buys a merge conflict for no speed.

## The symptom the user reported

> *"I'm getting multiple reports like 'ground 1 o'clock, 2 km' when those should really collapse
> into a group."*

Confirmed in the speech rows of `~/dcs-belief-truth.jsonl`: `"ground, 11 o'clock, 1 kilometre."`
spoken **four times**, and three other clock/range pairs spoken twice each.

## What the log shows

**18 distinct contacts for what is one outpost.** The far group all sit within ~160 m of each
other in truth. `CONTACT_8` and `CONTACT_10` are **1 m apart** — 0.03° subtended at 3 km — and are
separate contacts.

**They were founded across ten different polls, not one.** That is the decisive fact: per-poll
clustering never had the chance to merge them, so this is *association over time* failing, not
`perception.clustering`.

| contact | founded at range | position error then |
|---|---|---|
| `CONTACT_3` | 6956 m | **1576 m** |
| `CONTACT_11` | 5427 m | **1496 m** |
| `CONTACT_5` | 4176 m | 1233 m |
| `CONTACT_7` | 4169 m | 1039 m |

## Why — and the first hypothesis was wrong

The obvious reading is that position error grows with range until the association gate rejects a
genuine re-observation. **Measured, that is backwards.** `perception.estimation.naked_eye_sigma_m`
scales with range, so the 3-sigma gate grows *faster* than the error does:

| range | σ cross | σ down | 3σ gate, two looks |
|---|---|---|---|
| 1 km | 52 m | 170 m | 222 m cross / 721 m down |
| 4 km | 209 m | 680 m | **889 m cross / 2885 m down** |
| 8 km | 419 m | 1360 m | 1777 m cross / 5770 m down |

At 4 km the gate accepts a 2.9 km down-range discrepancy. Errors of 500–1600 m sail through.

**The gate being generous is the defect, not the cure.** `ContactStore.ingest`:

```python
if len(passing) == 1:
    contact = passing[0]        # merge
    contact.record(percept)
else:
    contact = Contact.from_percept(...)   # 0 OR 2+ -> a NEW contact
```

That `2+ → new contact` is the deliberate anti-guessing rule: when several contacts plausibly match,
do not guess which. Sound in isolation. But in a dense outpost at range, a wide gate means *many*
existing contacts pass — so every new look is ambiguous, founds another contact, and thereby makes
the *next* look ambiguous against one more candidate.

**This is a recurrence.** `plans/contact-duplication-ambiguity-runaway/` records the same runaway
(120 contacts for 2 real objects over 60 polls). Its fix was object-permanence correlation via
`Percept.continues_observation_id`, which bypasses the gate entirely — and that fix is still in
place and still correct. What is new is the *trigger*.

## Why object permanence does not save it here

Continuity is resolved by **majority object overlap** across a poll's clusters
(`naked_eye_source._build_observations`). It holds only while cluster membership is stable between
polls. At long range in a dense scene, three things churn it:

1. **The gaze sweeps.** The o'clock scan loop means a given group is only in the focus cone part of
   the time, so its members appear and disappear from the candidate set.
2. **The gate is marginal at range.** Candidates near the detection threshold flicker in and out
   between polls.
3. **`NAKED_EYE_MAX_NEW_GROUPS_PER_POLL = 3`** throttles how many new groups may be admitted per
   poll, so a dense outpost is admitted a few at a time across successive polls — which is exactly
   the "founded across ten polls" pattern the log shows.

When membership churns, the majority vote fails to resolve, continuity returns `None`, and `ingest`
falls through to the gate — where the runaway is waiting.

## One further observation, which complicates any fix

**Contacts drift between real objects.** `CONTACT_3` was founded as a BMD-1 at 6956 m and now
reports as a Ural-375 at 2771 m. The contact↔object join in the belief-truth log re-resolves to
whichever object is nearest now, so the per-contact "position error" figures above are error
*against whatever it is currently matched to*, not a stable per-object error. Any fix validated
against that join needs to account for it, or it will be measuring its own join instead of the
defect.

## Directions, none chosen

Deliberately not picking one — this needs a decision, and the anti-guessing rule is load-bearing.

- **Make the ambiguity rule range-aware.** Two contacts that are mutually ambiguous *and* close
  together in belief are more plausibly one thing than two; founding a third is the worst of the
  three options. Merging ambiguous-and-adjacent contacts, rather than splitting, inverts the
  runaway into convergence.
- **Cap the gate's growth.** σ scaling with range is physically honest for a *single* look, but a
  gate three kilometres wide is not discriminating anything. A ceiling would restore the rule's
  original meaning without touching the rule.
- **Make continuity survive churn**, e.g. by correlating on object ids present in *either* poll
  rather than requiring a stable majority. This attacks the trigger rather than the runaway.
- **Reconsider the per-poll admission cap** at least for candidates that cluster together. The cap
  exists to stop a burst of new contacts; here it is what spreads one group's founding across ten
  polls and breaks continuity.

  **DONE, 2026-09-25 — `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` raised 3 → 5** on the user's own
  perceptual grounding (*"distinction up to 5 is trivial. 6 - 10 take a couple of seconds, 10+ is
  more difficult and needs more sweeps"* — the subitizing boundary; 3 sat below it). See that
  constant's comment for why his three tiers need no tiered mechanism: at a 1 s poll, serial
  admission at 5 per poll reproduces all three.

  **This attacks the trigger, not the runaway.** Fewer polls to admit a dense scene means fewer
  chances for cluster membership to churn and continuity's majority-overlap vote to fail. Whether
  that alone is enough is a question for the next sortie over the same outpost — the ambiguity rule
  below is untouched and still open. If fragmentation persists with the cap at 5, the remaining
  directions are the real fix and this was only a mitigation.

## What would confirm a fix

The same sortie shape: a dense outpost approached from 8 km. Success is a small, stable number of
contacts that does not grow with dwell time, and no repeated identical callouts. The
`--belief-truth-log` plus `--eyesight-view` are now the instruments for exactly this — both were
built the day this was found, and the diagnosis above came entirely out of the log rather than
out of the code.
