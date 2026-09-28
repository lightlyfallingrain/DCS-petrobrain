# What the 2026-09-28 logs actually show — the noise is not fragmentation

Written 2026-09-28 from `~/dcs-belief-truth.jsonl` (4.2 MB, 6311 rows) after the user reported
*"all units get single call outs and it's way too much noise"* and asked whether this was already
covered. It was attributed to **X-B6** (`plans/contact-fragmentation-at-range/debug.md`, the
outpost-fragments-into-18-contacts runaway) in conversation before the log was read. **That
attribution was wrong**, and this note records why, so the fix is not aimed at the wrong mechanism.

## The file holds seven runs, not one flight

`t_sim` is not monotonic: six large backward jumps split the file into seven appended sessions
(24.5 / 9.8 / 7.7 / 1.9 / 0.6 / 21.6 / 6.4 min). Any rate computed over the whole file is
meaningless — the first pass over this data did exactly that and produced a nonsense figure.
Per-run numbers below.

| run | duration | utterances | contact reports (distinct) | rate | contacts | ever plural |
|---|---|---|---|---|---|---|
| 0 | 24.5 min | 149 | 131 (100) | 5.3/min | 52 | **3** |
| 1 | 9.8 min | 57 | 45 (37) | 4.6/min | 32 | **0** |
| 2 | 7.7 min | 53 | 41 (38) | 5.4/min | 40 | **0** |
| 6 | 6.4 min | 44 | 31 (28) | 4.8/min | 29 | **1** |

## The finding: contacts are singular, so the group vocabulary never gets a chance

**Only 3 of 52 contacts in the longest run were ever plural** (`believed_cardinality_hi > 1`), and
two runs had none at all. Against 62 distinct real objects in the join, 52 contacts is close to
1:1 — which is the *opposite* of X-B6's signature (one outpost exploding into 18 contacts). The
clustering and cardinality machinery from `plans/group-contact-model/` Stages 0–4a is working; it
is simply concluding, correctly under the angular separability model, that vehicles tens of metres
apart at 2 km are individually resolvable.

So the pilot hears one callout per vehicle, at roughly **one every eleven seconds for half an
hour**, each of the form `"ground, 12 o'clock, 2 kilometres."` — and the same line verbatim up to
seven times in one run.

Classification is the aggravating factor: 4310 of 5996 belief rows sit at `PRESENCE` /
`OP_GROUPSOMETHING`, i.e. the word is *"ground"* for almost everything. Every report is
near-identical by construction.

## Why speech-time aggregation does not rescue it

`belief.callouts.group_candidates` buckets by **the same `(unit type word, range word)` pair**, then
chains by adjacent clock. Two conditions have to hold at once, and in these runs they rarely do:

1. **The members must be pending simultaneously.** The scheduler speaks at most one thing per tick,
   and detections arrive spread across polls. The first contact is spoken before its neighbours are
   even detected, so there is nothing to group it with.
2. **The range *word* must match**, not the range. `_format_range_km`'s granularity puts
   `"2 kilometres"` and `"2.5 kilometres"` in different buckets, so two vehicles 400 m apart in
   depth at the same clock never aggregate.

The group path does fire for the player-requested `report` command, and there it degenerates
visibly — `"ground, 5 o'clock, 3 kilometres. ground, 5 o'clock, 4 kilometres. ground, 6 o'clock,
4.5 kilometres. And more."` is `render_report` joining three *separate* group lines because their
range words differ. That is more noise than one sentence, not less.

## What this means for the fix

The lever is **not** the association gate or the anti-guessing rule (X-B6's four directions), and
not the vocabulary (settled 2026-09-19, and `"a couple of"`/`"several"`/`"a handful"` are live in
`speech.py` today). It is the **callout policy**: how long Petrovich is willing to wait before
speaking, and how coarse the buckets are when he does.

X-B6 remains a real, separate defect — it was diagnosed from a different sortie shape (a dense
outpost approached from 8 km) and its `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` 3 → 5 mitigation was
never re-flown against that shape. Nothing here closes it. But it is not what made tonight loud.

## The question this leaves for the user, which is genuinely his

Everything above is mechanism. What a crew member *should* say when sixteen individually-resolvable
vehicles sit in one sector is a judgement about the cockpit, not about the code — and the existing
settled decisions do not cover it, because they assumed the plural case would arrive as one
plural *contact*, not as sixteen singular ones.
