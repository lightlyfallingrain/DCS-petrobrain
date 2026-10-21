---
name: project_untested_wiring_pattern_caught_at_reviewer_not_dod
description: 3rd occurrence (2026-10-21, BL-B66/9k113-effectors) of "leaf module unit-tested, its wiring into the poll loop/consuming site is not" — tracked in reviewer's own memory, caught at Reviewer each time, never reaching DoD as a live defect
metadata:
  type: project
---

`.claude/agent-memory/reviewer/project_terrain_callout_stage5_wiring_gap.md` tracks this defect
class at 3 occurrences as of the BL-B66 (9k113-effectors) DoD pass: a thoroughly unit-tested pure
function/module gets wired into a poll loop or other consuming site, and the wiring itself has zero
test coverage — confirmed each time by mutation (disabling the wiring left the full suite green).

**Process signal, not a code signal**: all three occurrences were caught and fixed at Reviewer,
before reaching DoD. That is the role sequence working as intended (Reviewer's "required fix" loop
is exactly for this). Recorded here so a future DoD pass checking "does this match a recurring
category" finds it fast, and so that if a 4th occurrence ever **does** reach DoD undetected by
Reviewer, that escalation is itself the signal to consider — per root `CLAUDE.md`'s "Milestone
Completion" framing — moving this check earlier (e.g. an Architect-time note: "state explicitly
which test will drive the wiring, not just the unit") rather than only at Reviewer.

9k113-effectors' own instance: `sight_effector.py`'s sequencer was 21-tests-thorough in isolation;
the ~130 lines wiring it into `logger.py`'s `_run_crew_text_poll_loop` had none, including an
implementer-added test-enabling recorder (`cockpit_switch_writes`) that no test in the diff ever
called — a tell worth watching for on its own.
