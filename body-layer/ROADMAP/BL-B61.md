# BL-B61 — `group_matches` test 4 cannot tell kinds apart at class level

- [ ] **BL-B61 — `Group.composition` resolves through `object_model.profile_for`, so 5 of 10 real
  `op_class` values bucket to `OP_GROUPSOMETHING`, and `group_matches` test 4 ("a different *kind*
  of member is evidence of a new group", D4) does almost nothing for a class-level belief.**
  #status/open Found at Architect stage during the `collapse(group, depth)` plan, 2026-10-13 —
  **deliberately raised at Architect rather than filed as a sixth occurrence discovered at
  Reviewer/DoD**, per the standing advice in the `dod` role's own memory
  (`project_recurring_air_defence_vocabulary_resolution_gap.md`).

  **Measured**, `plans/group-collapse/scratchpad/probe_matcher_independence.py` §2b, over the real
  vocabulary:

  | `class_raw` | `profile_for` (what `composition` uses) | `parent_class_of` (the lattice) |
  |---|---|---|
  | `OP_ARMORED` | `OP_GROUPSOMETHING` | `OP_ARMORED` |
  | `OP_SPAAG` | `OP_GROUPSOMETHING` | `OP_SPAAG` |
  | `OP_LRSAM` | `OP_GROUPSOMETHING` | `OP_LRSAM` |
  | `OP_SRSAM` | `OP_GROUPSOMETHING` | `OP_SRSAM` |
  | `OP_MRSAM` | `OP_GROUPSOMETHING` | `OP_MRSAM` |
  | `OP_TRUCK`, `OP_INFANTRY`, `OP_ZU23`, and every TYPE-level string | agree | agree |

  Shown live in `probe_ad_composition_retirement.py`: a group of two class-level `OP_LRSAM`
  contacts has `composition = (("OP_GROUPSOMETHING", 2),)` while
  `air_defence_composition = (("OP_LRSAM", 2),)`.

  **Consequence.** Test 4 compares *sets* of `op_class` with the air-defence classes subtracted. At
  class level — the common case at range — both sides are `{OP_GROUPSOMETHING}` for armour, SAMs and
  anything else `profile_for` cannot keyword-match, so the subset test passes trivially. **Test 3
  (air-defence, lattice-resolved per amendment A3) is carrying the whole kind-coherence load alone**,
  and it only fires when one side has an air-defence member.

  **This is the 5th occurrence of the `BL-B47` family** (`BL-B47` fixed, `BL-B51`/`BL-B56`/`BL-B57`
  open): a predicate resolving a *believed classification* through a DCS-**type**-keyed table when
  the value in hand can be a class-level `OP_*` string. `BL-B47`'s fix — route through
  `classification.parent_class_of`/`_op_class_of` — is the precedent shape, and `_op_class_of` is a
  **strict superset** of `profile_for` (measured in `BL-B47`: 0 verdicts lost, 4 gained over 1060
  candidate values), so switching can only widen.

  **Why it is filed rather than fixed.** It is **not a live defect**: both sides of every comparison
  resolve the same way, so the field is self-consistent and `BL-12`'s tests pass honestly. Changing
  the resolver changes *matching behaviour* — groups that currently re-match would stop, and
  `Group.composition` is also test 5's speed-bound input (`_plausible_speed_mps` per `op_class`),
  which would start seeing real classes and therefore real speed bounds. That is a `BL-12`
  behavioural change needing its own plan, its own sortie evidence, and a decision about whether
  `air_defence_composition` then becomes redundant with a lattice-resolved `composition`.

  **Bears on `BL-14`.** Its spec's `step [count] left|right` is defined as *"staying inside the unit
  group"*, which rests on stable group identity. `BL-14`'s plan should not be written against an
  assumed-strong test 4. Flagged in `plans/group-collapse/plan.md`'s Risks for that reason.

  **Not fixed by the `collapse` work.** That derivation reads `Contact.classification` through the
  lattice and never touches `Group.composition` — see that plan's Decision 3 and finding B. The two
  are independent.
