---
name: br1-stage1-review-approved
description: BR-1 Stage 1 (brain-layer async round trip) reviewed and approved clean — how the orchestrator's own 3-way merge resolutions were independently verified.
metadata:
  type: project
---

BR-1 Stage 1 (`feature/brain-layer`, `d6b537b`) — new `brain-layer/` subproject + body-layer
escalation/reply/revalidation wiring — reviewed APPROVED, no required fixes.

The task brief flagged that the orchestrator (not the implementer) had resolved three real merge
conflicts bringing `main` into a two-milestones-stale branch, and asked that those resolutions be
checked directly rather than trusted from the merge commit message. All three checked out on direct
read:

- `logger.py`: a log-and-continue guard (from `main`) wraps the whole poll body; the new
  `crew_console.drain_brain(...)` call had to land *inside* that guard, not appended after it, or a
  brain-reply exception would silently kill the poll thread. Confirmed by reading the actual
  indentation/`try`/`except` nesting, not by trusting the diff summary.
- `voice_commands.py`: `PendingConfirmation.bearing_degrees` (a field) was replaced by a general
  `slots` dict on `main` while the branch added `contact_pick`. Checking "nothing still expects the
  old field" required distinguishing `slots["bearing_degrees"]` (a dict-key access, fine, unrelated)
  from an attribute reference `.bearing_degrees` (would be a bug) — a grep for the bare string alone
  would have false-positived on every legitimate dict-key use.
- `crew_console.py`: an import-list conflict (`main` and the branch each adding a different
  `render_*` name) — verified by checking the merged import block actually names both, with no
  shadowing.

**Reusable technique**: when a task brief says "the orchestrator/implementer merged main into a
stale branch, check the conflict resolutions" — read the actual merged file at the specific lines,
don't infer correctness from "tests pass." A guard-placement bug (call landing outside a try/except)
or a stale-field reference are exactly the kind of thing that compiles, type-checks, and passes
tests that don't happen to exercise the failure path.

Also worth noting: this branch's `D10` validator and Stage 3's `awaiting_reply_to` exception were
both **deliberately unbuilt** and correctly so — verified by reading the plan's own stage table
(D10 explicitly scoped to Stage 2; the wire in Stage 1 is structured JSON from plain code, not raw
model text, so there is nothing yet for D10 to validate) and `job.py`'s own docstring (the
`awaiting_reply_to` exception is unreachable until Stage 3 sets that field on an outgoing payload,
so building it now would be untestable dead code). Don't flag a documented, correctly-scoped
absence as a gap — check the stage table before concluding something is missing.
