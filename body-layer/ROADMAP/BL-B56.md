# BL-B56 — A fourth copy of the air-defence vocabulary, outside the new guard

- [ ] **BL-B56 — `crew_console.py:291`'s `_FOLLOW_DESCRIPTOR_OP_CLASSES` maps `"sam"` ∪ `"aaa"` to a set
  that is set-equal to `AIR_DEFENSE_OP_CLASSES`, and is not covered by the `<=` drift guard
  [[BL-B51]] added.** #status/open Found by the Reviewer during [[BL-12]] Stage 0, 2026-10-11, while
  verifying that `BL-B51` had consolidated *all* the copies. It had consolidated the three the item
  named; this is a fourth, in a different shape, which is why a `grep` for the constant did not find
  it.

  **The failure it leaves open is the same one `BL-B51` closed, one surface along.** A future
  air-defence `op_class` — say `OP_XLRSAM` — added to `object_model` would be **caught** by
  `classification.py`'s new `<=` guard and **silently missed** by `follow SAM`: the pilot names a
  SAM, the resolver does not consider that class a SAM, and the command quietly matches something
  else or nothing. The mechanism is `classification._op_class_of`'s early return on any non-default
  `OP_*` string, which is exactly what made `BL-B47` cost `OP_LRSAM` months of silence.

  **It is a descriptor-vocabulary map, not a membership set**, which is why it was not folded into
  `BL-B51`'s consolidation and should not be folded naively now: `"sam"` and `"aaa"` are *separate*
  spoken descriptors that happen to partition the air-defence classes between them, so the right fix
  is probably a guard asserting the union of the two descriptor entries equals
  `AIR_DEFENSE_OP_CLASSES`, rather than replacing either entry with the shared constant. That
  preserves the pilot being able to say "aaa" and not get a long-range SAM.

  Deliberately **not** fixed in Stage 0: the Reviewer judged it outside `BL-B51`'s stated three
  copies and outside the stage's scope, and the orchestrator agreed rather than widening a stage
  that had no scope drift at all.

  Related: [[BL-B51]] (the three copies now consolidated to `belief.classification`), [[BL-B47]] (the
  predicate whose months of silence this class of defect produces).
