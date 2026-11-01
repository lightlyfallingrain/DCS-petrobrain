# Expected-area check — plan (`BL-B110`)

Architect pass 2026-11-01, on `feature/expected-area-check` at `e78305a5`. Inputs:
`explore-notes.md` (the user's own words; the last section, "Goal-check answers", governs),
`alignment.md` (goal check CONCERNS, E1–E8, findings 1–6, Q1–Q5 now answered), `BL-B110.md`, and
`plans/relative-distance-grouping/` (BL-B108, the base). No new DCS-internals claim is
load-bearing. The one DCS call this plan might add, `land.isVisible` between two arbitrary points,
is already used point-to-point by `petrobrain-line-of-sight-hook.lua` (`terrainClear(fromPoint,
toPoint)`), and its cost is measured in `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`.
So no investigator pass was needed.

### Goal

When a new sighting B lies on the bearing of a group A that Petrovich holds only in memory, he
does not silently fold B into A. Same-or-different is settled by what he perceives, ideally by
looking where A should be. The pilot then hears the right number of groups in the right places.
His binocular use moves to a per-sector rhythm: sweep a sector by eye, glass what is worth
glassing there, then move on.

### Read this first: what the measurement says about effort and value

The **trigger** decides whether a fold is ambiguous. It re-evaluates BL-B108's gate as if A had
been in this very look. The plan's whole shape follows from probing that trigger on BL-B108's own
sweep harness (scratch probe, 200 field realisations per cell, shipped code):

| case (memory-only, gap 6 s) | honest gate folds | trigger catches | residual fold |
|---|---|---|---|
| different groups, far binocular → near unaided, 4.5/3.0 km | 68% | 68% | 0% |
| same, 5.0/3.5 | 85% | 84% | 1% |
| different groups, far unaided → near binocular, 4.5/3.0 | 70% | 44% | 26% |
| same, 5.0/3.5 | 74% | 48% | 26% |
| same, 3.0/1.5 and 4.6/2.4 | 20% / 32% | 16% / 24% | 4% / 8% |
| different groups, same optic, any cell | 0–1% | 0% | 0–1% |
| **same group** re-seen through the gate, cross-optic, 2–4.5 km | 100% (correct) | **4–10% (false)** | — |
| same group re-seen, same optic | 100% | 0% | — |

Three things follow.

1. **Most of the pilot value is cheap.** Founding B as a new contact whenever the trigger fires,
   and calling it out at once, removes most of the 0–86% fold. That is user Q3's own fallback
   ("call B as new"). It costs a 4–10% chance of a duplicate contact when the *same* group is
   re-seen through the gate across optics. The gate path is rarer in flight than in this harness,
   because the object-permanence shortcut (`OBJECT_ID_MEMORY_S` = 600 s) re-attaches any group
   seen again within ten minutes before the gate is reached.
2. **The look at A's area cannot change what the pilot hears unless "A's area was seen empty" is
   a conclusion Petrovich can honestly draw.** Without that, the look has only two outcomes: "A
   seen there, so B is different" and "couldn't tell, so B is new" (Q3). Both call B out as new.
   The hold would buy only delay. So the expensive part of the feature is not the look. It is
   knowing **whether A's expected place was visible at all** (E5: terrain, trees, cockpit). Today
   nothing in body-layer can answer that for an empty patch of ground. DCS line-of-sight is
   per-object, the world-model offline LOS is testing-only by standing user direction
   (2026-10-05), and the forest model covers trees only.
3. **What the full check buys on top of point 1:** it removes the 4–10% duplicate rate, and it
   gives the pilot "A has moved, now …" and "A is no longer where it was" (Q4). That is real but
   narrow. It also needs a new cross-subproject channel (a point line-of-sight query through the
   Hook) and a contact-removal mechanism `ContactStore` has never had.

**So the plan is staged so the cheap, high-value part ships first, and the full check is built
only after the user has seen the measured numbers and chosen how visibility is judged.** The
user's direction for the full check is recorded in Stages 3–4 below and is buildable as written.
It is gated, not dropped.

### Affected Modules / Files

Stages 0–2 (definite):
- `body-layer/src/belief/optic_policy.py`: per-sector phase cycle; multi-look glass step; sector
  target filter; docstring rewritten (it describes the 2026-09-23 reading). New fields on
  `OpticState`.
- `body-layer/src/perception/gaze.py`: `ScanPlan` gains a one-pass sweep anchor
  (`sweep_legs`, `sweep_started_sim`), and `gaze_at` honours it. A public sector table derived
  from `SCAN_PLAN`.
- `body-layer/src/body.py`: build the sector-anchored plan once per poll for every `gaze_at`
  consumer: the naked-eye source, the LOS look-direction push and the debug/eyesight views. Pass
  the sector period, wedge and count to `decide_optic` instead of the hard-wired
  `SCAN_CYCLE_PERIOD_S`. Reset the sector on a scan-command change.
- `body-layer/src/tuning.py`: `_check_scan_decay_coupling` extended to cover the glass budget.
- `body-layer/src/belief/association_over_time.py`: `passes_gate` gains a keyword
  `as_if_optic_class: str | None = None`. The trigger is that one keyword; there is no new
  formula.
- `body-layer/src/belief/contacts.py`: `ingest` founds B instead of folding when the trigger
  fires, and records the believed-distinct pair.
- `body-layer/src/belief/callouts.py`: merge-echo suppression skips a believed-distinct pair.
- Tests: `test_optic_policy.py`, `test_gaze.py`, `test_body.py`, `test_decay.py`/`test_tuning.py`
  (coupling), `test_relative_distance_sweep.py`, `test_relative_distance_scenarios.py`,
  `test_callouts.py`, and a new `test_expected_area_trigger.py`.
- `body-layer/docs/STRUCTURE.md`, `config/defaults.toml` (regenerated).

Stages 3–4 (conditional, after Decision 2):
- Visibility source: `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`,
  `aircraft-layer/src/schema/line_of_sight.py`, the collector and API, and `body-layer`'s aircraft
  client. Exact list per Decision 2.
- New `body-layer/src/belief/expected_area.py`: check state, verdict function, actions.
- `contacts.py` (provisional contact, relocation, removal), `callouts.py` (hold, age-from-release),
  `groups.py` (`reconcile` excludes held contacts), `mission_memory/admission.py` (skip held
  contacts), `events.py`/`speech.py` (two new kinds), `body.py` (area look report, ATGM pause).

### Implementation Plan

**Stage 0 — Measure, then fix the trigger's definition (no behaviour change).**
- Turn the scratch probe into `tests/test_expected_area_trigger.py`, an ensemble over the salt seam
  with BL-B108's `_observation` shape. It reports the three numbers in the table above, plus a
  **long-gap** grid: same group, gaps of 120 and 600 s (stationary, then moving at
  `plausible_speed_mps`).
- Tune the trigger's hypothesis so the far-unaided → near-binocular residual drops without raising
  the same-group false-trigger rate. The candidate to try first is evaluating the hypothesis σ at
  the **tighter** of the two optics, not the look's own. The table, not reasoning, decides it
  (`feedback_noise_field_sweeps_need_an_ensemble`).
- **Gate for proceeding:** record the final residual and false-trigger rates in this plan before
  Stage 2 is implemented. If the false-trigger rate exceeds ~10% in any cell, stop and bring it to
  the user, since that is the duplicate rate they would hear.

**Stage 1 — Per-sector scan order (user Q1). It ships on its own and changes behaviour for every
contact.**

*What the code does today (verified, not taken from the docstring):*
- A glass phase starts only when `now − phase_started_sim ≥ scan_cycle_period_s`, and `body.py`
  passes **`SCAN_CYCLE_PERIOD_S` (16 s) unconditionally**. So the docstring's claim, and
  binocular-optic D2's, that a commanded o'clock sector "brings binoculars round sooner" is
  **false in flight**. `test_a_faster_scan_plan_brings_them_round_sooner` exercises `decide`
  directly with 4 s and has never been wired. This is a wiring defect that ships fixed as a side
  effect.
- A glass phase is **one look** (one chosen centre; every contact in the field of view benefits).
  It then returns to `SCANNING` and waits a fresh 16 s. **At most one binocular look per ≥16 s.**
- The free scan's gaze is `t_sim % 16`, absolute. It does not pause while binoculars are up, so
  after a look the eye resumes wherever sim time has reached.
- Every live contact is a candidate. There is no sector restriction.
- The original 2026-09-23 words were *"First complete the **current sector** naked eye scan"*.
  The implementation read "sector" as the whole free cycle. Q1 corrects that reading.

*New behaviour:*
- **Sector.** Free scan: `SCAN_PLAN` in consecutive chunks of `SCAN_SECTOR_LEG_COUNT` (default 4),
  so `(12,11,10,9)` and `(12,1,2,3)`, 8 s each. The table already is two sweeps out from 12.
  Commanded scan: the commanded legs are one sector (ahead `11,12,1`, one o'clock hour, compass
  legs). See Decision 1.
- **Sweep.** `SCANNING` sweeps the current sector once, from its first leg, anchored at
  `phase_started_sim`. The scan clock pauses while glassing, so no leg is skipped or repeated. This
  is a `ScanPlan` one-pass anchor, resolved in `body.py` once per poll and handed to every `gaze_at`
  consumer, so the LOS look-direction push, the naked-eye source and the eyesight view (E4: where
  he actually looks) cannot disagree. The push runs before `decide`, so it can lag one poll at a
  sector boundary. That is harmless at the push's ±90° cone, and stated.
- **Glass step**, at the sector's end: targets are contacts whose believed body azimuth lies in
  the swept sector's wedge (union of its legs' ±15° cones) and that pass the unchanged
  `is_worth_a_look`. That is the user's "new contacts in sector and units that plausibly could get
  a better identification": new contacts in their improvement window, plus the existing
  range/time retry rules. Looks run back to back (`choose_look` per look, unchanged) until none is
  left or `GLASS_STEP_MAX_S` is spent. Each look's own cap is `min(MAX_LOOK_S, remaining budget)`,
  so the bound is strict. Then the next sector.
