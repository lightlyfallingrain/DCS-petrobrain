# BL-W39 — `collapse(group, depth)` — the group tree, derived at read time

- [x] **`collapse(group, depth)` — Stages 1-4, merged 2026-10-13 (merge sha filled in by the
  merge step), `feature/group-collapse`. DoD-passed; NOT user-flyable — see acceptance boundary
  below, not a sortie waiver by omission.** #status/done `plans/group-collapse/plan.md`, from
  `docs/acceptance/2026-10-13-group-model-and-attention-tiers.md` Part 4 (user direction:
  *"collapse(group, depth) would be a good approach"*). Adds one derivation — group → class →
  sub-class → type → `CONTACT` (named per the user's own ladder, not `UNIT`) — over a `Group`'s
  existing `member_contact_ids`, storing nothing new. `Group.composition`/
  `air_defence_composition` are untouched and remain the match key; the derived tree is a separate,
  read-time projection for reporting.

  **Stage 1** — `belief/group_view.py`: `collapse(group, depth)`, `CollapseDepth` (`GROUP` /
  `CLASS` / `SUBCLASS` / `TYPE` / `CONTACT`), `CollapseNode` (`units_lo`/`units_hi` an interval
  summed from cardinality belief, never `len(members)`), canonical deterministic sort at every
  level. **Stage 2** — first consumer: `tools._group_facts` gains a `tree` key, inspectable via
  `console.py show <id>`. **Stage 3** — `speech._group_composition_clause` re-expressed over
  `collapse_members` (behaviour-preserving re-expression of an existing clause, not new scope); one
  real wording divergence found and kept deliberately: an `OP_GROUPSOMETHING`-class member inside a
  *mixed* composition clause now folds into the undifferentiated aggregate (`"something"`/
  `"N contacts"`) rather than saying `"group"` — reviewed, judged acceptable (conflating "resolved
  to the catch-all bucket" with "no claim at all" inside an otherwise-differentiated clause is
  defensible), and pinned by a test; `render_contact_report`'s single-contact path is untouched and
  still says `"group"`. **Stage 4** — `group_matches` test 4 shares the level-1 collapse table
  rather than its own carve-out; behaviour-identical, confirmed by mutation.

  A Stage 3 first pass hit what looked like a genuine semantic fork — an existing unmodified test
  pairing a type-shaped raw string (`"BMP-2"`) with class-level `classification_level` — and was
  reverted rather than silently decided. Reading the real producers
  (`naked_eye_source.py`/`hybrid_source.py`) showed no live channel ever emits that pairing; it was
  an unreachable fixture state, not a case the code needed to handle. User direction: *"Fix
  fixtures, land Stage 3."* Fixture corrected, Stage 3 landed with no behaviour change to the
  correction itself.

  Reviewer: APPROVED WITH MINOR FIXES (STRUCTURE.md staleness, missing pin test for the
  `OP_GROUPSOMETHING` wording), both closed and independently mutation-verified; confirmation pass
  APPROVED. Performance: APPROVED — MONITOR (the plan's own push-path cost figure was understated
  5-47x against the depth its caller actually requests — struck and corrected in `plan.md` §1;
  conclusion "depth is affordable" stands at the corrected figure). Security: APPROVED (one
  non-blocking finding — `units_hi` can propagate `math.inf` to a future strict-JSON consumer that
  does not exist yet; closed per option (C), a docstring warning, no code change). `body-layer`:
  1748 passed/4 xfailed, `ruff format --check`/`ruff check`/`mypy --strict` clean. `BL-B61` (already
  filed by the architect, not re-filed here) and `BL-B58`-`BL-B60` are untouched by this branch.

  **Acceptance boundary — this is not user-flyable, and that is deliberate, not a gap.** Nothing
  the pilot hears changes except the one `OP_GROUPSOMETHING` wording divergence named above, which
  is pinned by a test rather than left for a sortie to catch. The derivation's actual consumers —
  *"describe group"*, *"what armor is there"*, *"where's that Shilka"* — are Part 3's **high tier**
  and are unbuilt. So there is no sortie card: a flight cannot exercise a seam that produces no
  different audible output. The one thing worth a human's five minutes is inspection, not flight:
  `--console`'s `show <id>` on a group contact now has a `tree` key to look at.

  **Milestone completion question.** Yes, this changes what's next, in two ways:
  - **`BL-14` cannot be planned as a pure consumer of today's group model or of this derivation.**
    The attention-tier direction (`docs/acceptance/2026-10-13-...md`) says `BL-14` needs *per-unit*
    records for selected targets, produced by an attention-driven resolution mechanism that does
    not exist. `collapse` serves the reporting half (a cheap, derived, depth-bounded view for the
    pull path) but supplies no resolution — the two of six real units `BL-12` found with no record
    at all are still absent after this branch. See `BL-14`'s own entry, updated with this finding.
  - **`BL-B61`'s class-level resolution gap now has a concrete downstream consequence named**:
    `step left|right`'s "stay inside the unit group" semantics rests on group identity that
    `group_matches` test 4 cannot actually enforce at class level for 5 of 10 real `op_class`
    values. Not fixed by this branch (`collapse` reads `Contact.classification` through the
    lattice directly and never touches `Group.composition`), but the dependency is now explicit on
    `BL-14`'s own entry rather than only on `BL-B61`'s.

  Full DoD report: `plans/group-collapse/dod-check.md`.
