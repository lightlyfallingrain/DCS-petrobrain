# Stage 1 bench results on the real corpus

**Date:** 2026-09-19 · whisper.cpp 1.9.4, `ggml-small.en`, Apple Silicon · 252 clips, the user's own
voice and headset, recorded on the Windows box · matcher cutoff `_MATCH_CUTOFF = 0.6`

This file exists because these figures were being cited from `plans/inbound-speech/plan.md` prose,
which is a plan rather than a record. Constants in `command_matcher.py` and `voice_commands.py` are
set from the numbers below, so they need a place that is unambiguously data.

## Headline

| row | top-1 | verbatim | repaired | correct confidence | incorrect confidence |
|---|---|---|---|---|---|
| plain | 228/252 (90.5%) | 143/228 | 85 | mean 0.68, min 0.45, max 1.00 | mean 0.63, min 0.49, max 0.91 |
| **`--prompt`** | **250/252 (99.2%)** | **231/250** | **19** | **mean 0.82, min 0.60, max 0.95** | **mean 0.62, min 0.58, max 0.66** |

## The confidence distribution, and what it licenses

**On the plain row, confidence is unusable as a reject signal.** Correct and incorrect sit five
points apart (0.68 against 0.63) with almost entirely overlapping ranges, and the single most
confident answer in the whole run was *wrong* — 0.91 on `'Kansa lalask'` for "cancel task". Any
threshold that catches real errors discards a comparable pile of correct commands.

**Prompted, it separates.** Correct answers run 0.60 to 0.95 with mean 0.82; both failures land at
0.58 and 0.66, below that mean. A reject floor near 0.60 is therefore defensible *on this row and
no other* — `ACT_FLOOR = 0.60` is the measured minimum confidence of a correct answer, and the
claim depends on `--prompt` being in use.

The margin is thin and rests on two failures, so treat 0.60 as a starting point with evidence
rather than a tuned optimum. The sortie is what tests it against transmissions spoken while flying.

## The two remaining errors

```
disregard_2.wav   'This is the card.'    0.58   -> cancel_nevermind
scan_south_2.wav  'this kind of stuff'   0.66   -> scan_bearing_s
```

Both are safe misses — no match, so the behaviour is "say again" — rather than wrong commands.
Both are also patterned rather than random, and name the two weakest words in the vocabulary:
`disregard`, the redundant third phrasing of `cancel_nevermind`, and `scan`, heard as "this kind
of", which is the last survivor of a pattern that dominated every earlier run and is the most-used
verb in the vocabulary.

## How the number got here

Only one of these steps was about the speaker.

| | accuracy | what changed |
|---|---|---|
| 55.6% | first run | corpus truncated by a recorder bug — **not a voice result** |
| 90.5% | recorder fixed | sox buffer 8192 → 1024, tail capture, pre-roll |
| 98.4% | `--prompt` | soft vocabulary biasing |
| 99.2% | repetition collapsing | recovering whisper's own loop artefacts |

## Repaired matches, and why the split is reported

19 of the 250 correct answers matched only after fuzzy repair rather than arriving verbatim. That
split is reported separately because fuzzy matching can repair a wrong *verb* into a valid command
and score it correct — "record three o'clock" is one edit from "report three o'clock", and verbs
select the action here. A high accuracy carried by many repairs is a weaker result than the same
accuracy arriving verbatim, and prompted decoding improved the split (85 repairs down to 19) by
more than it improved the headline.
