---
name: project_optic_revocation_two_poll_lag
description: optic_policy's guidance_request revocation (disengage/drop_target) takes two polls, not the usual one-poll lag -- bounded, not a capability-gate bug, found during BL-B71's security deep analysis.
metadata:
  type: project
---

`logger.py`'s `decide_optic` reads `attack_run_state.requested_optic` as `guidance_request`, which
is itself one-poll-lagged against `drain_attack_run`'s own recompute (documented, `logger.py:578-591`).
`drain_attack_run` nulls `attack_run_state` once the `attack_target` task is gone, but the commands
that remove that task (`drop_target`'s `_handle_cancel_task`, and `disengage`'s `attack_run_transition`
flag) are both processed *later in the same poll iteration* than `drain_attack_run` itself. Net effect:
a command issued at poll N is not reflected in `attack_run_state` until the end of poll N+1, and
`decide_optic` doesn't see that `None` until poll N+2 -- one extra poll beyond the single-poll lag
pattern used everywhere else in this module (`home_phase`, `attack_run_transition` applied directly).

**Why it is not a security finding (checked explicitly, `BL-B71`'s security deep analysis,
2026-10-16):** during the extra poll, `_apply_guidance`'s sight-ceiling clamp still reads the
*current* `home_phase`, which `drop_target`/`disengage` never touch. So the lag can only extend an
*already pilot-authorized* grant (OBSERV already on) by one poll after the target was dropped -- it
can never grant a sight rung that was not already legitimately open. Symmetric across both exit
paths, bounded to one extra poll (sub-second to ~1 s at observed cadence).

**How to apply:** if `BL-B66`'s planned `OpticPhase.GUIDING` consolidation (unifying the gaze claim
and the optic choice, per `BL-B71.md`'s "known structural seam" note) touches this revocation path,
re-check whether the consolidation collapses this to the ordinary one-poll lag or leaves it as two.
Not worth a standalone fix on its own -- it was correctly left unfixed, not missed.
