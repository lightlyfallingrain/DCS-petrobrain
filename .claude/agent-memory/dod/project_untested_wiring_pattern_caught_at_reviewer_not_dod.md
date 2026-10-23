---
name: project_untested_wiring_pattern_caught_at_reviewer_not_dod
description: 5th occurrence (2026-10-23, BL-B90 Stages 1-2/effector-sequences) of "a branch/condition that reads as tested but isn't" — caught at Reviewer each time, never reaching DoD as a live defect; the two most recent occurrences are a distinct sub-shape (sibling-gate masking, not leaf/wiring-gap) but share the same root cause and the same place in the sequence where it gets caught
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

**Occurrence 5, BL-B90 Stages 1-2 (effector-sequences), 2026-10-23 — a distinct sub-shape within
the same family.** Not a leaf-module/wiring-site gap this time: both halves (`drain_config_error`'s
`silenced` check and its `intercom_open` check) were coded and wired together from the start. The
gap was that the one test written to cover the intercom gate
(`test_config_error_held_while_silenced_and_intercom_closed_then_speaks_once`) never reached a
state where `intercom_open is False` and `silenced is False` at the same time — every phase with
the intercom closed also had `silenced = True`, so the `silenced` check alone already explained
every assertion, and the intercom gate's own contribution was never observed. Reviewer confirmed by
mutation (deleting the intercom-gate `if` left the full suite green) and saved the specific lesson
as its own reviewer-memory file
(`.claude/agent-memory/reviewer/feedback_sibling_gate_masked_by_adjacent_flag_in_same_test.md`:
"two independent gates, one test, one gate's window always shadowed by the other"). **Why this
still belongs in this file**: the root cause — a test whose own narrative claims to cover a
specific condition but never actually isolates it — is the same "looks tested, is not" shape as
occurrences 1-4, and it was caught at the same stage (Reviewer, before DoD). It is a *sibling-gate*
variant rather than a *leaf/wiring* variant, so treat this file as now tracking two related
sub-patterns rather than one: (a) a pure module's own wiring into its consuming site has no test
at all, and (b) two gates share one test and one gate's window is always shadowed by the other's.
Both are "untested branch, caught at Reviewer, never DoD" — five occurrences of that outer shape
is a stronger signal than four that this may want a mechanical check (e.g. a Reviewer-stage
requirement to show, for any newly-added gate/condition, the specific test phase where every
*other* gate is held open/satisfied so this one's own contribution is isolated) rather than relying
on each reviewer's own mutation-testing diligence to catch it project-wide.
