### Implementation Summary

Implemented Stages 1, 2 and 4 of `plans/group-collapse/plan.md`. **Stage 3 was attempted,
discovered to change push-path speech behaviour for an existing, unmodified test, and reverted
rather than silently decided** — see "Stage 3 — attempted and reverted" below. This matches the
plan's own instruction: *"if the oracle disagrees anywhere, stop and report rather than adjusting
the expected line."*

### Files Changed

- `body-layer/src/belief/group_view.py` — new module. `CollapseDepth` (`GROUP`/`CLASS`/`SUBCLASS`/
  `TYPE`/`CONTACT`, `IntEnum`), `CollapseNode` (frozen dataclass), `collapse_members(members, depth,
  now_sim)`, `collapse(store, group, depth, now_sim)`. Builds the tree with four small per-level
  helper functions (`_class_children`/`_subclass_children`/`_type_children`/`_contact_children`)
  rather than one generic depth-dispatching recursion — an early draft that recursed generically by
  `CollapseDepth` looped forever on a `SUBCLASS`-level "remainder" bucket re-entering its own
  dispatch at the same level; the four explicit functions make each level's bucketing boundary
  (class → sub-class → type/undifferentiated-remainder → contact) a function boundary instead.
- `body-layer/src/belief/classification.py` — `CLASS_GROUP_OF`, the level-1 vocabulary (Decision 7):
  a sparse dict mapping every `AIR_DEFENSE_OP_CLASSES` member to `"air defense"`, identity for
  everything else via `.get(c, c)` at call sites.
- `body-layer/src/belief/tools.py` — `_group_facts` gains `now_sim` and a `tree` key (shallow,
  `CollapseDepth.SUBCLASS`), serialised via a new `_collapse_node_to_dict` helper that applies this
  module's absent-not-null convention recursively. Gated on `ContactStore.callout_observable` (any
  member, not all) before `collapse` is even called.
- `body-layer/src/belief/groups.py` — `group_matches` test 4's `classes - AIR_DEFENSE_OP_CLASSES`
  carve-out replaced with a `classification.CLASS_GROUP_OF`-based filter. Own commit per the plan
  (BL-12 code merged two days prior).
- `body-layer/docs/STRUCTURE.md` — registered `group_view.py`.
- `body-layer/tests/test_group_view.py` — new, 17 tests.
- `body-layer/tests/test_tools.py` — 3 new tests for the `tree` key and its observability gate.
- `body-layer/tests/test_groups.py` — 1 new test isolating Stage 4's changed line from test 3.

### Stage 3 — attempted and reverted

**What was built, then reverted.** `_group_composition_clause` was re-expressed as a renderer over
`collapse_members(..., CollapseDepth.TYPE)`, using throwaway `Contact` fixtures built purely from
each `facts["classification"]`'s `(value, level)` pair (`_synthetic_contact_for_facts`) — this
avoided threading `store`/`now_sim` through three call sites and two of the function's own direct
unit tests, which call it with bare `{"classification": {...}}` dicts carrying no `"id"` and no
store at all.

**What broke, found by running the full suite rather than only `test_speech.py`.**
`test_crew_console.py::test_report_speaks_a_persisted_group_as_one_counted_answer` — an existing,
unmodified test — asserts `render_group_full_disclosure(...).text == "Three BMP-2, 3 o'clock, 1
kilometre."` for three contacts whose `classification.value == "BMP-2"` and `.level ==
SpecificityLevel.CLASS` (the common test-fixture default across this codebase: `Observation`'s own
`classification_level` default is `CLASS` while `classification_raw` defaults to `"BMP-2"`, a
type-shaped string, for fixtures that are not exercising classification at all).

