# BL-B82 — No scanning before takeoff, replacing the on-ground silence default

- [x] **BL-B82 — Petrovich does not scan before takeoff; this replaces the on-ground silence
  default.** #status/done #needs-flight Raised by the user 2026-10-19, while scoping `[[BL-B81]]`
  (radio check). Built on `feature/radio-check`, after `[[BL-15]]`'s Stage 1 merged, as this
  entry's own build order specifies. Reviewer/Performance Reviewer/Security all APPROVED; DoD
  passed at merge commit `92ae5b3cbee63548fa49344d171296ff3aca40b8` (`plans/radio-check/
  dod-check.md`) — **merge to `main` pending**, not blocked on live acceptance. `#needs-flight`:
  the gate logic is directly tested (both poll loops, mutation-verified by Reviewer; existing
  belief confirmed to decay but not be wiped on the ground) but whether 10 m AGL and "no callouts
  at all while grounded" feel right in the cockpit is unverified. Acceptance card published:
  https://claude.ai/artifact/QxCKq1kgUVKZnG1bfxzd8t (`docs/acceptance/2026-10-19-radio-check-card.md`).

  **Milestone-completion question (root `CLAUDE.md`):** does this change what the next milestone
  should be, or invalidate a downstream assumption? No — it replaces a narrower mechanism
  (`maybe_apply_on_ground_default`, a one-shot silence latch) with a strictly more general one (a
  per-poll on-ground gate that also covers look-command refusal), and nothing downstream depended
  on the old mechanism's narrower shape; `[[BL-B81]]` was explicitly designed to need no special
  casing once this landed, and that held.

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
