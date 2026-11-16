---
name: vocabulary_bare_word_tokens
description: When a plan names one token for several bare single-word phrases (e.g. "left/right/forward/back" -> one token), split into one enumerated token per word instead of trying to carry a slot through the generic phrase-table match.
metadata:
  type: feedback
---

When implementing a plan's vocabulary table row that lists ONE token name for SEVERAL distinct
bare single-word phrases (e.g. BL-16 P2b's `hvrt_translate` row covering "left"/"right"/"forward"/
"back", and `hvrt_step` covering "up"/"down"), do not try to carry the matched word as a "slot" on
one shared token via `command_matcher.py`'s generic phrase-table fallback. That fallback only
returns `_PHRASE_INDEX[best_phrase]` (the token name), never which literal phrase matched — once
several phrases share one token, the direction information is gone by construction, and "no slot
parser needed" (a plan's own instruction) rules out adding a parser to recover it.

**What to do instead**: split into one enumerated token per word (`hvrt_translate_left`,
`hvrt_translate_right`, ... `hvrt_step_up`, `hvrt_step_down`), each a plain `PHRASES` entry of one
word, dispatched through a small lookup table (`token -> direction`) in `crew_console.py` to one
shared handler — the exact shape `_RELATIVE_SCAN_TOKENS` already uses for "scan ahead"/"scan
left"/"scan right". Also update `DISPATCHED_COMMAND_TOKENS` to the enumerated names, not the
plan's literal singular name.

**Why**: the plan's "Token" column in its vocabulary table is a readback/behaviour-level summary,
not a literal implementation contract — what matters is that the *spoken phrase -> action*
mapping and the *readback per phrase* match the table exactly, not that there is exactly one
internal token per table row.

**Also check for a bare single-word collision when doing this**: a bare word like "right" can
fuzzy-anchor onto an *existing* verb-anchored branch via `difflib.SequenceMatcher` even without
being a verb itself — measured: `ratio("right", "sight") == 0.8`, well above `VERB_FLOOR` (0.5),
so a bare "right" resolved to `point`'s own `relative` slot (which already lists "left"/"right" in
`RELATIVE_WORDS`) before the new enumerated token's own phrase-table entry was ever reached. Fix:
check the new bare single-word tokens as an **exact, whole-transcript** match (`len(words) == 1
and words[0] in <lookup>`) *before* any fuzzy verb-anchor branch runs in `match_transcript`, rather
than narrowing the existing branch's tolerance (which risks regressing its own calibrated
matching). Grep every existing `RELATIVE_WORDS`/`STEP_DIRECTION_WORDS`/similar slot-word table for
overlap with the new bare words before assuming no collision exists — do not just test the happy
path.
