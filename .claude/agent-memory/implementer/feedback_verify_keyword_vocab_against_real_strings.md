---
name: feedback-verify-keyword-vocab-against-real-strings
description: When hand-authoring a substring keyword table against a DCS-sourced identifier field, check keywords and their tests against real identifier strings, not plausible-sounding guesses.
metadata:
  type: feedback
---

A PB-1.5 review (`plans/pb1.5-naked-eye-detection/review.md`, fixed in the following session)
found `body-layer/src/perception/object_model.py`'s `OP_SHIP` keywords
(`cruiser`/`frigate`/`corvette`/`destroyer`/`boat`/`ship`) and its SA-3/6/8/9/13/15 keywords were
English/NATO-designation words, not real DCS `object_type` strings — completely unreachable
against live `LoGetWorldObjects` data (0 real matches for the SA-* set; the 6 `OP_SHIP` "matches"
were coincidental English-word substrings inside unrelated compound names, not real hits). The
masking mechanism: the unit tests asserted against fabricated strings (`"Grisha corvette"`,
`"SA-3 Launcher"`) that happened to contain the keyword by construction, so they passed even
though every real ship/SAM type fell through to fallback.

**Why:** a keyword table against a DCS-derived free-text field (`object_type`, but the same risk
applies to any Lua-sourced identifier/name field) is easy to hand-author from plausible-sounding
English or NATO-designation words that never actually appear in DCS's own identifiers, which are
hull/component proper nouns (`"Slava"`, `"5p73 s-125 ln"`, `"Kub 2P25 ln"`). A test written
against a fabricated example string that "should" match doesn't catch this — it only proves the
keyword matches itself.

**How to apply:** when hand-authoring or reviewing a keyword/lookup table against any
DCS-sourced identifier field, (1) pull a real sample of the field's actual values (a Lua source
file already synced locally, e.g. `HelperAI_reporting_names.lua`'s 595-entry
`dcs_object_type -> reporting_name` map, is the authoritative source for `object_type` — see
`aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`) and check each keyword
against it before trusting the table; (2) write/fix tests to assert against those real strings,
not hand-typed guesses that only prove self-consistency; (3) commit a small curated sample of
real strings as a test fixture with a coverage-floor assertion, so a future edit narrowing a
keyword can't silently regress reachability without a test failing. When one category in a table
turns out broken this way, spot-check sibling categories in the same table the same way — this
review's SA-3/6/8/9/13/15 finding came from being asked to spot-check after the OP_SHIP bug was
found, and it turned out equally broken. Related: [[project_pb1_5_naked_eye]].
