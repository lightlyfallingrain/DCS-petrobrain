---
name: project-bl16-vocabulary-grep-stopped-one-layer-short
description: BL-16 amendment plan check — a plan that correctly grepped for vocabulary token collisions still never routed the new tokens into the one table (audio-adapter's hand-synced vocabulary.py) that actually biases speech recognition toward them.
metadata:
  type: project
---

BL-16 parked-mode (mode 2) amendment check, 2026-11-15. Generalizable shape, not specific to this
feature.

**A plan can do real due diligence on "does this new word collide with an existing one" and still
miss "does this new word get heard at all."** The amendment's vocabulary table (~15 new spoken
tokens: break turns, break-away, HVRT translate/hold/step, etc.) came with an explicit, grepped
collision check against `body-layer/src/belief/crew_console.py`'s token tables and
`audio-adapter/src/vocabulary.py`'s `PHRASES` table — genuinely done, not assumed, and correct as
far as it went. But the plan's own text for the audio-adapter side of the work said only "new slot
parsers needed" (i.e. `command_matcher.py`-level argument parsing) and never named the one step
that actually gets a new word into Petrovich's ears: adding it to `vocabulary.py`'s
`TOKENS`/`PHRASES` tables, which `to_prompt()` feeds into whisper's recognition bias and which
`audio-adapter/CLAUDE.md` documents, in its own words, as a **rule**, not a nicety — "a new command
or slot word goes into these tables, never only into `command_matcher.py` or body-layer, or
whisper is never biased toward it." That file's docstring even names the exact failure this
produces if skipped: a 2026-10-23 incident where an under-populated prompt caused real mis-hears
("violence"/"same ahead" in the speech logs").

**Lesson for future plan-aligner passes, on any feature that grows the spoken vocabulary:**
checking for collisions in the matching/dispatch tables is necessary but not sufficient. Trace the
new words all the way to the *recognition-bias* layer too — in this project, that's specifically
`audio-adapter/src/vocabulary.py`'s hand-synced `TOKENS`/`PHRASES`, which has **no automated check**
tying it to `crew_console.py`/`ALLOWED_COMMANDS`, so a plan that only mentions the dispatch side is
a plausible, easy-to-miss gap. Read `audio-adapter/CLAUDE.md`'s "Structure" section for
`vocabulary.py` before signing off any plan that adds player-spoken tokens — it is the file that
tells you this layer exists and that it is a rule, not a convention to infer.

This is a different shape from [[project_bl16_parked_u3_contradicts_ep5]] (an open recommendation
cited as closing an expectation it contradicts) and from
[[project_bl16_late_requirement_and_recommendation_drift]] (a later user requirement the plan text
never absorbed) — here the plan's own stated due-diligence (the grep) was real and correct, but
stopped one layer short of where the behaviour actually lives.
