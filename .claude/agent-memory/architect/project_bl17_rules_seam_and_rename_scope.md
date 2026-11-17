---
name: project-bl17-rules-seam-and-rename-scope
description: BL-17 (speech commands as Lua rules) seam choice — body-layer loads Lua and PUTs patterns to audio-adapter, rule id = existing token name — and the measured ~2000-occurrence "bearing" rename that made the rename's scope a user decision
metadata:
  type: project
---

BL-17's plan (`plans/speech-rules/plan.md`, 2026-11-17) settled the cross-subproject seam this
way: **body-layer loads `config/rules/*.lua` (lupa, the only lupa importer is `rules/sandbox.py`)
and pushes `(id, pattern)` to audio-adapter via `PUT /rules`; the adapter compiles patterns,
matches, owns collision checks and the whisper prompt, and returns accepted/rejected ids. Re-push
is driven by an `X-Rules-Version` header on the existing transcripts poll, not a timer.**
Rules run *inside* `handle_command` after its preamble, injected as a closure (no import cycle).
A ported rule keeps its old token name and slot names, so BR-2's `BRAIN_COMMANDS`, speech logs and
the confirm band carry over untouched.

**Why:** the matcher (1,300 lines) and whisper normalisation are recogniser facts already living in
audio-adapter; moving them, or sharing a pattern file across subprojects, would break module
independence or split one rule across two files.

**How to apply:** later BL-17 port stages and BL-B95 (triggers, interrupts) build on this seam —
do not add a second loader or let audio-adapter read Lua. Check the plan's D1–D12 before
re-deciding any of it.

**Rename-scope lesson:** the user said "change the naming in existing code" for bearing→heading.
`grep -rio bearing` measured ~670 (body-layer src) + 150 (audio-adapter) + 63 (world-model) + 79
(Export.lua) + ~1050 (tests), the bulk of it perception geometry that is never spoken. A literal
reading would have been ~2000 edits in the most calibrated code for no pilot value — so the scope
became an explicit U-decision (U17) with the count attached, recommending command surface only.
Measure an instruction's literal reach before planning it; a one-line direction can hide a
cross-subproject rewrite. Related: [[project_voice_command_completeness]].
