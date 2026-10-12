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

---
---

# Round 2 — review of the fix round (`a673512`)

**Appended 2026-10-11. Round 1 above is unchanged.** This round reviews the single commit at
`feature/bl12-group-contact-identity`'s tip, *"Record that the eager cohesion cap is calibrated on
true spacing"* — round 1's one required fix, its two optional observations, and the A6 plan
amendment.

## Verdict

**APPROVED.** No required fixes. One substantive optional refinement (§7) and two cosmetic ones.

The required fix is answered, and answered better than it was asked: **two of the figures in round 1
were wrong, and this round corrected them rather than transcribing them.** My *"all four
cross-checks are ground truth"* was a miscount of a five-bullet block, and the 2–7 km tabulation
described a regime no infantry contact can occupy. Both corrections are verified below.

## Provenance of this review

- `git rev-parse HEAD` on dispatch: **`8b7686fc`** — `main`, **diverged** from the branch, not
  behind it. Merge base `6daeec6`; `main` carries two `agent-sha-gate` commits the branch does not,
  and the branch carries eleven `main` does not. Reported rather than worked around, and **no
  `--ff-only` was attempted** (it was unavailable by definition).
- Verified against a **detached checkout of `a673512`** (`git checkout --detach`), tree clean. Import
  resolution proved to the worktree's own tree, not the root checkout's:
  `belief.groups` resolves to
  `/Users/sg/Code/DCS-petrobrain/.claude/worktrees/agent-a1ae3f9caff590a4a/body-layer/src/belief/groups.py`.
- **The cherry-pick was verified, not assumed.** `git show 0f1bd9b --format=""` and
  `git show a673512 --format=""` are **byte-identical** patches. The tree difference between the two
  commits is exactly `BL-B56.md` + the backlog index — the orchestrator's own entry — so the
  implementer's content came across whole.

## Checks — re-run, exactly at baseline

| subproject | format | lint | mypy | tests |
|---|---|---|---|---|
| body-layer | 118 files already formatted | pass | no issues, 54 files | **1643 passed, 4 xfailed** |
| audio-adapter | — | pass | no issues, 15 files | **255 passed, 1 skipped** |

Both exactly the stated baseline.

## Claim-by-claim verification

### 1. "Documentation only" — re-established structurally, and strictly stronger than claimed

I did not credit the test count, which is the implementer's own point. Instead I extracted both
touched `.py` files at `e20ea2f` and `a673512` with `git archive` and compared their ASTs with
**every docstring node removed entirely** — stronger than the implementer's "docstring constants
blanked", because a changed numeric constant anywhere would survive the strip and show up.

- `body-layer/src/belief/groups.py` → **AST_EQUAL**
- `body-layer/tests/test_crew_console.py` → **AST_EQUAL**
- `GROUP_REPORTING_EAGER_COHESION_CAP_M: Final[float] = 500.0` on **both** sides.

One refinement to the implementer's framing: in `groups.py` the new prose is `#:` *comments*, which
never enter the AST at all, so AST equality there proves no code moved but was never at risk from
the prose. In `test_crew_console.py` it is a real docstring, and the strip is what makes the
comparison meaningful. The conclusion holds either way: **prose only, no number, no code path.**

The commit touches six files, and the two `.py` files are the only source/test files among them.

### 2a. The five-bullet count and classification — correct, and round 1 was wrong

Counted from `groups.py:293-318`. Five bullets:

| bullet | spacing? | provenance |
|---|---|---|
| clock hour, `2·tan(15°)·R` = 0.536 R | **no** | a conversion of the 500 m |
| the 260 m infantry pair | yes | fixture, positions literal |
| nearest-neighbour p95 **342 m** | yes | reduced from the sortie log |
| cluster-to-cluster median **236 m** | yes | ibid. |
| unit-widths currency, 500 / 1.8 = 277.8 | **no** | a conversion of the 500 m |

**Three spacings, two conversions, five bullets.** The implementer's count and classification are
right and my round-1 *"every one of the four cross-checks"* was a miscount — it counted the block as
four and treated all four as measurements. The correction is recorded in the docstring in the form a
later reader can check.

Sub-claims both verified:
- `plans/post-review-fixes/explore-notes.md:146` does say *"deduplicated by `object_id`"*, with
  p95 342 m at `:155` and median 236 m at `:171`.
- `tests/test_groups.py:401-402` writes the pair as `_contact("C1", 0.0, 0.0, …)` and
  `_contact("C2", 260.0, 0.0, …)` — **literals, no noise applied.** Proved, not read off the
  docstring.

### 2b. `σ_Δ` — 338 m, not 336 m; the brief's figure was 1,400 rounded first

Re-derived from the real constant rather than from the docstring:

- `perception.estimation.RANGE_FRACTIONAL_SIGMA = 0.17`; `0.17 × √2 = 0.240416`.
- × **1406.25 m** → **338.1 m** ✔ (× 1,400 m → 336.6 m — which is exactly where the brief's
  *"≤ ~336 m"* came from: the ceiling rounded to 1,400 before multiplying).
- × **3403.1 m** → **818.2 m** ✔

Both docstring figures are right and both of the brief's corrections to itself are confirmed.

### 3. The four infantry presence ceilings — re-run through `tier_ranges`, all four match

Run against the real constants with `cwd` inside the worktree's `body-layer/`. Note the keyword is
`group_salient`, not `group_admitted`:

```
unaided   group_salient=False -> presence=  600.00
unaided   group_salient=True  -> presence= 1406.25
binocular group_salient=False -> presence= 1452.00
binocular group_salient=True  -> presence= 3403.12
```

Matches 600.0 / 1406.2 / 1452.0 / 3403.1 exactly. `NAKED_EYE_RANGE_CAP_M = 10000.0` **binds at none
of them**, as claimed. Infantry `size_m=1.8` confirmed at `perception/object_model.py:229`.
`vars(optics)` holds exactly two `Optic` instances — `UNAIDED_OPTIC`, `BINOCULAR_OPTIC` — so **the
9K113 really is absent from the code**, which is the whole basis for retiring my 5 km and 7 km rows.

### 4. The killed claim — confirmed dead, and the gap is real

The round's first rewording attributed a no-duplicate-copy property to a companion test. Confirmed
that was correctly abandoned:

- `tests/test_classification.py:304` —
  `test_air_defence_classes_cover_every_air_defence_class_in_the_object_model` asserts
  `air_defence_by_name <= AIR_DEFENSE_OP_CLASSES`. It is an **`object_model` coverage guard**; it
  says nothing about where any consumer reads the set from.
- The actual companion, `:358`
  `test_the_drift_guard_fires_on_a_new_air_defence_class_and_a_pin_would_not`, asserts the
  **`<=`-versus-`==` direction** property. Also not a no-duplicate-copy claim.
- **Proved the negative by grep**, not by the graph: no `is AIR_DEFENSE_OP_CLASSES` identity
  assertion anywhere in `src`/`tests`/`tools` (an identity check is the one cheap thing that *would*
  distinguish the shared set from an identical local copy), and no source-scanning test among the
  nine files that read files at all touches the air-defence vocabulary.

So the revised docstring is accurate: **no test asserts no-duplicate-copy; only `BL-B51`'s grep
did.** See §7 — I think this now wants filing.

### 5. The third falsification criterion — present, correct, and pilot-observable

