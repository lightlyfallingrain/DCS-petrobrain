# BL-B51 — Three copies of the air-defence class set, one drift guard

- [ ] **BL-B51 — The air-defence class set exists in three places and only one of them has a guard that
  can notice `object_model` growing.** #status/open Found by the Reviewer during [[BL-B47]],
  2026-10-10, and **verified by mutation**. Exposure is *unchanged* by that fix — the old predicate
  tested the same set — so this is not a regression, but `BL-B47` made the set matter more: the push
  predicate, the pull clause **and** the freshness marker now all resolve against it.

  | copy | guard | can it notice a new `OP_*` air-defence class? |
  |---|---|---|
  | `crew_console.py:264` | `air_defence_by_name <= _AIR_DEFENCE_OP_CLASSES`, derived from **both** `object_model` tables | **yes** |
  | `belief.groups.AIR_DEFENSE_OP_CLASSES` (`groups.py:234`) | `== frozenset({…five literals…})` | **no** |
  | the third copy | — | — |

  **Measured:** injecting a fake `OP_XLRSAM` profile turns the `crew_console` test **red** and leaves
  `test_constants_are_the_stated_assumptions` **green**. A literal equality pin is a *change
  detector*, not a drift guard — it fires when someone edits the frozenset and stays silent when the
  object model grows underneath it, which is the only direction that actually loses coverage.

  **This exact drift already cost real coverage.** `OP_LRSAM` went unrecognised for months in the
  other copy, which is what [[BL-B47]] fixed. The lesson is not about air defence: a pin against a
  literal cannot protect a set whose correctness is defined by its relationship to another table.

  Leaving `crew_console`'s copy in place was correct — it already resolves via the lattice and its
  comment states a real reason for living there. The defect is that two copies have no `<=` guard,
  and that three places can disagree about what air defence is. Fix shape: one set, one `<=` guard
  derived from both `object_model` tables, with the other sites importing it.

  Worth doing before or alongside anything that widens the air-defence treatment further, since
  every such change raises the cost of the three copies disagreeing.