- Nothing worth a look → straight on to the next sector, with no pause. A commanded narrow sector
  with nothing to resolve still gets its binocular search (`SEARCHING`) at the end of the pass, as
  today.
- An interrupted step (unsteady, or the pilot's command calls `lower_binoculars`) ends the step and
  advances the sector. Pending marks drop as today (Fix B1).
- **Unchanged:** everything with `home_phase is SIGHTING` (the 9K113 has its own dwell/glance
  cycle; the glance-away `SCANNING` sub-state is a different branch), `_apply_guidance` (attack-run
  optic override), and the retry constants.
- New tunables, `belief.optic_policy.`, `status="judgement"`, `#needs-flight`:
  - `GLASS_STEP_MAX_S`: 6.0 (lo 2.0, hi 7.0). First sentence: *"The longest Petrovich keeps
    binoculars up after sweeping one sector by eye, before moving on to the next."*
  - `perception.gaze.SCAN_SECTOR_LEG_COUNT`: 4 (lo 1, hi `len(SCAN_PLAN)`). `hi` must be an AST
    literal, so use 8 and validate the cross-key case in the coupling check.
- **Cross-key coupling (an X-T26 trap, so checked, not commented):** extend
  `tuning._check_scan_decay_coupling` so that the worst revisit of any leg, `len(SCAN_PLAN)·
  FOCUS_DWELL_S + n_sectors·GLASS_STEP_MAX_S`, stays below `POSITION_HALF_LIFE_S`. Defaults give
  16 + 2·6 = 28 < 30. Today's worst case is 16 + 6 = 22.
- `decide`'s `scan_cycle_period_s` becomes `sector_period_s` plus the sector wedge and count. That
  is a mechanical rename across ~130 test call sites.

*Downstream effects, named:*
- **Callout timing:** a new contact is glassed up to 8 s after its sector sweep ends, not up to
  16 s. `CONTACT_CLASSIFICATION_CHANGED` follows `CONTACT_DETECTED` sooner and more often. The
  scheduler's one-line-at-a-time rule is unchanged, so this is a denser stream, not a backlog.
- **Coverage:** the worst full revisit goes from 22 s to 28 s, against a 16 s `OBSERVED_WINDOW_S`.
  A flank contact drops out of "observed" phrasing for longer whenever both sectors glass. Measure
  it in the Stage 1 scenario test. If it shows in speech, derive `OBSERVED_WINDOW_S` from the
  worst revisit rather than the bare cycle (one line, same coupling check).
- **9K113:** no change while OBSERV is on. After "Observ off", scanning restarts at sector 0 (see
  Co-moving Fields).
- **Commanded sectors** really do bring binoculars round faster now: one o'clock hour means a look
  after every 2 s pass. This is the user's own 2026-09-23 *"o'clock scan is faster, allowing more
  frequent binocular use"*, now true in flight.

*Tests that must be rewritten, not extended (escalation item, Decision 3):*
`TestPhaseCycle`'s premise is "a look only after a completed full cycle". It covers
`test_binoculars_are_not_raised_mid_scan` (becomes mid-*sector*),
`..._come_up_at_the_end_of_a_completed_scan`, `test_a_faster_scan_plan_brings_them_round_sooner`
(now a body-level wiring test), `test_nothing_worth_looking_at_restarts_the_scan` (now advances
the sector), and `test_the_scan_must_complete_again_before_the_next_look`. The last one's premise
is **reversed**: two looks may now follow each other inside one glass step. Its replacement asserts
that the eye must sweep again **between glass steps**. `test_gaze.py`'s free-scan cycling tests
stay, because `FREE_SCAN_PLAN` without an anchor keeps today's absolute indexing for non-optic
callers. The other ~120 call sites are the rename only.

New tests:
- sector boundaries and order
- the scan clock pauses during glassing (no leg skipped)
- the target filter is limited to the sector
- multi-look step under budget, with the strict bound
- interrupt advances the sector
- command change resets to sector 0
- the commanded-sector cadence through `body.run_once` (the wiring test the old test never was)
- the coupling check rejects a violating `tuning.toml`

**Stage 2 — Never fold an ambiguous memory-only match (E1 delivered, Q3 as the default).**
- **Trigger** (`ContactStore.ingest`, gate branch only, never continuity), all of:
  - the percept resolves through the gate onto A: the single passing candidate, or the
    within-group ambiguous-fold target;
  - A is not claimed by any observation in this poll (A was not in this look);
  - `passes_gate(percept, A, now, as_if_optic_class=<Stage 0 choice>)` is **False**. That means:
    had A been in this very look, this percept would read as a different thing.

  Perceived quantities and model parameters only, the same correlation helper as BL-B108, no new
  constant.
- **Action:** found B as a new contact, not a fold. Record `(B, A)` as believed-distinct on the
  store.
- `CalloutScheduler._is_merge_echo_of_earlier_contact` skips a believed-distinct pair. Without
  this, B is founded and then **silenced** as A's merge-echo, because A is earlier-founded,
  not lost and "plausibly same". That would be a second silent path to the same defect.
- B is called out at once. The verdict is known: Petrovich cannot tell, so B is new (Q3, and
  "less noise" is not served by waiting for a look that cannot conclude "same").
- Unchanged: A, the AD carve-out (D6), groups (1.5 km is past every cohesion cap), mission-memory
  admission (B gets its own entry, BL-B108 Q4).
- Tests:
  - `test_relative_distance_sweep.py`'s memory-only fence ceilings are **lowered** to the Stage 0
    residual + 10 points. That is data, not premise.
  - Add a cross-optic same-group **false-split fence** at the Stage 0 rate + 5 points.
  - E1a in `test_relative_distance_scenarios.py` asserts two callouts **spoken**, cross-optic and
    memory-only.
  - A merge-echo test: a believed-distinct B is spoken.
- **`test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact` asserts exactly 100%.**
  Under Stage 2, the gate-only harness measures 90–96% at the cross-optic cells. That guarantee
  must be restated as a fence (Decision 3). It is the one E2/E3 trade this stage makes, and it is
  the direction the user chose in Q3.

**Stage 2b — Terrain landmarks: measure, do not build (user, earlier Q4).**
- After Stage 2, the residual fold on the harness is the Stage 0 table's last column (0–26%,
  worst far-unaided → near-binocular at 4.5–5 km). That is exactly the cross-optic, across-time
  case alignment finding 4 says an anchor would help.