`groups.py:398-407`. It reads as a non-verdict (*"is **not** a verdict on this number, and must not
be read as one"*), attributes the effect to the range and the raised optic, and says it self-resolves
as fusion tightens. All three are right:

- The arithmetic supports the attribution. σ_Δ exceeds the 500 m cap only beyond R ≈ 2,080 m, and
  infantry cannot be held past 1,406 m unaided — so any sighting of this effect **is** binoculars at
  range, by construction.
- *"before this cap existed they paired immediately"* is true, and for the reason the same block
  already gives: the cap replaced `math.inf`, and at n = 2 the relative test cannot reject any pair,
  so two infantry formed one group at any separation.
- It is observable by ear: individual contact reports, then a pairing a few seconds later.

### 6. The A6 plan amendment — reads as settled, not as a second condition

`plans/group-contact-identity/plan.md:281`. It states the guard is **unconditional, not a fallback**,
says the Q-A/Q-B condition is settled, and gives the reason the guard is needed *with* 0b rather than
instead of it. Verified the cited evidence: `test_the_eager_cap_still_chains_a_long_infantry_line`
exists (`tests/test_groups.py:640`) and does pin four infantry at 400 m spacing — 3 gaps × 400 m =
1,200 m, 2.4 of `_format_range_km`'s 500 m buckets.

The row still opens *"Unchanged, **conditional on Stage 0**"*, but that is Stage 4's dependency on
Stage 0 having shipped, which is a different and still-accurate statement — not a surviving
condition on the guard. It reads as settled.

## What must not have regressed — checked

- **Only six files touched**, two of them `.py`. `belief/groups.py`'s logic is AST-identical (§1);
  `decay.py`, `belief/speech.py` and the BL-13 pull path are **not in the diff at all**, so
  `_is_air_defence` cannot have moved.
- **`crew_console.py:291` is untouched.** Read at the tip: `"sam": frozenset({"OP_SRSAM",
  "OP_MRSAM", "OP_LRSAM"})`, `"aaa": frozenset({"OP_SPAAG", "OP_ZU23"})` — still the fourth copy,
  still set-equal to `AIR_DEFENSE_OP_CLASSES` in union, correctly left for `BL-B56`.
- **No Stage 1 work**: no new files, and nothing matching a trace line.
- `body-layer/STRUCTURE.md` still has **no `groups.py` entry**; `BL-B48`, `BL-B51` and `BL-12` are
  all still `#status/open`. Both correctly deferred to merge.
- Spot-verified four of the implementer's own falsification-table rows: `naked_eye_sigma_m` has one
  definition (`estimation.py:98`, range-only) and one call site (`naked_eye_source.py:949`); exactly
  two `Final[Optic]` declarations; the *"copilot needing a moment"* phrase is really inside
  `_cluster_contacts`' docstring.

## 7. Optional refinements

**1. (Substantive) The "so" clause under the 342 m / 236 m figures is not supported by the fact it
cites, and I could not settle it either way.** The docstring argues the two log figures are ground
truth *because* the log was **deduplicated by `object_id`** — *"keyed to distinct real objects, so
the per-contact scatter this cap actually sees is deduplicated out of them."* Deleting the mechanism
and asking whether the conclusion still holds: **it does not follow.** `BeliefTruthRow`
(`src/belief_truth_log.py:122`) carries **both** `true_x`/`true_z` **and** `believed_x`/`believed_z`,
keyed by `object_id`. Deduplicating *believed* positions by `object_id` would remove duplicate
*contacts* for one object — the churn the explore note names — while leaving each surviving belief's
own error fully intact. The dedup key therefore proves the rows are one-per-object; it does not prove
the positions are truth.

The truth reading is very probably correct, and the explore note's *"nearest-neighbour spacing,
distinct objects"* points that way. But **the field is named nowhere and the reduction script was not
retained** (`plans/post-review-fixes/` holds only `explore-notes.md`), so I could not prove it. The
260 m fixture I *did* prove, which makes the asymmetry visible: one of the three spacings is
demonstrated, two are inferred.

Why it is optional rather than required: the band conclusion is unaffected. Even on the belief
reading, those figures were measured at that sortie's short ranges, where σ_Δ is small, and the
1.4–3.4 km binocular band stands either way. **The fix is one clause** — either name the field
(`true_x`/`true_z`) or hedge the provenance and say the reduction was not kept.

**2. The stated coverage gap should be filed, not only stated.** §4's finding is now written into a
test docstring — *"no test asserts that, only `BL-B51`'s grep over `src`/`tests`/`tools` did"* — and
filed nowhere. A gap recorded only in prose is the lesser version of the exact thing this round did
well everywhere else: making an accepted edge distinguishable from an oversight. It is **live, not
theoretical**: `BL-B56` documents a fourth copy existing right now, and the failure path is
`BL-B47`'s months of silence — re-introduce a local copy, the equivalence test still passes because
the copy is identical that day, then `object_model` grows, the `<=` guard fires on the consolidated
set, someone updates it, and the copy drifts unseen. The cheapest guard is an identity assertion
(`is AIR_DEFENSE_OP_CLASSES`) at each consumer, which is the one thing that distinguishes shared set
from identical copy. **This is pre-existing — `BL-B51` left it, this round did not introduce it** —
which is why it is a backlog entry and not a fix to this commit. *Not filed by me:* the session ends
at this verdict, so it is carried in the handoff below for the next session to mint.

**3. (Cosmetic) Two drifted line numbers in `implementation.md`'s falsification table.** It cites the
*"copilot needing"* phrase at line 567; it is at **570**. And it reports `naked_eye_sigma_m` as
having *"one prose mention"*, which this round's own edit made **two** (`association_over_time.py:167`
and the new `groups.py:380`). Both substantive claims hold; only the coordinates slipped.

**4. (Cosmetic) The cap's comment block has roughly doubled**, from ~56 lines to ~134 for one
constant. I am **not** calling this out as bloat: the content is load-bearing (a quoted user
decision, a mechanism, a band, a do-not-retune instruction) and it matches the convention every
neighbouring constant in this module follows. Worth one note only because `σ_Δ ≈ 0.24·R` now appears
in four places — but three of those are **dated records** (round 1 above, the acceptance document,
and this section) which by this project's own convention do not get swept, leaving `groups.py` and
`BL-B55` as the only two present-tense copies, and `BL-B55` cross-references rather than restates.
**No action.**

## Review confidence

**Full read.** Nothing spot-checked. What was re-established independently rather than credited:

- Both touched files AST-compared across `e20ea2f`→`a673512` with **all** docstrings stripped, from
  two `git archive` extractions — not from the test count.
- The cherry-pick proved content-identical to `0f1bd9b` by byte-comparing the two patches.
- The five-bullet block counted and classified from source.
- `tier_ranges` **run** over both optics × both salience values; all four ceilings matched.
- `0.17 × √2` taken from the live constant; 338.1 / 818.2 recomputed, and the brief's 336 m
  diagnosed as 1,400-rounded-first.
- The 260 m fixture's literal positions read from the test.
- The no-duplicate-copy gap proved absent by **grep** (no identity assertion, no source-scanning
  air-defence test) rather than inferred — per this project's graph-to-find/grep-to-prove split.
- Both check suites re-run from the detached tip.

**The one thing I could not settle** is optional refinement 1: whether the 342 m / 236 m figures were
reduced from `true_*` or `believed_*`. The reduction script does not exist in the repo and the field
is named in no document. Flagged rather than asserted in either direction.

---

# Review — BL-12 Stage 1 (`b54841b..c2c7e2d`, commits `9d7f4ae`, `327816c`, `c2c7e2d`)

Reviewed 2026-10-12 against `plans/group-contact-identity/plan.md`'s Stage 1 section and the
2026-10-11 amendment (A2–A6), `plans/group-contact-identity/implementation.md`'s Stage 1 log,
`body-layer/CLAUDE.md`'s Invariants, and `body-layer/ROADMAP/BL-12.md` / `BL-B48.md` / `BL-B51.md` /
`BL-B55.md` / `BL-B56.md`.

**Base check.** Worktree HEAD was `cb39159` (behind the named tip), a strict ancestor of the
expected `c2c7e2d` with a clean tree — fast-forwarded with `git merge --ff-only c2c7e2d`. No
divergence, nothing worked around.

---

## Verdict

**APPROVED WITH REQUIRED FIXES.** The core mechanism — `group_matches`, the four-phase `reconcile`,
the `groups`/`remembered_groups` split, the lattice-based air-defence resolution — is built exactly
as amendment A2/A3 specify, and every claim in `implementation.md` that I could independently check
reproduced. Two required fixes, both small; see below. Neither touches the mechanism's correctness
for the scenarios already tested — the first is a real test-coverage regression on one existing
test, the second is a scoping call that should be ruled explicit rather than left implicit.

---

## Required Fixes

**1. The `test_callouts.py` rewrite makes the test pass vacuously — it no longer exercises the
suppression logic it was written to protect.**

