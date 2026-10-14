---
name: check-the-premise-not-just-the-mechanism
description: a review prompt's own framing of a concern can carry a false premise about the data model (e.g. "Percept carries derived_world_position") -- verify the premise against the actual class definition before answering the question built on it
metadata:
  type: feedback
---

On BL-14 Stages 1-3 (`plans/attack-run/review.md`), the dispatching prompt's finding 1(b) assumed
`Percept` carries `Observation.derived_world_position` (because `Observation` does) and asked
whether `Contact.last_percept` therefore widens belief code's one-hop reach to ground truth. Direct
read of `percept.py` showed this premise is false: `Percept` is structurally stripped of every DCS
truth field by design (its own docstring says so), and `derived_world_position` exists only on
`Observation`, which never crosses into `belief/`. The real (and narrower, already fenced) widening
is `relative_direction` alone.

**Why: a prompt's framing is not evidence, however confident it reads.** Even a careful dispatching
message (this one was unusually detailed, citing line numbers and prior patterns) can misstate a
class's actual fields from memory. Treat "does X widen access to field F" as two separable claims --
"X reaches F" and "F exists on the type in question" -- and check the second directly before
answering the first.

**How to apply:** whenever a review brief states what a type "carries" or "exposes" as the setup for
a question, grep/read that type's own definition before answering, even when the claim sounds
exactly like a known project invariant (no-omniscience, grep fences) that primes agreement. Refuting
the premise is itself useful review output, not a distraction from the actual question.

Related: [[feedback_grep_fence_literal_text_not_runtime_access]] (implementer memory, same feature)
-- the actually-correct narrower finding this session confirmed by mutation-testing the fence rather
than reading it.
