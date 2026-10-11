# BL-12 Stage 0 — implementation

Branch `feature/bl12-group-contact-identity`, from tip
`bae8963` ("Amend the BL-12 plan: BL-B48 is blocking, not inherited").
Stage 0 only. Stage 1 is not started and nothing here reaches into it.

Three commits, in the order `body-layer/CLAUDE.md`'s "Mechanism and calibration never share a
commit" requires:

| sha | stage | kind |
|---|---|---|
| `1ec68fb` | **0a** — `_pair_backstop_m` requires **both** members `EAGER` | mechanism |
| `68598f7` | **0b** — `GROUP_REPORTING_EAGER_COHESION_CAP_M = 500.0` replaces `math.inf` | calibration |
| `b9632e4` | **BL-B51** — one air-defence class set, one `<=` drift guard | refactor |

---

## Stage 0a — the mechanism (`1ec68fb`)

### Measured, before and after, on this tree

Reproduced through `body-layer/.venv`'s interpreter against the real profiles and the real
constants (`GAP_RATIO=3.0`, `UNIT_WIDTHS=20.0`, `MIN_MEMBERS=2`), **before** changing anything, and
again after. The amendment's four-row table reproduced exactly.

| scene | relative threshold | before | after |
|---|---|---|---|
| `armor@1km + truck@3km` | 6,000 m | 0 groups (pair threshold 130 m) | **0 groups — unchanged** |
| `armor@1km + infantry@7km` | 18,000 m | one group, **6,000 m** | **0 groups** (threshold 88 m) |
| `armor + truck + infantry` | 6,000 m | one group of three, **6,000 m** | **0 groups** (130 / 88 / 78 m) |
| three infantry @30 m | 90 m | one group, 60 m | **one group, 60 m — thresholds and unions identical** |
| two infantry @5 km | 15,000 m | one group, 5,000 m | one group, 5,000 m *(closed by 0b)* |

The fifth row is the fault Stage 0a deliberately leaves open and is why 0b exists.

### The architect's precedent claim — verified at the source

The amendment says rule 1 of `_pair_backstop_m`'s own docstring already makes a mixed
*installation* pair fall through on the identical argument. **It does, verbatim:**

> *"A **mixed** pair (one installation component, one not) falls through to the ordinary rule below
> — an installation cap is only meaningful when both members are plausibly parts of the same
> site."*

Rule 2's new wording mirrors it, and
`test_a_mixed_infantry_pair_falls_through_exactly_as_a_mixed_installation_pair_does` asserts the
equivalence by computing the ordinary value from the sizes rather than writing it out, so retuning
`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` cannot make that test lie.

### Counterfactual (run, not reasoned)

Reverted the predicate to `or` in `src/belief/groups.py` — the code path, not a constant any test
imports. Four tests went red (`test_infantry_no_longer_bridges_…`,
`test_armor_and_distant_infantry_do_not_merge`,
`test_infantry_does_not_bridge_armor_and_truck_at_sortie_scale`,
`test_a_mixed_infantry_pair_falls_through_…`); the armour+truck control, the infantry-only scene and
both installation rows stayed green. Restored by `shasum`
(`58716fca14b94808d2018bb19fa34b772e81f0c9`), not by eye.

---

## Stage 0b — the cap (`68598f7`)

`GROUP_REPORTING_EAGER_COHESION_CAP_M = 500.0`. **A stated assumption, not a measurement** — same
posture as `GROUP_PROXIMITY_GAP_RATIO` and `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS`, and the user
judges it in the air.

### Where the number came from

**Primary derivation — the resolution of the sentence the group is spoken in.**
`belief.speech._format_range_km` rounds a spoken range to the nearest 0.5 km. Run, not read: 2 750 m,
3 000 m and 3 249 m all say *"3 kilometres"*; 3 251 m says *"3.5 kilometres"*. So *"that group, two
o'clock, three kilometres"* is a claim with **500 m of resolution**, and a group wider than that
holds members the same renderer would place in different buckets — which is exactly the pilot-facing
question the user was asked. `groups.py` does **not** import `speech` (its docstring: this module
reads nothing speech-shaped); the figure is transcribed from that rounding step.

**Cross-checks against figures already in the repo:**