Old `_group_composition_clause` grouped by the literal `(value, level)` pair and rendered a
`"class"`-level value through `_OP_CLASS_DISPLAY.get(value, <literal fallback>)` — since `"BMP-2"`
is not a key in that table, the fallback returned the literal string, so three such members
rendered as `"Three BMP-2."`. The new `collapse_members`-based grouping resolves *every* class-level
value through the lattice (`classification.parent_class_of`, exactly Decision 3/finding B's point)
before bucketing — and `parent_class_of("BMP-2")` resolves to `"OP_ARMORED"` via `object_model.
profile_for`, same as a real type string would. So the three members collapsed into the `OP_ARMORED`
sub-class and rendered as `"Three armor."`

**Why this is not a bug to quietly fix either way.** It is a genuine semantic fork the plan's own
probes did not surface, because `probe_matcher_independence.py`'s round-trip test used only
internally-consistent `(value, level)` combinations (a `CLASS`-level value is always the bucket
string itself, e.g. `"OP_ARMORED"`, in real naked-eye/hybrid percepts — never a bare type string
held at the wrong level). The mismatched combination only arises from test fixtures whose default
`classification_level` doesn't match their default `classification_raw`'s own natural specificity.
Whether the push-path full-disclosure line *should* resolve such a claim through the lattice
(richer, consistent with everything else this plan does) or keep rendering the literal held string
(preserves every existing test byte-for-byte) is a product decision about what Petrovich says, not
an implementation bug — so it was left unbuilt rather than decided silently, per the plan's own
explicit instruction for exactly this situation.

**What was kept from the attempt.** While debugging this, a second, narrower and genuinely correct
divergence was found and fixed (see `group_view.py`'s `_subclass_label`, committed separately): a
claim held below `SpecificityLevel.CLASS` (`PRESENCE`/`UNKNOWN`) was being resolved through the
lattice by *value* alone, ignoring `.level` — so a presence-level member with a resolvable raw
value (the same test-fixture pattern above) was wrongly promoted into a real sub-class bucket. This
is unambiguously a bug in Stage 1's own semantics (a `PRESENCE`-level claim has, by the lattice's own
definition, no class claim at all, regardless of its raw string) and not a product-judgment
question, so it was fixed and kept. Fixing it was *necessary* to make the two Stage 3 prototypes
agree with `test_speech.py`'s own `test_render_group_disclosure_first_differentiation_is_full_once`
("Truck and something.") — but it did not, on its own, rescue the `test_crew_console.py` case above,
which is a `CLASS`-level (not `PRESENCE`-level) mismatch and therefore a different question.

**Everything from the reverted attempt was fully removed from `speech.py`** (`git checkout --`
against the Stage 2 commit) rather than left half-wired or commented out.

### Tests Added

- `test_group_view.py` (17): depth ladder (`GROUP`/`CLASS`/`CONTACT`), the air-defence branch
  collapsing two sub-classes to one class, a class-level-only roster resolving `OP_LRSAM` the lattice
  way (`Group.composition`'s `BL-B61` blind spot), a mixed class/type roster (siblings, no redundant
  single-child wrap in either the all-type or all-class-level case), order independence (the plan's
  own sorting-bug precedent), empty/single-member/all-left-the-store groups, `classification` vs
  `last_class_raw` divergence (the lattice's `hold` rule), the cardinality interval at `CONTACT`
  depth (never `len(members)`), confidence routed through `classification_confidence_at` (and that
  shallower nodes expose none), and the `_subclass_label` level-gate fix.
- `test_tools.py` (3): a class-level breakdown renders in `tree`; `tree` is absent when no group
  member has ever been confirmed observable; `tree` is present when only one of three members is
  (the **any**, not all, predicate).
- `test_groups.py` (1): test 4's `CLASS_GROUP_OF`-based exclusion, isolated from test 3's own
  air-defence-confirmation gate via a fixture-only inconsistency between `composition` and
  `air_defence_composition`.

### Mutations Run

- `tools.py`: `if any_observable:` → `if True:` — turned `test_group_fact_tree_absent_when_no_
  member_is_observable` red (tree present when it should be absent). Restored; sha
  `ba8c9ea4b2b06b8da399ca64fc2bf4a278642913` before and after.
- `group_view.py`: `_subclass_label`'s level gate removed (bare `value is None` check) — turned
  `test_collapse_members_presence_level_claim_stays_unknown_even_if_its_value_resolves` red
  (`OP_ARMORED` instead of `unknown`). Restored; sha `c03857c4f6eea31fd309e133cec8df732508f809`
  before and after.
- `groups.py`: test 4's `CLASS_GROUP_OF`-based filter replaced with a bare pass-through — turned
  `test_group_matches_composition_still_excludes_air_defence_via_class_group_of` red (`False`
  instead of `True`). Restored; sha `bdf0c8847a200f2a0a5312e5194df82ebe609707` before and after.

### Checks (body-layer/)

- `ruff format --check`: pass
- `ruff check`: pass
- `cd body-layer && .venv/bin/mypy src` (run via the main checkout's binary, cwd in this worktree's
  `body-layer/`): pass, 57 source files, no issues
- `pytest`: 1747 passed, 4 xfailed (baseline 1726 passed / 4 xfailed; +21 new tests: 17 + 3 + 1)

### Notable Discoveries

- **Test fixtures across this codebase commonly hold a type-shaped `classification_raw` (e.g.
  `"BMP-2"`) at the default `classification_level` (`CLASS`)**, a combination real naked-eye/hybrid
  percepts never produce (a `CLASS`-level claim's value is always the bucket string itself in real
  perception). This is invisible to any code that renders `(value, level)` literally without
  resolving `value` through the lattice, and becomes visible the moment something does — exactly
  what happened here. Worth knowing before any future change routes more of this codebase's
  class-level handling through `classification.parent_class_of`.
- **A generic depth-dispatching recursion for the collapse tree is a trap**, not just a style
  choice: a `SUBCLASS`-level "remainder" bucket (members held below `TYPE` within an otherwise
  type-split sub-class) must not re-enter the same per-level dispatch it came from, or it recurses
  forever. The four explicit per-level functions in `group_view.py` exist specifically because the
  generic form hit this.
- **`BL-B61`'s own measurement list ("all 131 keyword entries...") was not re-derived here** — this
  plan's finding A/B and `BL-B61` were taken as already-measured and read, not re-counted.

### Stage 3 — landed (second pass)

The semantic fork the first pass stopped on turned out to be a fixture defect, not a product
question — confirmed independently (not re-trusted from the first pass's own account) against the
real producers before touching anything: `perception.naked_eye_source._classification_for_tier`
(`hires` → `reporting_name_for` at level 3, falling back to `op_class` at level 2 only when the
name lookup misses; `medres` → `op_class` at level 2) and `perception.hybrid_source.py:284`
(hardcoded `classification_level=3`, with its own comment on why). **No real producer ever pairs a
type-shaped raw string with level 2** — level 2 always carries an `op_class` bucket string. The
`test_crew_console.py` fixture pairing `classification_raw="BMP-2"`/`classification_level=2`
(hardcoded in `_observation_at`) was exactly that unreachable state, not a case Stage 3 needed to
make a product decision about.

**Fixture classification table** (every test touched, reachable vs. not):

| test | fixture | classification | verdict |
|---|---|---|---|
| `test_speech.py::test_group_composition_clause_singular_is_bare_noun` | `OP_TRUCK`/class | reachable | unaffected (own OP_* string resolves identically through the lattice) |
| `test_speech.py::test_group_composition_clause_counts_members_exactly` | `OP_ARMORED`×2, `OP_TRUCK`/class | reachable | unaffected |
| `test_speech.py::test_render_group_disclosure_differentiated_group_gives_composition` | `OP_ARMORED`×2, `OP_TRUCK`/class | reachable | unaffected |
| `test_speech.py::test_render_group_disclosure_threat_capable_member_leads_the_line` | `ZSU-23-4 Shilka`/type, `OP_ARMORED`×2/class | reachable | unaffected (`ZSU-23-4` doesn't go through `_group_composition_clause` itself — only the leading-member branch reads it; `envelope_for` behaviour unchanged since `_match_type_row` has no `"ZSU"`/`"Shilka"` row match either way) |
| `test_speech.py::test_render_group_disclosure_mixed_pair_uses_the_composition_clause` | `OP_ARMORED`, `OP_TRUCK`/class | reachable | unaffected |
| `test_speech.py::test_render_group_disclosure_first_differentiation_is_full_once` | `Ural truck`/presence + `OP_TRUCK`/class | reachable | unaffected ("something" aggregation preserved via the `label == "unknown"` check on `group_view._subclass_label`'s own gate) |
| `test_crew_console.py::test_report_speaks_a_persisted_group_as_one_counted_answer` | `BMP-2`/class (hardcoded) | **unreachable** | fixture corrected to `classification_level=3`; assertion unchanged (a type-level value renders verbatim either way, confirmed by mutation below) |
| `test_crew_console.py::test_report_speaks_an_already_spoken_group_in_full` | `BMP-2`/class (hardcoded, same scene) | **unreachable** | fixture corrected for consistency with its sibling (identical physical scene); its own assertions (`content_signature is not None`, the final `render_report_summary` line) don't pin the literal composition text either way, so this correction changes nothing observable — done for honesty of the fixture, not because this test would otherwise fail |

No other test file calls `_group_composition_clause`/`render_group_disclosure`/
`render_group_full_disclosure` directly (`grep -rln` across `tests/`), so these seven are the whole
surface Stage 3 touches.

**What changed in `speech.py`.** `_group_composition_clause` now builds one throwaway `Contact` per
`facts` dict (`_contact_for_member_facts` — classification + cardinality only; every other `Contact`
field is a placeholder never read by `collapse_members`, per that module's own docstring) and calls
`belief.group_view.collapse_members(contacts, CollapseDepth.TYPE, now_sim=0.0)`, then walks the
tree's leaves (`_leaf_nodes`, depth-first over `CollapseNode.children`) and renders each through the
*same* vocabulary as before (`_unit_type_display`/`_plural_unit_type_display`/
`_undifferentiated_phrase`/`_SPOKEN_NUMBERS`) — a leaf labelled `"unknown"`
(`group_view._subclass_label`'s own name for "no class claim resolves, regardless of why") is
aggregated as undifferentiated exactly as the old `(value, level)`-literal check was; every other
leaf is rendered via `_LEAF_LEVEL_WORD` mapping `CollapseDepth.SUBCLASS → "class"` /
`CollapseDepth.TYPE → "type"` (the only two levels a leaf can hold at `CollapseDepth.TYPE`, per that
table's own docstring — `group_view._class_children` only emits a bare `CLASS`-level leaf when
called with `max_depth == CollapseDepth.CLASS`, which this function never requests). `now_sim=0.0`
is a dead argument at this depth — only a `CollapseDepth.CONTACT` leaf's `confidence` field ever
reads it, and this function never asks for contact depth.

**Why this is behaviour-preserving for every existing test, not just asserted to be.** The one real
mechanism change is that a class-level member now buckets by `classification.parent_class_of`
(the lattice) rather than the literal `(value, level)` string pair — but every reachable class-level
value in this codebase's real producers *is* already an `op_class` string that resolves through the
lattice to itself (`classification._op_class_of`'s own early return), so the two groupings coincide
for every input a real percept can produce. Canonical sort order also changed (alphabetical by
label at every level, `group_view`'s own invariant, vs. the old first-seen insertion order) — every
existing composition test's input happens to already be in alphabetical class order
(`OP_ARMORED` before `OP_TRUCK` in both orderings), so no existing assertion catches this, but it is
a real, deliberate behaviour change for the live push path: a group whose members are *observed* in
non-alphabetical class order now always speaks in the same canonical order regardless, which
removes an existing source of order-dependent wording rather than introducing one.

**Notable discovery not caught by any test, flagged rather than silently fixed or shipped.** A
`CLASS`-level member whose raw value is literally `object_model.DEFAULT_OP_CLASS`
("`OP_GROUPSOMETHING`") — reachable via `medres` detecting a type the keyword tables don't
recognise — used to render through `_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"] = "group"` (added
2026-09-22 after a live sortie heard the raw enum name; see that table's own comment). Under
`group_view._subclass_label`, this exact value resolves to `"unknown"` (`classification._op_class_of`
explicitly excludes `DEFAULT_OP_CLASS` from ever resolving, by design, for the lattice's
parent-consistency question) — so inside a *group's* composition clause specifically, such a member
now speaks as part of the undifferentiated aggregate (`"something"`/`"N contacts"`) rather than as
`"group"`. The single-contact report path (`render_contact_report`/`_contact_report_text`) is
**not** touched by this — it still reads `_unit_type_display` directly off the facts dict and still
says `"group"` for this value. No existing test exercises `OP_GROUPSOMETHING` at class level through
`_group_composition_clause` specifically (`test_render_contact_report_maps_default_op_class_to_
display_word` tests the single-contact path at `presence` level, not this one), so nothing failed —
but this is a real, if narrow, wording change for a reachable value, left unfixed because fixing it
properly means deciding whether `group_view.py` itself (merged Stage 1/2/4 code, out of this stage's
stated scope) should distinguish "no class claim" from "resolved to the default bucket," which is a
design question for the architect/user, not something to decide silently inside a migration commit.

**Mutation verification.**
- `tree = collapse_members(contacts, CollapseDepth.TYPE, now_sim=0.0)` → `CollapseDepth.CLASS`:
  turned 17 tests red (every test that reaches `_group_composition_clause`, including both corrected
  `test_crew_console.py` tests), with a `KeyError` on `_LEAF_LEVEL_WORD[CollapseDepth.CLASS]` (the
  table is deliberately total only over `SUBCLASS`/`TYPE`). Restored; sha
  `ebe2d70ba9b8a924236ab34bbbaba1fff116f752` before and after.
- `if leaf.label == "unknown":` → `if False:`: turned
  `test_render_group_disclosure_first_differentiation_is_full_once` red
  (`"Truck and unknown."` instead of `"Truck and something."`). Restored; same sha before and after.
- Reverted `test_report_speaks_a_persisted_group_as_one_counted_answer`'s own fixture correction
  (`classification_level=3` → `2`, Stage 3 code left intact) to confirm the *fixture* fix itself is
  load-bearing, not cosmetic: turned it red (`"Three armor..."` instead of `"Three BMP-2..."`) —
  the exact failure the first pass's revert note described. Restored; sha
  `de4fb28de8d595a53320262a251b81c148b2d1a8` before and after.

**Latent mismatched sites left alone.** Per the task's scope instruction, only the two fixture call
sites `_group_composition_clause` actually surfaced were corrected. `_observation_at`'s own default
(`classification_level=2` with `classification_raw="BMP-2"`) remains the default for every other
caller — three more call sites in `test_crew_console.py` use it un-corrected (lines ~362, ~1484,
and the four-contact `report_all` scene), because none of them cohere into a `Group` or reach
`_group_composition_clause`/`render_group_disclosure`; they exercise `render_report_summary`, which
already resolves class values through `classification.parent_class_of` directly and was never
sensitive to this mismatch. `Percept.classification_level`'s own default (`2`) is unchanged, per
the task's explicit instruction not to touch it.

**Checks (second pass).** `ruff format --check`: pass. `ruff check`: pass. `mypy --strict` (cd
`body-layer`): pass, 57 source files. `pytest`: **1747 passed, 4 xfailed** — identical to the
first pass's own already-landed-Stages-1/2/4 baseline; Stage 3 adds no new tests (re-expression of
an existing function, not new behaviour), only two one-line fixture corrections.

### Reviewer change request — both required fixes closed (third pass)

`plans/group-collapse/review.md` approved with two required fixes. Both addressed; no `group_view.py`
behaviour change, per the reviewer's own verdict on the second fix.

**Fix 1 — `STRUCTURE.md`'s `group_view.py` entry.** It still read "Stages 1-2" and described Stage 3
as "attempted and reverted," written at `c60c6cb` before Stage 3 actually landed (`fc87237`).
Updated the header to "Stages 1-4" and replaced the stale closing paragraph with one describing the
landed state: the fixture-correction finding (type-shaped raw paired with `classification_level=2`
is unreachable; real producers only ever pair that level with an `op_class` bucket string), the
canonical-sort behaviour change for the push path, and the `OP_GROUPSOMETHING` wording divergence
(reviewed, pinned by test, not a bug) — matching the register of the surrounding entries rather than
restating the plan.

**Fix 2 — a pinning test for the `OP_GROUPSOMETHING` wording change.** Added
`test_speech.py::test_group_composition_clause_folds_op_groupsomething_into_undifferentiated`,
pinning both shapes the reviewer reproduced: a pure `OP_GROUPSOMETHING` pair (`"two contacts"`) and
mixed with a differentiated member (`"truck and something"`), plus an assertion that the
single-contact path (`_unit_type_display("OP_GROUPSOMETHING", "class")`) still returns `"group"` —
the deliberate asymmetry the reviewer flagged as itself worth pinning. The docstring records why
this is a pin, not a fix: `classification.parent_class_of("OP_GROUPSOMETHING")` returns `None` by
design, the value is reachable (naked-eye `medres` on an unrecognised type at class level), and it
has now been wrongly assumed unreachable twice (the 2026-09-22 live sortie that added
`_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"] = "group"`, and this plan's own first implementation pass).

**No `group_view.py` or `speech.py` behaviour was changed** — per the reviewer's verdict, this is
(a), a deliberate and acceptable narrow divergence, not a defect; fixing it would touch merged
Stage 1 code and is an architect/user-level question about `_subclass_label`'s semantics, out of
this change's scope.

**Verified by mutation.** Changed `group_view._subclass_label`'s fallback from
`"unknown"` to `"OP_ARMORED"` (so `OP_GROUPSOMETHING` resolves into a real sub-class bucket instead
of the undifferentiated aggregate) — the new test went red: `assert 'two armor' == 'two contacts'`.
Restored; `shasum` of `group_view.py` identical before and after
(`c03857c4f6eea31fd309e133cec8df732508f809`), confirming no diff survived the mutate/restore cycle.

**Checks (third pass).** `ruff format --check`: pass. `ruff check`: pass. `mypy --strict` (cd
`body-layer`): pass, 57 source files. `pytest`: **1748 passed, 4 xfailed** (1747 + the one new
pinning test), confirmed by name in an unfiltered collection, not a `-k` run.
