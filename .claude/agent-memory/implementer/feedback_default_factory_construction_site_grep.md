---
name: default-factory-construction-site-grep
description: a grep-based "exactly one construction site" test for a dataclass field declared via field(default_factory=ClassName) must match the factory reference, not a literal ClassName( call -- that substring never appears
metadata:
  type: feedback
---

When a plan or review asks for a mechanical "construction site" check (the
`BL-B71`/mission_memory `Entry(` pattern: grep for `\bClassName\(` to prove
there is exactly one place a class gets built), check first whether the one
real site is a dataclass field declared as
`field(default_factory=ClassName)`. That line never contains the substring
`ClassName(` -- there is no call syntax, the class object itself is the
factory and the dataclass machinery calls it. A regex built on the `Entry(`
precedent (`\bClassName\(`) will find **zero** hits there and the test fails
for the wrong reason (looks like "nobody constructs it", not "the one
construction site uses a different syntax").

**Why:** caught building `BL-B66`'s `test_guidance_unit_state_is_constructed_
in_exactly_one_place_in_logger_py` -- `guidance_unit_state: GuidanceUnitState
= field(default_factory=GuidanceUnitState)` in `logger.py` is the plan's
named single construction site, but `re.findall(r"\bGuidanceUnitState\(",
text)` returned `[]`, not `[1 match]`.

**How to apply:** for a `default_factory=ClassName` site, assert on
`r"default_factory=ClassName\b"` instead (or in addition to) the bare-call
regex; use the bare-call regex only to assert the module *never* constructs
the class literally elsewhere (that check works fine, since a real call site
does contain `ClassName(`). Also watch the inverse trap: a docstring that
describes the pattern in prose (e.g. "never a fresh `ClassName(...)`
mid-sequence") can accidentally contain the literal `ClassName(` substring
and make a "this module never constructs it directly" test fail against its
own comment -- word such docstrings to avoid the call-shaped substring (say
"never constructs this class fresh" instead of spelling out `ClassName(...)`).
