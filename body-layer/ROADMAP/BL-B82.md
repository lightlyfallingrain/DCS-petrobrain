# BL-B82 — No scanning before takeoff, replacing the on-ground silence default

- [ ] **BL-B82 — Petrovich does not scan before takeoff; this replaces the on-ground silence
  default.** #status/open Raised by the user 2026-10-19, while scoping `[[BL-B81]]` (radio check).

  > *"About the silence on ground. A better approach would be: do not scan before takeoff. That's a
  > better trigger and better behaviour. You can replace the ground silence logic with this one."*

  **What it replaces.** `CrewConsole.maybe_apply_on_ground_default` (`plans/spu8-intercom/plan.md`
  Stage 5) sets `silenced` at mission start when ownship is on the ground, and only a command ends
  it. Silence suppresses *speech*; the user's point is that the thing to suppress on the ramp is the
  *scan* — the trigger is takeoff, not a command.

  **Consequence for `[[BL-B81]]`.** With the ground default gone, "radio check does not end silent
  mode on ground" no longer has a ground mode to protect. It still matters for the explicit
  `silence` command: radio check answers through it and leaves it on.

  ## Open — put to the user 2026-10-19

  - One-shot (first takeoff of the mission), or every time on the ground (a FARP landing)?
  - What still works on the ground: commands (`watch`, `scan forward`, radio check), calls about a
    threat that is already visible?
  - What counts as takeoff: the existing 10 m AGL threshold, or something else?