- The harness cannot model a landmark, so it measures the residual, not an anchor's effect. That
  is the honest limit.
- **Proposal rule:** if, after Stage 0 tuning, any clear-case cell's residual stays above 10%,
  open a follow-on entry (`/explore` first) for anchor-relative placement, using world-model
  `describe_position`/`nearest_features` around A and B. Otherwise record the residual on
  `BL-B110.md` and stop. Nothing is built in this feature.

**Stage 3 — Was A's expected place visible? (conditional: Decision 2, after Stages 0–2 numbers.)**

"Seen empty" requires all of:
- the look ran to its natural end, steady;
- A's expected area lies within the look's sweep envelope, and its angular half-width (A's
  believed position, `LOOK_SWEEP_SIGMA`·bearing σ, plus growth at `plausible_speed_mps(A)` since
  last seen) is at most `EXPECTED_AREA_MAX_HALF_WIDTH_DEG` (new tunable, default 15°, lo 4.25, hi
  30). Past that, one look cannot cover the area, and the check is "cannot look";
- inside the cockpit mask;
- A's believed type is within that optic's detection range at A's expected range
  (`visibility.tier_ranges` on `profile_for(A.last_class_raw)`);
- not in forest by the world-model landcover (map knowledge, as `perception/forest.py` already
  reads it);
