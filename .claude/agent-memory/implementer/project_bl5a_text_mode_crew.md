---
name: project_bl5a_text_mode_crew
description: BL-5a text-mode crew interaction implementation details and deviations from plan
metadata:
  type: project
---

Implemented 2026-09-10 on `feature/bl5a-text-mode-crew-interaction` (cut from BL-4, deliberately
not depending on unmerged `feature/bl5-tool-api`). 333 -> 367 tests.

New modules: `belief/utterance.py` (regex-table intent parser, first-match-wins), `belief/speech.py`
(`OutgoingSpeech`, templates, `route_event`), `belief/escalation.py` (`handle_player_utterance`,
`BrainClient` stand-ins), `belief/crew_console.py` (`CrewConsole`, separate from debug `console.py`).
`logger.py` got `--crew-text` (mutually exclusive with `--console`/`--overlay`) reusing
`ConsolePerceptionRunner`'s poll-loop machinery verbatim (`_run_crew_text_poll_loop`/`_repl` mirror
the `--console` versions, plus a `drain_events` call after each poll).

Key deviations, useful if BL-6/BL-7/PB-7/PB-8 touch this surface again:
- **`bypass_gate` is not a field on `belief.events.Event`** — `events.py` was out of scope
  (Affected Modules explicitly excluded it) and `EventKind`'s closed Literal has no "urgent call"
  member. Built a separate `speech.UrgentCall` type instead; `route_event(store, event: Event |
  UrgentCall, now_sim, enrichment=None)` dispatches via `isinstance`. If a real threat-detection
  channel lands (BL-7+), it should construct `UrgentCall`s the same way `!inject-urgent` does.
- **No candidate score** — `belief.tools.find_contact` (BL-2) has no ranking, so
  `utterance.ReferenceCandidate` carries only `id`/`why`, not the plan's illustrative `score` field.
  If `find_contact` ever gains real ranking, that's the place to add a score, then thread it through.
- **`CONTACT_ATTENTION_CHANGED` has no speech template** (route_event returns None, doesn't ack) —
  read as intentional scope-narrowing of the plan's "all four lifecycle kinds" phrasing (4 of 5
  EventKind values), not an oversight. A future milestone narrating area-entry attention changes
  adds a template here.
- Reference resolution strips only leading filler words (`that`/`the`/`a`/`an`); place-name/trailing
  clause phrasing ("by the road") stays unmatched by design until BL-5's `find_place` lands.
