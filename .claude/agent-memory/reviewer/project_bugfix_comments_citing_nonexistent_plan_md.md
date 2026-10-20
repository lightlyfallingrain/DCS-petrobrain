---
name: bugfix-comments-citing-nonexistent-plan-md
description: a Debugger-flow fix (no Architect plan, only debug.md) can still get new code comments citing "plans/<feature>/plan.md" by habit, even when the first half of the same fix correctly cited debug.md -- grep for it every time a reviewed feature's plans/ directory lacks a plan.md
metadata:
  type: project
---

On `fix/taking-fire-visible-shooter`'s second half (`9cbd2ace`, reviewed 2026-10-20), 17 new
docstring/comment citations across 8 files (`naked_eye_source.py`, `percept.py`, `contacts.py`,
`events.py`, `speech.py`, and their three test files) pointed at
`plans/taking-fire-visible-shooter/plan.md`. That directory only ever held `debug.md`,
`implementation.md`, `review.md` -- there never was an Architect plan, because this was a
Debugger -> Reviewer flow (a bug fix per `docs/acceptance/<date>-sortie-feedback.md`, not a new
feature). The first half of the *same* fix (`6029f184`) correctly cited `debug.md` throughout.

**Why this happens**: most of this codebase's citation convention is `plans/<feature>/plan.md`
(Architect-authored features), so an implementer writing a second batch of comments for an
existing feature directory reaches for that pattern reflexively, even when the directory in
front of them has no such file.

**How to apply**: before approving any diff that adds new `plans/<feature>/...` citations,
`ls plans/<feature>/` once and confirm the named file actually exists. A bug-fix-only feature
directory (debug.md + review.md, no plan.md) is the specific shape to watch for -- it is legal and
common (`AGENTS.md`'s "Bug fix" sequence: Debugger -> Reviewer -> Security -> DoD, no Architect
step at all), but a citation that silently assumes the Architect step happened is wrong and cheap
to catch with one `grep -rl "plans/<feature>/plan\.md" src/ tests/` plus one `ls`.