- **terrain-clear** from the eye to A's believed point, and to the two along-line ±2σ points.

The last item needs Decision 2's source. With the recommended option, the Hook takes up to N
probe points per poll on its existing inbound channel and returns `terrain_clear` for each,
computed by `land.isVisible(eye, point)` with `land.getHeight` for the ground. The verdict
arrives one Hook poll later (~1 s). **Fail closed:** no answer means "cannot look", never "empty".

**Stage 4 — The expected-area check proper (conditional on Stage 3).** All of the user's Q2–Q5
answers, as designed below.
- **Check state** (`belief/expected_area.py`): `ExpectedAreaCheck(b_id, a_id, opened_sim,
  sector_index, a_area, b_released: bool)`, held on `ContactStore`. Stage 2's trigger now opens a
  check instead of releasing B.
- **The "when" lives in one pure function.** `resolve_checks(checks, store view, area_look_reports,
  now, pause) -> list[Verdict]` is called from `ContactStore.tick`. It sits beside four actions,
  each doing one thing:
  - `release_as_new(B)`
  - `relocate(A, from=B)`
  - `mark_absent(A)`
  - `hold(B)`

  It reads three state params:
  - `store.callout_held(id)`
  - `store.expected_area_targets()`, LookTargets flagged `area_check=True`
  - `optic_state.area_look_report`, a frozen report of the last finished look: envelope, steady,
    natural end, the contacts seen in it

  That keeps the "when" away from the actions (root `CLAUDE.md`, behaviour as actions).
