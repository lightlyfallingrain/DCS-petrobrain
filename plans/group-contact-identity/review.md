# Review — BL-12 Stage 0 (`bae8963..7b2e3b4`)

Reviewed 2026-10-11 against `plans/group-contact-identity/plan.md`'s 2026-10-11 amendment (A2, A6,
Q-A/Q-B), `plans/group-contact-identity/implementation.md`, `body-layer/CLAUDE.md`'s Invariants,
`body-layer/ROADMAP/BL-12.md` / `BL-B48.md` / `BL-B51.md`, and
`plans/post-review-fixes/explore-notes.md` §2.

**Base check.** The worktree's HEAD was `8b7686f` (`main`), **diverged** from the named tip — two
unique commits (`abc3f8a`, `8b7686f`, main's `agent-sha-gate` fix), so `--ff-only` was not
available. Reported rather than worked around, then reviewed from a detached checkout of
`7b2e3b4235486e38010f648ec9fbe972f3d93ea9` in this worktree (both unique commits are on `main` and
reachable; nothing could be lost). HEAD contains `b9632e4`, **not** the pre-amend `8497771`.

---

## Verdict

**APPROVED WITH ONE REQUIRED FIX** (documentation only — see Required fix 1). The code is correctly
scoped, the mechanism/calibration split is real, and every behavioural claim in
`implementation.md` reproduced. The required fix is a paragraph in one docstring, not a change to
any number or any code path.

---

## Checks, re-run (not taken from the log)

Root checkout's venv binaries, cwd inside each subproject (the worktree has no `.venv`);
`pyproject.toml`'s `pythonpath = ["src", "../world-model/src"]` resolves against this worktree's own
rootdir, so the code under test is the tip's.

| check | result |
|---|---|
| `body-layer` `ruff format --check src tests` | 118 files already formatted |
| `body-layer` `ruff check .` | All checks passed |
| `body-layer` `mypy src` (`--strict`, CWD inside subproject) | Success, 54 source files |
| `body-layer` `pytest` | **1643 passed / 4 xfailed** |
| `audio-adapter` `ruff check .` / `mypy src` / `pytest` | passed / 15 files / **255 passed, 1 skipped** |

**The +11 delta is accounted for exactly**, derived from the diff rather than from the report:
`git diff bae8963 7b2e3b4 -- body-layer/tests` adds **13** `def test_` and removes **2**
(`test_infantry_eager_policy_bridges_…` renamed, `test_air_defence_classes_cover_…` moved
`test_crew_console.py` → `test_classification.py`). 13 − 2 = 11.

---

## Claim-by-claim verification

### 1. The measured behaviour table — reproduced, all five rows, at three code states

Ran `_cluster_contacts` against the real profiles and real constants with `_pair_backstop_m` swapped
for three variants (original `any`-EAGER + `inf`; 0a `both`-EAGER + `inf`; the tip). Printed each
pair's backstop, each pair's `pair_threshold`, the unions and the cluster extents.

| scene | relative | original | after 0a | tip (0b) |
|---|---|---|---|---|
| armor@1 km + truck@3 km | 6,000 | 0 groups (130 m) | 0 groups | 0 groups |
| armor@1 km + infantry@7 km | 18,000 | **1 group, extent 6,000 m** | **0** (88 m) | 0 |
| armor + truck + infantry | 6,000 | **1 group of 3, 6,000 m** | **0** (130/88/78 m) | 0 |
| three infantry @30 m | 90 | 1 group, 60 m | 1 group, 60 m | 1 group, 60 m |
| two infantry @5 km | 15,000 | 1 group, 5,000 m | 1 group, 5,000 m | **0** (500 m) |

**Bit-identical, confirmed as thresholds and not only as the union**: in the three-infantry scene
every pair's `pair_threshold` is `90.0` at all three states (the relative test binds; the backstop is
never read), and the union is `{I1, I2, I3}` throughout. The claim is exact.

