---
name: bl8-kneeboard-design
description: BL-8 mission memory — own package beside belief, the one carved import exception, worth-remembering vs worth-saying, the shut fold door; the 2026-10-17 explore notes supersede this memory's first version
metadata:
  type: project
---

**Revised 2026-10-17 after the `/explore mission memory` conversation.** The first version of this
memory was written before the user had settled the design, and it got two things wrong that a later
pass would otherwise have inherited. Both are corrected below; the parts that survived are the
reasoning, not the structure.

The plan of record is `plans/bl8-mission-memory/plan.md`; the specification is
`plans/bl8-mission-memory/explore-notes.md` (the user's own words, ten numbered decisions).

**Why:** this is the project's dominant failure mode — trusting a stored account over the current
state. A memory that pins a structure the user later decided differently is worse than no memory,
because it reads as evidence.

**How to apply:**

- **WRONG in v1: "`belief/kneeboard.py`, a sibling of `ContactStore` inside `belief/`."** It is its
  own package, `body-layer/src/mission_memory/`. The user's framing settles it: memory is *"the
  third queryable store beside belief and the world model"*, whose job is the cases belief
  **cannot** answer.
- **WRONG in v1: "No new tool — fold into `get_situation`, keep the BL-6 15-tool freeze intact."**
  The user's own direction makes the `TOOL_SET` extension *"a deliberate, documented act"*. The
  split that actually holds: **reuse where the new thing is a subset of an existing payload**
  (BL-7's mission phase, correctly folded into `get_situation`), **extend where it is a new store**
  (memory — a contact-keyed tool structurally cannot reach a mark, or a group belief has dropped).
- **The import direction is still the invariant that matters, with one carved exception.**
  `mission_memory` may import `belief`; **no module in `belief/` may import `mission_memory` except
  `belief/tool_api.py`**, which is a leaf and the composition root of the brain surface, so it
  cannot create a cycle or let a note re-enter belief. Enforced by a grep test, not by convention.
  Notes never enter `passes_gate`.
- **The fold door stays shut, and this is the counter-argument to have ready.**
  `fold_position(estimate, estimate)` could fold a written-down position into live belief. Folding
  an old snapshot *shrinks* the covariance — Petrovich gets more confident by consulting a note
  written before the thing moved. Precision laundering.
- **Staleness is a property of *reading* a note, not of the note.** Readers call
  `covariance.inflated(now - as_of_sim)`. No new half-life in `decay.py` — none of the five existing
  ones is the right reuse, because a note's staleness is a *motion* question not a *confidence* one.
- **Worth-remembering and worth-saying are different judgements.** The argument, because it will be
  challenged: speech is bounded by one voice channel and deliberately suppresses plenty he firmly
  believes; memory is bounded by consequence. Fuse them and the file becomes a transcript of what
  was said — which `speech_log.jsonl` already is — and the "safe from" consumer cannot answer about
  a group he never mentioned. So the writer is driven by **belief-state transitions**, never by
  percepts and never by callouts, placed after `run_once()` and before `drain_events()`.
- **An entry's `y` does not have the same provenance as its `x`/`z`.** `PositionEstimate` carries
  only `x`, `z`, `covariance`, `as_of_sim`; altitude is `Contact.last_alt_m`, a last-*observed*
  value. Anything plotting all three as equals overclaims. Same shape of trap as `as_of_sim` versus
  the write time.
- **`BL-8.md` points at the wrong code for its own named consumer.** It says the "safe from" callout
  is switched off in `belief/speech.py`'s `engaged=False` branch. It is not — `speech.py` renders it;
  the gate is `belief/callouts.py`'s `_OBSERVABILITY_EXEMPT_KINDS`, and its stated reason is
  **priority, not memory**. So BL-8 does not automatically unblock it. Corrected in the entry file
  2026-10-17.
- **No second ground-truth exception.** `detection_trace_writer.py` is the only sanctioned one
  (`body-layer/docs/STRUCTURE.md`). `lat`/`lon` come from `dcs_to_wgs84` applied to the *believed*
  x/z.
- **Briefing boundary, unchanged from v1 and still reserved rather than built:** the compact
  artifact is the only channel, `CompactLocation` has no position field, so a briefed entry carries
  `place_name` with `position=None`.
- See [[bl7-mission-phase-design]] for the reuse-versus-extend precedent this one is measured
  against.