- **The look.** It is not a new act. A's expected area is a `LookTarget` in the same sector's glass
  step. `choose_look` ranks `area_check` targets first, then watched, then coverage (unchanged
  below that). B is also a target. The user's "B first, then A": when B and A's area fit one
  binocular field, one look covers both. That is alignment finding 3, the usual case at 50–800 m
  AGL (0.6° apart at 100 m AGL against a 4.25° half-field). Otherwise B's look comes first, then
  A's. An area look ends when A is observed, or when its sweep has held each step for ≥ one poll,
  or at its cap. It is not "nothing left to improve", which would end it on its first poll for an
  already-typed A.
- **Hold bound, stated in sector terms:** B's verdict is due at the end of the glass step of the
  sector in which B was detected, plus one poll for the LOS answer. That is a structural bound, not
  a timer, the same way 2026-09-23's lockout was made structural:
  - free scan: ≤ remaining sweep (≤ 8 s) + `GLASS_STEP_MAX_S` (6 s) + 1 s ≈ **15 s worst**, about
    7–10 s typical;
  - one o'clock hour: ≤ 9 s.

  Past that → Q3: release B as new.
- **`CALLOUT_MAX_AGE_S` (10 s) would silently kill a held callout**, since it retires on age from
  `event.t_sim`. So:
  - the hold check sits **before** the age check and defers without consuming;
  - a released contact's events age from `max(event.t_sim, released_sim)`.

  E3's "a held callout must never quietly become no callout" is a test, not a comment.
