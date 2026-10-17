---
name: feedback-regex-guard-against-doc-examples
description: when reviewing a regression-guard regex, check it against every documented example form of the thing it bans, not just the form in the incident report
metadata:
  type: feedback
---

A regression-guard test's pattern should be checked against every *documented* variant of the
banned form, not only the specific string from the incident that motivated it.

**Why:** `fix/lua-hook-wiki-link-brackets` (2026-10-17) added
`aircraft-layer/tests/test_dcs_export_lua_syntax.py` to ban `[[ID]]` wikilinks inside `.lua` files,
after three such links broke Lua's long-bracket comment nesting and caused a total detection
blackout. Its regex, `r"\[\[[A-Za-z][\w-]*\]\]"`, matches the three incident IDs (`BL-B73` etc.)
but does not match `[[AA-1.1]]` — the dotted stage-link form that `docs/DOC_CONVENTIONS.md` itself
documents as a legitimate wikilink variant (*"Stages: `[[AA-1.1]] [[AA-1.2]]` …"*). A future dotted
stage link pasted into a Hook header comment would reproduce the exact incident this test exists to
prevent, silently.

**How to apply:** when a plan or fix adds a guard regex/pattern meant to be "the floor" against a
whole family of input (here: "any wikilink form this repo's own convention produces"), grep the
convention doc that defines the family for every documented shape, and check the regex against each
one directly (`re.fullmatch`) rather than trusting that the incident's own examples cover the space.
A guard narrower than the convention it is guarding against is a gap that looks like full coverage
in the diff and in the test's own passing run.
