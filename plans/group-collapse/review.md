### Review Summary

Reviewed `feature/group-collapse` at `fc87237d462865d9d7f3ddf81cfb06cab7542519` (worktree HEAD was
a strict ancestor of this sha on a clean tree; fast-forwarded, verified by `git rev-parse HEAD`
after). Read `plans/group-collapse/plan.md`, `implementation.md`, all six scratchpad probes,
`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md`, `BL-B61.md`,
`body-layer/CLAUDE.md`, `body-layer/docs/STRUCTURE.md`. Read every changed source/test file in
full and the full commit-by-commit diff `cbf4c1e..fc87237` (8 commits). Ran format/lint/mypy/pytest
myself from inside `body-layer/` (not taken on the implementer's word) and ran three of my own
mutation checks independent of `implementation.md`'s own mutation table.

**My own verification, not just reading the account of it:**
- `ruff format --check` / `ruff check`: pass. `mypy --strict`: pass, 57 source files (confirmed
  resolution to this worktree's own `src`, not the main checkout's, by triggering an import error
  from this tree's own file path). `pytest`: **1747 passed, 4 xfailed** — matches the claimed
  baseline+new-tests count exactly.
- Independently reverted the `test_report_speaks_a_persisted_group_as_one_counted_answer` fixture
  correction (`classification_level=3` → `2`) and reran just that test: it goes red exactly as
  claimed (`"Three armor..."` vs `"Three BMP-2..."`), restored, confirmed `git diff` clean
  afterward. The fixture correction is load-bearing, not cosmetic.
- Independently confirmed, by reading `perception/naked_eye_source.py:_classification_for_tier`
  and `perception/hybrid_source.py:284`, that no real producer ever pairs a type-shaped raw string
  with `classification_level=2` — `hires` emits a type string at level 3 (falling back to
  `op_class` at level 2, never a type string, on a reporting-name miss), `medres` emits `op_class`
  at level 2, and the scope channel hardcodes level 3. The corrected fixture pairing is reachable;
  the original was not.
- Independently reproduced the `OP_GROUPSOMETHING` finding from source, not from the implementer's
  account: `_group_composition_clause([{"classification":{"value":"OP_GROUPSOMETHING","level":
  "class"}}]*2)` → `"two contacts"`, and mixed with a differentiated member → `"truck and
  something"`. Confirmed `_unit_type_display`/`render_contact_report`'s single-contact path is
  untouched and still resolves this value to `"group"` via `_OP_CLASS_DISPLAY`.
- Grepped `group_view.py` for `last_class_raw`/`describe_contact`/`profile_for` and for raw
  `.confidence` reads: every hit is in docstring prose explaining what the module *doesn't* do;
  no occurrence in executable code. Grepped `groups.py`'s diff: only test 4's two set-comprehension
  lines changed, no `Group` dataclass field added, `composition`/`air_defence_composition`
  untouched.
- Confirmed `callout_observable` is the remembered test (`last_observable_sim` +
  `CALLOUT_OBSERVABILITY_GRACE_S`), not a raw mask read, and that `tools.py`'s new gate uses `any`
  over members, matching `callouts.py`'s own existing group loop (no new predicate written).
- Confirmed `group_view.py` imports nothing from `perception/` — no FOV/mask state crosses in, per
  Decision 6.

### Required Fixes

- **`body-layer/docs/STRUCTURE.md`'s `group_view.py` entry is now stale and asserts something
  false about the merged state.** It was written at commit `c60c6cb`, *before* Stage 3 landed
  (`fc87237`, the branch tip), and still reads "Stages 1-2" and "**Stage 3 ... was attempted and
  reverted**" with a description of the reverted-attempt's divergence. Stage 3 is in fact merged
  on this branch — `speech._group_composition_clause` now calls `collapse_members`, confirmed by
  reading the diff and running it. STRUCTURE.md is the file `body-layer/CLAUDE.md` tells every
  future agent to read before touching a module ("you are expected to read the entry for any
  module before modifying it") — an agent reading it before touching `speech.py` or `group_view.py`
  would be told Stage 3 doesn't exist and would be missing the real, documented behaviour change
  (the `OP_GROUPSOMETHING` wording divergence, the canonical-sort-order change) that *is* in
  `implementation.md`'s later "Stage 3 — landed (second pass)" section but never made it back into
  STRUCTURE.md. This is exactly the kind of staleness this project's own `CLAUDE.md` repeatedly
  calls out as a silent, compounding failure mode. Needs its STRUCTURE.md entry updated to describe
  the landed Stage 3 (the fixture-correction finding, the canonical-sort behaviour change, the
  `OP_GROUPSOMETHING` wording note) before merge — small, bounded, no code change.

- **The `OP_GROUPSOMETHING`-in-a-group's-composition-clause wording change has no test.** Verified
  reachable and real (see above): `"group"` → `"something"`/`"N contacts"` for this one value,
  specifically inside `_group_composition_clause`, specifically when mixed with other classified
  members. `_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"] = "group"` exists *because* a live sortie
  (2026-09-22) proved this value reachable and penalised the project for not having a word for it
  — this project's CLAUDE.md states the standing lesson plainly: *"untested wording is exactly how
  this value was wrongly assumed unreachable twice."* Leaving a third reachable wording path for
  the same value untested repeats the pattern this plan's own brief calls out. **My verdict on the
  three-way question:** this is **(a) acceptable as a deliberate, narrow behaviour change — not a
  defect requiring a code fix in this stage** — because conflating "classified to the catch-all
  class bucket" with "no class claim at all" inside a composition clause that is otherwise naming
  real sub-classes is a defensible reading (the implementer's own "'Group, and a group' is
  nonsense" point holds for the differentiated case), and because fixing it properly means deciding
  whether `group_view._subclass_label` should distinguish "resolved to the default bucket" from "no
  claim resolves," which touches Stage 1 code merged earlier in this same branch and is rightly the
  kind of question Decision 7's "nothing richer invented without the attention-tier milestone"
  posture defers rather than a Stage 3 scope item. I agree with the implementer's scoping judgment.
  **But it must not land untested.** Add one test — in `test_speech.py`, alongside the other
  `_group_composition_clause` tests — pinning the current behaviour (`"truck and something"` for a
  mixed `OP_TRUCK`/`OP_GROUPSOMETHING` roster, or equivalent), with a comment naming this review and
  linking to `implementation.md`'s own "Notable discovery not caught by any test" section, so the
  next person who touches `_subclass_label` or `_OP_CLASS_DISPLAY` sees a failing test rather than
  silently changing pilot-facing wording a third time. This is a few lines, not a design change.

### Optional Refinements

- `_type_children`'s final sort key is `(int(node.level), node.label)`, which sorts a `SUBCLASS`
  remainder leaf before its `TYPE` siblings regardless of label (e.g. the undifferentiated
  "OP_ARMORED" remainder always precedes a "T-72B" type leaf, never the reverse, even though
  "OP_ARMORED" < "T-72B" alphabetically would put it there anyway in this case — the point is the
  sort key doesn't *need* alphabetical agreement to be canonical, it only needs to be a
  deterministic function of content, which it is). This is correct and canonical as implemented
  (verified by the order-independence test and by my own reading of the sort key), but the
  deliberate "level before label" ordering across sibling levels isn't called out in the
  function's own docstring the way the label-based sort at every other level is. A one-line
  comment would save the next reader re-deriving why a `SUBCLASS` sibling sorts ahead of `TYPE`
  siblings. Cosmetic.
- `implementation.md`'s mutation table restores each mutated file to a specific sha; I did not
  re-verify every one of those shas, only re-ran the two mutations most load-bearing to the
  reviewer brief (fixture correction, `OP_GROUPSOMETHING`) myself from source. The `_subclass_label`
  level-gate mutation and the `tools.py` `if any_observable: → if True:` mutation are plausible on
  reading (the code paths they describe exist exactly where claimed) but were not independently
  re-run by me. Not required — these are narrower, lower-risk claims than the two I did re-run —
  but noting the boundary of my own verification honestly.

### Verdict

**APPROVED WITH MINOR FIXES.** Both required fixes are small (one doc update, one new test) and
neither touches the plan's scope, the invariants, or any merged behaviour. Everything else —
signature, home, source field/resolver, `CONTACT`-not-`UNIT` naming, cardinality interval (never
`len(members)`), canonical sorting at every level, the FOV/mask cost-pruning-not-content-filtering
gate (any-not-all, remembered-not-raw-mask), the `air_defence_composition`/`composition`
survival, the `_subclass_label` level-gate fix, Stage 4's shared table, and the fixture
corrections — checked out clean against the plan, the user's verbatim direction, and my own
independent reruns, not just the implementer's account of them.

### Review Confidence

Full read of every changed file and every commit in the range, plus my own independent
verification runs (format/lint/type/test, two targeted mutations from source, two reachability
greps) rather than relying solely on `implementation.md`'s own tables. The one place I did not
re-verify beyond reading is the full shas-before/shas-after claim for the `_subclass_label` and
`tools.py` mutations in `implementation.md`'s first mutation table — noted above as an optional
item, not a gap in the verdict, since the claims are consistent with the code I did read in full
and I independently re-ran the two mutations the reviewer brief itself flagged as highest-risk.

---

### Confirmation pass — both required fixes closed (`ed50840`)

Scope: confirming only the two required fixes above, against `ed50840a2b43ef117773f4624951eb9a0c6c960b`
(three files: `body-layer/docs/STRUCTURE.md`, `body-layer/tests/test_speech.py`,
`plans/group-collapse/implementation.md`). Not a second full review.

Worktree HEAD (`f25c57c`) was a strict ancestor of the named tip on a clean tree; fast-forwarded,
confirmed by `git rev-parse HEAD` after.

**Fix 1 — `STRUCTURE.md`.** The entry now reads "Stages 1-4" and describes the landed state
(fixture-correction finding, canonical sorting of the push-path composition line, the
`OP_GROUPSOMETHING` wording divergence) in the same register as the surrounding entries — prose
explaining *why*, not a changelog. No longer asserts Stage 3 was reverted; grepped the rest of the
file and found no other stale reference to it.

**Fix 2 — the pinning test.** `test_group_composition_clause_folds_op_groupsomething_into_undifferentiated`
covers both required shapes (pure `OP_GROUPSOMETHING` pair → `"two contacts"`; mixed with a
differentiated member → `"truck and something"`) plus the single-contact asymmetry
(`_unit_type_display("OP_GROUPSOMETHING", "class") == "group"`), matching exactly what the change
request asked for.

**Verified by mutation myself, not from the implementer's table.** Confirmed `shasum
src/belief/group_view.py` matched the implementation note's stated pre-mutation value
(`c03857c4f6eea31fd309e133cec8df732508f809`) before touching anything. Changed `_subclass_label`'s
fallback from `"unknown"` to `"OP_ARMORED"` and reran the new test: it went red with
`assert 'two armor' == 'two contacts'` — the exact failure reported. Restored the line and
confirmed the checksum was identical and `git status`/`git diff` showed no residual change. The
pin is real: it fails for the stated reason when the behaviour it protects is removed.

**No behaviour changed.** `git diff ed50840~1 ed50840 --name-only` lists exactly the three files
above; no `src/` file appears in the diff. Confirmed independently via `git diff 7f03e73
ed50840 --stat -- body-layer/src/` (empty).

**No existing assertion's expected value was altered.** The only change to `test_speech.py` is a
pure addition (one new test function appended after the existing
`test_group_composition_clause_counts_members_exactly`); no existing `assert` line in that file
was touched by this commit.

**Checks run myself, inside `body-layer/`** (worktree has no `.venv`; borrowed the main
checkout's binaries by absolute path, cwd kept in the worktree):
`ruff format --check` pass, `ruff check` pass, `mypy --strict` pass (57 source files), `pytest`
**1748 passed, 4 xfailed** — matches the expected count exactly (1747 + the one new pinning test).

### Verdict (confirmation pass)

**APPROVED.**

### Review Confidence (confirmation pass)

Full read of the one commit in scope, plus independent mutation verification (not taken on the
implementer's table) and independent diffs confirming no behaviour change and no altered
assertions. This is a narrow confirmation of two specific fixes, not a re-review of the whole
feature — the original pass's "Review Confidence" note above still describes the depth of that
broader read.
