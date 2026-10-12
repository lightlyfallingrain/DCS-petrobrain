---
name: bl12-amendment-findings
description: BL-12 amendment pass (2026-10-11) — the infantry cohesion bridge is amplified not dissolved by group identity; a plan's air-defence carve-out silently reintroduced a defect fixed the day before; id stability is not roster stability
metadata:
  type: project
---

Three transferable findings from amending `plans/group-contact-identity/plan.md` (BL-12) against
five days of merges. All three were found by reading current code, not by being told.

## 1. A plan that *consumes* a defective upstream mechanism can amplify it rather than inherit it

`BL-B48`'s question was "does BL-12's model dissolve the infantry cohesion bridge?" The framing
invites yes/no. The real answer was **neither** — BL-12 makes it worse, because every field BL-12
remembers about a group is an *aggregate* over a cluster it does not produce, and aggregates hide
extent. `centroid_uncertainty_m` (RMS of members' own position radii) says nothing about a 6 km
spread, so one membership flip moved the centroid **1,667 m** against a displacement bound of ~15 m.

**Why:** persistence turns a transient wrong value into a *spoken, asserted* wrong value, and a
heading derived from it is fabricated. A defect tolerated on a stateless path is not automatically
tolerable on a remembering one.

**How to apply:** when a plan adds memory or identity over an existing computed structure, ask what
property of that structure the new aggregates *cannot see*. For clustering, that is extent. Measure
one membership flip's effect on every new aggregate before accepting the plan's own thresholds.

## 2. A merged fix does not propagate into an open plan that names the old path

The BL-12 plan specified its air-defence carve-out as `last_class_raw` → `object_model.profile_for`
→ `AIR_DEFENSE_OP_CLASSES`. `BL-B47` had been merged the day before precisely because that path
cannot resolve a **class-level** belief: measured, `profile_for("OP_SRSAM"/"OP_MRSAM"/"OP_LRSAM"/
"OP_SPAAG")` → `OP_GROUPSOMETHING`, so **4 of 5 air-defence classes fail**. `OP_ZU23` passes only by
accident (the literal matches a keyword). The correct side is the classification lattice
(`classification._op_class_of` / `parent_class_of`) — type resolvers take type names, lattice
functions take believed classifications.

**Why:** the plan was written before the fix, cites the function by name, and reads as current. The
gate in question was the single one where the plan itself says ambiguity must *not* resolve toward
memory, because a wrongly-continued SAM suppresses a warning rather than mislabelling a contact.

**How to apply:** for every *named function* an open plan depends on, check what merged against it
since the plan was written — `git log --oneline -20 -- <file>` and the backlog entries for that
module. Relatedly, [[feedback_amend_plans_when_ground_shifts]] is the outbound half of this; this is
the inbound half, and the inbound half is the one nobody is assigned.

## 3. Group *id* stability is not group *roster* stability

`GroupStore.reconcile` recomputes clusters every tick; a property-match phase hands an existing id to
a freshly computed cluster. So making ids persist does **not** stabilise who is in a group. This
matters because `BL-B50`'s ratchet (and its Security lapse condition) is keyed on *membership*
flipping on consecutive ticks, and it was natural to assume the identity milestone would address it.
It does not — the cohesion fix and the contact-level fold do.

**How to apply:** when a milestone promises "X survives", name the field. Identity, roster, position
and disclosure history are four different survivals and a plan can deliver one while another
consumer needs a different one.
