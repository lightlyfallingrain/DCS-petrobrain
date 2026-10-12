---
name: recurring-air-defence-vocabulary-resolution-gap
description: 4th occurrence of a predicate resolving air-defence status (or a derived property) through object_model.profile_for's DCS-type-keyed table when the value in hand is a class-level OP_* string or an external descriptor — raise at Architect, not Reviewer/DoD.
metadata:
  type: project
---

**Four occurrences now of the same underlying mechanism**, each found independently, at different
stages, across two features:

1. `BL-B47` (fixed 2026-10-11) — `speech._is_air_defence` resolved a believed classification
   through `object_model.profile_for`, a DCS-*type*-keyword table, so 4 of 5 air-defence `op_class`
   values were never recognised before type identification (`OP_LRSAM` silent for months; `OP_ZU23`
   passed only by the coincidence that its literal string matches that table's own keyword).
2. `BL-B51` (open) — the air-defence class set exists in three places; two of the three have no
   `<=` drift guard against `object_model` growing, only a literal-equality pin that cannot notice
   a new class being added underneath it.
3. `BL-B56` (open) — a fourth copy, in a different shape (`crew_console.py`'s `follow SAM`/`follow
   AAA` descriptor map), not caught by `BL-B51`'s consolidation because it maps descriptors to a
   set rather than testing membership in one.
4. `BL-B57` (open, found during `BL-12` Stage 2b) — `position_belief.plausible_speed_mps`'s
   `installation_component` override (D8's "~0 for entrenched") never fires for a class-level
   belief, because `profile_for` resolves `installation_component` by keyword-matching a *type*
   string and a class-level belief carries a bare `OP_*` string instead — so an entrenched SA-3
   site believed only to class is treated as mobile (8.0 m/s) for gate-sizing.

**Why this is a distinct pattern from
[[project_recurring_keyword_table_vocabulary_mismatch]]**, though it shares `profile_for` as the
collision point: that memory is about joining two *externally*-authored vocabularies (F10 labels,
Hoggit wiki names) against DCS-internal type strings. This one is entirely internal — the
classification lattice's own class-level string (`OP_SRSAM`, etc.) being handed to a function whose
keyword table was built assuming a DCS *type* string, never a class string. `BL-B47`'s fix
(resolving through `classification.parent_class_of`/`_op_class_of`, the lattice walk, instead of
`profile_for`) is the precedent correct shape for the membership-test case; `BL-B51`, `BL-B56` and
`BL-B57` are each the same fix needed for a different field or site and have not had it applied.

**How to apply:** whenever a plan or review touches `object_model.profile_for` (directly or via
`_profile_for_contact`), check whether the value being resolved can ever be a class-level `OP_*`
string rather than a DCS type string — if so, the lookup is in this family and should route through
the classification lattice, not `profile_for`, regardless of which field (`installation_component`,
air-defence membership, descriptor sets) is being read. This is now a 4th occurrence surfacing at
Reviewer/DoD-discovery time across two separate features (`BL-13`'s query path, `BL-12`'s group
identity); raise it as an explicit Architect-stage question — *does `object_model.profile_for`
ever receive a class-level string here, and if so, route through the lattice instead* — rather than
filing a fifth backlog item next time it is found.