| check | figure | verdict |
|---|---|---|
| one clock hour's cross-range width | `2·tan(15°)·R = 0.536 R` | 500 m fits inside one clock hour from **R ≥ 933 m**; below that it may straddle two — accepted, the pilot can see for himself inside a kilometre |
| the infantry pair `EAGER` was introduced for | 260 m | admitted, 1.9× margin |
| measured nearest-neighbour spacing, distinct objects | median 16 m, p75 55 m, **p95 342 m** | admitted at p95 |
| measured cluster-to-cluster separation, 100 m link | median 236 m, **p75 378 m** | *under* the cap, so two clusters a denser rule would keep apart can still merge — the accepted latitude |
| in this module's own unit-widths currency | 500 / 1.8 = **277.8** infantry unit widths vs 20 | stated in metres because what it bounds is a *spoken* extent |

Spacing figures from `plans/post-review-fixes/explore-notes.md` §2.

**What would falsify it** (both observable only once Stage 1's group-identity trace line exists):
two infantry groups the pilot thinks of separately, under 500 m apart, spoken as one; or a real
infantry group more than 500 m across that stops being reported at all.

### Equal to the installation cap by coincidence

`GROUP_REPORTING_INSTALLATION_COHESION_CAP_M` is also 500.0, from unrelated evidence (real S-75/S-125
launcher spacing, ~60–230 m). Kept as **two** constants, and
`test_the_eager_cap_and_the_installation_cap_do_not_move_together` drives that by **mutation**:
monkeypatching either constant must move its own path's backstop and leave the other's alone.
Comparing the two numbers would have passed whether or not the paths are wired separately.

### The cap bounds a pair, not a cluster

Single-link chaining still lets four infantry at 400 m spacing cohere across 1 200 m
(`test_the_eager_cap_still_chains_a_long_infantry_line`). That is `_cluster_contacts`' documented
convoy property and not what 0b narrows. **Pinned deliberately**, so a future reader does not
rediscover it as a defect: if a sortie shows a chained infantry line spoken as one thing at an
unbelievable width, the fix is a cluster-extent rule, not a smaller cap.

### Counterfactual (run)

Set the cap back to `math.inf`. The three Stage 0b behaviour tests and the constants pin went red;
the rest of the suite stayed green. Restored by `shasum`
(`34465a177b8d64d907fca99d3c0beb0179b65c83`).

---

## BL-B51 — one set, one guard (`b9632e4`)

`belief.groups.AIR_DEFENSE_OP_CLASSES`, `belief.crew_console._AIR_DEFENCE_OP_CLASSES` and
`eyesight_view._AIR_DEFENCE_CLASSES` → **`belief.classification.AIR_DEFENSE_OP_CLASSES`**.

**Home chosen as `belief.classification`**, not `object_model` and not `groups`:

- every consumer resolves through `parent_class_of`/`_op_class_of`, which live there — `BL-B47`'s
  boundary decision, and load-bearing rather than tidy: `_op_class_of` early-returns any non-default
  `OP_*` string, so a *class*-level belief carries the `OP_*` value itself and matches no keyword.
  Four of the five classes fail a `profile_for`-based test at class level.
- `crew_console`'s own comment argued against `object_model` — *"which classes a crew command treats
  as air defence is a command-vocabulary question"* — and that argument still holds. Its reasoning is
  preserved in place rather than deleted.
- `classification.py` imports only `object_model`, so there is no cycle, and all three consumers
  already imported it.
- `groups.py` **never read the set**, so moving it out of there changes no behaviour. Its own
  installation cap asks the narrower `installation_component`-on-both question and is untouched.

**Guard verified by mutation against the real tables.** Injected
`("sa-99 fakeinject", ObjectTypeProfile(size_m=9.0, op_class="OP_XLRSAM"))` into
`_REPORTING_NAME_KEYWORD_PROFILES`:
`test_air_defence_classes_cover_every_air_defence_class_in_the_object_model` went **red**, everything
else stayed green. Restored by `shasum` (`17eb80706052dd3814cd56ad435a6fce3f9b5141`).

`test_groups.py`'s `== frozenset({five literals})` assertion was **removed with the set** rather than
moved: it is a change *detector*, silent when `object_model` grows underneath it, which is the only
direction that loses coverage. A companion test,
`test_the_drift_guard_fires_on_a_new_air_defence_class_and_a_pin_would_not`, asserts that property
directly, with the naming predicate written out separately rather than imported so a change to the
real predicate cannot make both tests agree about nothing.

**The name keeps the American `DEFENSE` spelling** against the project's usual British, deliberately:
it means `belief.speech` changes only its import line. Counted by `grep` over that file: **4 code
references** — 1 import plus 3 uses, in `_summary_air_defence_clause`,
`_summary_air_defence_freshness_clause` and `_is_air_defence` — and **4 docstring mentions**, two of
them inside `_is_air_defence`, which `BL-13` fixed the day before. Two docstring references were
repointed `belief.groups.` → `belief.classification.`; no logic in that function or in `BL-13`'s pull
path was touched.

Line numbers are deliberately not cited anywhere for these: the commit message for `b9632e4` gives
four of them and **all four are already wrong**, because `ruff`'s import sort moved the import inside
this same change (`:216` → `:202`) and one docstring mention is hyphen-split across lines so `grep`
does not see it. The decomposition (1 + 3 code, 4 docstring) is the measurement; the offsets were
noise that went stale within one commit.

`crew_console`'s old `<=` test was replaced **in place** by a wiring test:
`test_watch_nearest_air_defence_resolves_through_the_one_shared_set` asserts the command's predicate
answers yes across the whole shared set and no for the three profiled non-air-defence classes. That
is what the consolidation can break and what the drift guard does not cover.

---

## Files changed

| file | what and why |
|---|---|
| `body-layer/src/belief/groups.py` | 0a: `_pair_backstop_m`'s eager branch takes `and`, not `in (…)`. 0b: `GROUP_REPORTING_EAGER_COHESION_CAP_M` added and returned in place of `math.inf`. B51: the air-defence set removed, replaced by a note on why the installation cap is a different question. |
| `body-layer/src/belief/classification.py` | B51: hosts `AIR_DEFENSE_OP_CLASSES`, the one copy. |
| `body-layer/src/belief/crew_console.py` | B51: local copy removed, imports the shared set; the "why not `object_model`" and `OP_LRSAM` history kept in place. |
| `body-layer/src/eyesight_view.py` | B51: local copy removed, imports the shared set; its false "only eight `OP_*` values" count corrected. |
| `body-layer/src/belief/speech.py` | B51: import line + 2 docstring references repointed. No logic. |
| `body-layer/tests/test_groups.py` | the bridging test inverted; 4 Stage 0a acceptance tests, the mixed-pair equivalence, 4 Stage 0b tests; the air-defence pin removed. |
| `body-layer/tests/test_classification.py` | B51: the `<=` drift guard, moved here, plus its `==`-is-not-a-guard companion. |
| `body-layer/tests/test_crew_console.py` | 0a: new `_cohering_contacts_across_a_band_boundary` fixture for the leak test; `_in_scope`'s stale cohesion claim corrected. B51: import repointed, `<=` guard replaced by a wiring test. |
| `body-layer/tests/test_callouts.py` | 0a: the 2C transcript fixture's expectation and two docstring paragraphs. |
| `body-layer/tests/test_speech.py` | B51: import repointed. |

---

## Test-impact: both kinds of mismatch, per the role's step 1b

The amendment named only *"`tests/test_groups.py`'s `test_constants_are_the_stated_assumptions` gains
any new constant from 0b"*. That is the one entry it got right. **Three other tests changed, two of
them in files the amendment never mentions.**

1. **`test_groups.py::test_infantry_eager_policy_bridges_a_non_infantry_pair_that_would_not_merge_alone`
   asserted the defect**, at 230 m rather than 6 km. Inverted and renamed. (Escalation rule
   "existing tests must be rewritten rather than extended" applies; the user's binding decision 1
   makes the asserted behaviour wrong, so inverting it *is* implementing the decision — flagged
   rather than done silently.)
2. **`test_callouts.py::test_2c_transcript_fixture_renders_four_lines_not_seven`** cohered through
   the bridge. Its five-member group (3 infantry + BTR-70 + truck) is now **two infantry-only
   pairs** — `CONTACT_1`/`CONTACT_3` and `CONTACT_6`/`CONTACT_7`, dumped from the run. Still four
   lines; line 3 changed and line 4 is new. The **grouping is now asserted beside the sentences**,
   because the line count alone would pass over a single five-member group. Measured line timings:
   t=0, 4, 9, 14. The 2-o'clock pair (founded t=12) says nothing inside the window — recorded as
   observed, no mechanism claimed.
3. **`test_crew_console.py::test_slotted_report_summary_does_not_leak_an_out_of_scope_group_member`**
   — **the important one, and it was caught by its own guard.** The test asserts
   `len(store.groups) == 1` with the comment *"without it this test would pass while exercising
   nothing"*, and that assertion is what fired: `_three_banded_contacts` (armor 1 km / truck 3 km /
   infantry 7 km) **only ever cohered through the `BL-B48` bridge**. Without the guard the test would
   have gone green over an empty group set and silently stopped testing the leak.

   Repaired with a new fixture rather than by weakening the test:
   `_cohering_contacts_across_a_band_boundary` coheres on the **ordinary** rule with no eager
   latitude anywhere in it (armor↔truck ~100 m against 130 m; truck↔infantry ~70 m against 78 m)
   while straddling the 2 km band boundary — a *stronger* fixture for the leak than the original.
   `_three_banded_contacts` is left exactly as it was; its own two tests assert band filtering and
   labelling and never read a group.