The amendment's second, unrecorded fault also reproduces: at n = 2 `relative_threshold = 3 × d ≥ d`
always, so the relative test is vacuous and the absolute backstop is the only gate — which is why
row 5 needed 0b.

### 2. Mechanism/calibration split — holds, by reading both diffs

- `1ec68fb` (`body-layer/src/belief/groups.py:462`): the only non-comment change is
  `if CohesionBackstop.EAGER in (backstop_i, backstop_j)` →
  `if backstop_i is CohesionBackstop.EAGER and backstop_j is CohesionBackstop.EAGER`. **No number
  changes anywhere in the commit.**
- `68598f7`: adds `GROUP_REPORTING_EAGER_COHESION_CAP_M = 500.0` (`groups.py:338`) and changes one
  `return math.inf` to `return GROUP_REPORTING_EAGER_COHESION_CAP_M` (`groups.py:462`). **No
  predicate, branch or control flow changes.**

Filtering the whole `bae8963..7b2e3b4` source diff down to non-comment lines leaves exactly: the
predicate, the return value, the new constant, the moved frozenset, and three import/usage
repoints. **No scope drift at all.**

### 3. The cap's derivation

**The rounding claim is correct, and it is correct at the boundary too.** Run against
`belief.speech._format_range_km`: 2,749 → `"2.5 kilometres"`; 2,750 / 3,000 / 3,249 / **3,250** →
`"3 kilometres"`; 3,251 → `"3.5 kilometres"`. The bucket `[2750, 3250]` is 500 m wide **inclusive**,
so the docstring's claim — *a group wider than 500 m contains members the renderer would bucket
differently* — is exactly true, and 500 m is the **largest** width with that property. The converse
is not claimed and would be false (a 500 m-wide pair can straddle two buckets), and the docstring
does not claim it. Sound.

Cross-checks re-derived: `2·tan(15°) = 0.5359`, so `500 / 0.5359 = 933.0 m` — correct.
`500 / 1.8 = 277.8` unit widths — correct. 260 m pair → 1.92× margin — correct.

**The inference from a spoken-range bucket to a *pair* cap is sound as far as it goes. What it does
not survive is the believed-vs-true position distinction — Required fix 1 below.**

### 4. Pair, not cluster — I agree with the call, and I would not add a cluster-extent rule now

`test_the_eager_cap_still_chains_a_long_infantry_line` pins it: four infantry at 400 m spacing span
1,200 m and still cohere, because every *neighbour* gap is inside the cap. Verified.

**I agree this is the right call, and the argument is stronger than "out of scope".** D7's own target
sentence is *"that column, now 2 o'clock, three kilometres, still moving north on the road"* — a
column. A hard cluster-extent cap would reject the very object D7 exists to describe, and
`_cluster_contacts`' convoy property is load-bearing for it. Capping the link and leaving the span
free is the only one of the two that keeps a convoy a convoy. Pinning it with a test, rather than
leaving a reader to rediscover it, is the right disposal.

**But one plan statement is now wrong in a way that matters for Stage 4.** A6 makes the speech-time
extent guard conditional: *"If Q-A declines 0b, Stage 4 needs an extent guard at speech time
instead."* Q-A/Q-B were **accepted**, and chaining means a bounded-link group can still span 1.2 km,
which is 2.4 spoken range buckets. **So the speech-time extent guard is needed regardless of 0b, not
instead of it.** Not a defect in this diff — flagged so Stage 1/4 scoping does not inherit the
conditional. See Observation 1.

### 5. The two caps are genuinely isolated — mutation-verified

`test_the_eager_cap_and_the_installation_cap_do_not_move_together` monkeypatches each module
attribute in turn and asserts the other path held; `_pair_backstop_m` reads both globals at call
time, so the patch reaches the code. **Mutated to check the test is not decorative**: changed the
eager branch to `return GROUP_REPORTING_INSTALLATION_COHESION_CAP_M` →
`assert 500.0 == 1234.0`, that one test red, the other 30 in the file green. Restored by `shasum`
(`f9915f0968194a4b1e7515823a7e27da52e4c378`). It is the only test in the suite that catches that
mutation, which is correct given the two numbers are equal — a comparison of the values could not.

