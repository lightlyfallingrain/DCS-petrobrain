# BL-B82 — No scanning before takeoff, replacing the on-ground silence default

- [ ] **BL-B82 — Petrovich does not scan before takeoff; this replaces the on-ground silence
  default.** #status/open Raised by the user 2026-10-19, while scoping `[[BL-B81]]` (radio check).

  > *"About the silence on ground. A better approach would be: do not scan before takeoff. That's a
  > better trigger and better behaviour. You can replace the ground silence logic with this one."*

  **What it replaces.** `CrewConsole.maybe_apply_on_ground_default` (`plans/spu8-intercom/plan.md`
  Stage 5) sets `silenced` at mission start when ownship is on the ground, and only a command ends
  it. Silence suppresses *speech*; the user's point is that the thing to suppress on the ramp is the
  *scan* — the trigger is takeoff, not a command.

  **Consequence for `[[BL-B81]]`.** None left: radio check is an ordinary command (user,
  2026-10-19), and with no ground silence the pilot hears the answer during engine start.

  ## Decided — user, 2026-10-19

  1. **Every time on the ground**, not only before the first takeoff — a FARP landing stops the scan
     too.
  2. **Not looking on the ground.** Commands are still heard and answered (radio check has to work
     during engine start); Petrovich simply does not scan. *"(would be looking on troop drop in
     enemy territory, but modelling that is deferred)"*
  3. **Takeoff = the existing 10 m AGL threshold** (`ON_GROUND_AGL_THRESHOLD_M`): *"good enough."*

  ## Left to the plan

  - What a look command (`watch`, `scan forward`) answers on the ground — proposed: an "unable"
    with its reason, per the project's "say again" vs "unable" distinction.
