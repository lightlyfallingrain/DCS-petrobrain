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

  4. **A look command on the ground** (`watch`, `scan forward`) answers *"unable, on the ground"* —
     understood, not doable (the "say again" vs "unable" distinction). User: *"fine"*.

  ## Build order (user, 2026-10-19: *"Queue these so that build order makes sense, no need for
  parallel."*)

  1. `[[BL-15]]` Stage 1 merges first — its refusal mode changes `CrewConsole`'s command dispatch.
  2. **`BL-B82`** — removes the on-ground silence default, which `BL-15`'s reset also touches.
  3. `[[BL-B81]]` radio check — on the settled dispatch, an ordinary command.

  `feature/radio-check` is rebased onto `main` after `BL-15` merges, before building.