- **While held, B is excluded from** `GroupStore.reconcile` (like `lost`) and from mission-memory
  admission. B still gets glassed and still accumulates classification.
- **Verdicts:**

| evidence at the verdict | verdict | pilot hears |
|---|---|---|
| A observed during the area look (any channel) | different: release B | B as a new contact; A not re-announced (E1) |
| area seen empty (Stage 3), composition compatible, displacement plausible | same: `relocate(A, from=B)`, remove B | Q4a: A's line with its new place (wording: Decision 4) |
| area seen empty, composition or displacement not plausible | different: release B, `mark_absent(A)` | B as new, then Q4b: A no longer at its last place |
| cannot look: not viewable, too large, interrupted, step over, deadline | release B as new (Q3) | B as new; A untouched (E5: not seen ≠ empty) |
| B is a threat type (AD `op_class`) or B fires | release B immediately (Q2); check continues | B now; a later "same" relocates A and speaks Q4a |
| ATGM run engaged or attack-run optic grant standing | all open checks resolve "cannot look" at once (Q5) | B on what is known; `hold_routine` still governs speech in missile flight |

- **Composition (E7):** count ratio of the believed intervals' midpoints ≤ `COMPOSITION_MATCH_RATIO`
  (new, default 2.0: 3 vs 5 compatible, 3 vs 8 not), plus the existing class compatibility. It
  decides only between "same" and "different" once the area is seen empty. It never decides
  without a look.
- **Displacement (E6):** `contacts_plausibly_same(A, B)` with A's covariance grown at
  `plausible_speed_mps(A's op_class)` (the existing one-table rate) over `B.first_seen −
  A.last_seen`. No new speed constant.
- **Relocation and removal** are the first contact-removal in `ContactStore`. The fields that must
  move together are under Co-moving Fields.
- New event kinds `CONTACT_RELOCATED`, `CONTACT_ABSENT`, in `_TEMPLATED_KINDS`, subject to the
  observability gate. `CONTACT_ABSENT` is spoken only if A was announced to the pilot before.
- Tests (scenario, 1 s polls): one per verdict row, the 15 s bound, age-from-release, the hold
  never dropping, a masked area ⇒ "cannot look" (not "empty"), the ATGM pause, a threat B spoken
  immediately, and every row of the Co-moving Fields table.

**Stage 5 — Docs, entry, test card.** `STRUCTURE.md`; regenerate `defaults.toml` and read the
**rendered** first sentences; `BL-B110.md` updated with what shipped and the measured residual;
the test card names `main` and `#needs-flight`. Cards:
- free scan, two groups on one bearing, far one glassed first, then crest a ridge;
- a commanded o'clock scan, listening for binocular cadence;
- Stage 4 only: a group that moves out of its area while hidden.

### Co-moving Fields

