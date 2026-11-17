---
name: feedback-cross-thread-one-shot-queue-vs-single-slot
description: when routing a cross-thread (REPL-thread-reachable) write through a CrewConsole one-shot field, use a plain list + list.append (GIL-atomic, mirrors _pending_positional_replies) if the field can legitimately hold more than one distinct pending fact at once; a single-slot field like observ_transition only works when there is exactly one domain fact in play
metadata:
  type: feedback
---

`body-layer/src/belief/crew_console.py` has two different shapes for "a command handler leaves a
signal for `body.py`'s poll loop to apply, because the handler cannot reach poll-thread-owned
state directly" -- both exist already, pick based on cardinality, don't default to the one you
saw most recently:

- **Single one-shot slot** (`observ_transition`, `weapon_safety_transition`,
  `ai_pilot_goal_transition`, ...): correct when the field represents exactly one domain fact that
  can only be in one state at a time (OBSERV is on or off; there is one outstanding flight goal).
  Reset at the top of every `handle_command` dispatch and rolled back by `_reset_one_shot_command_
  state` on a rule error (D6) -- both rely on the precondition that only *this* dispatch could have
  set a non-`None` value, which holds because the top-of-dispatch reset already cleared any stale
  one.
- **Plain `list` + `.append()`** (`_pending_positional_replies`, and now `pending_effector_writes`,
  `[[BL-17]]` D20 Stage 3d review Required Fix 1): correct when several *different* facts can
  legitimately be pending at once (several different positional readbacks; several different
  effectors each with their own ad hoc write). `list.append()` is GIL-atomic in CPython, so
  concurrent appends from the poll thread's own voice dispatch and the REPL thread's typed
  dispatch cannot lose an entry -- no `threading.Lock` anywhere in this file, and none needed for
  this shape. Drained by the poll loop via swap-with-a-fresh-`[]` (`pending, self.field = self.
  field, []`), not iterate-then-clear, so an append landing during the swap is captured in the
  *next* drain rather than wiped by an unconditional `= []` after the loop. **Not** reset by
  `_reset_one_shot_command_state` and **not** in `handle_command`'s top-of-dispatch reset -- an
  entry queued by an earlier dispatch this poll has not yet drained must survive an unrelated later
  command (same reasoning `where_is_it_requested` already documents for itself).

**The tell for which shape to use**: ask whether two *different* values of the "what is pending"
concept can coexist. If yes (an arbitrary effector name, an arbitrary readback), use the list
shape. If no (a fixed enum with one slot), the single-slot shape is simpler and already has D6
rollback coverage for free -- don't build a list where a slot would do, and don't force a list's
job into a slot (a second different-effector request would just overwrite the first and silently
drop it, a worse bug than the one being fixed).

**Testing a closure built inside `body.py`'s `main()`**: that closure is untestable directly
(`main()`'s CLI wiring is untested by design, per `body-layer/CLAUDE.md`'s module map). Test the
boundary instead -- write a stand-in closure in the test file that does exactly what the real one
does (validate, then touch only the testable field/function), dispatch it from a real
`threading.Thread` to stand in for the REPL thread, and separately simulate the poll loop's own
drain on the test's own thread. `test_rules_effector_action.py`'s `test_effector_write_queued_
from_background_thread_is_applied_on_next_poll_drain` is the worked example.
