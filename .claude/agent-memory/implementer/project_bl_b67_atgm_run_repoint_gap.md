---
name: project_bl_b67_atgm_run_repoint_gap
description: BL-B67's body.py engage-apply block always builds AtgmRunState fresh on re-point, contradicting the plan's own Co-moving Fields table -- latent until Stage 7 wires decide() in, must be fixed then
metadata:
  type: project
---

Found while implementing `[[BL-B67]]` Stage 3 (`plans/bl-b67-atgm-run/plan.md`), 2026-10-29.

`body.py`'s engage-apply block (`AtgmRunState(contact_id=atgm_contact_id)`, built in Stage 1)
always constructs a wholesale-fresh `AtgmRunState` on every `engage ... missiles`, including a
re-point while an ATGM run is already active. The plan's own Co-moving Fields table says
otherwise for that exact transition ("engage missiles, ATGM run active, new target"): `atgm`
should **keep** `phase`/in-flight/`selected_step` and only reset the range latches and update
`contact_id`.

This was harmless through Stage 1/2 (`AtgmRunState` carried only `contact_id`, nothing else to
lose) and stayed uncaught by Stage 1-2's own review (its "four rows Stage 1 claims" list never
named this transition). It becomes a real bug the moment Stage 7 wires `decide` into the poll
loop: a re-point mid-flight would silently forget the missile is in flight and reset back to
`PREPARING`.

**Why:** classic instance of
[[feedback_decide_fresh_dataclass_construction_drops_fields]] — a fresh `ClassName(...)`
construction site carries forward only what is named, and a field added later (Stage 3's
`phase`/`selected_step`/etc.) is invisible to "does this work" until the construction site is
actually exercised with something to lose.

**How to apply:** Stage 7 (whoever wires `decide` into `body.py`'s poll loop) must fix the
engage-apply block's re-point branch to `replace()` the existing `AtgmRunState` (keeping
phase/in-flight/selected_step/tracked_family, resetting only the three range latches and
`contact_id`) instead of constructing fresh, when an ATGM run was already active. Do not
re-introduce the current (wrong) wholesale-fresh behaviour unexamined just because it is what is
already there. Documented in `body-layer/docs/STRUCTURE.md`'s `atgm_run.py` entry and
`plans/bl-b67-atgm-run/implementation.md`'s Stage 3 section too — this memory is the
cross-session pointer so a cleared context picks it up before touching that block again.
