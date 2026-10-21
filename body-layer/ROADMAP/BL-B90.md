# BL-B90 — Configurable cockpit effector sequences

- [~] **BL-B90 — Move cockpit switch sequences out of code into startup-loaded files: a named
  effector registry plus one sequence file per (aircraft, role, trigger).** #status/in-progress
  Concept `docs/concept/configurable-cockpit-effector.md`; explore pass 2026-10-21,
  `plans/effector-sequences/explore-notes.md`. On `feature/effector-sequences`.

  First cut replaces `[[BL-B66]]`'s hard-coded power-up, OBSERV and safety-bar writes only;
  gating stays in code; overlapping triggers queue; readback is registry-driven at low rate;
  validation errors at body-layer startup. **Slewing is not in scope and never will be** — it is
  code, `[[BL-B80]]`. Sequenced before `BL-B80`, after the `BL-B66` Stage 5 sortie flies on the
  current hard-coded build.
