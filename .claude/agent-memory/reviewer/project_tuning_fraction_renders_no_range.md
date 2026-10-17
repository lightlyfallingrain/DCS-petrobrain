---
name: project_tuning_fraction_renders_no_range
description: tuning.fraction()-declared constants render no "range:" line in config/defaults.toml because generate_defaults.py's AST scan only reads lo=/hi= keywords at the call site, and fraction() has none (it fixes 0.0/1.0 internally by delegating to real()) -- not a defect in code using fraction(), a pre-existing generator gap first exposed by BL-8's GROUP_ENTRY_CONFIDENCE_FLOOR.
metadata:
  type: project
---

`tuning.fraction(key, default, status=status)` is sugar for `real(key, default, lo=0.0, hi=1.0,
status=status)` — the 0..1 bound is genuinely enforced at runtime. But `tools/
generate_defaults.py`'s AST scan (per its own docstring, "the call's keyword arguments") only
reads `lo=`/`hi=` literals present at the *call site itself*. `fraction()`'s call site has neither,
so the generator has nothing to extract, and the rendered `config/defaults.toml` entry for a
`fraction()`-declared key carries no `range:` line at all — unlike every `real()`-declared
constant, which shows `range: <lo> .. <hi>`.

**Why this surfaced now, and why it isn't a BL-8 defect:** `mission_memory.admission.
GROUP_ENTRY_CONFIDENCE_FLOOR` is the *first* use of `tuning.fraction()` anywhere in `body-layer/
src/`. The gap was there in the generator from `fraction()`'s own introduction; nothing had
exercised it until this constant.

**How to apply:** When reviewing a tuning constant declared via `tuning.fraction(...)`, do not read
a missing `range:` line in the rendered TOML as evidence the bound isn't enforced — check
`tuning.py`'s `fraction()` definition instead, which hardcodes `lo=0.0, hi=1.0` and calls `real()`.
The rendering gap is a `generate_defaults.py` limitation (it would need to special-case `fraction`
calls, or `fraction()` would need to pass `lo=0.0, hi=1.0` explicitly as literals for the scanner to
pick up), not a runtime safety gap. Worth fixing in the generator eventually, but is not blocking
on any one feature that merely uses `fraction()` as designed.
