---
name: generator-strips-legitimate-closing-backtick
description: body-layer's tools/generate_defaults.py had two _first_sentence() bugs -- stripped a legitimate closing inline-code backtick, and split on a period inside an embedded pilot quote -- a fourth/fifth instance of the "check the rendered file, not the comment" defect class, found on BL-B80 v2 (SLEW_EL_DPS, SEEN_AIM_HEIGHT_OFFSET_M). FIXED in BL-B80 v2 review fix 1 (28d45a09); this entry is now the historical record plus the transferable lesson.
metadata:
  type: project
---

**Status: fixed.** `body-layer/tools/generate_defaults.py`'s `_first_sentence()`/`_SENTENCE_SPLIT`
were rewritten in BL-B80 v2 review fix 1 (commit `28d45a09`). Verified by re-review (mutation
of both the regex and the strip logic independently reproduced the original red, then restored
clean) -- this is not a residual risk, it is closed. Kept as a memory entry for the transferable
lesson, not as an open finding.

**The two original bugs, for context:**

1. `_SENTENCE_SPLIT` matched `\.` optionally followed by `**`/backtick, assuming any markup
   *closing* a sentence sits *after* the period. The normal, correct Markdown form is the
   opposite -- `` `X`. `` -- markup closes, *then* the full stop. `_first_sentence` then did
   `parts[0].strip().strip("*\`")`, which blindly stripped trailing backticks/asterisks
   regardless of why they're there -- eating the legitimate, correctly-placed closing backtick of
   an inline-code span that happened to be the sentence's last token (`SLEW_EL_DPS`).
2. The same regex had no awareness of an embedded quotation's own internal punctuation, so a
   comment quoting the pilot verbatim with its own full stop split at the period *inside* the
   quote, discarding the quote's substance (`SEEN_AIM_HEIGHT_OFFSET_M`).

**The fix:** `_SENTENCE_SPLIT` now has a forward lookahead requiring an even number of `"` between
the candidate period and the end of the comment block (so a period inside a balanced quoted span
never ends the sentence), and `_first_sentence` no longer blanket-strips both ends -- it only
removes markup the split's own optional group actually matched *after* the period, putting it
back after the period unless that markup also opened the sentence (in which case both ends are
dropped as a whole-sentence wrap). Regenerating repaired 9 entries total: the two above plus 7
already on the branch that had silently lost a leading or closing backtick/asterisk
(`ATTACK_RUN_ELEVATION_GATE_DEG`, `ATTACK_RUN_LINED_UP_AZIMUTH_DEG`,
`BUILT_UP_VILLAGE_MAX_AREA_M2`, `ATTACK_TARGET_LOS_MAX_AGE_S`, `FIRING_MAX_AGE_S`,
`IDENTITY_HALF_LIFE_S`, `MEDRES_ANGULAR_RADIUS_RAD`) -- confirming this was a generic generator
defect, not confined to the two new tunables that exposed it. New
`tests/test_generate_defaults_first_sentence.py` holds the fix with 7 tests, 4 of which fail
against the pre-fix code (verified again independently at re-review, not just taken from the
implementer's account).

Both corruptions used to regenerate identically from a fresh run, so `test_tuning_defaults_toml.py`'s
staleness check passed on both -- it only proves the committed file matches a fresh regeneration,
never that the generator itself is correct. This is why the fix needed its own dedicated test file
rather than relying on the staleness check to hold it.

**Transferable lesson, still live:** when adding a new `#:` comment whose first sentence would
embed a quoted period or end on a legitimately-closed inline-code span, the generator now handles
both correctly -- but **always re-read the rendered `config/defaults.toml` line itself after
regenerating**, not the source comment, before trusting a new tunable's description. The generator
fix closes this specific class of corruption; it does not change the standing instruction that the
rendered file, not the `.py` diff, is the thing to check (`.claude/agents/reviewer.md`, "Verifying
the tuning pattern").

See `plans/9k113-sight-pointing/review.md`'s "Finding 1" (original) and its "v2 re-review" section
(fix verification) for the full trace.
