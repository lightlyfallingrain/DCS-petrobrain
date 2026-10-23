# BL-B90 — Configurable cockpit effector sequences

- [~] **BL-B90 — Move cockpit switch sequences out of code into startup-loaded files: a named
  effector registry plus one sequence file per (aircraft, role, trigger).** #status/in-progress
  (`feature/effector-sequences`) Concept `docs/concept/configurable-cockpit-effector.md`; explore
  pass 2026-10-21, `plans/effector-sequences/explore-notes.md`; **planned 2026-10-21,
  `plans/effector-sequences/plan.md`**; started 2026-10-23 — plan revision for BL-B80 v2 first,
  then Stage 0 (the switch-list generator).

  **Sequenced after `[[BL-B80]]`** (user direction 2026-10-21: *"we'll do BL-B80 first, the slew
  is important. BL-B90 after that. Merge the plan and leave it for now"*). Nothing in the design
  needs BL-B80 to exist first — this is ordering only. BL-B80 v2 merged 2026-10-23 and rewrote the
  code this entry targets, hence the plan revision.

  First cut replaces `[[BL-B66]]`'s hard-coded power-up, OBSERV and safety-bar writes only;
  gating stays in code; overlapping triggers queue **per trigger**; readback is registry-driven at
  low rate. **Slewing is not in scope and never will be** — it is code, `BL-B80`.

  **Registry covers the whole Mi-24P, generated from ED's own cockpit scripts** (user direction:
  *"ED files is better. Use DCS-bios data as reference for what they do, if DCS file does not
  provide info."*) — DCS-BIOS is a by-hand labelling reference only, never parsed or vendored
  (GPL-3.0).

  **Decided 2026-10-23** (explore-notes, "2026-10-23"): queues per trigger; takeoff sequence runs
  on every takeoff, the file's own row conditions handle the already-powered case; a bad sequence
  file is logged, ignored, and announced on the intercom — body-layer keeps running (supersedes the
  2026-10-21 "fail loudly at startup"); its own short re-flight card.
