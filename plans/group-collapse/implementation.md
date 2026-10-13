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
