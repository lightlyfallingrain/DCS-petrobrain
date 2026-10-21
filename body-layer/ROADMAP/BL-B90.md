# BL-B90 — Configurable cockpit effector sequences

- [ ] **BL-B90 — Move cockpit switch sequences out of code into startup-loaded files: a named
  effector registry plus one sequence file per (aircraft, role, trigger).** #status/open
  Concept `docs/concept/configurable-cockpit-effector.md`; explore pass 2026-10-21,
  `plans/effector-sequences/explore-notes.md`; **planned 2026-10-21,
  `plans/effector-sequences/plan.md`** (merged plan-only; not started).

  **Sequenced after `[[BL-B80]]`** (user direction 2026-10-21: *"we'll do BL-B80 first, the slew
  is important. BL-B90 after that. Merge the plan and leave it for now"*). Nothing in the design
  needs BL-B80 to exist first — this is ordering only.

  First cut replaces `[[BL-B66]]`'s hard-coded power-up, OBSERV and safety-bar writes only;
  gating stays in code; overlapping triggers queue; readback is registry-driven at low rate;
  validation errors at body-layer startup. **Slewing is not in scope and never will be** — it is
  code, `BL-B80`. The `BL-B66` Stage 5 sortie flies on the current hard-coded build.

  **Registry covers the whole Mi-24P, generated from ED's own cockpit scripts** (user direction:
  *"ED files is better. Use DCS-bios data as reference for what they do, if DCS file does not
  provide info."*) — DCS-BIOS is a by-hand labelling reference only, never parsed or vendored
  (GPL-3.0).

  **Open for the user before implementation** (plan, "Decisions Requiring User Input"): queue per
  trigger vs one global queue; takeoff power-up one-shot per mission vs the concept table's "every
  time"; startup-fatal validation as body-layer's first refuse-to-start; whether a short re-flight
  card is wanted.
