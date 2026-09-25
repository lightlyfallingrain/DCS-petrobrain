---
name: d10-structured-candidates
description: BR-1 D10's 2026-09-25 revision — why matching rendered prose failed, the unknown-vs-mismatch asymmetry, and the why-strings-that-don't-exist finding
metadata:
  type: project
---

BR-1's brain-reply validator (D10) was revised on 2026-09-25 to match **token overlap over
structured candidate fields** instead of substrings over a rendered `why` string.

**Why:** a rendered enrichment summary is worded unlike speech, so a substring test over it rejects
the model's genuinely correct evidence ("near the village" is not a substring of "near Gemerek
village"). The deeper finding, and the one that mattered: **the `why` strings the measurements
assumed did not exist at all.** `belief.utterance._resolve_reference` calls `find_contact` with no
`enrichment`, and `_contact_summary` never renders `facts["semantic"]` even when enriched — so a real
candidate's `why` is `"T-72, observed, currently visible."`, identical across candidates, with no
place text. D9's A/B question was therefore degenerate in already-merged code and nobody had noticed.

**How to apply:**

- **When a design plans to match model output against text, check what that text actually is at
  runtime, not what the plan's worked example shows.** Both the measurement table and two review
  passes reproduced a hand-written `why` string. The one cheap check that would have caught it was
  reading the call site for the argument that was not passed.
- **Two jobs need two representations.** `why` is what Petrovich *says*; the structured fields are
  what the validator *matches* and what the prompt *projects from*. Conflating them is what the
  original rule did wrong.
- **"Unknown is not a mismatch" — settled, and the direction is load-bearing.** An absent
  classification claim (`SpecificityLevel` below the level being matched) blocks a PICK and forces
  ASK, because treating absence as a mismatch is Petrovich acting as if he knew what he does not.
  `Contact.classification.level` is sticky and never decays, which is what makes this checkable.
- **But place *absence* is a decided negative**, and that distinction is code-grounded, not carved
  out for convenience: `tools.py` and `enrichment.py` both document the absent-not-null contract
  ("checked and found nothing" vs "doesn't know yet"), and every candidate in one `find_contact` call
  is enriched through the same `describe_position` query and the same `NEAR_FACT_RADIUS_M` radii.
- **Location is the only channel that can discriminate in this design**, because `find_contact`
  selected the candidates by substring-matching the pilot's *class* word — so they already agree on
  class by construction. Classification fields exist mostly to make *non*-discrimination provable.
- **`_OP_CLASS_DISPLAY["OP_ARMORED"]` is `"armor"`, not `"tank"`, and that is correct** — the class
  also covers BMP/BTR. Do not add a `tank → OP_ARMORED` synonym; it would make "that tank" match a
  BTR. A per-*type* synonym layer is BR-2 work and touches `perception/object_model.py`.
- **`SemanticFact` discards structure it already has.** `semantic_facts_for` holds
  `SettlementInfo.name`/`.subtype` etc. and flattens them into prose; `feature_id` is a display
  fallback (ridge/valley variants embed a distance, names could contain a colon) — never parse it.
  Add explicit `kind`/`subtype`/`name` fields instead. Additive: consumers read `["text"]` only.

Related: [[project_br1_brain_layer_design]], [[project_bl26_classification_refinement]],
[[project_provenance_confidence_pattern]].
