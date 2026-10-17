---
name: project_bl8_import_direction_closure_injection
description: When a plan's Affected Modules says a belief/ module gains a handler for a new package belief/ may not import, the resolution is a plain closure built in logger.py and injected -- not a field typed as that package's own class.
metadata:
  type: project
---

BL-8 (mission memory) Decision 1 made the import direction structural: `mission_memory` may import
`belief`, but no module in `belief/` may import `mission_memory` except `belief/tool_api.py` (which
does not exist until Stage 5). Decision 6 then asked `belief/crew_console.py` to gain
`_handle_mark_here`/`_handle_mark_target`, which need to call into `mission_memory.marks`/
`mission_memory.store.MissionMemory`.

These two decisions are in real tension, and the plan's Affected Modules section did not flag it —
it just listed `crew_console.py` as gaining the handlers, as if that were purely a dispatch
question.

**The resolution**: `CrewConsole` gets two `Callable` fields (`mark_here_fn: Callable[[float], str]
| None`, `mark_target_fn: Callable[[str, float], str] | None`), never a `MissionMemory` field or any
import of `mission_memory`'s types. `logger.py` — which sits outside `belief/` and may import
both — builds the actual closures (capturing the live `MissionMemory` instance, the resolved
theatre, and reading `runner.enrichment` live rather than captured, mirroring `_speech_log_sink`'s
own reasoning for why) and assigns them onto `crew_console.mark_here_fn`/`.mark_target_fn` before
the poll thread starts. `CrewConsole`'s own handler methods just call the closure and wrap the
result in `list[str]`.

This is not a new pattern — `transcript_log`/`speech_log_sink` already use exactly this shape for
the identical reason (CrewConsole must not import `speech_log`/other debug-sink modules directly).
The non-obvious part was recognising that Decision 1's import-direction rule applies with full
force even when a different decision in the same plan casually assigns the belief-side module a
"gains a handler" line — read the Affected Modules section's claims against the plan's own
structural invariants before assuming they're compatible as written.

**How to apply**: whenever a plan says module A (inside a restricted-import boundary) "gains" a
handler/dependency on module B (outside the boundary, or which may not import A's side), check the
plan's own import-direction decision before coding the obvious `from B import X` into A. If A is
restricted, the closure-injection pattern (the composition root — usually the CLI entrypoint or
`main()` — builds the closure, A only holds a `Callable` field) is this project's established way
out, not a deviation worth escalating.
