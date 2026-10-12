---
name: bl12-stage2-round-approved
description: BL-12 Stage 2 (per-class growth-rate mechanism/calibration split) review round -- mutation results for the ordering claim and the four moved tests, and the installation_component class-level gap ruling.
metadata:
  type: project
---

Reviewed `feature/bl12-group-contact-identity` at `b180c7e` (three commits on `33d78d8`: `2e05f87`
mechanism, `2f75286` calibration, `b180c7e` log). Verdict: **APPROVED**. Full detail in
`plans/group-contact-identity/review.md`'s Stage 2 round; this is the transferable part.

**Mutation results, each restored after observing the failure:**
- Reversed the order of `Contact.record`'s `growth_rate_mps = contact_growth_rate_mps(self)` vs
  `self.last_class_raw = percept.classification_raw` (moved the resolve to *after* the overwrite).
  **Full suite stayed green (1674/4).** The docstring's "resolved before overwriting" claim is true
  by reading but **pinned by no test** -- a future refactor could invert it silently. Not required
  for this round (Stage 1's `[[feedback_mutate_the_assertion_not_just_the_accessor]]` lesson is about
  verifying an existing test, not inventing a new one for every unpinned ordering claim), but worth
  a cheap regression test if this function is touched again.
- The two `test_contacts.py` fixtures (`range(1, 19)` replacing `range(1, 22)`): reverting to 22
  under the new calibration **fails both tests** (`2 == 1`-shaped assertion errors) -- confirms the
  renumbering is a tight re-derivation, not a loosened/rounded bound.
- `test_groups.py`'s ambiguity-tiebreak rescale (x∈[27,37]/4s replacing x∈[21,31]/2s): reverting to
  the old numbers under the new calibration drops `ambiguous_property_matches_count` to 0 --
  confirms real re-derivation.
- `test_enrichment.py`'s added `growth_rate_mps=plausible_speed_mps("OP_TRUCK")` on two `fold_position`
  calls: removing it diverges the "ground truth" computation from `fused.x` by ~0.2 m at `abs=1e-6`
  tolerance -- confirms it is load-bearing, not cosmetic.

**Ruling on the flagged-not-fixed discovery**: `object_model.profile_for` cannot resolve
`installation_component` from a bare class-level string (e.g. `"OP_SRSAM"` alone), so an entrenched
SAM believed only at class level gets the default `8.0` m/s instead of D8's `0.0` until identified to
type. Implementer's "numerically harmless" claim checks out **only** for the op_class axis (every
air-defence class's calibrated row is 8.0, same as the default fallback) -- it does **not** make the
installation-override miss harmless; that one axis genuinely returns the wrong number. Correctly
described as pre-existing and shared with `_installation_of`/`_pair_backstop_m`, and **does not
interact with D6's threat-suppression concern** -- D6 is gated through `classification._op_class_of`
(already corrected by amendment A3), a different code path from the growth-rate table. This one
widens a displacement/gate bound, not a threat-envelope lookup. Filed as `BL-B57` rather than left as
a log note only, because it sits inside, not adjacent to, what Stage 2b calibrates, and D8's own
headline case ("~0 for entrenched") is exactly the one it silently fails.