`test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent` injects a hand-built
`Group` directly into `store._groups._groups[...]`, bypassing `GroupStore.reconcile` entirely. Under
Stage 1's new semantics, `store.groups` filters to `last_observed_sim == self._last_reconciled_sim`
— and the injected group's `last_observed_sim` stays at its dataclass default (`0.0`), which never
matches `_last_reconciled_sim` (`6.0` at injection time, from the last real `store.tick()` call; it
is never advanced again because `poll()` only calls `scheduler.tick`, never `store.tick`). So
`store.groups` is **empty** for the rest of the test, which I confirmed by instrumenting the exact
fixture.

The consequence is not cosmetic. `CalloutScheduler.tick`'s whole group-disclosure block — the one
this test exists to exercise — is `for belief_group in store.groups:` (`callouts.py:1140`). With
the injected group invisible to that loop, `_already_reported_member_ids`, `render_group_disclosure`
and the suppression check never run for it at all. **I verified this by mutation**: I replaced
`_already_reported_member_ids`'s body with `return frozenset()` (which, if the loop ran, would
defeat suppression and make the group speak its full composition) and re-ran the test — it still
passed. Restored afterwards; full suite re-confirmed green (1663/4).

The implementer's own fix note frames this as "the property the test actually cares about (never
marked spoken) was unaffected by which accessor read it" — true of the *read*, but it misses that
the group became unreachable by the *production code path* the test is supposed to be driving. The
rewritten assertion (`store.remembered_groups[0].last_spoken_signature is None`) is true for a
reason that has nothing to do with suppression working: nothing ever touches this group now.

**Fix, not a reopening of the invariant decision**: give the injected `Group` a `last_observed_sim`
that matches what `_last_reconciled_sim` will be at the time of injection (`6.0` in this fixture, to
line up with the last real `store.tick()` call before the direct injection), so it is "currently
observed" for the rest of the test and the scheduler's group loop actually processes it, the same as
before Stage 1. This restores exactly what the test was checking, with the one Stage-1-aware
addition the original docstring already anticipated — the fixture models a group that could not form
by real `reconcile` (A and C are 500 m apart, outside the cohesion gate), which is exactly why it
was built by direct injection in the first place; it now additionally needs the one field Stage 1
added to mean "observed."

**2. A4's trace-line promise is not met by a mechanism nobody calls — rule needed on whether this
blocks Stage 1.** I agree with the implementer's three reasons for not wiring `--group-trace`
through `logger.py` in this commit, and the mechanism (`trace_sink`/`group_trace_sink`, fully tested)
is real engineering progress. But A4's stated reasons for promoting the trace line to "Stage 1's
first commit" are not about the mechanism existing — they are about **D5's rarity claim and
`BL-B50`'s lapse condition becoming checkable from an actual sortie**, and reason 4 names the
alternative outcome explicitly: *"the alternative first evidence is a wrong spoken line in
flight."* With no `--group-trace` flag, a live sortie today produces exactly zero observable trace
of phase-2 property matches — nothing has changed from before Stage 1 in what the pilot or a
debrief can check. I am not asking for `logger.py`'s wiring to be redone to a higher standard; I am
asking that this be ruled on explicitly rather than left as a flagged-but-undecided scope question,
since BL-12 stays on one branch and the user's acceptance of D5 is conditional on rarity being
checkable. **Recommendation**: land the CLI flag (one flag, one ~79-line writer mirroring
`speech_log.py`, one `_per_run_log_paths` entry) before this feature reaches DoD — it does not need
to block Stage 1's own merge into the feature branch, since the mechanism is already correct and
stages stay together until the whole milestone's DoD.

---

## What I verified independently

- **A3's lattice correction** (`_air_defence_op_class_of` reading `classification.parent_class_of`,
  never `object_model.profile_for`): reproduced the amendment's own six-row probe against this tree.
  `profile_for("OP_MRSAM")` resolves to `OP_GROUPSOMETHING` (miss); `parent_class_of("OP_MRSAM")`
  resolves to `OP_MRSAM` directly (hit) — matches the amendment's table exactly, row for row.
- **`GroupStore.groups` still means "currently observed"** for every pilot-facing consumer. Grepped
  `speech.py`, `tools.py`, `callouts.py`, `crew_console.py`: every one reads `.groups` or
  `.group_for_contact`, none reads `remembered_groups` or `_groups` directly. `group_for_contact`
  itself is correctly narrowed to iterate `self.groups`, not `self._groups`/`remembered_groups`.
- **The expire phase freezes properties for real.** Read the diff's phase-4 `Group(...)`
  reconstruction: every Stage-1 field (`centroid_x/z`, `composition`, `installation`,
  `air_defence_composition`) is carried over unchanged from the prior `Group`, only
  `last_reconciled_sim` advances. `test_a_group_with_no_matching_cluster_is_retained_not_dropped_
  within_the_window` and the expiry-boundary test both exercise this directly and I traced the code
  path matches what they assert.
- **`group_matches`/`group_match_score` against the amendment's six tests**: read each of
  `test_group_matches_rejects_a_mismatched_installation_flag` through
  `test_ambiguity_resolution_prefers_nearest_centroid_then_lowest_id` against the predicate's actual
  code (not just the test names) — all six tests are exercised in isolation plus once end-to-end via
  `GroupStore.reconcile` in the ambiguity test. `centroid_uncertainty_m` is RMS, confirmed both by
  reading `_centroid_uncertainty_of` (`sqrt(fmean(r*r))`) and by
  `test_centroid_uncertainty_is_the_rms_of_member_radii`'s literal expected-value computation. Test
  5's displacement bound and the one-sided "stopped" rule match the plan's own documented
  justification (zero-bound is a special case of the always-stricter direction, since
  `elapsed_s >= 0`); I agree this is the correct narrowing rather than a silent weakening.
- **No omniscience, every new field.** `_composition_of`/`_installation_of`/`_centroid_of`/
  `_centroid_uncertainty_of`/`_extent_of`/`_cluster_is_stopped` each read only `Contact.position` or
  `Contact.last_class_raw`/`Contact.motion.state` — no `Observation`, no DCS object id, no
  `derived_world_position`. Read every function body, not just the docstrings' claims.
- **`BL-B48`/`BL-B51` roadmap entries still `#status/open`**: correct, per Stage 0's own review —
  already flagged there as a merge-time update, not a Stage 1 defect. `BL-B56` (filed during Stage 0
  review) is unaffected by Stage 1 and correctly untouched.

## Checks (confirmed, not merely trusted)

