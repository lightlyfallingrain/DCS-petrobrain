---
name: mi1-mi15-review
description: Mission Interpreter's first code (MI-1 parser + MI-1.5 filter) — verification technique for the no-leak invariant and vendoring claims
metadata:
  type: project
---

APPROVED. All Implementer claims verified directly rather than trusted: grepped vendored
`_vendor/dcs_lua/{parse,serialize}.py` import lines to confirm zero non-`typing` deps; confirmed
`CrewAvailableMission` (mission-interpreter's author-only-knowledge filter output, analogous to
BL's contact-memory invariant) has literally no raw-passthrough field by reading the dataclass
fields directly; proved the gitignored-real-sample skip-guard actually works (not just written
correctly) by physically moving `research/samples/*.miz` aside and rerunning pytest — 12 passed, 2
skipped cleanly. This "move the gitignored fixture aside and rerun" technique is reusable for any
future subproject with a real-sample-optional / synthetic-fixture-always test split (see
`world-model`'s and now `mission-interpreter`'s CLAUDE.md "Testing" sections for the pattern).

One repo-wide (not this-PR) doc quirk worth knowing for future reviews: both `world-model/CLAUDE.md`
and now `mission-interpreter/CLAUDE.md`'s Commands sections document `mypy <subproject>/src` run
from repo root, which silently drops `--strict` — confirmed by injecting an untyped-function probe
and rerunning both ways. Always invoke `mypy` with the subproject dir as cwd when actually verifying
a review's strict-mode claim, don't trust the documented one-liner as written.

Only fix needed: implementer's own agent-memory files (MEMORY.md edit + new project file) were left
unstaged/untracked — a two-command `git add`, not a design issue. Worth checking `git status`
outside the feature diff itself, since implementer/reviewer memory writes are easy to forget staging.
