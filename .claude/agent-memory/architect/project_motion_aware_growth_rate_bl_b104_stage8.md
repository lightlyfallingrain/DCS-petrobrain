---
name: motion-aware-growth-rate-bl-b104-stage8
description: BL-B104 Stage 8 built the motion-keyed contact growth rate direction from 2026-10-13 that had sat unbuilt; the one resolution point is contact_growth_rate_mps, gated on Contact.on_surface (not Contact.motion) to keep air contacts bit-identical.
type: project
---

`docs/acceptance/2026-10-13-position-uncertainty-direction.md` ("position uncertainty must key on
observed movement, not class") was captured during `BL-12` and explicitly left unplanned — its own
"Next step" said it wanted its own entry. It sat unbuilt for over two weeks. `plans/bounded-fold-
displacement/plan.md` §6 later probed a *narrower* form of the same question (`0.0` only for
`"stopped"`, class rate for `None`) and found it didn't change that plan's own bound, but did not
build the direction either.

BL-B104 Stage 8 (2026-10-30) finally built it, triggered by a live E5 fold (two groups on one
bearing collapsing to one contact during a masked closing run) rather than by someone returning to
the open note. The user's words that day were simpler than any of the 2026-10-13 note's three
candidate shapes (no horizon, no decay curve): `"stopped"` **and** `None` both get a tiny constant
rate; `"moving"` gets the class-table rate.

**Why: a captured-but-unscheduled direction note is easy to lose entirely** — this one was found
only via `gq.sh` surfacing it as a graph node ("Position uncertainty keyed on observed movement, not
class"), not by anyone remembering it existed. Two live plans (`bounded-fold-displacement`,
`attack-run`) already referenced it as "awaiting its own entry" and both needed a pointer added once
this stage landed.

**How to apply**: when a user direction note under `docs/acceptance/` says "not planned here, wants
its own entry" and names an open calibration question, that note is a live, unscheduled TODO, not a
closed one — a later architect pass touching the same mechanism (here: `contact_growth_rate_mps`,
the single resolution point both `Contact.record`'s gate/fold-bound and `attack_run._tier2_alignment`
call) should grep for it before designing fresh, and should amend it in place once built rather than
leaving it to be rediscovered a third time.

**The concrete design hazard this stage's own review caught before shipping**: gating the new tiny
rate on `Contact.motion` directly (rather than `Contact.on_surface`) would have changed behaviour for
*air* contacts too — `naked_eye_source` computes `apparent_motion` for every admitted cluster
regardless of domain, so an aircraft momentarily read as `"stopped"` (or never motion-classified via
the scope/hybrid channel) would have silently dropped from ~8 m/s to the tiny rate mid-flight. Gating
on `Contact.on_surface` (BL-B104's own Stage 2 field) instead keeps every air contact's
`contact_growth_rate_mps` call bit-identical to pre-Stage-8, because that branch no longer reads
`Contact.motion` at all for `on_surface is False`. Worth checking for this shape again: whenever a
new belief rule is gated on "was this observed moving", check whether the field that actually
differs between the intended target population and an unintended one is domain (`on_surface`), not
the motion flag itself — the motion flag can be populated for both.
