---
name: shared-mechanism-vs-per-handler-tests
description: When a decision (e.g. "lost contacts still resolve") is enforced by one shared resolver called from several handlers, one end-to-end test at one handler plus tracing the call graph is adequate evidence for the others -- don't require N duplicate end-to-end tests when the mechanism genuinely is not duplicated.
metadata:
  type: feedback
---

On BL-B102 (`plans/that-it-referent/`), Decision 4 required that a mentioned-but-now-`lost` contact
still resolve for *every* referent-taking command (`where_is_it`, `follow`, `select_target`,
`engage`, `mark_target`). The implementer only wrote one explicit end-to-end test for this
(`where_is_it`). Instinct says "test gap" across the other four handlers.

**What actually settles it**: trace whether the other four handlers reimplement the resolution or
call the exact same function. Here all five call `CrewConsole._resolve_referent_target`, which
calls the same `resolve_referent`/`_report_scope(restrict_to_ids=...)` path -- a single `if/elif`
in `_report_scope` is what skips the `certainty == "lost"` drop. Because the mechanism is shared,
not duplicated per-handler, one end-to-end test plus confirming the call graph is adequate
evidence; demanding four more copies of the same test would be testing the dispatcher's wiring
(which is already covered by the ordinary non-referent tests for those handlers), not the lost-
contact behaviour itself.

**Why:** the user's own "verify by mutation, per entry" standing instruction is about guard
entries/enumerated sets, where each entry genuinely is independent. A shared-function call site is
the opposite shape -- the thing to verify is "does this handler call the shared function with the
right inputs," not "does this handler have its own copy of the lost-contact logic." Flagging the
single-tested-handler asymmetry as an *optional* refinement (more visibility, not more safety) is
the right review call, not a required fix.

**How to apply:** before writing "handler X has a test for Y but handlers A/B/C don't," check
whether A/B/C route through the same function X does. If yes, it's an optional test-visibility
nit. If no (each handler has its own copy/variant of the logic), it's the real gap the "verify by
mutation, per entry" rule is for -- require it.
