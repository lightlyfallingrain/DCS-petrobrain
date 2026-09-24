---
name: bl8-kneeboard-design
description: BL-8 kneeboard/memory-layer design decisions — append-only note store beside ContactStore, the shut fold door, and the import-direction invariant
metadata:
  type: project
---

BL-8 is a **kneeboard**: an append-only `Kneeboard` of immutable `Note` records living in a new
`body-layer/src/belief/kneeboard.py`, a *sibling* of `ContactStore`, both owned by `logger`. Notes
hold `PositionEstimate` **copies**, never references. Persistence is append-only JSONL, the same
posture `speech_log.py`/`detection_trace_writer.py` already use. Corrections append a note with
`supersedes` set — you strike through, you do not erase.

**Why:** `ContactStore` is live belief; the kneeboard is a *record* of belief. Putting the record
inside the thing it records is how the two start fusing. Append-only also buys BL-0 replay
determinism for free and makes the disk form and memory form identical.

**How to apply:**

- **The fold door is deliberately shut.** `plans/precise-position-belief/plan.md` kept
  `fold_position`'s signature `(estimate, estimate) -> estimate` so a written-down position *could*
  fold in. BL-8 names that door and leaves it shut: folding an old snapshot into a live estimate
  *shrinks* the covariance — Petrovich gets more confident by consulting a note written before the
  thing moved. Precision laundering. If a later plan proposes folding a note in, this is the
  counter-argument.
- **Staleness is a property of *reading* a note, not of the note.** Readers call
  `covariance.inflated(now - as_of_sim)`. No new half-life in `decay.py` — checked, none of the five
  existing ones is the right reuse, because a note's staleness is a *motion* question not a
  *confidence* question.
- **The milestone's real invariant is an import direction**, and it is the thing a later refactor
  breaks silently: `kneeboard.py` must not be imported by `contacts.py`,
  `association_over_time.py`, or `position_belief.py`. Notes never enter `passes_gate` — contact
  identity stays geometric-from-percepts (BL-2). Linking is a post-`tick` read-side step in `logger`
  that affects language only.
- **Code holds the pen, never the brain.** Three writers with named admission rules
  (`commanded`/`briefed`/`observed`); the auto-writer is one rule keyed on `belief/threat.py`'s
  envelope table. No new tool — BL-7's precedent (fold into `get_situation`) keeps the BL-6
  15-tool freeze intact. See [[bl7-mission-phase-design]].
- **Briefing boundary is structural, not conventional:** the compact artifact is the only channel,
  `mission-interpreter/src/filter/crew_available.py` runs upstream of it, and `Tagged` provenance is
  carried into the note rather than collapsed. `CompactLocation` still has no position field — a
  briefed note carries `place_name` and `position=None`.