Nothing else in the suite moved. `grep` over the suite for consumers of `belief.groups`
(`test_speech`, `test_crew_console`, `test_contacts`, `test_callouts`, `test_groups`, `test_tools`)
found no further fixture depending on an infantry bridge, and Stage 0b broke nothing at all outside
`test_groups.py` — so no other fixture's grouping depended on an unbounded infantry pair either.

---

## Checks

**body-layer/**

- `ruff format --check`: **pass** (`ruff format src tests` → 118 files unchanged)
- `ruff check .`: **pass**
- `mypy src` (`--strict`, from inside the subproject): **pass**, 54 source files
- `pytest`: **pass** — **1643 passed / 4 xfailed** (baseline at `bae8963`: 1632 / 4; +11 net)

**audio-adapter/** (untouched by this change; run because the task asked)

- `ruff check .`: **pass**
- `mypy src`: **pass**, 15 source files
- `pytest`: **pass** — **255 passed / 1 skipped** (matches baseline)

---

## What the amendment got wrong, and other notable discoveries

1. **The amendment's test-impact list was one entry long and missed two files**, one of which
   (`test_crew_console.py`) was only saved from going silently hollow by a guard assertion a previous
   author had put in for exactly this reason. That guard is the single most valuable line in this
   whole task.
2. **`body-layer/docs/STRUCTURE.md` has no `src/belief/groups.py` entry at all.** The task said to
   read it before modifying the module; `grep` for `belief.groups`, `GroupStore`, `_pair_backstop`,
   `CohesionBackstop` and `AIR_DEFENSE_OP_CLASSES` over that file returns **nothing**. The module's
   *why* lives entirely in its own ~180-line docstring, which is where this change recorded its
   reasoning. `clustering.py` does have an entry and it was read; it is a different module and was
   not touched. **Writing a `groups.py` entry was out of Stage 0's scope and is left flagged.**
3. **`eyesight_view.py`'s retired copy carried a false count**: its five values were described as
   *"the only eight `OP_*` values that table assigns"*. Wrong twice over — eight while listing five,
   and `object_model` assigns **9** distinct `op_class` values (`_KEYWORD_PROFILES`' 70 entries carry
   9, `_REPORTING_NAME_KEYWORD_PROFILES`' 61 carry 6, union 9; `DEFAULT_OP_CLASS` =
   `OP_GROUPSOMETHING` makes 10 reachable values). Corrected with the decomposition.
4. **The Stage 0a commit itself shipped one false reference**, caught and fixed in the Stage 0b
   commit: a docstring named
   `test_infantry_eagerness_is_bit_identical_for_an_infantry_only_scene`, which does not exist. The
   real name is `test_infantry_only_scene_keeps_identical_thresholds_and_unions`. Recorded because it
   is precisely the failure the implementer role's "say what would make X false" section is about,
   and it survived one commit.
5. **`_observation_for_follow`'s `range_m` is the reported range exactly**, because
   `_enrichment_context` stubs `project_terrain_aware` to a passthrough — and because all contacts in
   such a fixture sit on one radial, **member spacing is the `range_m` difference**. That is what
   makes 100 m / 70 m member spacing and a 2 km band boundary coexist in one fixture. Measured, not
   derived; an earlier attempt that reasoned from `_xz_for_clock` geometry put all three contacts in
   the `near` band.
6. **`AIR_DEFENSE_OP_CLASSES` keeps an American spelling in a British-spelling codebase**, chosen so
   the consolidation does not sweep `BL-13`'s just-landed pull path. A rename is a clean, separate,
   zero-risk commit whenever someone wants it.

## Not done, deliberately

- **Stage 1** — no group-identity matching, no `remembered_groups`, no trace line. The trace line
  (amendment A4) remains Stage 1's first commit; nothing here makes it harder, and Stage 0 touched no
  natural site for it.
- **`BL-B48` / `BL-B51` roadmap entries** are left `#status/open`. Closing them is a roadmap update,
  not an implementation step.
- `decay.py` untouched. `speech._is_air_defence`'s logic, `render_report_summary`, `_report_scope`,
  the freshness marker and the word budget untouched — the only edits in that file are an import line
  and two docstring module paths.
