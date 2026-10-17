---
name: voice-dispatch-table-vs-vocabulary-cross-subproject-gap
description: first occurrence (BL-8, 2026-10-17) of a new body-layer command token being dispatch-correct but voice-unreachable because audio-adapter's own vocabulary table was never touched -- not yet a recurring pattern, logged so a 2nd occurrence is recognized as one.
metadata:
  type: project
---

BL-8's `mark_here`/`mark_target` were wired into `belief/crew_console.py`'s dispatch table and
passed every unit test via the `!voice` developer harness, which simulates an already-resolved
match. Three review passes (Reviewer, Performance, Security) each correctly scoped themselves to
`body-layer` and missed that `audio-adapter/src/vocabulary.py` had no corresponding entry —
`match_transcript` returned `None` for every plausible phrasing. DoD caught it only by probing
`match_transcript` directly rather than trusting the dispatch-table change or the harness.

**This is distinct from `project_recurring_keyword_table_vocabulary_mismatch.md`** (DCS-internal
type strings vs. external naming sources under-joining within one lookup table) — that pattern is
about two externally-authored vocabularies failing to join inside `object_model.profile_for`. This
one is about a *module-independence seam*: a command's dispatch half lives in `body-layer`, its
recognition half lives in a separate subproject (`audio-adapter`) with its own hand-synced table,
and nothing enforces the two stay in sync. Same *shape* (silent under-coverage across a vocabulary
boundary), different *mechanism* — keep them as separate memories unless a second instance of
*this* mechanism shows up.

**Why:** `CLAUDE.md`'s module-independence rule means `audio-adapter` cannot import or be checked
against `body-layer`'s dispatch table mechanically; a plan's "Affected Modules" list is the only
thing that would have named it, and it didn't.

**How to apply:** if a *second* feature adds a voice-dispatchable `body-layer` command and again
omits `audio-adapter/src/vocabulary.py` from its own plan, that is occurrence 2 of this specific
mechanism — at that point this memory should be promoted to recommend an Architect-stage check
(a step in `plan.md`'s template: "does this add a voice command? if so, name
`audio-adapter/src/vocabulary.py` as an affected file") rather than relying on DoD to catch it a
second time by probing. See the implementer's own memory on the same incident,
`[[project_voice_token_needs_audio_adapter_vocabulary]]` (implementer role), and `NOTES.md`'s
Mission Memory (BL-8) section for the harvested version of this lesson.
