---
name: project_bl26_classification_refinement
description: BL-2.6 (classification refinement) design decisions — specificity lattice, monotone fusion, ED's coarse-class ceiling, and the offline-executability requirement
metadata:
  type: project
---

**BL-2.6** (`plans/classification-refinement/plan.md`, branch `feature/classification-refinement`)
grades Petrovich's identity claims by observation quality. Label confirmed as BL-2.6 (not a PB-x):
it is scheduled in the BL sequence, its mechanism is contact-memory work, and it is *not* a new
perception tier — which is the thing that earned PB-1.5 its PB- label. See
[[project_bl25_text_panel_output]] for the naming rule this applies.

**Durable design decisions worth reusing:**

- **Specificity = total order over levels (unknown/presence/class/type), tree over values.** The
  "better claim" relation needs a total order to be well-defined; the *values* only need a
  parent-of function, which `belief/association_over_time._op_class_of` already is. An
  unresolvable parent yields `unknown` comparability — permits refinement, never asserts
  contradiction. Same three-valued posture BL-2 already took.
- **Monotone specificity is its own hysteresis.** Once you rule that a coarser observation never
  overwrites a better one, range oscillating across a tier threshold cannot produce event spam —
  no hysteresis constant is needed and adding one would be noise. The *only* residual spam path is
  two channels persistently disagreeing, which needs a short contradiction lockout. Reach for the
  structural rule before reaching for a tuning constant.
- **Confidence decays, level does not.** A crew member who identified something becomes *less
  sure*, he does not revert to "something." Letting the level decay would reintroduce oscillation
  on a slower clock. `decay.py`'s long-declared, never-consumed `IDENTITY_HALF_LIFE_S` is what
  finally gets used.
- **Keep `Contact.last_class_raw` (most recent raw percept) as the *association gate's* input, and
  put the held belief in a separate field.** Feeding the gate the monotone best-claim would make it
  progressively stricter and start rejecting genuine re-observations. Two fields with clearly
  different jobs beat one field with a compromised meaning.

**The investigator finding that changed the design (2026-09-09, Session 6 addendum to
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`):** ED's
ambient-callout fragment bank has **no per-model vocabulary at all** — coarse class is ED's own
ceiling for what a crew member perceives without the sight. So the naked-eye channel caps at class
and specific types arrive only via the scope channel. Also a clean negative on Q1: `min_angular_
radius` has no readable consumer in Lua *or* in any DLL string table, so the tier→specificity
reading is **ours**, not ED's, and must be documented as an owned modeling choice (same posture
PB-1.5 took with `BINOCULAR_RANGE_MULTIPLIER`). **Why this matters beyond BL-2.6:** two prior plans
have now leaned on "ED's constants mean X"; that mapping has never actually been verified and
probably cannot be. Do not let it drift into fact in a future plan.

**Offline-executability is a real constraint on this project's plans (user requirement,
2026-09-09).** A planning session may have `$DCS_INSTALL_PATH` while the implementing session does
not. **How to apply:** while access exists, extract every DCS-derived fact the implementation will
need into a committed `research/` doc or data file with provenance (source path, DCS version,
extraction date) rather than leaving "go read the install" in the plan; then add an explicit section
listing what is available offline and what genuinely still needs a live sortie. `win-mac-sync/` is
gitignored and will not exist on the offline machine — always cite the committed research doc, never
that path.

Related: [[project_bl2_contact_memory_design]], [[project_pb1_5_naked_eye_revision]].
