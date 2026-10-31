---
name: async-speech-worker-design
description: Moving a poll-thread HTTP call to a background worker can turn an existing "reads runner live, safe because single-threaded" closure into a real data race — drain results back onto the owning thread instead of calling the sink from the worker
metadata:
  type: project
---

**Planned 2026-10-20 (`plans/async-speech/plan.md`), for `CrewConsole._print`'s synchronous
`speech_client.push_speech` call blocking body-layer's 1 Hz poll thread** (user direction, same
sortie: *"mouth is independent of eyes and arms"*). `brain_client.BrainLayerClient` already solved
the same class of defect for the brain-escalation call on 2026-09-25 — see
`performance-reviewer/project_brain_layer_poll_thread_stall.md` for the measured cost (13.4ms down
vs. 5015.4ms wedged) and `two_speech_lanes_push_and_reply.md` (2026-10-14) which had already named
the speech case specifically as the next instance of this pattern.

**The non-obvious finding, not assumed from the ask**: `logger._speech_log_sink`'s closure
deliberately reads `ConsolePerceptionRunner.last_t_sim`/`scan_plan`/`last_ownship_state` **live**
("as they are at the moment of speech" is the whole point of that design, per its own docstring).
That is only safe because it has always been called synchronously, on the same poll thread that
mutates those fields. Moving the HTTP call to a worker thread and having the worker call that sink
directly on completion would read poll-thread-owned, poll-thread-mutated state from a second thread
with no lock — a real race, invisible until a test specifically constructs the interleaving.

**Why: any closure/sink built to run "on the poll thread" needs re-auditing the moment any part of
its call chain moves to a background worker** — the docstring's own safety argument
("single-threaded, so live reads are fine") silently stops being true. The fix is not a lock; it is
to keep the sink's *call* on the owning thread by having the worker deposit results into a
queue/buffer and having the owning thread (poll loop) drain and call the sink itself, once per poll
— the same "background thread does I/O, owning thread drains a buffer" shape `BrainLayerClient.
poll_replies()` already established. This also incidentally makes the sink's own stated intent
*more* true (closer to the real moment of speech), not less.

**How to apply**: before moving any call off a single-threaded poll/REPL loop in this codebase,
grep for every closure/method that call chain reaches and check whether any of them was documented
as "reads live state, safe because single-threaded" (a "see this docstring" phrase is the tell).
`body-layer/src/belief/brain_reply.py`/`escalation.py` and anything touching
`ConsolePerceptionRunner` directly are the likely future hits, given the precedent above.

**Companion decision, also reusable**: to avoid an Escalation-Rules-triggering mass test rewrite
(~53 existing assertions in `test_crew_console.py` relied on the old synchronous call), the new
worker is an *optional* collaborator (`speech_worker: SpeechWorker | None = None`) and `_print`
falls back to the old direct synchronous call when it is unset — so every existing test that
doesn't pass `speech_worker=` keeps exercising the old, already-correct path completely unchanged,
and only a handful of new tests need to construct the real threaded worker. See
`[[two-speech-lanes-push-and-reply]]`.
