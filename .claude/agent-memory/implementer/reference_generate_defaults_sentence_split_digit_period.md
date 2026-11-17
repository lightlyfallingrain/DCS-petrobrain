---
name: generate-defaults-sentence-split-digit-period
description: generate_defaults.py's first-sentence splitter never splits after a period preceded by a digit (merges two sentences) and has no abbreviation guard, so "e.g."/"i.e." mid-sentence splits too early (truncates one) -- two opposite failure modes, same fix
metadata:
  type: reference
---

`body-layer/tools/generate_defaults.py`'s `_SENTENCE_SPLIT` regex has a
negative lookbehind for a digit immediately before the period
(`(?<!\d)`), there specifically so `"0.1"` inside a sentence never splits
it. Side effect: a `#:` comment whose intended first sentence legitimately
ends on a numeral or a short reference like "Stage 3." does not split
there either — the renderer silently walks past it to the *next* period
and merges both sentences into `config/defaults.toml`'s rendered comment.

Hit on BL-B104 (`plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 3,
`DEPRESSION_SIGMA_DEG`): first sentence ended "... Stage 3." and the
rendered first line in `defaults.toml` turned out to be two sentences
concatenated, not caught by reading the source diff — only by reading the
*rendered* TOML, which this role's own instructions already ask for ("check
the rendered `defaults.toml`, not the comment") for exactly this class of
defect.

**How to apply**: when writing a `#:` tuning comment, make sure the first
sentence's own period is not immediately preceded by a digit (a bare
number, a "Stage N", a version-looking token). Rephrase so the sentence
boundary lands on an ordinary word, then regenerate and *read* the
rendered file before considering the constant done — same check this
project's commit-quality gate already expects, just caught one step
earlier.

**The opposite failure, hit on BL-17 Stage 3b (`RULE_GATE_HOLD_TIMEOUT_S`):**
the splitter has no abbreviation guard either, so a period that is *not*
digit-adjacent still splits even when it isn't really a sentence boundary
— "its category's gate said `HOLD`, e.g. the takeover-settle window)
before giving up..." split at "e.g." (a period followed by a space, like
any other sentence end), truncating the real first sentence mid-clause.
Avoid any abbreviation ("e.g.", "i.e.", "etc.") or other embedded ". "
inside the sentence you intend as the description — reword with "such
as"/"that is"/"and so on" instead of hoping the tool special-cases it.
Same remediation both ways: regenerate and read the rendered
`defaults.toml` line itself, since a diff of the source comment reads as
plausible in both failure directions.
