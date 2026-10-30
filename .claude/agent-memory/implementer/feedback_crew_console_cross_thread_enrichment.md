---
name: crew-console-cross-thread-enrichment
description: Calling CrewConsole.handle_command from any thread other than body.py's own poll/REPL thread needs a foreground-thread-local EnrichmentContext, or it raises sqlite3.ProgrammingError
type: feedback
---

`ConsolePerceptionRunner.enrichment` (and `_run_crew_text_poll_loop`'s own
`crew_console.enrichment = runner.enrichment` line, ~body.py:3525) holds a
`sqlite3.Connection` opened on the **background poll thread**. Any other
thread that calls `CrewConsole.handle_command`/`handle_line` for a command
that resolves through `_report_scope`/`get_contacts`/enrichment (e.g.
`"engage"` with a descriptor/clock/sector slot) and reuses
`crew_console.enrichment` as-is will raise
`sqlite3.ProgrammingError: SQLite objects created in a thread can only be
used in that same thread` — confirmed by running it, not theoretical.

**Why this isn't obvious from reading `_run_crew_text_poll_loop` alone**:
that function itself sets `crew_console.enrichment = runner.enrichment`
every poll, which looks like "the console's own enrichment, kept fresh" —
but it is really "whatever the poll thread's own connection currently is",
safe only for same-thread callers.

**The fix already exists in production** — `body._run_crew_text_repl`'s
own docstring documents fixing exactly this (BL-B96): build a
thread-local `sqlite3.Connection`/`EnrichmentContext` lazily on the
calling thread, keyed off `runner.world_model_store`/
`runner.last_ownship_state`, and assign it to `crew_console.enrichment`
right before dispatching — never read `runner.enrichment` from a second
thread.

**How to apply**: any test harness (or future production surface) that
drives `CrewConsole` from a thread other than the one
`_run_crew_text_poll_loop` runs on must replicate this pattern — open its
own `sqlite3.Connection` via `perception.geometry.open_world_model`, build
its own `EnrichmentContext`, and set `crew_console.enrichment` to it
immediately before the call. See
`body-layer/tests/test_bl_b104_scenario_mock_flights.py`'s
`_ForegroundEnrichment` for a worked example (BL-B104 Stage 7).

A plain read-only `get_contacts(..., enrichment=...)` call, `set_attention`
alone, and `attack_target_task` alone do NOT reproduce the crash by
themselves against a *correctly* thread-local enrichment — only reusing
the background thread's own connection does.
