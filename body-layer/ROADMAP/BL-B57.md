# BL-B57 — A class-level installation belief gets a non-zero plausible speed

- [ ] **BL-B57 — `position_belief.plausible_speed_mps`'s `installation_component` override (D8:
  "~0 for entrenched") never fires for a classification held at class level**, because
  `object_model.profile_for` resolves `installation_component` by keyword-matching a DCS *type*
  string, and a class-level belief carries the bare `OP_*` string instead (e.g. `"OP_SRSAM"`). #status/open
  Found by the Implementer during [[BL-12]] Stage 2b, 2026-10-12, flagged in the implementation log
  rather than fixed; confirmed and filed by the Reviewer the same stage round.

  **Concretely**: an entrenched SA-3 site, believed only to class (`last_class_raw = "OP_SRSAM"`,
  not yet identified to type), resolves through `_profile_for_contact`/`contact_growth_rate_mps` to
  the *default* profile (`object_model.DEFAULT_OP_CLASS`, `installation_component=False`), so
  `plausible_speed_mps` returns the default row (`8.0` m/s) instead of `0.0`. D8's own headline case
  — "~0 for entrenched" — is exactly the one this silently misses, and a class-level belief is most
  of a sortie's air-defence exposure (type identification happens late, if ever).

  **Numerically bounded on the op_class axis, not on the installation axis.** Every air-defence
  `op_class` in Stage 2b's table (`OP_SPAAG`/`OP_ZU23`/`OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`) is `8.0`,
  identical to the default-fallback row — so a class-level belief that fails to resolve its real
  `op_class` still lands on the right number *for that axis*. `installation_component` has no such
  fallback symmetry: its correct value (`0.0`) differs from the default (`8.0`), so the miss is
  real, not merely coincidentally-correct-anyway.

  **Does not interact with [[BL-12]]'s D6 carve-out.** D6's concern — a wrongly-resolved air-defence
  belief suppressing a threat warning — is gated through `belief.classification._op_class_of`
  (corrected by [[BL-12]]'s amendment A3, merged as part of Stage 1/3), a different code path from
  the growth-rate table. This item widens a displacement/association-gate bound, not a threat-
  envelope lookup — the practical effect is a class-level-believed entrenched site being treated as
  mobile for gate-sizing purposes, not a missed warning.

  **Pre-existing, shared, not new.** `_installation_of` and `_pair_backstop_m` (`belief/groups.py`)
  resolve `installation_component` through the identical `_profile_for_contact` → `profile_for` path
  and have had this gap since the installation cohesion cap was built
  (`group-cohesion-redesign/plan.md` §1). [[BL-12]] Stage 2 is the first consumer for which the
  *default-vs-correct* values genuinely diverge (`0.0` vs `8.0`, not `0.0` vs `0.0`), which is why it
  surfaced here and not earlier.

  **Not fixed in [[BL-12]] Stage 2**: `profile_for`'s keyword-substring resolution has no route from
  a bare `OP_*` string to entrenchment, and widening it (a second, class-keyed installation table,
  or threading `Contact.classification`'s lattice-level info through) is exactly the kind of
  resolution-path change `BL-12`'s amendment A3 took as its own separate, reviewed commit for the
  air-defence-membership case — this item is that same shape of fix, for a different field, and
  deserves the same treatment rather than a drive-by patch inside a calibration commit.

  Related: [[BL-B51]] (three copies of the air-defence set, same `profile_for`-resolution family of
  defect), [[BL-B56]] (a fourth copy, same family), amendment A3 in `plans/group-contact-identity/
  plan.md` (the precedent fix, for the membership-test case rather than the speed-table case).
