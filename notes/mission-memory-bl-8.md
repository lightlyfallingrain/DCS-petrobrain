# Mission Memory (BL-8)

- **`tuning.fraction()`'s call sites render no `range:` line in `defaults.toml`, even though the
  bound is genuinely enforced at runtime.** `fraction()` fixes `lo=0.0`/`hi=1.0` internally by
  delegating to `real()`, but `generate_defaults.py`'s AST scan only reads `lo=`/`hi=` keyword
  arguments at the call site itself — which `fraction()`'s call site has none of. This was the
  first use of `tuning.fraction` in the codebase, so the generator gap was never exercised before.
  Not a defect in the constant's own declaration; a pre-existing generator limitation anyone
  declaring a `fraction()` key should expect, not mistake for their own error
  (`plans/bl8-mission-memory/review.md`).
- **A field's "one sanctioned reader" restriction, stated only in that field's own docstring, does
  not visibly extend to code written outside the module the docstring lives in.**
  `belief.contacts.Contact.last_percept`'s docstring names `belief.attack_run` as its one sanctioned
  reader; `mission_memory` (a sibling package outside `belief/` entirely) also avoided it, correctly,
  but by independent reasoning rather than by reading an enforced rule — the restriction is
  currently enforceable only by a reader doing the same grep. Worth stating in the field's own
  docstring that the restriction is package-wide, not file-local, next time it's touched
  (`plans/bl8-mission-memory/implementation.md`).
- **When one package may not import another (an enforced one-way boundary), a handler whose logic
  lives on the forbidden side still reaches the permitted side as a plain injected closure** —
  the same shape `speech_log_sink`/`transcript_log` already use. `belief/crew_console.py` may not
  import `mission_memory`, so `mark_here`/`mark_target` reach it as
  `Callable[[float], str]`/`Callable[[str, float], str]` built in `logger.py` (which may import
  both) and injected into `CrewConsole`. The pattern generalizes beyond this one feature: whenever
  an import-direction invariant and a "this module gains the handler" plan decision are in tension,
  closure injection from the one module allowed to see both sides is the resolution, not an
  exception to the invariant (`plans/bl8-mission-memory/implementation.md`).
- **A new voice-dispatchable command token wired into `body-layer`'s dispatch table is not
  reachable by voice until `audio-adapter/src/vocabulary.py` also gets a matching `TOKENS`/
  `PHRASES` entry — a cross-subproject step a plan's "Affected Modules" list can silently omit.**
  `mark_here`/`mark_target` dispatched correctly in unit tests via the `!voice` developer harness,
  which simulates an already-resolved match, so three review passes (Reviewer, Performance,
  Security) each correctly scoped themselves to `body-layer` and missed that `audio-adapter` had
  no entry at all — `match_transcript` returned `None` for every phrasing until DoD probed it
  directly. A plan adding a voice-reachable command needs to name
  `audio-adapter/src/vocabulary.py` explicitly, and the check is to probe `match_transcript` on
  the intended phrasings, not to trust the `!voice` harness, which tests dispatch rather than
  recognition (`plans/bl8-mission-memory/dod-check.md`).
