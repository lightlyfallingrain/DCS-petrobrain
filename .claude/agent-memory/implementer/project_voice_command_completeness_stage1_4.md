---
name: voice-command-completeness-stage1-4
description: crew_console dispatch rename + report-family wiring + bearing quantisation wire fix
metadata:
  type: project
---

Implemented Stages 1-4 of `plans/voice-command-completeness/plan.md` (Stage 5 — o'clock scan
tokens + compass-scan-drives-gaze — deliberately deferred, out of scope for this pass).

**Test-fixture geometry gotcha, worth knowing before writing any future enrichment-based test in
body-layer.** Every existing `_enrichment_context` helper across `test_crew_console.py`/
`test_callouts.py`/`test_speech.py` monkeypatches `belief.enrichment.project_terrain_aware` to an
identity passthrough of its `observer` argument. Because `_terrain_aware_world_position` calls it
with `percept.ownship_at_observation` as that observer, a contact's *reported* `relative_now`
(bearing/range/clock from current ownship) ends up being computed against the **observing
ownship's own position at the time of the most recent contributing observation** — not against
`bearing_deg`/`range_m` projected outward from it. This is non-obvious from reading the source and
cost real time to reverse-engineer empirically. To place a test contact at a controlled direction/
range under this fixture, control it via the observation's `ownship_at_observation` x/z, not via
`bearing_deg`/`range_m` (those fields are then arbitrary placeholders for this purpose only —
`ContactStore.ingest`'s own spatial gate still uses them for real, so keep them plausible).

**Plan-vs-reality mismatch found in step 1b (test-impact check).** The plan named
`audio-adapter/tests/test_transcript_queue.py`/`test_server.py` as the Stage 3 test targets;
neither file tests `TranscriptEvent`/`POST /transcribe`. The real coverage lives in
`audio-adapter/tests/test_transcribe_api.py`, found by `grep -rl TranscriptEvent tests/` before
writing anything. Unlike the two documented prior incidents (a phantom test name; a file omitted
from the list entirely), this was a real file just named wrong — worth grepping for regardless of
which failure mode you expect.

**`DISPATCHED_COMMAND_TOKENS`** (module-level frozenset in `crew_console.py`) is now the canonical
"has real `handle_command` dispatch behaviour" set, asserted against by test — 38 of the
vocabulary's 41 tokens; the other 3 (`wake_petrovich`/`cancel_nevermind`/`say_again`) are handled
above `handle_command` entirely and never reach it. An unrecognised token now `logger.warning`s
(still returns `[]`) instead of vanishing silently — the failure mode this whole milestone existed
to fix.

**`group_facts` extraction pattern**: `belief.callouts._chain_by_clock` was generic-izable via a
plain `TypeVar` with zero behaviour change, because it never read anything `Event`-specific — only
built `dict[int, list[T]]` and appended references. `group_candidates` now maps grouped facts back
to their originating `Event`s via `id(facts)` object-identity, safe because `group_facts` only
reorganises references into new lists, never copies/recreates the dicts it's given. Worth
remembering as a general pattern: when extracting a shared algorithm that currently operates on
`(richer_type, derived_key)` pairs, check whether the algorithm body ever needs anything from
`richer_type` beyond the derived key before assuming a generic extraction needs new plumbing.

Full implementation log: `plans/voice-command-completeness/implementation.md`.
