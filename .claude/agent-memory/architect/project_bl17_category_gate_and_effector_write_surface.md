---
name: project-bl17-category-gate-and-effector-write-surface
description: BL-17 revision 2 — rule dispatch gained a per-category precondition gate (PASS/HOLD/UNABLE) and an effector-write action surface that extends effector_engine rather than duplicating it; both are reusable patterns, not BL-17-specific
metadata:
  type: project
---

Two coordinator mid-task corrections during BL-17's revision-2 re-plan
(`plans/speech-rules/plan.md`, D16/D20, 2026-11-17) produced patterns worth reusing elsewhere in
this codebase, not just in BL-17's own stages.

**Category gates, not per-action checks, for a precondition shared by many actions.** The first
draft had every flight-control handler check `held_heading is None` itself (copy-pasted across
seven handlers). The coordinator's correction: when several rules share one coarse precondition
("has controls," "right seat"), declare it once per **category** and run it before the matched
rule's handler is even invoked — never repeat the check inside each handler. Shape: a closed
`GATE_REGISTRY: dict[category, GateFn]` in code (never in the sandboxed Lua — the gate is "the
when," which this project's own "actions, state params, when" convention already keeps apart from
"the what"); a rule declares its category as a plain required argument at registration time; the
outcome is **three-valued, not two** — `PASS`/`HOLD(reason)`/`UNABLE(reason)` — because "not yet
ready, will resolve soon" (a takeover settling) and "genuinely blocked until something external
changes" (not flying at all) are different pilot experiences and need different retry behaviour,
not one undifferentiated refusal.

**One shared state type feeds both a dispatch-time gate and a recognition-time hint.** The same
`CrewState` (or whatever the domain's equivalent is) that a gate reads must be the *only* place
that state is computed — if the speech-recognition layer (or any other consumer) independently
re-derives "is he flying" from the same underlying fields, the two readings can disagree within
one poll. Compute once per poll, assign to one field, let every consumer read that field.

**Extend a stateful, multi-poll engine via an extracted shared primitive plus a second run kind —
never a second write path.** `effector_engine.advance` only knew how to process trigger-fired
sequence-file rows. Rules needed single ad hoc writes (no sequence file, no trigger). The fix was
not a parallel write function: the actual per-row execution (self-check → `absolute_write` gate →
the real write → bookkeeping → spoken-line emission) was pulled out of the trigger-run loop into
its own named function, and a **second kind of run** (keyed differently — by a request id instead
of a trigger enum) was added to the engine's own state, processed by the *same* extracted function
in the *same* `advance()` call, sharing the same per-poll collision bookkeeping. The lesson
generalises: when a new caller needs a capability a stateful engine already has, but via a
different entry shape, extract the primitive and add a run kind — do not fork the engine.

**How to apply:** before adding a second "does X need to happen before Y runs" check anywhere in
`crew_console.py`/`rules/`, check whether `gates.py`'s registry already covers the category, or
should gain a new one. Before adding a second way to write a cockpit switch, check
`effector_engine.advance`/`_execute_switch_row` first. Related:
[[project_bl17_rules_seam_and_rename_scope]], [[feedback_temporal_precondition_tautology]].
