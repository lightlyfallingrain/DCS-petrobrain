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
  2026-10-21 "fail loudly at startup"); its own short re-flight card. **Readback rate/scope,
  2026-10-23 (explore-notes)**: switch positions move off BL-B80's per-frame push to a lower-rate,
  ideally on-demand `Export.lua`-level query — not deferred to backlog, this is BL-B90's own
  **last** stage (R7/Stage 4, `plan.md`).

  **Stage 0b — the offline effector-registry generator — done, 2026-10-23**
  (`body-layer/tools/generate_effector_registry.py`), DoD-passed
  (`plans/effector-sequences/dod-check-stage0.md`). Stage 0a's live recon
  (`aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md`, build 2.9.30.28738) corrected
  several of the plan's and `mi24p-command-surface.md`'s original guesses (devices.lua's
  declaration form, the command_defs.lua include direction, the raw-literal field names, the real
  18-of-22 helper set, the always-resolved `seat`/`seat_explicit` pair, the three-way completeness
  invariant) — `plan.md`'s "Forms the parser must handle" section is updated to state these as
  fact, not as open questions. One security finding filed and fixed in the same batch
  (`[[BL-B91]]`, TOML control-character escaping in `label`/element `name`).

  **Stage 0c/0d — done, 2026-10-23.** Real run on the Windows DCS machine against
  2.9.30.28738: 749 heads = 514 elements + 235 field patches, **0 unhandled**; dump committed as
  `body-layer/config/effectors-raw.toml` (`872aa905`). Every 0d control point matches — the five
  device ids, `asp_commands.Power`, all six BL-B66 switch writes (761 now confirmed as ED's
  `WEAP-DISTR-POWER-OP-PTR`), 738/856, and 664 on the operator seat
  (`plans/effector-sequences/implementation.md`, "Stage 0c/0d"). **Next: Stage 1** — curated
  registry + sequence loader.

  **Milestone-completion question**: Stage 0b's completion does not change what Stage 0c/1+ should
  be — the generator was built *to* the plan's spec (corrected where the recon proved the plan's
  original guess wrong) — but it does sharpen one downstream assumption: Stage 1's curated
  `effectors.toml` can now be filled in directly from the real dump's `seat`/`shape`/`cmds`/`args`
  field names once Stage 0c/0d land, with no further format negotiation, since those names are now
  implementation-fact rather than plan-guess.

  **Stages 1-2 — done, DoD-passed, 2026-10-23** (`plans/effector-sequences/dod-check-stage1-2.md`).
  Curated registry + sequence loader (`belief/effector_registry.py`/`effector_sequences.py`) and
  the engine/wiring (`belief/effector_engine.py`, `logger.py`, `crew_console.py`) replace
  `sight_effector.py`'s hand-written takeoff/OBSERV/weapons-safety write blocks. Built to plan with
  three revisions made live during implementation: **R12** — the engine itself skips a row whose
  effector is already observed at the target value (an implicit self-check on every row, not just
  takeoff's), so the shipped takeoff file carries no explicit `!= on` condition at all; **R13** —
  per-aircraft layout (`config/sequences/<aircraft-dir>/`, `config/effectors-raw/<aircraft-dir>.toml`)
  with a device/cmd/arg collision resolved "first TOML-file-order entry wins, reject the rest" (not
  "drop both," which is what the plan said before this revision); and the performance review's
  change request gating `GET /spu8/state` behind `config_error_pending` so the fetch only runs
  until the one-shot config-error line has fired, not every poll of every sortie. Reviewer
  APPROVED (one required fix on the SPU-8 intercom-gate test coverage, closed and mutation-
  verified in the same batch), security deep analysis APPROVED (no findings), performance review
  APPROVED with the one change request above, closed and mutation-verified. `plan.md`'s R12/R13
  rows and D6 now state the built behaviour directly rather than only in the review reports.
  `body-layer/CLAUDE.md`'s module map and this entry are the user-facing pointers to the new
  modules, the "add a new effector" how-to, the bad-file posture, and the two tunables.

  **Re-flight card published**: `docs/acceptance/2026-10-23-bl-b90-sequences-reflight.md`, branch
  `feature/effector-sequences`, not yet merged. #needs-flight — six items (cold-start takeoff
  order/timing, second-takeoff no-op, Observ/weapons readback parity, warm air-start silence,
  hand-switched-off recovery, one deliberately broken sequence file) all clearable in one sortie on
  the branch above; nothing here has been flown yet, only built and reviewed.

  **Next: Stage 3 is this card** (already published, awaiting a flight) **and then Stage 4** —
  the generic low-rate/on-demand switch readback (R7), BL-B90's own last stage, not deferred. No
  merge yet: the user decides when, after (at least) this card's flight.
