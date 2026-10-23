---
name: project_untested_wiring_pattern_caught_at_reviewer_not_dod
description: 4th occurrence (2026-10-22, BL-B80 v2/9k113-sight-pointing) of "leaf module unit-tested, its wiring into the poll loop/consuming site is not" — caught at Reviewer each time, never reaching DoD as a live defect, but recurring even when the plan names it explicitly up front
metadata:
  type: project
---

`.claude/agent-memory/reviewer/project_terrain_callout_stage5_wiring_gap.md` tracks this defect
class: a thoroughly unit-tested pure function/module gets wired into a poll loop or other
consuming site, and the wiring itself has zero test coverage — confirmed each time by mutation
(disabling the wiring left the full suite green).

**Process signal, not a code signal**: all four occurrences were caught and fixed at Reviewer,
before reaching DoD. That is the role sequence working as intended (Reviewer's "required fix" loop
is exactly for this). Recorded here so a future DoD pass checking "does this match a recurring
category" finds it fast, and so that if an occurrence ever **does** reach DoD undetected by
Reviewer, that escalation is itself the signal to consider — per root `CLAUDE.md`'s "Milestone
Completion" framing — moving this check earlier (e.g. an Architect-time note: "state explicitly
which test will drive the wiring, not just the unit") rather than only at Reviewer.

Occurrence 3, 9k113-effectors: `sight_effector.py`'s sequencer was 21-tests-thorough in isolation;
the ~130 lines wiring it into `logger.py`'s `_run_crew_text_poll_loop` had none, including an
implementer-added test-enabling recorder (`cockpit_switch_writes`) that no test in the diff ever
called — a tell worth watching for on its own.

**Occurrence 4, BL-B80 v2 (9k113-sight-pointing), 2026-10-22 — the strongest version of this
signal yet.** The plan itself named the requirement explicitly, by number, before implementation
started: Stage 3's own text calls for *"a wiring test through `run_once` (the recurring
leaf-tested/wiring-untested defect, three prior instances) and a mutation of that wiring to show
the test catches it,"* and Stage 3b repeats the same requirement in its own words. The implementer
still did not build either one — Reviewer's first pass (`review.md`, Finding 3) found zero
`mutation`-tagged tests anywhere near `sight_head`/`select_sight_goal`, for either stage, and it
became one of three required fixes before DoD. **Naming the defect class in the plan, by its exact
prior-occurrence count, was not sufficient to prevent a 4th instance.** This raises the question
root `CLAUDE.md`'s "Milestone Completion" framing asks: is a prose instruction at planning time
the right place to close this, or does it need a mechanical check (e.g. a Reviewer-stage grep for
`mutation` near any newly-wired leaf module, or an Implementer checklist item that cannot be
marked done without one) rather than relying on the plan's own words being read and acted on.
Still caught at Reviewer, not DoD — the sequence held — but four occurrences of the same shape,
one of them immune to an explicit in-plan warning, is itself the signal.
