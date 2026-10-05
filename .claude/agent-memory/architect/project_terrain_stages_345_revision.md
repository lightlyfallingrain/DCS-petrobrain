---
name: terrain-stages-345-revision
description: Terrain Stages 3-5 re-plan (2026-10-05) — "next valley" became an ownship-relative crossing count, not a basin graph; landform facts were already structurally mute in speech.py
metadata:
  type: project
---

Stages 3-5 of `plans/terrain-feature-probing/plan.md` were re-planned on 2026-10-05 as "Revision 3"
after geomorphons (`WM-B6`) + the relief gate replaced the never-shipped watershed design.

**The reframing that unlocked it: "next valley" does not need a basin graph.** The old Stage 3
assumed basin adjacency would "come free". With a flat set of 234,799 traced `LineString`s there is
no face structure, so "the valley the contact is in" is not an object in the data. But the pilot's
phrase is a claim about *what lies between us and it* — so it reduces to counting deduplicated
ridge crossings on the ownship→contact segment. Query-time, ~100 lines, no rebuild.
**Why:** the build-time alternative would have cost the user a second full ~14-minute cold
`syria-full` rebuild one day after they ran one, to precompute an answer that is ownship-relative
and therefore not precomputable at all.
**How to apply:** when a plan wants a static topology tag, first check whether the question is
actually observer-relative. If it is, the tag cannot answer it and the rebuild is pure cost.

**Two measured facts about the live consumer that any Stage 5 work must start from:**

- Landform rows carry `confidence={"geometry": "low"}` → 0.4 in
  `enrichment.py::_FEATURE_CONFIDENCE_NUMERIC`, and `speech.py::_contact_report_text` speaks only
  `max(semantic, key=confidence)`. **Terrain is structurally outbid by road/settlement facts and
  effectively never reaches the pilot today.** The live symptom is silence, so naive wiring flips
  straight from mute to over-naming with nothing in between.
- `NEAR_FACT_RADIUS_M["ridge"]/["valley"] = 1000.0` was tuned when the store held **12** ridges in
  a 20 km region. Against 234,799 rows it admits essentially always. A constant can be invalidated
  by a data-volume change four orders of magnitude away with nothing flagging it — see
  [[feedback_verify_state_not_the_account_of_it]].

**Selection rule adopted**, whose default is to name nothing: emit a position qualifier only if the
nearer of {nearest ridge, nearest valley} is within ~300 m *and* beats the other kind by ~2x.
**Why:** the stated trap is a contact in a valley sitting nearer a ridge line; the dominance test
makes that case produce *no* qualifier rather than the wrong one.

Related: [[project_wmb6_geomorphons_plan]], [[project_contact_report_flood]].
