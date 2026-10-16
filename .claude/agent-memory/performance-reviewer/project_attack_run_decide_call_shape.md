---
name: attack-run-decide-call-shape
description: belief.attack_run.decide is called at most once per poll, for exactly the one engaged attack-run contact -- not a loop; BL-B70's cause-taxonomy diff added no new frequency, allocation class or iteration
metadata:
  type: project
---

Reviewed for BL-B70 (`plans/attack-run-sortie-fixes/`, `feature/attack-run-fixes` @ `d826a54`).
`belief.crew_console.CrewConsole.drain_attack_run` is `decide`'s only caller, wired once per poll
immediately before `drain_events` (`_run_crew_text_poll_loop`). It resolves exactly one
`contact_id` (`self._active_attack_target_task()`) and does two O(1) store lookups
(`self.store.contact(id)`, `self.store.group_for_contact(id)`) before calling in -- never a loop
over `ContactStore`'s full contact set. BL-B70's cause taxonomy (`_no_look_cause`, 4-way
`Literal`) and the deleted angular-delta cadence clause (`_should_emit` is now a single string
comparison) are both O(1) per call and use primitives already paid for elsewhere every poll
(`profile_for` is `@cache`d at 0.04 us/call, confirmed unchanged). Net effect of this diff on the
hot path: strictly less work per call (one comparison deleted, nothing added that scales with
contact/candidate count), same call frequency.

**Reusable point**: when a plan says "pure functions, no new state machine, no new per-tick
cost" for a guidance/decision module, the thing actually worth verifying is the *caller's* call
shape (how many times, over how many items, per poll) -- the pure-function body itself is rarely
where a plan's performance claim turns out wrong on this codebase; an unverified caller loop is.

See also [[project_body_layer_poll_loop_diagnosis]] (the "5 Hz spec" correction -- apply the
real ~1.0-1.4s period, not a stale docstring figure, whenever a dispatch brief cites BL-B30's old
framing) and [[project_bl11_los_gate_cost_collapsed]] (same genre of stale-figure trap, different
gate).