### 6. `BL-B51` — mutation re-run, and the decomposition re-counted

- **Drift guard re-run from scratch**: injected
  `("sa-99 fakeinject", ObjectTypeProfile(size_m=9.0, op_class="OP_XLRSAM"))` into
  `_REPORTING_NAME_KEYWORD_PROFILES` (`body-layer/src/perception/object_model.py:455`).
  `test_classification.py::test_air_defence_classes_cover_every_air_defence_class_in_the_object_model`
  went **red** as claimed (two `test_speech.py` spoken-vocabulary tests also fired — pre-existing
  coverage, a bonus). Restored by `shasum` (`17eb80706052dd3814cd56ad435a6fce3f9b5141`, which also
  matches the sha `implementation.md` recorded — independent corroboration that the file was restored
  cleanly after the implementer's own run).
- **Removing `crew_console`'s copy changed no behaviour**: the retired local held
  `{OP_SPAAG, OP_ZU23, OP_SRSAM, OP_MRSAM, OP_LRSAM}`, set-equal to the shared constant, and the only
  code change is `parent_class_of(value) in _AIR_DEFENCE_OP_CLASSES` →
  `… in AIR_DEFENSE_OP_CLASSES` (`crew_console.py:1357`). Grep over `src`, `tests`, `tools` finds
  **no remaining code copy** of the five-value set outside `classification.py:217` and the `==`
  assertion inside the companion test.
- **The replacement is not weaker than what it replaced in that file**: the `<=` guard did not
  disappear, it *moved* verbatim to `test_classification.py` and is mutation-proven red there. The
  new `test_watch_nearest_air_defence_resolves_through_the_one_shared_set` covers a different
  property (the command's verdict ≡ the shared set's membership, asserted across the boundary in both
  directions). Net coverage up.
- **Removing `test_groups.py`'s `== frozenset({…})` pin rather than moving it is right**, and for the
  reason given: a literal pin cannot notice `object_model` growing, which is the only direction that
  loses coverage. The companion test asserts that property as a property, with the naming predicate
  written out again so a change to the real predicate cannot make both tests agree about nothing.
  Correct construction.
- **The 9-distinct-`op_class` decomposition re-run**, since a count in prose is this project's most
  frequent sole defect: `_KEYWORD_PROFILES` 70 entries / **9** classes; `_REPORTING_NAME_KEYWORD_
  PROFILES` 61 entries / **6**; union **9** (`OP_ARMORED, OP_INFANTRY, OP_LRSAM, OP_MRSAM, OP_SHIP,
  OP_SPAAG, OP_SRSAM, OP_TRUCK, OP_ZU23`); `DEFAULT_OP_CLASS = OP_GROUPSOMETHING` is **not** in the
  union, so 10 reachable. **Every figure in `eyesight_view.py:77-87`'s correction is right**, and the
  five values are exactly the air-defence subset of the 9.

---

## The test-impact finding, judged as an escalation

**The escalation was correct to raise and the amendment's one-entry list was a real miss.** Three
tests changed; two in files the amendment never names.

### `test_crew_console.py` leak test — the repair is real, not cosmetic

**Verified the new fixture has no eager latitude, by profile resolution rather than by reading the
docstring.** `_cohering_contacts_across_a_band_boundary`
(`body-layer/tests/test_crew_console.py:4169`) uses class-level raws, which resolve as:
`OP_ARMORED` → `OP_GROUPSOMETHING` (so `_representative_size_m` substitutes the 7.0 m unknown size,
`STRICT`), `OP_TRUCK` → `OP_TRUCK` 6.0 m `STRICT`, `OP_INFANTRY` → `OP_INFANTRY` 1.8 m `EAGER`.
Pairs: armor↔truck 100 m against 130 m ✓; truck↔infantry 70 m against 78 m ✓; armor↔infantry 170 m
against 88 m ✗. **The fixture's docstring numbers (130, 78) are exactly right**, and the single
infantry member participates only through a *mixed* pair, so the eager branch is never entered at
all. **There is no both-EAGER pair in the fixture.**

Independently corroborated by mutation: under the `or` revert *and* under `cap = math.inf`, **no
`test_crew_console.py` test failed** — the fixture has zero dependence on either.

The repaired test is also stronger than described: it asserts the group exists, that it has 3
members, that the pull answer names only the armour, **and** that `render_group_full_disclosure`
still names all three — so the fixture is proven leak-*capable*, not merely group-forming. Good
work.

### `test_groups.py`'s bridging test — inverted, and I agree

**I agree with both the inversion and with flagging it.** The test asserted a behaviour the user's
decision 1 declares wrong; leaving it would have made the suite assert against the decision.
Inverting it *is* implementing the decision, and `AGENTS.md`'s "existing tests must be rewritten
rather than extended" is satisfied by raising it rather than by not doing it.

**On "the new rule or merely the new output":** the inverted test itself asserts output
(`store.groups == []`). **The rule is asserted** by
`test_a_mixed_infantry_pair_falls_through_exactly_as_a_mixed_installation_pair_does`
(`tests/test_groups.py:715`), which computes the ordinary unit-widths value from the sizes and asserts
a mixed eager pair equals it — so retuning `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` cannot make it
lie, and it asserts the *equivalence with rule 1* that the precedent argument rests on. Between the
two, the rule is covered. Confirmed by mutation: the `or` revert turns both red.

One honest note on the counterfactual record: `implementation.md`'s Stage 0a counterfactual says
**four** tests go red on the `or` revert. At the tip, **three** do
(`test_groups.py::test_infantry_no_longer_bridges_…`, the mixed-pair equivalence, and
`test_callouts.py::test_2c_transcript_fixture_…`) — because `test_armor_and_distant_infantry_do_not_
merge` and `test_infantry_does_not_bridge_armor_and_truck_at_sortie_scale` are now caught by the 0b
cap instead of by the predicate. The claim is true of `1ec68fb`, which is where it is scoped.
Nothing to fix; recorded so a later reader does not read it as a tip-state claim.

### `test_callouts.py`'s 2C transcript — the added assertion is real

`sorted(sorted(g.member_contact_ids) for g in store.groups) == [["CONTACT_1","CONTACT_3"],
["CONTACT_6","CONTACT_7"]]` (`tests/test_callouts.py:1114`). It is specific, it is adjacent to the
sentences, and it does what the comment claims: the four-line count alone would pass over a single
five-member group. Confirmed red under the `or` mutation. The docstring's forward-pointer is also
true — the already-reported fold it says is "no longer exercised here" **is** directly pinned in
`tests/test_speech.py:2395-2505`.

---

## What must not have regressed — checked

- **BL-13's pull path is untouched.** `crew_console.py`'s diff is the import line, the retired
  constant's comment block, one docstring line pair and one expression inside `_believed_air_defence`.
  `render_report_summary`, `_report_scope`, the freshness marker and the word budget appear nowhere in
  the diff.
- **`speech.py`'s 8 lines are**: `AIR_DEFENSE_OP_CLASSES` added to the `belief.classification` import,
  removed from the `belief.groups` import (4 lines of churn), and two docstring module paths
  (`_is_air_defence`, `render_group_disclosure` branch 4). **`_is_air_defence`'s body is byte-identical**
  — still `return _summary_op_class(facts) in AIR_DEFENSE_OP_CLASSES`, resolving through the lattice.
  `BL-B47`'s mutation-verified widening is un-weakened.
- **`decay.py` untouched**; not in the diff.
- **No Stage 1 work.** No `remembered_groups`, no `group_matches`, no group-level matching, no trace
  line. The only `trace`-shaped hit in the source diff is `eyesight_view.py`'s pre-existing
  `DetectionTrace` import moving with the import sort. Stage 0 touched no site the trace line will
  want, so it has not been made harder.
- **`eyesight_view.py`'s 28 lines** are the retired constant's replacement comment, the import, and
  two `in` expressions. Correction verified above.
- **No DCS writes, no `world-model/data/` staging, no debug code, no `TODO`s**, nothing
  omniscience-shaped (the clustering still reads only `Contact.position`, the believed estimate).
- **Agent memory is at the repo-root path** (`.claude/agent-memory/implementer/…`), and `MEMORY.md`
  gained one appended line. Correct on both counts.

---

## Required fix

### 1. `GROUP_REPORTING_EAGER_COHESION_CAP_M`'s derivation is calibrated on *true* spacing but applied to *believed* spacing — record it

**File:** `body-layer/src/belief/groups.py`, the `GROUP_REPORTING_EAGER_COHESION_CAP_M` docstring
block (`:275-338`), specifically the cross-check table and the "What would falsify it" paragraph.
**Also** `plans/group-contact-identity/implementation.md` §"Where the number came from".

**I am not asking for the number to change** — decision 2 reserves that for the user's judgement in
flight, and 500 m is a defensible first value. The required fix is that the *recorded reasoning omits
the dominant error term*, which is what makes the flight judgement interpretable or not.

`_cluster_contacts` compares `contact.position.x/.z` — the **fused belief**, explicitly *not*
uncertainty-budgeted (its own docstring). Every one of the four cross-checks is a **ground-truth**
figure: the p95 342 m nearest-neighbour and median 236 m cluster separation are reduced from the
belief-truth log *deduplicated by `object_id`* (`plans/post-review-fixes/explore-notes.md` §2), and
the 260 m pair is a synthetic fixture with zero-covariance positions.

The scale of the term left out, from `perception/estimation.py`:
`sigma_down_m = RANGE_FRACTIONAL_SIGMA (0.17) × range`. For two independently observed, genuinely
co-located infantry contacts, the believed separation has `σ_Δ ≈ 0.17·R·√2 = 0.24·R`:

| range | `σ_Δ` | P(believed separation > 500 m), single look |
|---|---|---|
| 2 km | 480 m | ~30 % |
| 3 km | 720 m | ~49 % |
| 5 km | 1,200 m | ~68 % |
| 7 km | 1,680 m | ~77 % |

So beyond roughly 2 km a real, tight infantry group can fail the cap **on belief noise alone**,
in the under-merging direction the *"ok to merge infantry too eagerly"* grant exists to avoid — and
at those ranges the clock-hour escape hatch (*"inside a kilometre the pilot can see for himself"*)
does not apply. It is **bounded**: fusion shrinks the error roughly as 1/√looks, so this is a
several-second delay in grouping rather than a permanent failure, and `_cluster_contacts`' own
docstring already accepts that delay class as *"a human copilot needing a moment"*. That is why this
is a documentation fix and not a behavioural one.

**What to add:** one paragraph naming belief-position noise as the mechanism, the `0.24·R` figure,
the note that all four cross-checks are true-geometry, and a third falsification criterion —
*infantry at range reported individually for several seconds before pairing, where before 0b they
paired immediately*. Without it, the pilot's in-flight observation will be mis-attributed to the
cap's value when the cause is the range.

---

## Observations (optional — not blockers)

1. **A6's speech-time extent guard should become unconditional for Stage 4.** As written it fires
   only *"if Q-A declines 0b"*; Q-A/Q-B were accepted and chaining still permits a 1.2 km span,
   which is 2.4 spoken range buckets. Worth one line in the plan before Stage 1 starts, so Stage 4
   does not inherit the conditional. (Also the natural consumer of the trace line's `extent` field,
   which A4 already requires.)
2. **A fourth hand-enumerated copy of the same vocabulary survives, unguarded**:
   `belief/crew_console.py:291` `_FOLLOW_DESCRIPTOR_OP_CLASSES` whose `"sam"` ∪ `"aaa"` entries are
   set-equal to `AIR_DEFENSE_OP_CLASSES`. `BL-B51` named three copies and consolidated three, so
   this is outside its scope — but it is the same drift class, and the new `<=` guard does not cover
   it: an `OP_XLRSAM` would be caught in `classification.py` and silently missed by `follow SAM`. A
   one-line `AIR_DEFENSE_OP_CLASSES <= sam | aaa` assertion in `test_crew_console.py` would close it;
   better as a new `BL-B` item than as a Stage 0 addition.
3. **One docstring overclaim**,
   `tests/test_crew_console.py::test_watch_nearest_air_defence_resolves_through_the_one_shared_set`:
   *"must read the shared set rather than a local copy"* is not what the test can distinguish — an
   identical local copy would pass it too. What it *does* assert (verdict ≡ membership across the
   set's boundary, both directions) is the right and stronger property; only the sentence is
   imprecise. Same defect class the implementer self-reported as item 4.
4. **0b is nearer mechanism than calibration on a strict reading** — it introduces a gate that did
   not previously exist at n = 2, rather than retuning one. The Architect's staging pre-authorised
   the framing (*"0b (calibration, gated on Q-A) a finite eager cap replacing `math.inf`"*), the
   control flow is untouched, and the commit boundary still gives each behaviour shift one
   attributable cause — so the invariant's purpose is served. Noted only so the precedent is not
   read as "changing a return value is always calibration".

---

## The two deferred items — I agree with both

- **`body-layer/docs/STRUCTURE.md` has no `src/belief/groups.py` entry.** **Verified**: grep over that
  file for `belief.groups`, `GroupStore`, `_pair_backstop`, `CohesionBackstop` and
  `AIR_DEFENSE_OP_CLASSES` returns nothing; the only `groups` hits are the word in two unrelated
  `crew_console`/`speech` entries. **Correctly deferred.** Writing the first entry for a ~180-line
  module docstring is its own piece of work, and it changes what "read the module's history before
  judging it" means here: the module's *why* is in the docstring, which is where this change put its
  reasoning — the right place given no entry exists. Worth a `BL-W`/`BL-B` item rather than being
  bolted onto Stage 0.
- **`BL-B48`/`BL-B51` left `#status/open`.** **Verified** — all three entries (`BL-12.md` too) still
  carry `#status/open`. **Correctly deferred**: closing them is a merge-time roadmap update, and
  `BL-12` itself is not done. Flag for whoever merges: both should close in the merge commit's
  roadmap edit, with `BL-B48` noting the second fault (the vacuous relative test at n = 2) that
  `BL-B51`'s sibling fix closed.

---

## Review confidence

**Full read**, with reproduction rather than reading where a claim was load-bearing:

- All three source commits' diffs read line by line; the whole `bae8963..7b2e3b4` source diff
  filtered to non-comment lines to bound scope drift.
- The five-row behaviour table reproduced at three code states through the real profiles and real
  constants, printing per-pair backstops, thresholds, unions and extents.
- `_format_range_km` run at eleven inputs, including both bucket boundaries.
- **Four mutations run and restored by `shasum`**: `or`-revert of the predicate; `cap = math.inf`;
  eager branch returning the installation constant; `OP_XLRSAM` injected into
  `_REPORTING_NAME_KEYWORD_PROFILES`.
- The new `crew_console` fixture's "no eager latitude" claim checked by resolving each member's
  profile and each pair's backstop, not by reading the docstring.
- The 9-`op_class` decomposition re-counted from the tables.
- Both subprojects' full check suites re-run; the +11 test delta derived from the diff.

Nothing was spot-checked.
