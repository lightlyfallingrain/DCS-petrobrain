---
name: overlay-speech-callouts
description: CrewConsole spoken text -> overlay push wiring, bypass_gate prefix, and the private-method-signature-widening move that carried it through.
metadata:
  type: project
---

Implemented `plans/overlay-speech-callouts/plan.md` on `feature/overlay-speech-callouts`: routed
`CrewConsole`'s spoken text (readbacks, contact reports, drained lifecycle events, injected urgent
calls) to the DCS in-cockpit overlay via `POST /text/push`, through `_print` as the single funnel
point both `handle_line` and `drain_events` already call.

**Widening a private method's return type was the cleanest way to carry `bypass_gate` through.**
`_handle_inject_urgent` originally returned bare `list[str]`, discarding `OutgoingSpeech.
bypass_gate`. Since it's private and no test called it directly (only `_act` was, and that
signature stayed untouched), widening it to `tuple[list[str], bool]` was safe and let `_print`'s
`"!! "` prefix logic read the flag straight from `route_event`'s result instead of re-deriving
"was this line urgent" from string content at the call site. Worth checking for direct test calls
before assuming a private method's signature is load-bearing either way.

**`route_event` always returns non-`None` for an `UrgentCall` input** (only the `Event` branch can
return `None`, for an unknown contact) -- confirmed by reading `speech.py` rather than assuming.

**Field-not-mutation for the urgent prefix**: the plan's resolved decision was to prefix the
*pushed* overlay copy only, at the `_print` call site, never mutating `OutgoingSpeech.text` --
kept `output`'s printed copy exactly as spoken, mirrors how `logger.ConsolePerceptionRunner`
already treats overlay push as a display-only second sink, not a rewrite of what was said.

No new files this milestone -- only edits to `crew_console.py`, `logger.py`,
`test_crew_console.py`, `body-layer/CLAUDE.md`. All body-layer checks passed (mypy strict, ruff
format/check, pytest 444 passed).