Built from construction sites (`grep -n 'OpticState(' body-layer/src`: two fresh constructions,
SEARCHING and GLASSING entry), plus every `replace(…optic_state…)` site in `body.py`. Two new
fields: `scan_sector_index`, and `glass_step_started_sim` (budget clock). Both fresh-construction
sites must carry both forward explicitly, the BL-B71 lesson.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `phase_started_sim`, `scan_sector_index` | first poll (`phase_started_sim is None`) | start | sector 0, sweep anchored now |
| `scan_sector_index`, `glass_step_started_sim` | internal (`decide`) | sector sweep ends, ≥1 target in sector | phase GLASSING, step clock = now, sector index **unchanged** until the step ends |
| `glass_step_started_sim` | internal | look ends naturally, budget left, next in-sector target | new GLASSING entry carries the step clock (**not** reset); pending marks committed for the finished look only |
| `scan_sector_index`, `phase_started_sim` | internal | step ends (budget, nothing left) or sweep ends with nothing to glass | index + 1 mod n, `SCANNING` anchored now, step clock `None` |
| same | **external**: `lower_binoculars` (player command) while GLASSING/SEARCHING | interrupt | as the row above (advance); pending marks dropped (Fix B1) |
| same | **external**: `lower_binoculars` while SCANNING-at-home | none | unchanged (existing `test_lowering_while_already_scanning_changes_nothing` stands) |
| `scan_sector_index`, `phase_started_sim` | **external**: scan command issued or cancelled (`command_t_sim`/sector identity changes; *not* compass legs recomputed from heading) | plan change | index 0; if SCANNING, anchored now; if GLASSING, the step finishes, then index 0 |
| `scan_sector_index` | **external**: OBSERV off (`body.py` observed edge, `_force_observ_off`) | SIGHTING → SCANNING home | index 0, anchored now, step clock `None` |
| `scan_sector_index` | **external**: OBSERV on | SCANNING → SIGHTING home | unchanged and unread while SIGHTING; step clock `None` |
| `hands_busy_until_sim` | external | any | no sector/step change (a suppressed poll advances nothing, as today) |

Stage 4 adds a second set: the contact-removal set for `relocate(A, from=B)`, to be grep-verified
at implementation.
- `ContactStore._contacts` loses B.
- `_observation_id_to_contact_id`: B's ids point to A, so continuity of B's objects lands on A.
- B's events are consumed.
- `ExpectedAreaCheck` is closed.
- A takes B's `position` (anchor included) through `dataclasses.replace` on the estimate, and its
  classification/cardinality are folded with the existing fold functions, never fresh-constructed.
- Any `attack_run`/`atgm_run` target id equal to B is re-pointed to A. This can only arise after a
  Q2 early release.
- `OpticState.attempted_*` and `CalloutScheduler` maps keyed by B: stale entries are harmless and
  are not cleaned. Tested, not assumed.

### Risks & Unknowns

- **Per-sector glassing changes what every sortie sounds like.** It doubles the possible binocular
  rate, brings identifications sooner, and makes classification-change lines denser. It is the
  user's direction, but it is also the largest behaviour change here and has nothing to do with
  BL-B110's own defect. That is why it ships alone (Decision 3) and gets its own card.
- **The Stage 0 false-trigger rate is the duplicate rate the pilot hears** after Stage 2. Gate-path
  same-group re-sightings occur only past the 600 s continuity window or when clusters re-form.
  How often that happens in flight is unmeasured. `sortie-log-triage` can count gate-path
  foundings near a remembered contact.
- **The far-unaided → near-binocular residual (up to 26%)** survives Stage 2, and Stage 4 does not
  touch it: no trigger, no check. Only a tighter trigger (Stage 0) or anchors (Stage 2b) reach it.
- **Stage 3 on the recommended option is cross-subproject Lua with a Windows-only verification.**
  It fails closed. The 1 Hz Hook cadence adds ~1 s to the hold.
- **Stage 4 introduces contact removal**, which this store has never had (architect memory
  `contact-dup-continuity-of-track`: "`ContactStore` has no contact-deletion mechanism at all").
  Every consumer of a contact id is a place a dangling id can surface.
- **Wording (Q4a):** Petrovich cannot tell "A moved" from "A was misjudged in range". Both
  produce the same verdict. "Has moved" asserts motion he did not see.
- **Revisit time 28 s** sits close to `POSITION_HALF_LIFE_S` (30 s). The coupling check keeps a
  tuned file from crossing it, but the defaults leave 2 s of margin.

### Second-order effect