**body-layer/** (from this worktree, binaries resolved against the root checkout's `.venv` per the
task's instruction):
- `ruff format --check src tests`: pass, 118 files
- `ruff check .`: pass
- `mypy src --strict` (from inside `body-layer/`): pass, 54 source files
- `pytest -q`: **1663 passed, 4 xfailed** — matches the implementer's reported numbers exactly

**audio-adapter/** (untouched by this change, run because the task asked):
- `ruff check .`: pass
- `mypy src`: pass, 15 source files
- `pytest -q`: 255 passed, 1 skipped — matches baseline

## Review Confidence

**Full read**, with one mutation test performed (required fix 1, described above) rather than
inferred from the implementer's own account — this is the thing the project's reviewer memory
specifically names: a test asserting an absence must be mutated, not read. Every other claim in
`implementation.md`'s Stage 1 section that could be independently checked (A3's lattice resolution,
the `groups`/`remembered_groups` consumer split, the expire-phase freeze, the six match-predicate
tests) was checked against the actual code and, where numeric, re-run against the real tree —
nothing here was spot-checked or taken on the implementer's word alone.

---
---

# Round 4 — review of the fix round (`43ed428`)

**Appended 2026-10-12.** Reviews the single commit at `feature/bl12-group-contact-identity`'s tip,
*"BL-12 Stage 1 review: restore the neutered suppression test, wire `--group-trace`"* — Round 3's
two required fixes, against `plan.md`'s A4 and the implementer's agent-memory note on the sibling-
function tradeoff.

**Base check.** Worktree HEAD was `cb39159` (behind the named tip), a strict ancestor of `43ed428`
with a clean tree — fast-forwarded with `git merge --ff-only 43ed428`. No divergence, nothing
worked around.

## Verdict

**APPROVED.** Both required fixes are answered correctly and verified independently, not taken on
the implementer's account.

## Fix 1 — verified by reproducing the reviewer's own mutation, not by reading

Reproduced the exact mutation from Round 3: inserted `return frozenset()` as the first statement of
`_already_reported_member_ids` (`body-layer/src/belief/callouts.py:841`). Ran
`test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent` alone — **red**, with
`spoken` gaining a third line, `"Pair of Ural truck."`, exactly as the implementer reported. Reverted
with `git checkout -- src/belief/callouts.py`, confirmed `git status --porcelain` empty, re-ran the
same test — **green**.

**The fixture's `6.0` is genuinely tied to `_last_reconciled_sim`, not a literal that happens to
match today.** `GroupStore.reconcile` sets `self._last_reconciled_sim = now_sim` at
`groups.py:1310`, and `.groups`'s filter (`groups.py:1037`) is
`group.last_observed_sim == self._last_reconciled_sim`. The fixture's last real `store.tick()` call
before the direct injection is `store.tick(now_sim=6.0)` (`test_callouts.py`, immediately after the
`OBS_C` ingest) — `poll()` never calls `store.tick()` again, so `_last_reconciled_sim` stays at `6.0`
for the rest of the test. The injected `Group`'s `last_observed_sim=6.0` is pinned to that same call
by construction, not by coincidence: if the fixture's timeline shifted (a different `now_sim` on
that `tick()` call), the needed value would shift with it, and nothing about `6.0` is special beyond
being that call's argument.

## Fix 2 — the flag reaches the sink, costs nothing when absent, and matches the sibling writer's posture

Traced the whole path from the CLI down: `--group-trace PATH` (argparse, `logger.py:2272`) →
`_resolve_group_trace_log_path` (stamp/`expanduser`/`mkdir`/degrade, reusing the shared
`_RESOLVE_FAILURES` tuple) → `GroupTraceLogWriter(args.group_trace).write` passed as
`group_trace_sink=` to **both** `ConsolePerceptionRunner` constructions (`--crew-text` and
`--console`, `logger.py:2484`/`:2555`) → `run_once`'s `self.store.tick(..., group_trace_sink=
self.group_trace_sink)` → `ContactStore.tick`'s existing `group_trace_sink` keyword
(`contacts.py:1079`) → `GroupStore.reconcile`'s `trace_sink=` parameter (`contacts.py:1516`) →
called once per trace record at `groups.py:1311-1313`. Not merely constructed — the new
`test_console_runner_threads_group_trace_sink_into_store_tick` spies on `store.tick` and asserts the
kwarg is the exact sink passed in, which I read against the production code it exercises rather than
trusting the test name.

**A4's minimum fields are all present** in the trace record built at `groups.py:1264-1272` (phase
`found`/`property`) and `:1300-1308` (phase `expired`): `group_id`, `phase` (one of
`overlap`/`property`/`found`/`expired` — `overlap`/`property` collapse to the single `resolution_
phase[cluster]` value set earlier in `reconcile`, which I traced reads `"overlap"` or `"property"`
depending on which phase claimed the cluster), the roster (`member_contact_ids`, sorted), the
centroid (`centroid_x`/`centroid_z`), **`extent_m`** (`None` on expiry, correctly — an expired
group's current extent is not computed), and `composition`. This machinery was built in Stage 1
itself (`c2c7e2d`); what Round 3 added is the only thing that was missing — a caller.

**Default is a true no-op.** `group_trace_sink: ... | None = None` on `ConsolePerceptionRunner`
(same posture as `overlay_client`), and `GroupStore.reconcile` only calls `trace_sink` inside `if
trace_sink is not None:` (`groups.py:1311`) — with the flag absent, `trace_records` is still built
(the list-append cost is unconditional) but never iterated into a sink call. That is the same
cost profile `DetectionTrace`/`SpeechLog` already carry when their own flags are absent, so this is
not a regression class; confirmed by reading, not re-measured, since the task did not ask for a new
performance pass and this is a handful of dict-building calls per reconcile at most (D5's own rarity
claim).

**Failure posture matches `speech_log.py` exactly.** Diffed the two `write()` methods side by side:
identical `_disabled` flag, identical unbuffered open-append-except-`OSError` shape, identical
"report once, then silently no-op" policy, identical `print(..., file=sys.stderr)` message shape
with only the label (`"group-trace"` vs `"speech-log"`) differing. `GroupTraceLogWriter`'s own
`test_an_unwritable_path_disables_after_one_reported_failure` pins the same property
`test_logger.py`'s speech-log equivalent does. `ContactStore.tick`'s call to `group_trace_sink` is
likewise not wrapped in a caller-side `try/except`, matching the implementer's own stated reasoning
for why the writer itself must never raise — read, not just cited.

**Stamping/naming matches the existing three logs.** `_resolve_group_trace_log_path` calls the same
`per_run_log_path` function `_per_run_log_paths` uses for the other three, so the stamp format is
identical and the resolved path prints through the same `"{label}: writing {rolled}"` loop
(`logger.py:2451-2457`, `group-trace` added to the three-tuple of `(label, rolled)` pairs). One gap,
optional below: `sortie-log-triage/SKILL.md`, the stated consumer, still only names three logs.

## The sibling-function design choice — accept it, file nothing new

Verified the blast-radius claim rather than crediting it: `grep -n "_per_run_log_paths(" tests/
test_run_log_paths.py` returns exactly 9 hits, and reading each confirms all 9 are positional
3-tuple unpacks (`trace, truth, speech = logger_module._per_run_log_paths(...)`). Widening the
function to a 4-tuple would force touching every one of those 9 call sites' unpacking for a reason
unrelated to what any of them test — which is the literal shape of "modifying existing tests without
it being the point of the fix," so declining the literal "one line" phrasing from Round 1's review
and writing a sibling function instead is the right call, not merely a defensible one. The
duplication is real (the `resolve` closure's stamp/`expanduser`/`mkdir`/except-`_RESOLVE_FAILURES`
logic is reproduced verbatim rather than factored out) but bounded — one function, ~25 lines,
reusing the shared exception tuple rather than redeclaring it — and the implementer flagged the
tradeoff explicitly in both `implementation.md` and a new agent-memory file rather than picking
silently, which is exactly the right disposal for a local, reversible choice under `AGENTS.md`'s
Escalation Rules. **This does leave two divergent policies for "resolve a per-run log path"** (one
function serving three logs, a second serving the fourth) — worth a backlog item if a fifth log
is ever added, at which point the duplication would be the wrong call, but not now with exactly one
sibling.

## Checks — confirmed, not merely trusted

**body-layer/** (binaries resolved against the root checkout's `.venv`, `cwd` inside `body-layer/`):
- `ruff format --check src tests`: pass, 120 files already formatted
- `ruff check .`: all checks passed
- `mypy src --strict`: success, 55 source files (54 + `group_trace_log.py`)
- `pytest -q`: **1671 passed, 4 xfailed** — matches the implementer's reported numbers exactly

**audio-adapter/** (untouched by this change, run because the task asked):
- `ruff check .`: pass
- `mypy src`: success, 15 source files
- `pytest -q`: **255 passed, 1 skipped** — matches baseline

## What must not have regressed — checked

- Exactly the 8 files the task named were touched (`git show 7b02510..43ed428 --name-only`); no
  stray file.
- No `TODO`/`FIXME`/debug-print/`pdb` in either new source file.
- Agent memory at the correct path (`.claude/agent-memory/implementer/…`), one file, with
  `description:`/`type:` frontmatter.
- `git status --porcelain` clean at the fast-forwarded tip before I made any change, and clean again
  after the mutation test was reverted.

## Optional refinements (not blockers)

1. **`sortie-log-triage/SKILL.md` names three sortie logs; there are now four.** The skill is the
   stated consumer of these logs' stamping/naming convention, and the new `--group-trace` output
   follows that convention exactly (same `per_run_log_path` stamp, same stderr announce line), but
   the skill's own description and file-resolution section don't mention it yet. Not a defect in
   this commit — the skill is a separate file with its own maintenance path — but worth a one-line
   addition next time that skill is touched, so a debrief session knows to look for it.
2. **The phase-collapse from `resolution_phase[cluster]` to the trace record's `phase` field is
   worth one more word in `groups.py`'s trace-record comment** (currently none at the construction
   site, `groups.py:1264-1272`) — `"overlap"`/`"property"` are set earlier in the function and simply
   read back here, which I had to trace rather than read off a local comment. Cosmetic; the fields
   are correct and A4 is satisfied either way.

## Review Confidence

**Full read**, with mutation reproduced myself (fix 1) rather than taken from the implementer's
account, the call-site count for the sibling-function tradeoff re-grepped rather than credited, and
the full CLI-to-`trace_sink` call chain traced through six files rather than inferred from the test
names. Both check suites re-run from the fast-forwarded tip. Nothing spot-checked.

---

# Round: BL-12 Stage 2 — Per-classification uncertainty growth (D8)

Reviewed `2e05f87` (2a, mechanism), `2f75286` (2b, calibration), `b180c7e` (log + agent memory), on
top of `33d78d8`. Eleven files, matching the task's own list exactly
(`git diff --stat 33d78d8 b180c7e`).

## Mechanism/calibration split — real, not nominal

`body-layer/CLAUDE.md`'s "Mechanism and calibration never share a commit" is honoured literally:
2a adds `plausible_speed_mps(op_class, installation_component)` returning `GATE_GROWTH_RATE_MPS`
for every input (`del op_class, installation_component; return GATE_GROWTH_RATE_MPS`) and threads
it through every elapsed-motion call site (`_inflated_since_last_fuse`, `fold_position`,
`clamp_to_detection_envelope`, the new `association_over_time.contact_growth_rate_mps`,
`groups._plausible_speed_mps`); 2b replaces only the function body with the real table. Checked out
`2e05f87` on its own (`git archive` to a scratch dir, `body-layer/.venv` run against it): **1672
passed, 4 xfailed** — 1671 pre-existing + the one new bit-identity test, exactly as claimed.

**The bit-identity claim is sound, but by algebra plus one direct test, not by an end-to-end
pin.** `test_plausible_speed_mps_stage_2a_is_flat_for_every_class` establishes that
`plausible_speed_mps` itself returns `GATE_GROWTH_RATE_MPS` for every `op_class`/`installation_
component` combination that appears anywhere in the codebase's tables. Combined with the call-site
diffs — which only add a `growth_rate_mps` parameter defaulting to `GATE_GROWTH_RATE_MPS`, with no
other logic touched — that is sufficient to prove no behaviour change; I did not find a gap in the
reasoning. There is no test that exercises the full pipeline (`Contact.record` → gate) and asserts
bit-identical gate outcomes directly, but the full 1672-test suite passing unchanged at 2a serves
that role in practice. **Deleting the test in 2b was right, not merely convenient**: 2b's whole
purpose is to make `plausible_speed_mps` stop being flat, so a test asserting flatness for every
input would fail by design after 2b and would have to be deleted or rewritten either way; keeping
it would mean either a contradiction in the suite or disabling it, neither better than deletion.

## One table, no second copy — confirmed, with one explainable fallback

`grep -rn "plausible_speed"` across `src/` turns up exactly one table (`position_belief.
_PLAUSIBLE_SPEED_MPS` / `_DEFAULT_PLAUSIBLE_SPEED_MPS`), one public function, and every consumer
(`association_over_time.contact_growth_rate_mps`, `groups._plausible_speed_mps`) delegating to it.
`groups.py` still imports `GATE_GROWTH_RATE_MPS` directly for one use:
`max((_plausible_speed_mps(op_class) for op_class in group.composition), default=GATE_GROWTH_RATE_MPS)`
— the `default=` fires only if `group.composition` is empty. Traced: the sole construction site
(`groups.py:874`, the "found" phase) always sets `composition=_composition_of(members)` from a
real, non-empty member list (`GROUP_REPORTING_MIN_MEMBERS = 2`), so this branch is unreachable for
any group that has gone through `reconcile`'s found phase — `composition: tuple[...] = ()` is a
dataclass default kept only for the additive-fields backward-compatibility rule Stage 1 established,
not a live path. **Optional, not required**: using `_DEFAULT_PLAUSIBLE_SPEED_MPS`-equivalent (i.e.
calling `plausible_speed_mps` with no classes rather than falling back to the raw constant) would
remove even the theoretical inconsistency, but since the branch is dead in practice this is not
worth a commit on its own.

## Installation-component keying — honoured

`plausible_speed_mps(op_class, *, installation_component=False)` checks `installation_component`
first and returns `0.0` unconditionally, never keyed on an `op_class` list — exactly the reasoning
`group-cohesion-redesign/plan.md` §1 gives for rejecting an `op_class`-keyed installation set (one
`op_class` bucket, e.g. `OP_SRSAM`, covers both a genuine fixed site and a single-vehicle mobile
system). Read, not just cited: §1's own example (`"osa"` vs `"s-125"` both inside `OP_SRSAM`) is the
exact case this structural keying was built to keep separate, and it does.

## `Contact.record`'s resolve-before-overwrite ordering — true, but unpinned

Read `contacts.py:506-531`: `growth_rate_mps = contact_growth_rate_mps(self)` executes at line 508,
reading `self.last_class_raw` as it stood *before* the call; `self.last_class_raw =
percept.classification_raw` does not happen until line 531, after both `fold_position` and
`clamp_to_detection_envelope` have already consumed `growth_rate_mps`. The ordering is correct as
documented.

**Verified by mutation, not just reading**: moved the resolve to after the overwrite (and after
`self.last_alt_m`) in a scratch copy of `contacts.py`. Full suite stayed green — **1674 passed, 4
xfailed, unchanged** — so no existing test would catch a regression that made the rate follow the
*new* classification instead of the old one. This is a real gap, not a blocker for this round: the
ordering is a one-line, load-bearing fact with no behavioural test pinning it, and the natural test
(a contact whose classification changes between two consecutive looks, with a growth rate that
differs enough between the two classes to move the resulting covariance measurably) was not written
in either commit. Recommend a follow-up test next time `Contact.record` is touched for this
mechanism; not required to land this round because the plan's acceptance criteria for Stage 2 never
asked for one and the class-flip case is rare relative to what this stage actually calibrates.

## The four moved tests — re-derived correctly, verified by mutation on each

Reverted each moved fixture to its pre-2b numbers (restoring afterward) and re-ran against the
calibrated table:

| test | old numbers restored | result |
|---|---|---|
| `test_groups.py::test_ambiguity_resolution_prefers_nearest_centroid_then_lowest_id` | `x=21.0/31.0`, `now_sim=2.0` | `ambiguous_property_matches_count == 1` → **fails** (`0 == 1`) |
| `test_contacts.py::test_slow_directional_drift_never_reports_a_range_beyond_the_detection_cap` | `range(1, 22)` | **fails** (`assert 2 == 1`, second contact founds early) |
| `test_contacts.py::test_position_runaway_does_not_corrupt_a_second_contacts_cardinality` | `range(1, 22)`, `t_sim=21.0` | **fails** (same shape) |
| `test_enrichment.py::test_terrain_aware_position_reprojects_the_fused_estimate_not_the_last_look` | `growth_rate_mps` arg removed from both `fold_position` calls | **fails** (`1100.249… == 1100.442… ± 1e-06`) |

All four fail under the old numbers against the new calibration and pass only at the re-derived
ones — none is a loosened or boundary-exact rewrite; each still protects the invariant its docstring
states (gate-split timing, ambiguity nearer-wins, ground-truth parity), just at the correct new
magnitudes. This is the same check the `BL-B48` case established as a standing instrument, applied
here to a different table.

## `POSITION_HALF_LIFE_S` — value and asserts untouched, docstring corrected honestly

`decay.py`: the value stays `30.0`; both `assert`s (`OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S`,
`SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S < OBSERVED_WINDOW_S`) are byte-identical. The docstring now
says plainly that the 20 m/s derivation "no longer holds for any real contact" and that
recalibrating the half-life is future work — it does not quietly re-derive a new justification for
the same number, which would have been worse than leaving the old one.

## The flagged-not-fixed discovery — ruled on, and filed

`object_model.profile_for` cannot resolve `installation_component` from a bare class-level string
(`"OP_SRSAM"` alone matches no keyword), so an entrenched SAM believed only at class level gets the
default `8.0` m/s instead of D8's `0.0` until identified to type. Enumerated the same way amendment
A3 did for the air-defence membership gate: every air-defence `op_class` in the table is `8.0`, same
as the default fallback, so the *op_class* axis is genuinely harmless as claimed — but
`installation_component` has no such symmetry (its correct value, `0.0`, differs from the default,
`8.0`), so the miss is real on that axis.

**Ruling: correct reading, filed as [[BL-B57]] rather than left as a log note.** Pre-existing and
shared with `_installation_of`/`_pair_backstop_m` (true, as claimed) — but "pre-existing" does not
mean "not this stage's problem" when this stage is the first consumer for which the default and
correct values actually diverge (every earlier consumer of `profile_for`'s installation resolution
only needed a boolean gate, where `False`-by-default degrades safely; this one needs a *number*,
where the wrong default is numerically wrong, not just conservative). D8's headline case is exactly
the one this misses. **Does not interact with D6's threat-suppression carve-out**: D6 is gated
through `classification._op_class_of` (amendment A3's fix, already merged), a different path from
the growth-rate table reviewed here — this item widens a displacement/association bound, not a
threat-envelope lookup, so it is a separate, bounded miscalibration rather than a safety-relevant
interaction with D6.

## Checks

**body-layer/**:
- `ruff format --check .`: one unrelated pre-existing file flagged (`research/
  2026-10-05-security-audit.md`, a markdown code-block ruff reformats as if it were live Python —
  untouched by this diff, confirmed via `git diff 33d78d8 b180c7e -- <that path>` returning nothing).
  Not a regression from this stage.
- `ruff check .`: all checks passed.
- `mypy src --strict` (run from inside `body-layer`): success, 55 source files.
- `pytest -q`: **1674 passed, 4 xfailed** — matches the implementer's reported numbers exactly.
  Stage 2a alone (`2e05f87`, via `git archive` to a scratch dir): **1672 passed, 4 xfailed**,
  matching the claimed 1671 baseline + 1 new test.

**audio-adapter/** — not run by the implementer; checked the claim rather than accepting it.
`grep -rn "belief\.(groups|contacts|position_belief|association_over_time|decay)" audio-adapter/`
returns nothing: that subproject talks to body-layer exclusively over `POST /speak`/`/transcripts`
HTTP, no in-process import either direction (confirmed against `audio-adapter/CLAUDE.md`'s own
"Division of responsibility" framing). Ran it anyway: **255 passed, 1 skipped** — matches the
stated baseline exactly, confirming the claim.

## Required Fixes

None.

## Optional Refinements

1. **The resolve-before-overwrite ordering in `Contact.record` is load-bearing and unpinned** — a
   mutation that resolves the growth rate after `last_class_raw` is overwritten passes the full
   suite unchanged. Worth a direct regression test (a contact whose classification changes between
   two consecutive looks, with growth rates that differ enough to move the resulting covariance
   measurably) next time this function is touched for this mechanism. Not required this round.
2. **`groups.py`'s `max(..., default=GATE_GROWTH_RATE_MPS)` fallback is the one place the flat
   constant survives**, even though it is dead code today (the sole construction site always
   populates `composition`). Cosmetic — the "one table" principle is honoured in every reachable
   path — but a future caller passing an empty `composition` directly (bypassing `reconcile`'s
   found phase, e.g. a test fixture) would silently get the pre-calibration rate rather than the
   table's own default (`8.0`). Worth tightening if `Group` ever gains a second construction path.
3. **No direct unit test for `association_over_time.contact_growth_rate_mps`** itself (its
   `profile_for`-resolution logic is only exercised indirectly through the four moved fixtures,
   all of which happen to use `OP_TRUCK`). A direct test crossing a couple of `op_class`/
   `installation_component` combinations would pin the function's own contract rather than relying
   on fixture incidence. Optional.

## Verdict

**APPROVED.**

## Review Confidence

**Full read.** Checked out `2e05f87` standalone via `git archive` to confirm the stated 1672/4
Stage-2a-only figure rather than trusting the commit message. Mutated four things myself and
observed the result rather than re-deriving the author's reasoning: the `Contact.record` ordering
(found an unpinned-but-true claim), each of the four moved tests' old numbers (all four fail under
the new calibration, confirming genuine re-derivation, not loosening), and the `test_enrichment.py`
growth-rate arg (confirmed load-bearing). Ran `audio-adapter`'s suite myself rather than accepting
the "not run, nothing touches it" claim on the strength of a grep alone. Nothing spot-checked.

---

# Round: BL-12 Stage 3 — Within-group ambiguity resolution (D5 at contact grain, D6 carve-out)

Reviewed `54b6190` (mechanism), `0a28405` (plan-named test rewrite + two new tests), `fbbba25`
(2C fixture re-derived, not plan-named), `3fb6018` (`test_logger.py` decoupling, not plan-named),
`74f6efd` (log + agent memory), on top of `0abc738`. Seven files
(`git diff --stat 0abc738 74f6efd`), matching the implementer's own list exactly.

## Branch assembly, per rule 4

Worktree HEAD (`cb39159`) was a strict ancestor of the named tip `74f6efd` and the tree was clean —
`git merge --ff-only 74f6efd` succeeded, now at that sha.

## Branch 1 (D6) resolves through the lattice — verified by mutation, not reading

`_fold_target_for_ambiguous_candidates` reads `belief.classification.parent_class_of`, never
`object_model.profile_for`, exactly as amendment A3 and the implementation log state. Checked by
breaking it deliberately: swapped the resolution to
`object_model.profile_for(candidate.last_class_raw).op_class` (adding the one import that requires),
reran `test_air_defence_candidate_forces_a_new_contact_even_within_a_group` —
**fails, `2 == 3`**, falling through to branch 2's fold exactly as the test's own docstring predicts
for this specific mutation. Restored the file; `shasum` of `contacts.py` matches the pre-mutation
value, confirming a clean revert. `groups.py`'s companion fix (`_air_defence_op_class_of` reading
`classification.AIR_DEFENSE_OP_CLASSES`/`_op_class_of`, not `_profile_for_contact`) is read and
matches the same posture; `BL-B51`'s fold-into-one-set is also confirmed: the set now lives in
`belief/classification.py` alone, with `groups.py` importing it rather than holding its own copy.

## The growth-rate ordering counterfactual — reproduced exactly

Swapped `Contact.record`'s two lines (resolving `growth_rate_mps` after overwriting
`last_class_raw`, instead of before) and reran
`test_contact_record_resolves_growth_rate_before_overwriting_last_class_raw`: fails with
**`1281.5068493150686 == 1196.1538461538462 ± 0.00119615`** — the implementer's own reported numbers
to five significant figures. Restored; `shasum` matches.

## The two plan-unlisted test fixes — judged separately, as the task asked

**`3fb6018` (`test_logger.py`) is a decoupling, not a loosening.** `_make_observation` gains
additive, default-preserving `bearing_deg`/`range_m` parameters; only the one call that needed a
distinct position gets one. The test's own assertion is untouched — it still checks push-failure
isolation, now without an incidental dependency on ambiguity resolution it never intended to
exercise. Matches this project's own `feedback_shared_fixture_position_becomes_load_bearing`
agent-memory note (written the same round) precisely, and is the right kind of fix per that note's
own distinction (decouple the fixture vs. rewrite the assertion).

**`fbbba25` (`test_callouts.py`'s 2C fixture) is scrutinised hard, per the task's instruction, and
holds up.** Its new expectation was read off a run — I re-derived the same run independently rather
than trusting either the implementer's account or the diff: built a standalone script against the
real `ContactStore`/`GroupStore` reproducing the fixture's full event sequence through t=12 and
printed contact positions and group membership after the fold+reconcile. Result matched the test's
assertion exactly — one group, `{CONTACT_1, CONTACT_2, CONTACT_3, CONTACT_4}`, not the two
infantry-only pairs Stage 0a alone produced. This is independent reproduction, not re-reading the
same diff twice.

## The cascade finding — real, reproduced, characterised

**Real.** Confirmed above by independent reproduction (own script, not the implementer's), and by
running the actual test unmodified (`1 passed`). `CONTACT_4` (BTR-70) is never itself a candidate in
any `ingest` call in this fixture — it is absorbed purely by `_cluster_contacts`'s position-only
single-link re-clustering inside the same `tick()` call that follows the fold, because the fold
moved `CONTACT_1`/`CONTACT_2`'s fused positions (`fold_position` is a real weighted fuse) close
enough to `CONTACT_4` to clear the pair backstop/relative-gap test.

**Bounded within one incident, not a single-tick runaway — settled with a run, not an argument.**
Extended the same script ten further polls past t=12, injecting a fresh, nearby, genuinely new
infantry percept each poll. Each one folds onto the existing group (repeating the undercount,
moving the folded-onto contact's position a little further each time) but **group membership stays
at the same four contacts and `centroid_uncertainty_m` *shrinks*, 258 m -> 242 m, across the ten
polls** — re-observation tightens covariance faster than the drift widens it once the group is
actually being seen again. So this is not compounding cluster growth within one continuously-visible
episode. **The real risk is repeat-incident, not runaway-single-incident**: each time a group goes
unobserved long enough for covariance to inflate (an ordinary occurrence — terrain masking, a scan
elsewhere) and an ambiguous percept lands nearby exactly when visibility returns, one more
absorption of this shape can fire, independently, on its own schedule. I did not construct a clean
second, independent incident in the time available (my own attempt at one accidentally exercised a
different, pre-existing single-candidate continuity-merge path instead of the ambiguity fold,
which is a real distinction worth knowing but not evidence either way for repeat-incident
compounding) — flagged as the open half of this question in `BL-B58`, not asserted as settled.

**Partly, not wholly, a fixture artifact — measured, not assumed either way.** The fixture's
observations declare no `position_uncertainty`, so both gate sides fall back to the isotropic
`_FALLBACK_UNCERTAINTY_RADIUS_M` (300 m) — a path `association_over_time.py`'s own comment says
"should not happen in production." At this fixture's short ranges (280-500 m), real declared
naked-eye uncertainty (`naked_eye_sigma_m`: `sigma_cross = radians(3.0) * range`, `sigma_down =
0.17 * range`) is far tighter — about 49 m at 280 m, 89 m at 500 m, one-sided — than the 300 m
fallback, so the fixture's 500-900 m absorption range would not reproduce at these particular close
ranges with real declared uncertainty. **But at the ranges this project's own prior measurements
already cite as typical naked-eye operating range** — `plans/contact-duplication-ambiguity-runaway/
debug.md`'s ~590 m one-sided gate at 1200 m range, and `BL-12`'s own roadmap entry's 600 m gate
after 30 s unseen — real declared uncertainty alone is already comparable to or wider than this
fixture's fallback. So the mechanism is not confined to a fixture artifact; it would recur at
realistic mid-range engagement distances with entirely real numbers, just without this fixture's
own extra amplification at *these particular* close ranges. Filed in `BL-B58` with both halves
stated, not just the flattering one.

**D6's own gate is unaffected by the cascade — checked directly against the code, not inferred.**
The absorption resolves through `reconcile`'s phase 1 (overlap match, since the new cluster already
shares 3 of 4 members with the existing `Group`), which carries no class/air-defence/displacement
check at all — D6's hard air-defence-confirmation test only gates phase 2 (property match, a cluster
with *zero* member overlap against a remembered group), a path this absorption never reaches. Read
`reconcile`'s phase 1 and phase 3 construction directly: `Group.air_defence_composition` is
recomputed fresh from the matched cluster's actual current members on every call regardless of
phase, never carried over stale. So the risk this cascade poses is not a stale or bypassed
air-defence flag — it is that cluster *membership itself* can be corrupted by spurious position
drift, which would then correctly (but misleadingly, given the corrupted membership) update
`air_defence_composition` to match. I did not reproduce this with an actual air-defence contact in
the time available — noted as the concrete next check in `BL-B58`, not asserted as proven either
way.

**None of the plan's three named failure modes individually describes this**, as the implementer's
own log and the test's docstring already say, and I agree after reading all three against the
mechanism directly: failure mode 1 ("the group-level answer stays correct") is the one that comes
closest and explicitly does not cover it — here the group-level answer becomes wrong.

**Filed as `[[BL-B58]]`**, with three options and their relative costs (widen Stage 4's
not-yet-built extent guard to also suppress composition-based disclosure past a width bound;
bound a single fold's maximum position displacement; re-check cohesion before a plain overlap-match
absorbs a new member) — for the orchestrator to put to the user, per the task's own framing. No
option is applied here: the mechanism as built matches the plan and its amendments exactly, and
adding a safeguard not in the plan would be scope the implementer correctly declined to add
unprompted.

## Checks — confirmed myself, not accepted from the log

**body-layer/** (via `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`, this worktree has none of
its own):
- `ruff format --check src tests`: **pass**, 120 files already formatted.
- `ruff check .`: **pass**, all checks passed.
- `mypy src --strict` (run from inside `body-layer`): **pass**, 55 source files.
- `pytest tests -q`: **pass — 1676 passed, 4 xfailed**, matching the implementer's reported numbers
  exactly.

**audio-adapter/**: ran it myself rather than accepting the "not run, nothing touches it" claim —
`grep -rn "belief\.(groups|contacts|position_belief|association_over_time|decay)" audio-adapter/`
returns nothing (no cross-import either direction), and the suite itself: **255 passed, 1 skipped**,
matching the stated baseline exactly.

## Required Fixes

None. The mechanism matches the plan and amendment A3 exactly, verified by mutation on both the
air-defence resolution path and the growth-rate ordering; both plan-unlisted test changes are sound
(one a correct decoupling, one a correctly re-derived expectation, independently reproduced); all
checks pass with real numbers matching the log.

## Optional Refinements

1. **`BL-B58`'s repeat-incident-compounding question is left open**, not closed — my own attempt at
   a second, independent incident exercised a different continuity-merge path by accident rather
   than the ambiguity fold. Worth a clean second-incident reproduction before this is treated as
   fully characterised, though it does not block this round's verdict (the mechanism as implemented
   matches the plan; `BL-B58` is about a consequence the plan did not anticipate, not a defect in
   what was built against it).
2. **`BL-B58`'s air-defence-interaction question is also left open** for the same reason (time-boxed
   this round) — worth a direct reproduction with an actual air-defence contact as the absorbed
   member before closing that item, even though the code-level read (fresh recomputation every
   reconcile, no stale carry-over) already rules out the sharpest version of the worry (a stale,
   silently-wrong `air_defence_composition`).

## Verdict

**APPROVED.**

## Review Confidence

**Full read**, with one explicit limit stated above: `BL-B58`'s repeat-incident and
air-defence-interaction sub-questions are reproduced-in-part (bounded-within-one-incident is
settled with a run; whether the pattern can recur across independent incidents, and whether an
actual air-defence contact can be the absorbed member, are not — both left open in the filed
backlog item rather than asserted). Everything else in this round — both resolution-path mutations,
the growth-rate counterfactual, the 2C fixture's new expectation, both plan-unlisted test fixes, and
every check number — was verified directly: mutated and reran, or re-derived independently and
compared, not read off the log and trusted.

---

# Round 7 — BL-12 Stage 3.5, the group-cohesion admission gate (`BL-B58`)

**Branch `feature/bl12-group-contact-identity`, tip `005309c`.** HEAD at dispatch was `cb39159`
(a strict ancestor of `005309c`), tree clean — fast-forwarded with `git merge --ff-only 005309c`.
Four commits reviewed: `7946c8d` (fold_displacement_m provenance), `57f67d0` (the admission gate),
`c6e24c1` (2C fixture rewrite), `005309c` (log/roadmap/memory).

## What was reproduced, not just read

- **Commit 1 behaviour-neutrality.** Archived `7946c8d` to an isolated snapshot
  (`git archive 7946c8d | tar -x`) and ran `pytest` from inside that snapshot's `body-layer`:
  **1677 passed / 4 xfailed**, matching the claim exactly (1676 baseline + the one new provenance
  test). The new test (`test_fold_displacement_m_is_written_on_a_fold_and_reset_on_an_unambiguous_record`)
  pins all three branches named in the plan: zero before any fold, written and **accumulated**
  (not replaced) across two folds, reset to `0.0` on an unambiguous continuity-resolved record.
- **Commit 2's per-commit number.** Archived `57f67d0` the same way: **1682 passed / 4 xfailed**,
  with exactly one expected failure (`test_2c_transcript_fixture_renders_four_lines_not_seven`,
  the old name, failing because the fixture now renders 3 lines not 4) — matching the claim.
  `test_the_eager_cap_still_chains_a_long_infantry_line` ran green at this commit, confirmed by
  running it in isolation; the diff hunk for that function shows only its closing line touched
  (new tests inserted after it), so it is unmodified, not merely passing.
- **The ordering claim (`self._groups` read before reassignment).** Grepped `groups.py` directly:
  `prior_rosters = [group.member_contact_ids for group in self._groups.values()]` at line 1219,
  `self._groups = new_groups` at line 1378, nothing mutates `self._groups` between them.
  `member_contact_ids` is `frozenset[str]` (line 523). Confirmed `ingest` runs before `tick` each
  poll in the one place that matters, `logger.py`'s poll loop (`store.ingest(...)` at line 547,
  `store.tick(...)` at line 557) — so a fold's provenance is visible to the very tick the
  absorption would occur on, exactly as claimed.
- **Trying to break "the gate structurally cannot evict or found."** Reasoned through every
  shape I could construct and could not break it: prior co-members always take the ordinary,
  unaffected rule (so an existing group's internal links are never touched by the gate), and
  `fold_displacement_m >= 0` always, so the gate can only *increase* a measured gap for
  non-co-member pairs — never admit more than the ordinary rule would, never force a merge.
  A vetoed admission therefore either leaves a contact a singleton (dropped by
  `GROUP_REPORTING_MIN_MEMBERS`, reported individually — exactly the claimed shape) or splits a
  larger candidate cluster into pieces, each of which still contains its own full prior roster
  (since those internal links are untouched) and so still overlaps and inherits that roster's id
  via `reconcile` phase 1 — never phase 3 (found). I could not construct a case where the gate's
  veto causes an existing member to drop out of its own group, or causes a previously-nonexistent
  group to come into being. **Mutation confirms the load-bearing half of this claim directly**:
  removing the "prior co-members get the ordinary rule" branch (always applying the admission
  inflation) breaks Rows A, B and F — i.e. Row A's own assertion depends on `CONTACT_1`/`CONTACT_2`
  (both carrying large fold budgets, both prior co-members) staying linked despite their own
  budgets, which is exactly the exemption property under test. Restored cleanly afterward
  (`git checkout -- src/belief/groups.py`, verified clean).
- **The six-row table, measured directly.** Re-ran probe 3 (`probe_b58_candidate.py`, unmodified)
  from inside `body-layer`: output matches `implementation.md`'s paste byte-for-byte, including
  every `gap`/`eff`/`thresh` and `cur -> new` verdict, and Rows C/D/E print `INVARIANT ROW:
  IDENTICAL`. Re-ran probe 1 (`probe_b58_geometry.py`, the one-line signature fix) directly: t=15's
  `CONTACT_1-CONTACT_4` prints `81.9 gap 88.0 backstop 88.0 thresh LINK` — byte-identical to the
  plan's own numbers. Re-ran probe 2 (`probe_b58_second_incident.py`, unmodified — drives the real
  `ContactStore.tick()`/`GroupStore.reconcile()` pipeline) directly: `GROUP_1
  members=['CONTACT_1', 'CONTACT_3'] air_defence=[]` after the fold and at t=30 — matching
  `implementation.md` exactly, confirming the gate holds end-to-end through the real pipeline, not
  just the isolated predicate, and that `CONTACT_2`'s eviction (`BL-B59`) is still live in the same
  run.
- **The probe signature fix did not change what probe 1 measures.** The diff is a one-line call
  update passing `[]` for the new `prior_rosters` parameter, with a comment stating the probe's
  purpose (raw geometry, independent of the gate) is unchanged — confirmed by re-running it and
  getting the plan's own pre-implementation numbers back exactly.
- **The 2C fixture's new expectation, re-derived independently.** Mutated `_cluster_contacts`'s
  admission branch to `effective_gap = gap` (gate disabled) and reran
  `test_2c_transcript_fixture_renders_three_lines_not_seven`: it fails, reverting to the old
  four-line output (`"BTR-70, in 1 o'clock group."` reappears) — the test bites, it is not a
  decorative re-assertion of whatever the run happened to produce. Restored cleanly, reran clean.

## The three user decisions — verified in the files, not just the log

1. **`fold_displacement_m` resets on the next unambiguous record, no half-life, no new constant.**
   Confirmed in `contacts.py`'s diff: `contact.fold_displacement_m = 0.0` on both the continuity
   branch and the `len(passing) == 1` branch; no new constant appears anywhere in the diff or
   `mypy`/`ruff` output.
2. **`BL-B59` filed out of BL-12 and prioritised next, not parked unprioritised.**
   `body-layer/ROADMAP/BL-B59.md`'s own header states this disposition in the user's terms
   ("out of `BL-12`'s Stage 3.5, and prioritised next — not parked unprioritised... should be taken
   up next, not left in the general backlog") and the entry records the post-fix probe 2 re-run
   confirming the eviction half is still live against the shipped code, not just the pre-fix
   measurement.
3. **The 2C fixture's 3-line drop, accepted "as recommended, but recheck with BL-B50."**
   `body-layer/ROADMAP/BL-B50.md`'s recheck note is present, in the right place, and states the
   actual condition — that a fold-driven *admission* no longer producing flipping on this fixture
   is not evidence that `BL-B59`'s *eviction* mechanism won't reopen it, and names the concrete
   re-check ("re-run the 2C fixture... once `BL-B59` is live") rather than a vague "check later."

## Checks — measured, not accepted

**body-layer/** (the only subproject touched — confirmed via
`git diff --stat 7932fb3..005309c -- audio-adapter aircraft-layer world-model brain-layer
mission-interpreter`, empty):

- `ruff format --check src tests`: pass (120 files already formatted)
- `ruff check src tests`: pass, no findings
- `cd body-layer && mypy src` (strict, CWD-local): pass, 55 source files, no issues
- `pytest -q`: **1683 passed, 4 xfailed** — matches the claim exactly
- `audio-adapter`: ran it rather than accepted the "untouched" claim — **255 passed, 1 skipped**,
  matching the stated baseline
- `/invariant-check`: all mechanical checks PASS (no-omniscience boundary, module independence, no
  `sys.path` smuggling, `BINOCULAR_RANGE_MULTIPLIER` has not returned, no stray `print()` in
  `perception`/`belief` core, no bare `except`); the only WARN rows (7 swallowed exceptions, 4
  `type: ignore`) are pre-existing and untouched by this stage's diff

## Required Fixes

None. The provenance field, the gate, and the fixture rewrite each do exactly what the plan and
the implementation log claim, verified by re-running the plan's own probes directly, by mutation
on both the co-member exemption and the fixture's new expectation, and by independent archive
snapshots at each intermediate commit rather than trusting the implementer's per-commit numbers.
All three user decisions landed in the files where they will actually be read, in the user's own
terms.

## Optional Refinements

1. **Row F's property ("single-link routes around one tainted member") is measured on one
   synthetic armour triple**, as the plan's own Risks section states. Worth a second scene if a
   real sortie ever shows a tainted member with no clean path — not a defect in what shipped.
2. **The "repeat folds accumulate" semantics (commit 1) is a stated assumption, not measured
   against a real repeat-fold incident** — same posture as `BL-B58`'s own open sub-questions in
   the prior round. Low risk: the accumulate path is pinned by a direct test (two folds, no
   intervening clean look), it just hasn't been seen in a live incident yet.

## Verdict

**APPROVED.**

## Review Confidence

**Full read.** Every number in this round's checks table was run directly rather than accepted
from the implementation log: per-commit pytest counts via isolated `git archive` snapshots, all
three probes re-run and compared byte-for-byte against `implementation.md`'s paste, the co-member
exemption and the fixture's new expectation both confirmed by mutation (not just by reading the
assertion), and the "cannot evict or found" claim tested both by construction (reasoning through
candidate counterexamples) and by mutation of the one branch that makes it true. The two items
left as optional refinements are the same two sub-questions the plan itself states as open and
unmeasured, not new gaps found this round.
