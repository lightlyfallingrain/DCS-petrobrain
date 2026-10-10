---
name: slot-branch-beats-phrase-table
description: In audio-adapter, a slot-parsing branch placed in front of the phrase table is 4-7x CHEAPER than the phrase table it short-circuits — measured, so "new parsers on the live path" is not a cost risk.
metadata:
  type: project
---

Measured 2026-10-10 (BL-13), `command_matcher.match_transcript`, median of 7 x 2000 calls:

| transcript | path | µs/call |
|---|---|---|
| `report left` | slot branch (1 slot) | **116** |
| `describe armor two o'clock near` | slot branch (3 slots) | **148** |
| `follow two o'clock` | pre-existing follow branch | 95 |
| `scan left` | phrase table | **684** |
| `report contacts` | phrase table | **821** |
| `the weather is fine today` | no verb anchor | 547 |

So the **phrase table is the expensive part**, and any branch that returns before reaching it is a
net saving of ~500-700 µs. The next review asked to judge "three new parsers now run on every
anchored transcript" should expect a *win*, not a cost. Individual parsers are ~3.8 µs each, of
which **3.36 µs is `vocabulary.normalize_for_match`**, which every parser re-runs on the raw text —
so N parsers cost N normalisations. Hoisting one normalisation into the slot-parser would be a 4.7x
saving on a 19 µs term; at per-spoken-utterance frequency that is not worth taking.

The verb gates are cheap and do not chain: each branch gates on one short-string
`difflib.SequenceMatcher(verb, <verb>).ratio()` before touching any parser, so branch *ordering*
costs one ratio per skipped branch, not a scan.

Related: [[report-query-enrichment-dominates]].