Stage 2 makes two groups on one bearing reliably two contacts across optics. That is the
precondition `[[BL-B109]]` ("second group, beyond") named for itself, so this unblocks it. Stage
4's Q4a line is the same wording problem, and the two should be explored together. Stage 1's
per-sector glass step is also the slot a future 9K113-at-home check (OBSERV on) would reuse
through `choose_sighting_look`.

### How each alignment item is answered

- **E1**: Stage 2, for the cases the trigger catches; residuals in Stage 0's table.
- **E2**: Stage 2 trades a 4–10% gate-only false split, per Q3. Stage 4's "same" verdict removes
  it. Spread units found to be A's join A through the existing group cohesion.
- **E3**: Stage 2: no hold, immediate. Stage 4: structural bound and age-from-release.
- **E4**: Stage 1's single resolved plan feeds the eyesight view. Stage 4 area looks are ordinary
  looks.
- **E5**: Stage 3. Fail closed. Not seen ≠ empty.
- **E6**: `plausible_speed_mps` growth.
- **E7**: `COMPOSITION_MATCH_RATIO`, used only after a look.
- **E8**: Q2 and Q5 rows. `hold_routine` unchanged.

Open assumptions answered:
- **Trigger**: gate path, A not in this look, fails the as-if-same-look gate.
- **Which "remembered"**: any contact in the store, lost included. All are gate candidates already.
- **Hold**: per sector, ≈15 s worst.
- **Bound runs out**: Q3, B is new.
- **Optic**: the binocular glass step. The naked eye already had its chance in the sweep; the 9K113
  is the Q5 pause.
- **Area size**: A's σ plus speed growth, capped by `EXPECTED_AREA_MAX_HALF_WIDTH_DEG`.
- **Speed**: `plausible_speed_mps`.
- **Composition**: believed intervals.
- **Anchors**: Stage 2b.

### Decisions Requiring User Input

1. **What is a "sector" in free scan?** Recommended: the two halves of today's table, `12→9` and
   `12→3`, 8 s each. That gives a glass step after every half-sweep, and the worst revisit is 28 s.
   The alternative, per o'clock cone (a glass step every 2 s), would keep binoculars up most of the
   time, push the revisit well past 30 s, and break the decay coupling. Also: within one glass step
   Petrovich may glass several contacts back to back, with no eye sweep in between. Is that what
   *"binoculars on new contacts"* means (recommended: yes, capped at 6 s per step)?
2. **How should Petrovich judge that A's expected place was visible? This decides whether Stages
   3–4 are built at all.**
   - (a) **Recommended, if the duplicates matter:** a point line-of-sight query through the
     existing LOS Hook. This is the `look_around(x, y, alt)` you anticipated on 2026-10-05.
     `land.isVisible` is already used point-to-point there. It is honest, because it reports
     terrain, never units. Cost: Lua, wire, collector and client changes, plus a Windows
     verification.
   - (b) Cockpit mask, range and forest only, ignoring terrain. This is cheaper, but behind a
     ridge it will conclude "A moved" or "A gone" when it is not (alignment finding 2).
   - (c) **Neither for now:** ship Stages 0–2, fly, and count the duplicates with
     `sortie-log-triage` before deciding.

   **My recommendation is (c), then (a) if flights show duplicates.** Stages 0–2 deliver the
   nearer group being called out, which is the reason the feature exists. Stages 3–4 buy back a
   4–10% duplicate rate and the Q4 lines.
3. **Tests rewritten, not extended (`AGENTS.md` escalation).** `TestPhaseCycle`'s
   full-cycle-lockout premise (five tests) is replaced by per-sector equivalents, one of them
   reversed. `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact`'s exact 100% is
   restated as a measured fence (90–96% in the gate-only harness). Also confirm Stage 1 ships as its
   own merge ahead of Stage 2.
4. **(Stage 4 only) Wording of Q4a.** Petrovich cannot tell a move from a misjudged range.
   Recommended neutral form: *"That group — now two o'clock, three kilometres."* rather than "has
   moved". Settle it together with `[[BL-B109]]`'s `/explore`.
