---
name: project-voice-token-needs-audio-adapter-vocabulary
description: a new DISPATCHED_COMMAND_TOKENS entry in body-layer's crew_console.py is not reachable by voice until audio-adapter/src/vocabulary.py also gets a TOKENS/PHRASES entry — a cross-subproject step a plan's "Affected Modules" list can silently omit
metadata:
  type: project
---

BL-8's `mark_here`/`mark_target` were wired into `body-layer/src/belief/crew_console.py`'s
`DISPATCHED_COMMAND_TOKENS` and dispatched correctly in unit tests via the `!voice` developer
harness, which *simulates* an already-resolved match. But the plan's "Affected Modules" list never
named `audio-adapter/src/vocabulary.py`, so three review passes (Reviewer, Performance, Security)
each correctly scoped themselves away from the one file that actually turns a spoken phrase into
that token. The gap was only caught at DoD, by probing `match_transcript` directly on the new
command's plausible phrasings and getting `None` back.

**Why:** a command token living in body-layer's dispatch table is necessary but not sufficient for
voice reachability — `audio-adapter` is a separate subproject (module independence) with its own
hand-synced `TOKENS`/`PHRASES` table, and nothing enforces that the two stay in sync. A plan that
adds a voice-reachable command needs to name `audio-adapter/src/vocabulary.py` in its own right,
not assume it follows from the dispatch-table change.

**How to apply:** whenever a plan or task adds a new voice-dispatchable command token in
`body-layer`, check `audio-adapter/src/vocabulary.py`'s `TOKENS`/`PHRASES` for a matching entry
before calling the voice path done. Probe with `match_transcript` on the intended phrasings, not
just the `!voice` harness — the harness tests dispatch, not recognition. See
`[[feedback_worktree_no_venv]]` for the separate, unrelated worktree-tooling note from the same
feature.
