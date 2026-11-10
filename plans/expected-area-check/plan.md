# Expected-area check — plan (`BL-B110`)

Architect pass 2026-11-01, on `feature/expected-area-check` at `e78305a5`. Inputs:
`explore-notes.md` (the user's own words; the last section, "Goal-check answers", governs),
`alignment.md` (goal check CONCERNS, E1–E8, findings 1–6, Q1–Q5 now answered), `BL-B110.md`, and
`plans/relative-distance-grouping/` (BL-B108, the base). No new DCS-internals claim is
load-bearing. The one DCS call this plan might add, `land.isVisible` between two arbitrary points,
is already used point-to-point by `petrobrain-line-of-sight-hook.lua` (`terrainClear(fromPoint,
toPoint)`), and its cost is measured in `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`.
So no investigator pass was needed.

**Revised 2026-11-01, second architect pass, on `d235775f`**, after the plan check and the user's
answers (`explore-notes.md`, "Plan-check decisions", which govern). What changed:
- **Stage 1's sector is a third of the free scan (left, ahead, right)**, not a half-sweep. That
  reshapes `SCAN_PLAN` and forces the glass budget down; the arithmetic is in Stage 1.
- **This feature ships Stages 0–2 (and 2b, which builds nothing).** Stages 3–4 and the point
  line-of-sight query are a separate entry, `[[BL-B111]]`. Their design stays below, marked as
  moved, so the reasoning is kept in one place.
- **Decisions 1–4 are answered**, with the user's words, in the last section. Decision 5 is new and
  comes from the three-sector arithmetic.

**Revised 2026-11-02, third architect pass, on `0b1920f5`**, after the plan re-check and the
user's answers (`explore-notes.md`, "Plan re-check answers", which govern). Stage 1 only; Stages 0
and 2 are unchanged. What changed:
- **Order: ahead first, sides alternating.** Today's default `SCAN_PLAN` `(12,11,10,9,12,1,2,3)`
  already is that path, so **the table is no longer reshaped**. It partitions into four sectors
  (ahead-left half, left, ahead-right half, right), 4 s each. 12 o'clock stays swept every 8 s.
- **Decision 5 ANSWERED, (b):** 12 s of binoculars per cycle, and the budget gates the *start* of
  a look, never its length. It is counted over the last four glass steps (rolling), because a
  per-cycle reset would let two budgets land in one flank revisit window.
- **Selectivity checked against the code:** classification and identification at the current
  range are already gated. Detection is correctly absent from free scan. The one gap, a look that
  taught nothing at this range being retried after 64 s, is closed with a `GLASSING` stall cooldown
  (the `BL-B85` mechanism).
- **Worst flank revisit 28 s nominal, 32 s with poll slack, against the 30 s half-life.** Decision
  6 (new, default proceeds) accepts the ≤ 2 s overrun and restates the coupling on the real cliffs
  (lost, group expiry).

**Revised 2026-11-02, fourth architect pass, on `2a0fe2b0`**, after the user's answers on mission
density, optics priority and approach profile (`explore-notes.md`, the last two sections, which
govern). Stage 1 only. What changed:
- **Location looks (user: *"do in stage 1"*).** Binoculars can now be raised to fix *where a group
  is*, not only what it is. The criterion is the expected down-range tightening a binocular look
  would give at the current range, from BL-B108's own model, judged per group. Location looks rank
  before classification looks. IFF, the user's (b), is not modelled and is not built.
- **Finding that changes direction: in today's belief model a location fix does not stick.**
  Measured on the shipped `fold_position`: a binocular look takes a 3 km contact from ±501 m to
  ±357 m, and the second naked-eye sweep after it puts it back to ±486 m. That is BL-B108's
  one-anchor floor, and BL-B108's own plan says to escalate rather than patch it. **Decision 7
  (OPEN, needs the user)**. Location looks are built only once it is answered. The rest of Stage 1
  does not wait for it.
- **Circling and sideways flight checked.** Sectors stay body-relative. The glass step filters on
  the azimuth at step time, with a margin of half a binocular field, and a look now follows its
  contact through a turn. Both are measured below. The scenario test flies the user's approach
  profile as well as a straight line.
- **Decision 6 ANSWERED:** *"For the overrun - ok."*

**Revised 2026-11-02, fifth architect pass, on `cad3783a`**, after the user's answer to Decision 7
and his refined priority (`explore-notes.md`, "Decision 7 and the refined priority", which
governs). Stage 0a is new; Stage 1's location looks are reshaped. Everything else stands. What
changed:
- **Decision 7 ANSWERED (a)** (*"Option a"*). The floor cap is **Stage 0a**, built first: BL-B108's
  tests re-run before and after, any moved fence stops the work, and Stage 0's table is taken on
  the post-0a code.
- **Priority 1, detection and rough location, needs no binocular look.** The rough-location
  allowance is defined from what the pilot hears (Stage 1, "Priority 1"). Measured on the shipped
  estimator, a naked-eye look is **never** worse than it, at any range from 0.5 to 6 km and any
  altitude from 0 to 800 m AGL, under every shipped tuning key. The scan is the whole answer.
- **Priority 2/3: a look toward type identification ranks before a look toward a class.** The
  ladder already makes that distinction, and `choose_sighting_look` already orders by it; the glass
  step reuses the same bucket. IFF is not built (`[[BL-B12]]`).
- **Priority 4, exact location, only for what the pilot asked about**: a *watched* contact
  (effective attention `watch`/`priority`). Enemy units: not modelled (BL-B12). Mission target
  units: no such notion exists in body-layer (checked). Ranked **after** classification, so
  **Decision 8 is REVERSED**. The fourth pass's "≥ 100 m tighter, every group, ranked first"
  criterion and its group reduction are dropped.
- **Binocular range sense: kept as is** (user: *"Binoculars range sense - keep the current."*).

**Revised 2026-11-03, sixth architect pass, on `a3758a2c`**, after Stages 0a/0/1 merged and the
user held Stage 2 (`explore-notes.md`, "Stage 2 decision": *"Hold it until the stationary-group
case is fixed"*). New **Stage 1b** (below Stage 0's results), the Stage 2 prerequisite. What
changed:
- **Finding that changes direction: the "long-gap stationary" STOP is not a gap effect.** It is a
  harness artifact. The harness re-salts the noise field per trial, but not the look-to-look draw
  or the per-look bearing noise, so each gap cell got one fixed draw. Resampled, the same-group
  false split is **15–20% in every binocular → eye cell, at every gap, including 6 s**. The 3–7%
  short-gap figure was a lucky draw, and the 25–27% at 600 s an unlucky one.
- **The fix: the trigger fires only when B reads nearer than where A should be.** It is one
  direction test on perceived quantities, with no new constant. Measured: same-group false split
  **3–6% in every cell**, and the worst-case catch unchanged (residual 1–3%). The cost is that a
  different group reading *farther* than A still folds, as it does today (Decision 12).
- **The fix belongs here, not in `[[BL-B112]]`.** A stationary contact's covariance already does
  not grow (installation growth is 0). That is why its cells show the full rate at every gap.
  BL-B112 would move observed-stationary armour into the same regime, so the acceptance grid
  includes zero-growth cells. That way BL-B112 cannot reopen this.

**Revised 2026-11-10, seventh architect pass, on `cd58ab76`**, after the gate-covariance fix
(`6096b2b2`, `plans/same-optic-gate-indefinite/debug.md`) and the harness fix. Every trigger number
taken before it is **superseded**: the "Read this first" table, Stage 0's residuals, Stage 1b's
candidate table, and Decision 12's figures. They are kept below, labelled, not deleted. What changed:
- **Honest grid** (after Stage 1b, "Honest grid, seventh architect pass"). The as-if trigger
  catches **5–15 points**, only bino → eye with B nearer. The cross-optic gate fold it targets is
  60–86% and stays 58–79%. The sixth pass's 1–3% residual was the indefinite-`S` bug doing the
  catching.
- **Finding that changes direction: a second silent path, larger than the one Stage 2 targets.**
  The callout merge-echo rule silences 50–60 points of genuinely different, correctly split groups
  while A is not lost (`contacts_plausibly_same` is looser than the gate). No stage of BL-B110
  touches it.
- **Duplicates the pilot hears.** Past 120 s, `[[BL-B113]]`'s same-optic split is heard in full
  (10–12% by eye, 6–7% binocular), and Stage 2 neither adds to it nor removes it. The trigger's
  own added cost is 2–5 points two-sided, and ≤ 0.3 points one-sided.
- **Effort/value: Stage 2 as designed no longer earns a build in BL-B110** (Stage 2, seventh-pass
  redesign). **Decision 13 (OPEN)** asks whether to build it, with a recommendation.
  **Decision 12a**: the one-sided direction still holds if Stage 2 is built, for a different
  reason. **Decision 14 (OPEN)**: a new entry for the merge-echo gap.

### Goal

When a new sighting B lies on the bearing of a group A that Petrovich holds only in memory, he
does not silently fold B into A. Same-or-different is settled by what he perceives, ideally by
looking where A should be. The pilot then hears the right number of groups in the right places.
His binocular use moves to a per-sector rhythm: sweep a sector by eye, glass what is worth
glassing there, then move on.

### Read this first: what the measurement says about effort and value

> **Superseded, seventh pass (2026-11-10).** The table and points 1 and 3 below were measured on
> the indefinite-`S` gate, before `6096b2b2`, with a frozen harness. The real catch is 5–15 points
> in one cell family, not "most of the 0–86%". Point 2 still holds, and it is now the whole
> argument: only new information (BL-B111's look) separates two groups ~2σ apart. Current numbers:
> "Honest grid, seventh architect pass", after Stage 1b.

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

**User answer (plan-check Decision 2, "as recommended"):** Stages 0–2 ship under BL-B110. The
point line-of-sight query (option a) and Stages 3–4 are opened now as `[[BL-B111]]`, so they are
planned work rather than something a quiet flight could quietly cancel. The flight duplicate count
sets BL-B111's priority, not whether it happens.

### Affected Modules / Files

Stages 0–2 (definite):
- `body-layer/src/belief/optic_policy.py`: per-sector phase cycle; multi-look glass step under a
  rolling budget that gates look starts; sector target filter; `GLASSING` passes a stall cooldown
  to `is_worth_a_look` (new `GLASS_STALL_COOLDOWN_S`); docstring rewritten (it describes the
  2026-09-23 reading). New fields on `OpticState` (Co-moving Fields).
  Fourth pass, reshaped by the fifth: `LookTarget` gains `location_gain_m` (computed in
  `look_target_for`; no `group_id`, no group reduction); `choose_glass_look` with three buckets
  (type identification, then classification, then exact location; the `choose_sighting_look`
  pattern); the `GLASSING` predicate widened to "can still improve **or** (watched **and** worth
  locating)"; the sector filter widened by half a binocular field; the `GLASSING` branch shifts its
  sweep by the chosen contact's own body-azimuth change each poll. New tunable
  `EXACT_LOCATION_MIN_GAIN_M` (replaces the fourth pass's `LOCATION_LOOK_MIN_GAIN_M`).
- `body-layer/src/belief/position_belief.py` (**Stage 0a**, Decision 7 ANSWERED (a)):
  `_apply_floor` never raises a fused estimate above its own prior's inflated covariance.
- `body-layer/src/perception/gaze.py`: `ScanPlan` gains a one-pass sweep anchor
  (`sweep_legs`, `sweep_started_sim`), and `gaze_at` honours it. **`SCAN_PLAN`'s default is
  unchanged** (third pass). A public sector table derived from `SCAN_PLAN` by a pure partition
  function that `tuning` can also call without importing `gaze`. New tunable
  `GLASS_BUDGET_PER_CYCLE_S` and derived `WORST_REVISIT_S`, here because perception must not import
  belief.
- `body-layer/src/perception/naked_eye_source.py`: `_ACQUISITION_RETENTION_WINDOW_S` moves from the
  bare sweep period to `WORST_REVISIT_S` (Stage 1, "Derived windows").
- `body-layer/src/belief/decay.py`: no formula change; `OBSERVED_WINDOW_S` stays 16 s; one new
  assert for invariant I2 on code defaults.
- `body-layer/src/body.py`: build the sector-anchored plan once per poll for every `gaze_at`
  consumer: the naked-eye source, the LOS look-direction push and the debug/eyesight views. Pass
  the sector period, wedge, count and budget to `decide_optic` instead of the hard-wired
  `SCAN_CYCLE_PERIOD_S`. Reset the sector on a scan-command change. (Fifth pass: `_look_targets` needs no change for
  location; `watched` is already set there, and the fourth pass's `group_id`/group reduction is
  dropped.)
- `body-layer/src/tuning.py`: `_check_scan_decay_coupling` extended to five keys and two
  invariants (Stage 1).
- `body-layer/src/belief/association_over_time.py`: `passes_gate` gains a keyword
  `as_if_optic_class: str | None = None`. The trigger is that one keyword; there is no new
  formula.
- `body-layer/src/belief/contacts.py`: `ingest` founds B instead of folding when the trigger
  fires, and records the believed-distinct pair.
- `body-layer/src/belief/callouts.py`: merge-echo suppression skips a believed-distinct pair.
- Tests: `test_optic_policy.py`, `test_gaze.py`, `test_body.py`, `test_decay.py`/`test_tuning.py`
  (coupling), `test_relative_distance_sweep.py`, `test_relative_distance_scenarios.py`,
  `test_callouts.py`, and a new `test_expected_area_trigger.py`. Fourth pass:
  `test_position_belief.py` (Stage 0a), and the Stage 1 scenario test gains the approach
  profile. Fifth pass: `test_estimation.py` (the rough-location fence, Stage 1 "Priority 1").
- `body-layer/docs/STRUCTURE.md`, `config/defaults.toml` (regenerated), and `body-layer/CLAUDE.md`
  "Tuning". That section describes the three-key coupling; it becomes five keys and two
  invariants. Its 16.0 s cycle figure stays true.

Stages 3–4 (**moved to `[[BL-B111]]`**, not built in this feature; kept for that entry's plan):
- Visibility source: `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`,
  `aircraft-layer/src/schema/line_of_sight.py`, the collector and API, and `body-layer`'s aircraft
  client. Exact list per Decision 2.
- New `body-layer/src/belief/expected_area.py`: check state, verdict function, actions.
- `contacts.py` (provisional contact, relocation, removal), `callouts.py` (hold, age-from-release),
  `groups.py` (`reconcile` excludes held contacts), `mission_memory/admission.py` (skip held
  contacts), `events.py`/`speech.py` (two new kinds), `body.py` (area look report, ATGM pause).

### Implementation Plan

**Stage 0a — A new look never leaves the belief less certain than just before (Decision 7,
ANSWERED (a)). Built first, before Stage 0's measurements.** Fifth pass.
- **Why first:** it changes the covariance the trigger's gate reads (a binocular- or
  sight-grade belief stays tight under later naked-eye looks), so Stage 0's table taken before it
  would describe code that no longer exists. It is also what makes Stage 1's exact-location looks
  worth anything.
- **Order, BL-B108's own escalation rule:** (1) run `test_relative_distance_sweep.py`,
  `test_relative_distance_scenarios.py` and `test_position_belief.py` on the unchanged code and
  keep the output; (2) make the change; (3) re-run them as they stand. **If any BL-B108 fence or
  assertion moves, stop and report it** with both outputs. Do not edit the fence.
- **The change:** in `_apply_floor`, the floored covariance is capped at the prior's own inflated
  covariance (`_inflated_since_last_fuse(prior, t_sim, growth)`, the same value the fuse just
  used): `floor_trace = min(floor_trace, prior_inflated.trace())`. One `min`, one new parameter
  (the prior's inflated covariance, `None` for a founding look, which leaves the floor as today).
  Not a second anchor.
- **What it does not do, stated:** growth from elapsed time at `plausible_speed_mps` still
  applies, and that rate is per believed **class**, not observed motion. So a fixed armour contact
  (8 m/s) still loosens between looks: at 3 km, re-seen by eye every 16 s, σ² grows by
  (8·16)² per cycle, from 357 m back to naked grade in about seven cycles (~110 s), instead of
  two today. An installation component (growth 0) stays fixed. `[[BL-B112]]` (motion-aware
  certainty) is where an observed-stationary contact would stop loosening.
- **Ships with Stage 1's merge** (it is what Stage 1's exact-location look depends on, and Stage
  1's card covers it). It is a BL-B108 behaviour change, so the card says so.

**Stage 0 — Measure, then fix the trigger's definition (no behaviour change).**
- Turn the scratch probe into `tests/test_expected_area_trigger.py`, an ensemble over the salt seam
  with BL-B108's `_observation` shape. It reports the three numbers in the table above, plus a
  **long-gap** grid: same group, gaps of 120 and 600 s (stationary, then moving at
  `plausible_speed_mps`).
- Tune the trigger's hypothesis so the far-unaided → near-binocular residual drops without raising
  the same-group false-trigger rate. The candidate to try first is evaluating the hypothesis σ at
  the **tighter** of the two optics, not the look's own. The table, not reasoning, decides it
  (`feedback_noise_field_sweeps_need_an_ensemble`).
- **Stage 0's table is taken on the post-0a code**, never before it (fifth pass: Decision 7 is
  answered (a), and the floor change moved from inside Stage 1 to Stage 0a).
- **Gate for proceeding:** record the final residual and false-trigger rates in this plan before
  Stage 2 is implemented. If the false-trigger rate exceeds ~10% in any cell, stop and bring it to
  the user, since that is the duplicate rate they would hear.

**Stage 0 measured, implementer pass 2026-11-03** (on post-0a code, per the gate above):
`body-layer/tests/test_expected_area_trigger.py`, the ensemble harness on this committed code
(`n=100-150` trials/cell). Two candidate trigger definitions were tried, both re-evaluating
`passes_gate` "as if A had been in this very look" via a test-only stand-in for Stage 2's
not-yet-built `as_if_optic_class` keyword (Stage 2 itself is not built by this merge):

- **Variant 1 (the plan's literal candidate): both the hypothesis σ magnitude and the
  correlation field-class are set from the tighter of the two optics.** Catches the primary
  worked case well (far-binocular→near-unaided residual 1-6%), but the same-group, short-gap
  (6 s) false-trigger rate is 27-48% -- far past the 10% gate, because the substituted sigma is
  tighter than the look's own real declared noise, so a genuinely same-position reacquisition
  fails the stricter test from its own ordinary measurement error.
- **Variant 2 (adopted): only the correlation field-class is set to the tighter optic; the
  hypothesis σ stays the look's own real declared value, scaled to the hypothesis range exactly
  as the honest gate already computes it.** Same catch rate on the primary worked case
  (far-binocular→near-unaided residual 1-5%), and the same-group short-gap false-trigger rate
  drops to 3-7% -- inside the gate.

**Residual fold** (different groups, memory-only, gap 6 s, `n=100-150`):

| case | honest fold | residual (Variant 2) |
|---|---|---|
| far binocular → near unaided, 4.5/3.0 km | 81% | 1.3% |
| far binocular → near unaided, 5.0/3.5 km | 90% | 4.7% |
| far unaided → near binocular, 4.5/3.0 km | 70% | 70% (unresolved -- see below) |
| far unaided → near binocular, 5.0/3.5 km | 73% | 73% (unresolved -- see below) |

**The far-unaided → near-binocular residual is not reduced by either variant** (catch rate ≈0%
both ways): when the anchor itself was founded through the *looser* optic, the anchor's own wide
covariance dominates the gate's sum regardless of how tight the new look's hypothesis is made,
so tightening only the incoming look's side barely moves a sum the anchor's own looseness already
dominates. This confirms, at this harness's own (larger) measured scale, the Risks section's own
"survives Stage 2... only a tighter trigger or anchors reach it" -- `[[BL-B111]]`/Stage 2b are
where this would need to be closed, not Stage 0's own tuning.

**False-trigger rate** (same group, cross-optic reacquisition, Variant 2, `n=150`):

| case | gap | false-trigger rate |
|---|---|---|
| binocular → unaided, 2.0/3.0/4.5 km, armour (moving) | 6 s | 3-7% |
| unaided → binocular, 2.0/3.0/4.5 km, armour (moving) | 6 s | 0% |
| binocular → unaided, 2.0/4.5 km, installation (stationary) | 120 s | 7-15% |
| binocular → unaided, 2.0/4.5 km, installation (stationary) | 600 s | **25-27%** |
| unaided → binocular, any range, any gap | 120 s / 600 s | 0% |

**STOP finding, per this stage's own gate:** the long-gap, stationary, binocular-then-unaided
same-group cell exceeds the ~10% gate -- 7-15% at 120 s, 25-27% at 600 s. This is reported, not
engineered around. Stage 2 is not built by this merge (BL-B110 Stages 0a/0/1 only), so nothing
ships against this gap yet; it is recorded here for whoever builds Stage 2 to resolve first (a
gap-dependent escape, or a different hypothesis construction for the long-gap case, are the two
obvious directions, neither tried here since Stage 2 itself is out of scope for this merge). The
short-gap (6 s) and moving-class (armour, any gap) same-group cells all stay inside the gate.
`test_expected_area_trigger.py`'s own module docstring carries the full account and the exact
mechanism measured.
→ **Superseded by Stage 1b (sixth pass).** The gap dependence is a harness artifact. The real
false-split rate is 15–20% at every gap, and the fix is a direction test.

**Stage 1b — Fix the trigger's same-group false split (Stage 2 prerequisite; sixth pass,
2026-11-03).**

> **Superseded, seventh pass (2026-11-10): every rate in this stage was measured on the
> indefinite-`S` gate.** That covers 15–20% two-sided, 3–6% one-sided, residual 1–3% and 28%
> farther. The harness diagnosis (frozen `z_look` and bearing draw) stands. The measured outcome
> does not. On honest numbers the two-sided trigger adds 2–5 points of false split, not 15–20, and
> the one-sided ≤ 0.3. The catch is 5–15 points, not "residual 1–3%". The text is kept as the record.

Measured with a scratch probe on `a3758a2c`, before any design choice. It used
the harness's own `_observation`/`_as_if_gate`, `n` = 300–800 per cell, and all three draws
resampled per trial. Scripts:
`/private/tmp/claude-501/-Users-sg-Code-DCS-petrobrain/9af034a3-3761-4eb7-a81e-bb7415cff2d5/scratchpad/probe_gap.py`,
`probe_threshold.py`, `probe_fine.py` and `probe_onesided.py` (scratch, not kept; the Implementer
rebuilds them as the tests below).

*What was wrong with the measurement.* `_rates` re-salts the stable field per trial
(`_FIELD_REALISATION_SALT`), but two of the three noise terms ignore that salt:
- **the look-to-look draw `z_look`**, keyed by `(optic, poll_key = t_sim)`;
- **the per-look bearing noise**, keyed by `observation_id`.

The harness uses `t_sim` = 0 and `gap_s`, and the ids `"first"`/`"second"`, in every trial. So
each gap cell holds **one** fixed draw of both terms. The unaided `z_look` at `t_sim = 600` is
**+2.83σ**, at 120 s +0.96σ, and at 6 s −0.51σ. That is the whole "gap dependence".
`feedback_noise_field_sweeps_need_an_ensemble` warned about this for the field and not for these
two terms.

*Resampled* (Variant 2 as built, `n` = 150, ranges 2.0/3.0/4.5 km):

| same group, binocular → eye | gap 6 s | gap 120 s | gap 600 s |
|---|---|---|---|
| stationary (`s-125`, growth 0) | 16–21% | 15–22% | 12–21% |
| moving (armour, 8 m/s) | 13–17% | 0% | 0% |

The moving class passes at long gaps only because its grown covariance has stopped telling
anything apart. The same growth also takes the catch to zero. Eye → binocular is 0% everywhere,
as before.

*Why it happens.* Variant 2 sets the correlation class to the tighter optic. That claims the
look's stable range error is fully shared with the binocular anchor (k = 1). In the model the
cross-optic share is k_b/k_u = 0.7. So for a genuinely same group the down-range budget is too
small, and roughly one re-sighting in six fails 3σ. The honest gate (k = 0.7) splits only 1–3%.
It also folds 61–79% of the different-group pairs, which is BL-B108's defect. **No construction of
the hypothesis can separate the two populations better than the information allows.** The levers
are which errors to accept, and where. That is how the candidates were judged.

*Candidates, measured* (`n` = 800; "false" = same group split, worst of the six b→u cells;
"residual" = different groups still folded, the three b→u B-nearer cells):

| trigger | false split (worst cell) | residual, B nearer | residual, B farther (3.0/4.5) |
|---|---|---|---|
| none (BL-B108 today) | 1–3% (honest gate) | 61–79% | 28% |
| Variant 2, 3σ, two-sided (as built) | **20%** | 1–3% | 28% |
| Variant 2, two-sided, own threshold 4.5σ | 9.4% | 15–34% | 28% |
| Variant 2, two-sided, own threshold 5.0σ | 6.6% | 26–55% | 28% |
| **Variant 2, 3σ, one-sided: fires only when B reads nearer than A's hypothesis range** | **6.0%** (3.4–6.0% across cells) | **1–3%** | 28% (unchanged, today's fold) |

- **A gap-dependent escape is rejected.** It is aimed at an artifact: at zero growth the rate does
  not depend on gap.
- **A separate trigger threshold is rejected.** To get under 10% with any margin it gives back
  half to two thirds of the catch, in the very case the feature exists for.
- **Adopted: the one-sided trigger.** It keeps the full catch where B is nearer, and that is the
  case the feature exists for: a nearer group hidden behind a remembered farther one, on the
  approach. Same-group false splits are lopsided, because the hypothesis-range scaling shrinks
  the look's σ when B reads farther. About three quarters of them are "B reads farther", so they
  drop out. **What it gives up:** a different group that reads *farther* than A keeps folding at
  today's BL-B108 rate (28% in the measured cell). That is no worse than today, and it is the less
  urgent direction, because A is already known on that bearing. `[[BL-B111]]`'s look is what
  reaches it. **Decision 12.**

*The change (test-side now; production in Stage 2):*
1. **Harness fix, both cross-time harnesses.** In `test_expected_area_trigger.py::_rates`, every
   trial uses unique observation ids (`f"first-{trial}"`) and a per-trial time base
   (`t0 = trial * 1e-3`, second look at `t0 + gap_s`), so `z_look` and the bearing noise are
   redrawn per trial. **Not** a production seed change: salting those two hashes in
   `perception.estimation` would change flight-time draws. `test_relative_distance_sweep.py`'s
   cross-time helpers (`first`/`second` at fixed `t_sim`, lines ~471–566) have the same artifact.
   Apply the same fix there and re-run it. **If any BL-B108 fence or assertion moves, stop and
   report both outputs**; do not edit the fence (Stage 0a's rule).
2. **Direction condition in the stand-in.** The test-only trigger is `_as_if_gate(...)` failing
   **and** `percept.range_m < hypothesis_range_m`, where `hypothesis_range_m` is the observer →
   A's believed position, already computed inside the gate. Perceived and believed quantities
   only. No new constant, no tuning key, and `GATE_SIGMA_THRESHOLD` is unchanged.
3. **Gap grid 6 / 120 / 700 s, not 600.** At 600 s, `object_id_continuity_valid` is still true
   (`<=`), so in flight an intact same group re-seen at 600 s never reaches the gate. 700 s is the
   real gate-path regime for the user's case: a SAM site re-seen after more than ten minutes.
4. **Ground cells.** The harness is air-path only today. A SAM site is a ground unit, ranged
   through `surface_range_estimate` (depression cue). Add same-group b→u cells through the sweep
   harness's `surface=True` branch, at 100 m and 500 m AGL. **Unmeasured until then. If a ground
   cell exceeds the gate, stop and report**; do not tune around it.

*Acceptance, the number Stage 2 waits on:*
- **Same group, false split ≤ 10% in every cell** of: {b→u, u→b} × {2.0, 3.0, 4.5 km} × {6, 120,
  700 s} × {stationary `s-125`, armour}, plus the ground cells. Expected ≤ 6% (measured air
  cells). Fence each at 0.10 with `n = 200`; at p = 6% the standard error is 1.7 points, so the
  fence sits more than two standard errors clear.
- **Different groups, B nearer (far binocular → near eye; 4.5/3.0, 5.0/3.5, and 4.5/3.0
  stationary at 700 s): residual fold ≤ 10%.** Measured 1–3%.
- **Characterisations, not gates:** B farther (3.0/4.5) residual equals the honest fold (today's
  rate, ~28%). Far eye → near binocular is still ~70% (Stage 0's unresolved cell, unchanged).
- The full grid at `n = 800` is recorded once in this section by the Implementer. The suite runs
  the `n = 200` fences.
- `test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate` is
  **replaced**, because its premise ("≥ 15%") was the artifact. `test_expected_area_trigger.py`'s
  module docstring is rewritten. That is a premise change, approved here as the purpose of this
  stage.

**Stage 1b implementer pass, STOPPED 2026-11-09, per this stage's own gate ("if any BL-B108
fence or assertion moves, stop and report both outputs; do not edit the fence").** Step 1's
harness fix (`_e3_fold_rate`/`_fuse_two_looks` in `test_relative_distance_sweep.py`: per-trial
`observation_id` and a per-trial `t_sim`/`poll_key` base, `t0 = trial * 1e-3`, exactly as this
section specifies) was applied and run in isolation, before touching anything else. It moved two
`BL-B108` fences:

| test | before (fixed draw, this committed code) | after (per-trial fix applied) |
|---|---|---|
| `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact` | 71 passed | **fails**: unaided→unaided (`u_u`), 3 km, 4 s gap, honest same-optic reacquisition fold rate is **83–86%** (`n=100` then `n=300` for confidence), not the asserted 100%. unaided→binocular (`u_b`) stays 99–100%, consistent with its own fence. |
| `test_no_omniscience_fused_sigma_never_beats_the_tighter_optics_own_sigma` | 71 passed | **fails**: `_fuse_two_looks`'s own hard `assert len(store.contacts) == 1` (no tolerance) hits the already-known, already-fenced-elsewhere binocular→unaided non-fold rate (`test_e3_binocular_then_unaided_folds_almost_always` fences this direction at ≥ 90%, not 100%) at one cell (3.0 km, trial 7 of 60) once the draw is actually resampled instead of frozen at one lucky value. Re-measured with the fold-precondition excluded: 0 sigma-ratio violations across the 59 cells that did fold.

Full run: `71 passed in 33.31s` (before) → `2 failed, 69 passed in 31.61s` (after), both runs on
this committed production code, test-side change only.

**Mechanism, same one this stage's own module docstring already names for the gap-dependence
finding**: `z_look` is keyed by `(optic, poll_key=t_sim)` and the per-look bearing draw by
`observation_id` alone, both independent of `_FIELD_REALISATION_SALT` — so a cross-time helper
that reuses the same `t_sim`/id on every trial (as `_e1_fold_rate` and `test_e1_ground_units_
same_optic_stays_two_contacts` still do; out of this fix's stated scope, lines ~471–566 only)
freezes those two terms to one draw for the whole ensemble. Here that draw happened to be one on
which `u_u`'s same-optic reacquisition always folds. The real finding is not an artifact of this
fix: `u_u` same-optic, same-geometry reacquisition genuinely fails to fold about one time in six
or seven, a materially weaker guarantee than the "clear case: almost always" the plan and
`BL-B108` itself have stood on. **Not fixed, not edited, per this gate.** The code change that
produced this finding (the harness fix above) was reverted after measurement (`git checkout --
tests/test_relative_distance_sweep.py`), so the committed tree is unchanged and still green; the
numbers above are the full record of what was measured. Stage 1b's own harness fix in `test_
expected_area_trigger.py`, the direction clause, the 6/120/700 s gap grid, and the ground cells
are **not built by this pass** — they depend on step 1, which is the step that produced this stop.

**What this means for the plan.** `[[BL-B111]]`'s point-LOS/anchors discussion and this stage's
own "far-unaided → near-binocular residual" finding both assumed the same-optic case was the
solid ground everything else is measured against. It is not as solid as measured. Two directions,
neither tried here: (a) the `u_u` 4 s-gap reacquisition fold rate may simply be genuinely ~85%,
in which case `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact`'s "always" is
the thing that needs correcting (with the user's sign-off, since it is a `BL-B108` guarantee, not
this entry's own); (b) the gap/range combination tested (3 km, 4 s) may be unusually unlucky
among same-optic cells, in which case a wider same-optic sweep (as `test_relative_distance_sweep.
py`'s own `_e1_fold_rate`/`_E1_PAIRS` already do for the *different-groups* case) is what Stage 1b
or a follow-up should build before deciding anything is wrong. **Brought to the user before Stage
1b's harness fix, direction clause, gap grid, or ground cells are built.**

*What the pilot notices.* The case is a SAM site glassed at 4.5 km and seen again by eye after
more than ten minutes:
- Variant 2 as built would announce it as a new group about one time in five.
- With Stage 1b, at most about one in twenty, and only when his eye happens to read it nearer
  than he believed it.
- Inside ten minutes, object continuity re-attaches it before the gate, so nothing is announced
  either way. The exception is a cluster that re-formed in the meantime, the only same-group
  gate-path case inside the window.
- A group that really is nearer, on the bearing of one he remembers, is still called out
  (residual 1–3%).
- A group farther than the one he remembers is still folded silently, as today.

*Ships with Stage 2* (one merge). Stage 1b is test-side and measurement only. Stage 2 lifts the
stand-in into production as the trigger's third condition.

**Same-optic fold measurement 2026-11-09** (user decision, "measure first" — above, before any
fence or fold code change). Measures the honest same-group fold rate (not the as-if trigger) over
every noise draw the Stage 1b stop finding named as frozen: the field salt (existing seam), the
look-to-look draw `z_look` (keyed by `(optic, poll_key=t_sim)`), and the per-look bearing draw
(keyed by `observation_id`) — unique observation ids and a per-trial time base
(`t0 = trial * 1e-3`) alongside the field salt, exactly `feedback_harness_resampling_fix_can_
falsify_an_existing_guarantee`'s recipe. **No fence, test, or production code changed** — a new
script, `body-layer/tools/measure_same_group_fold.py` (no `slow`/`skip` pytest marker exists in
this project, checked: no `pytest.ini_options.markers`, no `conftest.py`; this follows the
`tools/summarize_detection_trace.py`-class precedent for a dev script outside the committed suite).
Grid: optic pairs `{u_u, b_b, u_b, b_u}` × ranges `{1.0, 2.0, 3.0, 4.5}` km × gaps
`{2, 4, 6, 30, 120}` s × classes `{armour (`OP_ARMORED`, 8 m/s growth), installation (`s-125`, 0
growth)}` = 160 air cells, plus `u_u` ground-unit cells (`surface=True`) at 100 m and 500 m AGL
over the same range/gap/class grid = 80 more, 240 cells total, `n=300`/cell, 72 000 trials,
652.8 s. Full per-cell table: `body-layer/tools/measure_same_group_fold.py`'s own `--out`
(regenerate with `PYTHONPATH=src:../world-model/src .venv/bin/python
tools/measure_same_group_fold.py --n 300`; the raw 240-row table is not reproduced here).

**Fold rate, aggregated over each pair's 20/40 cells (weighted by each cell's own non-fold
count, `n=300`/cell):**

| optic pair | fold rate | note |
|---|---|---|
| `u_u` (naked eye twice) | **89.7%** | 84.7–87.7% flat at every gap for the stationary class; 85.7–100% for the moving class, rising to 100% only once `gap_s` is large enough for growth to loosen the gate |
| `b_b` (binoculars twice) | **94.7%** | same shape, better floor: 91.0–93.7% stationary (flat), 93.3–100% moving |
| `u_b` (unaided founded, binocular re-sight) | **99.0%** | matches `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact`'s existing ≈100% fence |
| `b_u` (binocular founded, unaided re-sight) | **98.1%** | matches `test_e3_binocular_then_unaided_folds_almost_always`'s existing ≥90% fence |
| `u_u` surface, 100 m AGL | **87.1%** | ground units, same shape as the air `u_u` case |
| `u_u` surface, 500 m AGL | **90.6%** | higher than 100 m AGL — shallower depression angle at low AGL makes `surface_range_estimate`'s grazing cue noisier |

**The installation (zero-growth) class's flat rate across every gap from 2 s to 120 s — not just
the one 3 km/4 s cell Stage 1b's stop found — confirms that cell was not an unlucky single draw.**
It is a structural ceiling of same-optic reacquisition that elapsed time cannot loosen when
nothing inflates the contact's own covariance (`plausible_speed_mps(..., installation_
component=True) == 0.0`): **≈85–88% for `u_u`, ≈91–94% for `b_b`**, at every range and every gap
measured. The moving class's rate rises toward 100% only because growth eventually loosens the
gate enough to swamp this same ceiling — it is masking the same structural effect, not a
different, better-behaved one.

**Direction of non-folds** (`B`'s own reported range vs. the hypothesis range from the observer to
`A`'s believed position — Stage 1b's own Decision 12 direction signal), aggregated over all
non-fold trials for that pair:

| optic pair | non-folds where B reads nearer | farther |
|---|---|---|
| `u_u` air | 61.9% | 38.1% |
| `b_b` air | 73.8% | 26.2% |
| `u_u` surface 100 m AGL | 62.1% | 37.9% |
| `u_u` surface 500 m AGL | 68.9% | 31.1% |
| `u_b` air | 45.5% | 54.5% (`n`=121 non-folds total, roughly balanced) |
| `b_u` air | 28.7% | 71.3% (`n`=230 non-folds total) |

Same-optic non-folds lean nearer (62–74%); `b_u`'s lean farther (71%) instead — opposite signs,
so a one-sided "fires only when B reads nearer" trigger (Stage 1b's Decision 12, built for the
*different-groups* case) would, if it were ever applied to a same-optic reacquisition, suppress
the majority of same-optic non-folds for `u_u`/`b_b` but miss most of `b_u`'s. Not acted on here —
Stage 2's trigger condition is scoped to the different-groups defect, and this is reported only
because the task asked for the direction breakdown.

**Mechanism for `u_u`, by inspecting individual non-fold trials (not a formal attribution, an
inspection, per the task).** The gate's `correlated_innovation` (`position_belief.py`) computes
`S = P_est + P_look - (C + C^T)`, and `Covariance2D.inverse()` floors `S`'s determinant at
`max(1e-9 * trace(S)^2, 1e-300)` before inverting — that floor's own comment says it sits "orders
of magnitude above ... so it never fires on real data." **Measured, same-optic, zero-growth, 2 km,
4 s gap (installation class, `n=300`): the real determinant is negative on 7.0% of trials (21/300)
for `u_u`, 1.7% (5/300) for `b_b`, and 0% for `u_b`/`b_u` (0/300 each)** — the comment's premise
does not hold in the regime this feature's own same-group reacquisition lives in. A negative
determinant means `S` is not positive semi-definite at all; the floor clamps it to a tiny positive
number regardless, and the resulting "inverse" is not a valid precision matrix — the diagonal
terms (`S.zz`/`determinant`, `S.xx`/`determinant`) blow up to the tens of thousands against a
typical covariance trace of ~30 000 m², so the Mahalanobis test returns values of `1e7`–`1e9`
against the gate's `9.0` threshold (`GATE_SIGMA_THRESHOLD ** 2`) — rejecting the percept regardless
of how small its actual positional offset is. **On the same cell, split by the sign of the real
(pre-floor) determinant: positive-determinant trials fold 90.7% of the time (279/300, close to
what the aggregate rate would be without this effect); negative-determinant trials fold only 19.0%
of the time (21 trials)** — this single, previously-undocumented numerical degeneracy accounts for
roughly a third to half of this cell's own ~14% non-fold rate, on top of ordinary 3σ excursions
(where the approximate down/cross decomposition the mechanism dump below uses is meaningful).
**Same-optic only** (the correlation kernel's magnitude is largest when both looks share one optic,
pushing `C`'s cross term large enough to occasionally overshoot `P_est + P_look`); negligible for
`b_b` (binoculars' tighter base sigma leaves less room to overshoot) and absent for cross-optic
pairs in the cells checked. **Not fixed or changed here** — this is a candidate root cause for
whoever revisits `BL-B108`'s same-optic "always"/"almost always" guarantees (Stage 1b's own open
question (a)/(b)), not something this measurement-only entry acts on. A handful of individual
non-fold trials' own gate arithmetic (the ordinary, non-degenerate case: approximate down-range vs.
cross-range z-scores, elapsed-time growth contribution) is in the script's own `--out` dump; most
inspected `u_u` non-fold trials hit the determinant-floor pathway above rather than an ordinary
single-axis 3σ excursion, which is itself notable — the approximate decomposition's "which axis
dominates" framing understates what is actually happening in most of these cells.

**What this means for the plan.** Stage 1b's open question — (a) the `u_u`/`b_u` "always"/"almost
always" guarantees may simply be weaker than documented, or (b) 3 km/4 s was an unlucky single
cell — is answered **(a)**, with a third option Stage 1b did not anticipate: a chunk of the
weakness is not ordinary measurement noise at all but a numerical degeneracy in the gate's own
correlated-covariance formula, specific to same-optic reacquisition. **Brought to the user before
any fence, `correlated_innovation`, or `Covariance2D.inverse` change** — three different follow-
ups are now distinguishable rather than one: lowering `BL-B108`'s same-optic guarantees to match
what is actually measured; fixing `correlated_innovation` so `S` cannot go indefinite for a
same-optic pair (a `position_belief.py` change, not this entry's); or treating the ~85–94%
same-optic ceiling as acceptable and continuing to Stage 2 regardless. None attempted here.

**Honest grid, seventh architect pass, 2026-11-10** (on `cd58ab76`: the gate-covariance fix
`6096b2b2` merged in, harness fixed). **This replaces every trigger number taken before it:
Stage 1b's candidate table, Decision 12's figures, and the "Read this first" table.** Those were
measured on the indefinite-`S` gate, and the as-if trigger's "catch" was mostly that bug
(`test_expected_area_trigger.py`'s own re-measured comments say the same).

*Method.* Scratch probe (`probe_stage2_honest.py` in the architect's scratchpad, not kept), built on
`tools/measure_same_group_fold.py`'s own `_observation`/`_ownship`/`_fresh_realisation`. Every
trial redraws the field salt, `z_look` (per-trial `t0 = trial * 1e-3`) and the per-look bearing
draw (per-trial observation ids). Per trial it records:
- the honest fold, through the real `ContactStore.ingest`/`tick`;
- the Variant 2 as-if gate (correlation class set to the tighter optic);
- the direction (`percept.range_m <` the hypothesis range to A);
- when the gate splits, whether `callouts._is_merge_echo_of_earlier_contact`'s condition would
  **silence B's callout**: A not `lost` and `contacts_plausibly_same(B, A)`.

That last column is new, and it is what the pilot actually hears. Air path at 500 m; ground cells
use `surface=True` at 100 m AGL (SAM site, `s-125`). Same-group `n = 400` per cell (95% CI ±1.7
points at 3%, ±3 at 10%). Different-groups `n = 300` (±5 points at 70%, ±3 at 10%).

**Same group re-seen through the gate: duplicate callouts the pilot hears.** Each cell reads
"today / with two-sided trigger / with one-sided trigger".

| pair | gap 6 s (A not lost) | gap 700 s, stationary (A lost) | gap 700 s, armour |
|---|---|---|---|
| eye → eye (`u_u`) | 0.3–0.5% / same / same | **10–12%** / same / same (ground 10–11%) | 0% |
| bino → bino (`b_b`) | 0.2–0.5% / same / same | 6–7% / same / same | 0% |
| eye → bino (`u_b`) | 0.2–1.2% / same / same | 1.0–1.5% / same / same | 0% |
| bino → eye (`b_u`) | 0.2–1.0% / **2.0–5.8%** / 0.2–0.7% | 1.5–2.8% / **4.3–6.5%** / 1.5–2.8% | 0% |

- **The gate splits same-optic re-sightings 4–11% of the time** (`[[BL-B113]]`). Inside 120 s the
  merge-echo rule silences almost all of them, so the pilot hears ≤ 0.5%. **Past 120 s, A is `lost`,
  nothing silences the split, and BL-B113 is heard in full:** 10–12% by eye, 6–7% through
  binoculars. **Stage 2 does not change this.** For a same-optic pair the as-if gate *is* the
  honest gate, so the trigger never fires.
- **The trigger's own cost is small on honest numbers.** Two-sided adds 2–5 points, cross-optic
  bino → eye only. One-sided adds ≤ 0.3 points. The sixth pass's "15–20% two-sided" was the bug.
- Armour past 120 s never splits. Growth at 8 m/s swamps everything, which also means nothing is
  ever caught there (below).
- In flight, a same group inside 600 s goes through object continuity, not the gate. So the
  0.3–1% short-gap column covers only re-formed clusters. **The 700 s column is the real case**:
  a SAM site re-seen after ten minutes.

**Different groups on one bearing: B is never announced.** Silent = folded into A by the gate, or
founded and then silenced as A's merge echo. Each cell reads "today → with the trigger"; one- and
two-sided are identical to within 1 point in every cell. Far/near pairs are 4.5/3.0 and 5.0/3.5,
then 3.0/1.5 after the semicolon.

| pair | B nearer, gap 6 s | B farther, gap 6 s | B nearer, 700 s stationary | B farther, 700 s |
|---|---|---|---|---|
| bino → eye (`b_u`) | 72–86% → **60–79%**; 6–7% → 3–4% | 73–82%, unchanged; 41–45% | 70–82% → **58–76%**; 7% → 4% | 32–39%; 4% |
| eye → bino (`u_b`) | 78–81%, unchanged; 40–44% | 39–53%; 2% | 58–65%, unchanged; 22% | 21–31%; 1% |
| eye → eye (`u_u`) | 63–73%, unchanged; 28–30% | 63–72%; 30–37% | 7–11%; 5% | 8–12%; 1% |
| bino → bino (`b_b`) | 13–22%, unchanged; 0–2% | 13–25%; 2% | 1%; 0% | 1%; 0% |

Ground cells (100 m AGL, `s-125`, `u_u` and `b_u`) match the air cells within the CI.

**Of the three silent paths, the trigger reaches the smallest.**
1. **The gate folds B into A.** This is cross-optic only: 60–86% where the far contact was ranged
   through the other optic. The trigger takes **5–15 points** off it, and only in bino → eye with B
   nearer. It never touches eye → bino. **The information is not there to do better.** Naked-eye
   down-range σ is 0.17 R (≈ 510 m at 3 km), and the binocular anchor's is ≈ 535 m at 4.5 km, so
   groups 1.5 km apart on one bearing are about 2σ. The sixth pass already said this. The bug was
   hiding how true it is.
2. **The merge-echo rule silences B.** This applies at any optic pairing, while A is not lost
   (< 120 s). It takes **50–60 points** in same-optic eye → eye cells where the gate itself
   correctly split (gate fold 4–15%, silent 63–73%). `contacts_plausibly_same` is evidently looser
   than the gate. Why is unattributed: it is not inspected here and should not be guessed.
   **This is a finding that changes direction.** No BL-B110 stage touches it, and Stage 2's
   believed-distinct skip only covers trigger-fired pairs.
3. **Past 120 s, same-optic, nothing silences B:** 1–12% fold, which is BL-B108's floor.

**Stage 2b's proposal rule fires.** Its own text: "if, after Stage 0 tuning, any clear-case cell's
residual stays above 10%, open a follow-on entry". Every cross-optic nearer cell is 58–86%.

**Stage 1 — Per-sector scan order (user Q1). It ships on its own and changes behaviour for every
contact.**

*Revised 2026-11-02, third architect pass* (`explore-notes.md`, "Plan re-check answers", which
govern). The order is ahead first, then sides alternating; the glass budget is 12 s per cycle and
looks are not cut short; selectivity, not a tight timer, is what bounds binocular time. **The
default `SCAN_PLAN` no longer changes**: today's table already is the order the user described
(below). That removes the second pass's table reshape and all of its knock-on test-data churn.

*Build order inside Stage 1 (fifth pass).* One merge, together with Stage 0a.
- **1-scan:** the per-sector scan, budget, stall cooldown, sector margin and look-follow.
- **1-rank:** the glass step's look order by the user's refined priority (type identification,
  then classification, then exact location).
- **1-locate:** exact-location looks for watched contacts. Needs Stage 0a, which is now built
  first, so nothing waits on a decision.

(The fourth pass's "1-floor" step is now Stage 0a.)

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
- **Regions (user Decision 1, *"third of full scan. So basically left right and ahead"*; re-check:
  *"I meant regions, not order"*).** The three thirds `SECTOR_WEDGE_DEG` already defines: `left`
  9–11, `ahead` 11–1, `right` 1–3.
- **Order (user re-check: *"always start from ahead and sweep to left/right alternating. That
  way direction of flight is checked more often"*).** Ahead → left → ahead → right, repeating.
  **Today's default table `(12, 11, 10, 9, 12, 1, 2, 3)` is exactly that path**: the eye starts
  at 12, sweeps out through 11 to the left side, flicks back to 12, sweeps out through 1 to the
  right side, flicks back to 12. So `SCAN_PLAN`'s default stays as it is.
- **Sectors are the consecutive runs of legs that fall in the same third** (cyclic: if the
  table's first and last runs fall in the same third they are one sector). A leg on a boundary
  (11, 1) goes to `ahead`, since its ±15° cone straddles the line and ahead is where the aircraft
  is going. The default table gives four sectors, one glass step after each:

  | # | sector | legs | sweep | eye covers |
  |---|---|---|---|---|
  | 0 | ahead, outbound left | 12, 11 | 4 s | 10:30–12:30 |
  | 1 | left | 10, 9 | 4 s | 8:30–10:30 |
  | 2 | ahead, outbound right | 12, 1 | 4 s | 11:30–1:30 |
  | 3 | right | 2, 3 | 4 s | 1:30–3:30 |

  **How ahead is covered:** 12 o'clock is swept twice per cycle (8 s apart with nothing to
  glass), and ahead gets two glass steps per cycle. 11 and 1 are swept once each, as today. This
  also settles alignment re-check finding 4: first notice of a new contact dead ahead stays at
  today's ≈8 s, not the ≈14 s the second pass's single ahead visit would have cost.
- **Alternative considered and not chosen: a full-ahead "pendulum"** `(1, 12, 11, 10, 9, 11, 12,
  1, 2, 3)`, where each ahead pass sweeps all of 11–12–1. It sees 11 and 1 more often too, but
  costs 10 legs (20 s) of eye sweep per cycle: every flank revisit grows by 4 s (worst 36 s with
  the budget, table below), `SCAN_CYCLE_PERIOD_S`/`OBSERVED_WINDOW_S` move 16 → 20 s, and every
  test that pins the 16 s cycle changes. The user's stated reason, *"direction of flight is checked
  more often"*, is already met by 12 twice per cycle. Stated, not escalated: `SCAN_PLAN` is a
  tunable, the partition rule handles the pendulum unchanged (four sectors), and the coupling
  check below accepts it.
- `full` commanded is `SCAN_PLAN` verbatim, so it runs as the same four sectors. Other commanded
  scans stay one sector each (ahead `11,12,1`, left `11,10,9`, right `1,2,3`, one o'clock hour,
  compass legs).
- **Sweep.** `SCANNING` sweeps the current sector once, from its first leg, anchored at
  `phase_started_sim`. The scan clock pauses while glassing, so no leg is skipped or repeated.
  **When a sector ends with nothing to glass, the next sector anchors at the previous anchor plus
  the sector period, not at `now`**, so a quiet cycle is exactly `SCAN_CYCLE_PERIOD_S` and does
  not drift by a poll per sector (the existing `decay` asserts assume an exact 16 s quiet cycle).
  This is a `ScanPlan` one-pass anchor, resolved in `body.py` once per poll and handed to every
  `gaze_at` consumer, so the LOS look-direction push, the naked-eye source and the eyesight view
  (E4: where he actually looks) cannot disagree. The push runs before `decide`, so it can lag one
  poll at a sector boundary. That is harmless at the push's ±90° cone, and stated.
- **Glass step**, at the sector's end: targets are contacts whose believed body azimuth **at the
  glass step** (this poll's `LookTarget`, not where the eye saw it) lies in the swept sector's
  wedge (union of its legs' ±15° cones) **widened by half a binocular field**
  (`BINOCULAR_OPTIC.fov_half_angle_deg`, 4.25°; no new constant), and that pass `is_worth_a_look`
  (with the stall cooldown below, and the fourth pass's location predicate). The margin is there
  for body rotation (next item). A contact on a boundary can then be glassed in either adjacent
  step, and the attempted marks stop it being glassed twice. **Several looks per step are expected** (user Decision 1). Looks run
  back to back (`choose_look` per look, unchanged) until none is left or the budget will not admit
  another. Then the next sector.
- **Glass budget (user re-check: *"four is too short … when binoculars are used, it's better to
  not limit the time too tightly. The 12 s sounds ok"*).**
  - **The budget gates the start of a look, never its length.** A look starts only if
    `glass time over the last n glass steps (this one included) + MAX_LOOK_S ≤
    GLASS_BUDGET_PER_CYCLE_S`. A started look then runs to its own natural end
    (`look_is_finished`) or `MAX_LOOK_S` (6 s, unchanged), exactly as today. **No look is ever cut
    short by the budget**, and the window total still never exceeds 12 s. The price: once more
    than 6 s is spent, no further look starts in that window, so up to 6 s of the 12 can go unused
    in a busy cycle. That is the cost of never cutting a look.
  - **There is no per-step cap** any more. A busy sector may take the whole window's budget.
  - **Rolling, not reset once per cycle. This is a correction to alternative (b) as it was
    written.** A scalar `glass_cycle_spent_s` reset at sector 0 lets the end of one cycle's budget
    and the start of the next both fall inside one flank revisit window. The right flank's window
    holds glass step 3 of cycle k and steps 0–2 of cycle k+1, which is up to 2 × 12 s. The worst
    revisit would then be 16 + 24 = 40 s, not 28 s. So the budget is counted over the **last n
    glass steps** (n = number of sectors, 4), which is exactly the set of steps inside any one
    leg's revisit window. The state is a short tuple of the last n−1 completed steps' glass times
    (a step with nothing to glass contributes 0.0), plus the current step's own clock.
  - **Starvation is bounded:** if one sector takes the budget, the next sectors' steps are skipped,
    and their targets are glassed once the window rolls past the busy step (at most one cycle).
    A new contact ahead is still seen by eye every 8 s. The budget only delays its binoculars.
- **Selectivity (user re-check: *"Binoculars should be used to look closer when there is good
  probability that using them brings a benefit — detection, classification or identification.
  There's no use raising them on contacts where additional information is not available at current
  distance"*).** Read against the code, not the docstring:
  - **Classification and identification at the current distance: already gated.**
    `can_still_improve` (first test inside `is_worth_a_look`) requires the believed range to lie in
    `improvement_window_m`: `(unaided_class_m, binocular_class_m]` for a presence/unknown contact,
    `(unaided_type_m, binocular_type_m]` for a classed one, nothing for a typed one. Closer than the
    lower bound the eye gets that tier on its next pass, so a look is useless. Beyond the upper
    bound binoculars cannot get it either. Both bounds come from `tier_ranges`, the same code the
    eye uses, on the **believed** type (`_look_targets` passes `last_class_raw`; a presence contact
    gets the default profile). This is exactly the user's rule.
  - **Detection: not a per-contact question, and correctly absent from free scan.** A
    `LookTarget` is already detected. Binocular *detection* is the `SEARCHING` phase, which runs
    only on a commanded sector of ≤ 30° (user, 2026-09-23: *"there's no wide area binocular
    scan"*). Extra group members found during a classification look are a by-product, and they are
    not gated. Nothing is added here.
  - **The gap: a look that already failed at this range is retried anyway.** After a look that
    did not move a contact's level, `GLASSING` re-admits it after `OPTIC_RETRY_INTERVAL_S` (64 s)
    at the same range. It never passes `stall_cooldown_s`. `BL-B85` deferred exactly this
    (`SIGHT_STALL_COOLDOWN_S`'s comment: *"extending the same cooldown to it would be a `GLASSING`
    behaviour change beyond what this fix was asked for"*). A look that taught nothing at this
    range is the measured form of "additional information not available at current distance".
    With selectivity as the main bound on a 12 s budget, it belongs here. **Add:** `GLASSING`'s
    candidate filter passes `stall_cooldown_s=_EFFECTIVE_GLASS_STALL_COOLDOWN_S`. That is the same
    `is_worth_a_look` branch the sight uses, with a new tunable, and no second mechanism. The
    closing-range escape (`RETRY_RANGE_FRACTION`, 80% of the last attempt's range) is untouched,
    so a contact the aircraft is closing on is still retried as soon as it is worth it. The
    Implementer confirms that the `GLASSING` commit writes `attempted_at_level` (its entry already
    records `pending_attempted_at_level`) instead of assuming it.
- **Optics priority (fifth pass; user, refined, 2026-11-02, verbatim):** *"1 detection and rough
  location (the further away we are, the more imprecise the location is allowed to be. At close
  distances a more specific location can and should be obtained) 2 IFF, though that needs expected
  enemy territory and unit identification (eg. T-72 vs leopard) 3 classification 4 exact location
  (for enemy units especially and mission target units or anything the player asks for)"*, and
  *"Exact position is not even needed for all units."* This replaces the fourth pass's *"a)
  knowing where the groups are b) iff c) classification"* reading, its per-group location looks
  ranked first, and their group reduction. The fourth pass's text is at `cad3783a` for the record.

  - **Priority 1, detection and rough location: the naked-eye scan is the whole answer. No
    binocular look is raised for it.**
    - **The allowance, from what the pilot hears.** A contact is called by o'clock (30°, so ±15°)
      and by range rounded to 0.5 km (`speech._format_range_km`), "very close" under 500 m.
      Rough location is good enough when 1σ is inside **0.2 · R** down-range and
      inside half an o'clock across (pure proportion, no floor: re-check 3 Question 1, user
      2026-11-03 *"go with recommendations"*, so the fence keeps tightening close in). 0.2 · R is "five kilometres means four to six" far out,
      where the pilot's action (turn away, slow, keep watching) does not change with a finer
      figure. The allowance tightens in absolute terms as range falls, which is the user's
      *"further away … more imprecise … close distances a more specific location"*.
    - **What the model gives after one naked-eye look**, from the shipped `look_sigma_m` and
      `surface_range_estimate` (cue A fused with the depression cue for a ground unit):

      | R | across (any AGL) | down, 0–50 m AGL | down, 300 m AGL | down, 800 m AGL | allowance (down) |
      |---|---|---|---|---|---|
      | 0.5 km | 26 m | 81–85 m | 49 m | 48 m | 100 m |
      | 1.0 km | 52 m | 168–170 m | 127 m | 91 m | 200 m |
      | 1.5 km | 79 m | 254–255 m | 216 m | 152 m | 300 m |
      | 2.0 km | 105 m | 339–340 m | 307 m | 226 m | 400 m |
      | 3.0 km | 157 m | 509–510 m | 486 m | 397 m | 600 m |
      | 5.0 km | 262 m | 850 m | 834 m | 758 m | 1000 m |

      Down-range is at most **0.17 · R** (`RANGE_FRACTIONAL_SIGMA`, a plain constant), and only
      ever smaller with altitude, because the depression cue can only tighten the fuse. Across is
      3° (`BEARING_SIGMA_DEG`), against the ±15° of an o'clock. **So no contact is ever outside
      the allowance after a naked-eye look**, at any range, any altitude in the operating
      envelope, air or ground. Close in, the eye already gives the "more specific location" the
      user asks for: ±85 m at 500 m, ±49 m from 300 m AGL.
    - **No shipped tuning key can break it.** `RANGE_FRACTIONAL_SIGMA` is not tunable;
      `DEPRESSION_SIGMA_DEG` only tightens; `BEARING_SIGMA_DEG` at its `hi` of 14° gives ±14°
      across, still inside an o'clock; `BINOCULAR_RANGE_SIGMA_SCALE` does not touch the naked eye.
      Only a code change could, so the conclusion is fenced by a test, not by a tunable (Decision
      10).
    - **Between looks, a moving class can drift past it.** Growth at `plausible_speed_mps` (armour
      8 m/s) takes a 1 km contact past its 200 m allowance within seconds to tens of seconds unseen. That is not a binocular question:
      the glass step follows the eye's own sweep of that sector, so a contact the eye just saw is
      fresh, and one it did not see is either masked (binoculars no better) or beyond eye range
      (binocular re-detection, which free scan deliberately does not do, 2026-09-23). It is the
      revisit and `[[BL-B112]]`'s question, and nothing is built for it here.
  - **Priority 2, IFF: not modelled, not built.** `[[BL-B12]]` is deferred (infer from unit-type
    vocabulary and controlled terrain, never DCS truth; no terrain-control data exists). What serves
    it today is identification to type (T-72 vs Leopard), which also lets the pilot infer the side
    himself.
  - **Priority 2 before 3: a look toward type ranks before a look toward a class.** The ladder
    makes the distinction already: `current_level == "class"` in its type window
    (`unaided_type_m`, `binocular_type_m`] is one look from identification; `presence`/`unknown`
    in its class window is one look from a class. `choose_sighting_look` already ranks exactly that
    way for the 9K113 (*"first units not yet identified that might be inside identification
    range… same thing for class"*), so the glass step reuses its bucket. In practice the two rarely
    compete: for a 7 m vehicle the type window is 250–750 m and the class window 500–1750 m.
  - **Priority 3, classification:** the existing `can_still_improve` gate, unchanged.
  - **Priority 4, exact location: only for what the pilot asked about, ranked after
    classification.**
    - **Who qualifies, checked in the code, not assumed:**
      - *Enemy units*: no side is modelled (every contact is `UNKNOWN`, BL-B12). None today.
        When BL-B12 lands, "believed enemy" joins this predicate; noted on that entry.
      - *Mission target units*: **no such notion exists in body-layer** (grep: `mission_phase`
        holds MI-6's route and phases with points, not units; `mission_memory`'s `target_seq`/
        `target_ref` are attack-run records). Not built. It would come through the Mission
        Interpreter, which must also filter author-only knowledge first.
      - *Anything the player asks about*: a **watched** contact, i.e. effective attention
        `watch` or `priority` (`attention.effective_attention`, a voice "watch that truck at
        three o'clock" or a watch area). That is `LookTarget.watched`, already set in
        `body._look_targets`. An attack-run target is not attention-marked and is not added
        here (the pilot aims that run himself; the 9K113 run has its own sight path).
    - **Criterion:** `location_gain_m = position.range_uncertainty_m(observer) −
      look_sigma_m(R, BINOCULAR_OPTIC).sigma_down`, floored at 0; 0 with no `PositionEstimate`,
      and 0 beyond binocular presence range for the believed type (`tier_ranges`, the call
      `improvement_window_m` makes). Admitted when the contact is **watched** and the gain is at
      least `EXACT_LOCATION_MIN_GAIN_M`. Measured gain after naked-eye looks: ≈ 0.05 · R low
      (26 m at 500 m, 51 m at 1 km, 153 m at 3 km), less from altitude (7 m at 500 m and 26 m at
      1 km from 300 m AGL). So with the default below, a watched contact is glassed for position
      from ~0.5 km out at low level and ~1 km out from 300 m AGL; closer, the eye is already as
      good as binoculars.
    - **Admission, one predicate:** `can_still_improve(t) or (t.watched and t.location_gain_m ≥
      EXACT_LOCATION_MIN_GAIN_M)`, passed through the **existing** `can_improve` parameter to
      both `is_worth_a_look` and `look_is_finished`, so a location-only look neither fails to start
      nor ends on its first poll (the 9K113 narrow-search trap). `SIGHTING` is unchanged.
    - **Ordering:** `choose_glass_look` buckets the targets (0: `class` in its type window; 1:
      any other target `can_still_improve` admits; 2: exact location only) and runs `choose_look`
      unchanged (watched → coverage → nearest) inside the first non-empty bucket. Buckets 0–1 are
      `choose_sighting_look`'s own rule; the implementer shares the bucket function rather than
      writing a second. A location look still physically covers, and marks, any target in its
      envelope. **This is Decision 8 REVERSED** (location now after classification). Within a
      bucket, watched still comes first, so the 2026-09-25 *"even more so watched contacts"*
      stands inside each priority.
    - **No repeat at the same range**, from mechanisms that already exist: a look that fixed the
      range drives the gain to ≈ 0, and Stage 0a keeps it there for a growth-0 contact (for a
      moving class it re-grows over ~7 sweeps, Stage 0a); a look that fixed nothing leaves the
      level unchanged, so `GLASS_STALL_COOLDOWN_S` (180 s) governs, with the 80 % range escape
      untouched. So a watched armour group is re-glassed for position at most every ~3 min unless
      the aircraft closes on it.
    - **Budget:** watched contacts are few (the pilot names them), so this is a small, bounded
      demand on the 12 s window, far below the fourth pass's "one look per group per encounter".
    - New tunable, `status="judgement"`, `#needs-flight`:
      `belief.optic_policy.EXACT_LOCATION_MIN_GAIN_M`: **25.0** (lo 5.0, hi 500.0). First
      sentence: *"How much a binocular look must be expected to tighten the range of a contact the
      pilot asked to watch, in metres, before Petrovich raises binoculars just for its position."*
      Reasoning: about a vehicle group's own spacing; a smaller improvement is lost inside the
      group itself. **No cross-key coupling:** `BINOCULAR_RANGE_SIGMA_SCALE` at 1.0 makes the gain
      0 and location looks stop, the honest consequence.
    - **Binocular range sense stays as it is** (user, 2026-11-02: *"Binoculars range sense - keep
      the current."*): `BINOCULAR_RANGE_SIGMA_SCALE` = 0.7, still `#needs-flight`.
- **Body rotation: circling and sideways flight (user: *"~100 km/h and could include sideways
  movement and circling to keep safe distance"*).** Sectors are body-relative, so the ground under
  them turns whenever the aircraft does. At 28 m/s the rates are small: orbiting at 1.5–3 km turns
  the body 0.5–1°/s, and a contact abeam at 2 km drifts 0.8°/s even in straight flight. A
  rate-one turn is 3°/s. Checked by scratch simulation (sector windows at quiet 4 s steps, every
  start azimuth, both rotation senses):
  - **An orbited group is the easy case.** Circling a group keeps it at a constant body azimuth,
    so it sits in its own side sector and is glassed there. It never needs the ahead sector,
    because glassing is per sector, not ahead only.
  - **A contact can cross a sector boundary between sweep and step.** Without a margin, at
    0.5–3°/s the worst wait for a glass step covering it is **28 s** (16 s with no rotation): it
    misses the outgoing sector's step by a hair and the incoming one's by another. **With the
    half-field margin it is 16 s at 0.5°/s, 20 s at 1–2°/s, and 28 s only at 3°/s.** Hence the
    margin in the glass-step item above.
  - **A look must follow its contact.** Today a `GLASSING` sweep's steps are body azimuths fixed
    at look start. At 1°/s a 6 s look drifts 6°, which is past the 4.25° half-field. So: each
    `GLASSING` poll, if the chosen contact (`look_contact_id`) is in this poll's targets, shift
    `search_pattern_steps` and `look_envelope_azimuth_deg`/elevation by its body-azimuth and
    elevation change since the last poll. If it is absent, hold, as today. This is the 9K113 lock
    path's own approach (*"believed world bearing every poll"*) brought to binoculars, with no new
    field (Co-moving Fields). It is a pre-existing gap that the approach profile makes matter.
    Decision 9 is for the user to veto it as scope, and the default proceeds.
  - **Pre-existing, not introduced, stated:** the *eye's* own sweep aliases the same way. Today's
    table, quiet, at 0.5–2°/s: a contact crossing the 10/11 (or 1/2) leg boundary against the
    sweep at the wrong phase goes **~28 s** unseen. The sim gave 11 such cases in ~360 starts at
    1°/s. Add a full glass budget and that is ≈ 40 s, past the 30 s half-life (Decision 6's
    reasoning, a larger overrun, and rarer still). It stays below the 60 s group expiry and the
    120 s lost threshold, so I2's cliffs hold. Not fixed here: the fix is a perception cone
    overlap, outside this entry. The scenario test reports it.
- Nothing worth a look, or the budget does not admit one → straight on to the next sector, with
  no pause. A commanded narrow sector with nothing to resolve still gets its binocular search
  (`SEARCHING`) at the end of the pass, as today. `SEARCHING` is not counted against the glass
  budget: it runs only on a commanded single sector, which has no flank to protect.
- An interrupted step (unsteady, or the pilot's command calls `lower_binoculars`) ends the step and
  advances the sector. The time already spent counts. Pending marks drop as today (Fix B1).
- **Unchanged:** everything with `home_phase is SIGHTING` (the 9K113 has its own dwell/glance
  cycle; the glance-away `SCANNING` sub-state is a different branch), `_apply_guidance` (attack-run
  optic override), `MAX_LOOK_S`, `RETRY_RANGE_FRACTION` and `OPTIC_RETRY_INTERVAL_S` (still
  `4 × SCAN_CYCLE_PERIOD_S` = 64 s, because the cycle stays 16 s; the second pass's "pin at 64"
  item is no longer needed).
- **Revisit arithmetic (the trade the user should see).** Glass budget B = 12 s, rolling over
  four steps. A leg that is not glassed in the window is next seen after every sweep between its
  two passes plus every glass step between them. Poll slack is up to one 1 s poll per glass step
  that glasses (a step starts and ends on a poll).

  | leg | sweeps per cycle | quiet (nothing to glass) | worst, nominal | worst, with poll slack |
  |---|---|---|---|---|
  | **12** (dead ahead) | 2 | 8 s | 8 + 12 = 20 s | 22 s |
  | 11, 1 (ahead edges) | 1 | 16 s | 16 + 12 = 28 s | 32 s |
  | **10, 9, 2, 3** (flanks) | 1 | 16 s | 16 + 12 = 28 s | 32 s |
  | *today, every leg* | — | 16 s (12: 8 s) | 16 + 6 = 22 s | 23 s |
  | *second pass (3 sectors, 4 s steps)* | — | 14 s | 26 s | 29 s |
  | *pendulum alternative, flanks* | 1 | 20 s | 32 s | 36 s |

  **So the worst flank revisit is 28 s nominal and 32 s with poll slack, against
  `POSITION_HALF_LIFE_S` = 30 s.** The budget itself fits. The poll slack is what crosses the
  line, by up to 2 s, and only in a window where the whole 12 s was spent. The pendulum would
  cross it by 6 s. Decision 6, ANSWERED (*"For the overrun - ok."*), accepts it, with the invariant
  restated as below. The figures are for a non-rotating body. Rotation is covered under "Body
  rotation" above.
- **What crossing the half-life does, verified against the consumers of `certainty_of`/
  `POSITION_HALF_LIFE_S` (not the docstrings):**
  - **A flank contact that was not glassed in that window reads "estimated" instead of "tracked"
    for up to ~2 s, before the eye comes back.** No event fires: `lifecycle_event_kind` emits only
    on lost/reacquired, and lost is 120 s away. **No callout is added or dropped.**
  - **A watched contact's kilometre-crossing line** (watch-reporting) is withheld while
    "estimated" (`contacts.py`, `fresh` gate). It is announced at the next sighting, so it arrives
    up to ~2 s late. This is the one spoken effect, and only for a watched flank contact that
    crosses a kilometre boundary in that 2 s.
  - **Brain-facing phrasing hint** `"recent"` → `"remembered"` (`tools._PHRASING_CERTAINTY`) for
    those seconds. That only matters if the pilot asks a free-form question in that window.
  - **No re-acquisition churn.** Object continuity is 600 s (`OBJECT_ID_MEMORY_S`), groups are
    kept for 60 s (`GROUP_REIDENTIFY_WINDOW_S` = 2 × half-life), and the naked-eye acquisition
    debounce moves to the worst revisit (next item). `position_confidence` is a continuous decay
    (0.50 at 30 s, 0.48 at 32 s), with no step.
  - **Not affected by this choice, but louder than it:** the crew-query *"Last I saw"* freshness
    keys off `OBSERVED_WINDOW_S` (16 s), not the half-life. A flank contact is already "stale" for
    reports from 16 s, and in a busy window that now lasts to 28–32 s instead of 22–23 s. That
    follows from the budget, whatever Decision 6 says, and it is the existing "Coverage" risk.
  - **How often:** the worst case needs 12 s of binoculars inside one 16 s sweep cycle. That means
    at least two looks running the full 6 s without recognising anything, or several shorter ones.
    Under the selectivity rules a contact is glassed once in its improvement window, then not
    again for 64 s unless the aircraft closes to 80% of the range. With the new stall cooldown, a
    look that taught nothing waits longer still. So a full-budget window needs fresh in-window
    contacts arriving faster than one every ~10 s, or several contacts being closed on at once.
    That is a burst at first contact with a multi-group scene, lasting a cycle or two, not a steady
    state. A quiet scene is the bare 16 s sweep. The user confirms the design case (2026-11-02):
    *"a handful of groups a few km apart, typically. Larger missions have more units and groups,
    but still spread around."* So busy windows are rare in the missions flown. Exact-location looks
    (fifth pass) are for watched contacts only, so they add little. The Stage 1 scenario test
    measures it (below).
    Flight confirms it via `sortie-log-triage`'s certainty column. That is unmeasured until then,
    and stated as such.
- New tunables, `status="judgement"`, `#needs-flight`:
  - `perception.gaze.GLASS_BUDGET_PER_CYCLE_S`: **12.0** (lo 6.0, hi 30.0). First sentence: *"The
    most binocular time Petrovich spends across one full scan cycle, counted over the last cycle's
    glass steps, so no part of the windscreen waits longer than one sweep plus this."* The `lo`
    is `MAX_LOOK_S` written as a literal (an AST literal is required; `MAX_LOOK_S` is a plain
    `Final`, not tunable). Below it no look could ever start. **Declared in `perception.gaze`**
    beside `SCAN_PLAN`/`FOCUS_DWELL_S`, not in `optic_policy`. `naked_eye_source` needs the worst
    revisit, and perception must not import belief. `optic_policy` imports it from `gaze`. (The
    second pass put `GLASS_STEP_MAX_S` in `optic_policy` and `WORST_REVISIT_S` in `gaze`. That is
    an import inversion, now avoided.)
  - `belief.optic_policy.GLASS_STALL_COOLDOWN_S`: **180.0** (lo 60.0, hi 600.0). First sentence:
    *"How long binoculars leave a contact alone after a look at it taught nothing, unless the
    aircraft has closed on it since."* It is floored at `OPTIC_RETRY_INTERVAL_S` through an
    `_EFFECTIVE_` constant, the existing `_EFFECTIVE_SIGHT_STALL_COOLDOWN_S` pattern, so it is
    never shorter than the ordinary retry. Default reasoning: about ten quiet sweep cycles, or
    three ordinary retry intervals. Long enough that a stuck contact stops taking budget, short
    enough that one blocked by a transient cause (aspect, a tree line) is tried again inside an
    encounter. A starting value, same footing as `SIGHT_STALL_COOLDOWN_S`.
  - `GLASS_STEP_MAX_S` (second pass) and `SCAN_SECTOR_LEG_COUNT` (first pass) are **dropped**.
- **Cross-key coupling (an X-T26 trap, so checked, not commented).** Extend
  `tuning._check_scan_decay_coupling` to five keys: `FOCUS_DWELL_S`, `SCAN_PLAN`,
  `GLASS_BUDGET_PER_CYCLE_S`, `POSITION_HALF_LIFE_S`, `LOST_THRESHOLD_S`. Two invariants:
  - **I1, the existing one, unchanged:** `OBSERVED_WINDOW_S` (= `len(SCAN_PLAN)·FOCUS_DWELL_S`) <
    `POSITION_HALF_LIFE_S`. A *quiet* scene must keep every leg "observed"/"tracked" between
    passes, and the "tracked" band must exist. Defaults 16 < 30.
  - **I2, new, on the cliffs a revisit can actually fall off:** `WORST_REVISIT_S` =
    `len(SCAN_PLAN)·FOCUS_DWELL_S + GLASS_BUDGET_PER_CYCLE_S + n_sectors(SCAN_PLAN)·1.0` <
    `min(LOST_THRESHOLD_S, 2·POSITION_HALF_LIFE_S)`. Past `LOST_THRESHOLD_S` a flank contact would
    go lost → reacquired every busy cycle. That would mean audible `CONTACT_REACQUIRED` churn, and
    `LOST_THRESHOLD_S`'s own `lo` of 30 makes it reachable by a single in-bounds override today.
    Past `GROUP_REIDENTIFY_WINDOW_S` (2 × half-life) its group would expire and re-form. Defaults
    32 < min(120, 60). The `1.0` is the poll slack, a literal in `tuning` (`tuning` cannot import
    `body.py`'s `_DEFAULT_POLL_INTERVAL_S`; the comment cites it).
  - **Not an invariant, per Decision 6 (ANSWERED, *"ok"*):** worst revisit <
    `POSITION_HALF_LIFE_S`. It is written down as an accepted overrun (≤ 2 s at defaults), with
    the consequences listed above. `[[BL-B112]]` (motion-aware certainty, queued after this entry)
    would make it moot for stationary contacts.

  `n_sectors` comes from the same partition function `gaze` uses, placed where `tuning` can import
  it without importing `perception.gaze` (which imports `tuning`). The Implementer verifies the
  import graph instead of assuming it. A matching assert in `belief.decay` catches a code-default
  violation of I2 loudly, like the existing one for I1.
- **Derived windows that assumed "one cycle" = the bare sweep** (architect memory
  `feedback_scan_cycle_means_true_revisit`). With the table unchanged, `SCAN_CYCLE_PERIOD_S` stays
  16 s while the true revisit grows. Each consumer is decided:
  - `naked_eye_source._ACQUISITION_RETENTION_WINDOW_S` (= cycle) **must span the true revisit**,
    or a flank object ages out before the eye returns and is re-acquired as "newly visible" every
    busy cycle, defeating the debounce its own docstring (point 4a) exists for. **It moves to
    `WORST_REVISIT_S`** (32 s), exported from `gaze`.
  - `decay.OBSERVED_WINDOW_S` (= cycle, "seen within the current scan cycle") **stays on the bare
    sweep, 16 s.** Moving it to 32 s would put it above the half-life and break I1.
  - `optic_policy.OPTIC_RETRY_INTERVAL_S` stays `4 × SCAN_CYCLE_PERIOD_S` = 64 s unchanged.
  - `body.py`'s `SCAN_CYCLE_PERIOD_S` argument to `decide` is replaced by the sector period (as
    already planned).
- `decide`'s `scan_cycle_period_s` becomes `sector_period_s` plus the sector wedge, the sector
  count and the budget. That is a mechanical rename across ~130 test call sites.

*Downstream effects, named:*
- **Callout timing:** a new contact is glassed at most one sector sweep (4 s) after it is first
  seen, budget permitting, not up to 16 s. `CONTACT_CLASSIFICATION_CHANGED` follows
  `CONTACT_DETECTED` sooner and more often. The scheduler's one-line-at-a-time rule is unchanged,
  so this is a denser stream, not a backlog.
- **Binocular time:** up to 12 s per ~16 s cycle in a busy scene, against today's one look of at
  most 6 s per ~22 s. In a quiet scene it is zero, as today.
- **Coverage:** the worst full revisit goes from 22–23 s to 28–32 s in a full-budget window
  (table above). The "Last I saw" report effect and the ≤ 2 s "estimated" overrun are the visible
  edges, both named above.
- **Ahead:** 12 o'clock is swept every 8 s, as today. Ahead gets two glass steps per cycle.
- **9K113:** no change while OBSERV is on. After "Observ off", scanning restarts at sector 0 with
  a cleared budget window (see Co-moving Fields).
- **Commanded sectors** really do bring binoculars round faster now: one o'clock hour means a look
  after every 2 s pass, budget permitting. This is the user's own 2026-09-23 *"o'clock scan is
  faster, allowing more frequent binocular use"*, now true in flight.

*Tests that must be rewritten, not extended (escalation item, Decision 3, approved):*
`TestPhaseCycle`'s premise is "a look only after a completed full cycle". It covers
`test_binoculars_are_not_raised_mid_scan` (becomes mid-*sector*),
`..._come_up_at_the_end_of_a_completed_scan`, `test_a_faster_scan_plan_brings_them_round_sooner`
(now a body-level wiring test), `test_nothing_worth_looking_at_restarts_the_scan` (now advances
the sector), and `test_the_scan_must_complete_again_before_the_next_look`. The last one's premise
is **reversed**: two looks may now follow each other inside one glass step. Its replacement asserts
that the eye must sweep again **between glass steps**. `test_gaze.py`'s free-scan cycling tests
keep their premise, because `FREE_SCAN_PLAN` without an anchor keeps absolute indexing for
non-optic callers. The other ~120 call sites are the rename only.

*Tests whose numbers change:* **none expected from the scan table any more**, since the default
`SCAN_PLAN` and the 16 s cycle are unchanged. The second pass's list (`test_gaze.py` ~137–160,
`test_decay.py` ~65–76, `test_naked_eye_source.py` timings) drops out. A test that pins the
acquisition-retention window at 16 s does change (data). **Rule for the Implementer, unchanged:**
if a test only needs its expected values recomputed, update it. If its *premise* breaks, stop and
report it.

New tests:
- sector partition and order (default table → ahead 12,11 / left 10,9 / ahead 12,1 / right 2,3;
  the pendulum table → four sectors too; a three-third table (9…3) → three; boundary legs go to
  ahead; the cyclic first/last merge)
- a quiet cycle is exactly `SCAN_CYCLE_PERIOD_S` at 1 s polls (no per-sector drift)
- worst revisit at 1 s polls with a target in every sector, measured (not only the formula): the
  measured worst ≤ `WORST_REVISIT_S`, and the measured fraction of polls with a swept contact in
  "estimated" is reported. A flank object is not re-acquired as new across a busy cycle
  (`_ACQUISITION_RETENTION_WINDOW_S`)
- the rolling budget: a full step 3 followed by step 0 of the next cycle cannot exceed 12 s
  inside one flank revisit window (the case the scalar reset gets wrong)
- the budget gates starts, not lengths: with 7 s spent no look starts; a look started with 6 s
  left runs to its natural end or `MAX_LOOK_S`, never cut
- the scan clock pauses during glassing (no leg skipped)
- the target filter is limited to the sector
- `GLASSING` stall cooldown: a look that did not move the level → not re-admitted at 64 s at the
  same range; re-admitted at once after closing to 80%; re-admitted after the cooldown
- interrupt advances the sector and counts the time spent
- command change and "Observ off" → sector 0, cleared budget window
- the commanded-sector cadence through `body.run_once` (the wiring test the old test never was)
- the coupling check rejects a violating `tuning.toml` (e.g. `LOST_THRESHOLD_S = 30.0` with
  defaults elsewhere, which violates I2), falling back on every file-set coupled key, and accepts
  the pendulum table at defaults

Fourth pass, new tests:
- **The scenario test flies the user's approach profile, not only a straight line** (user:
  *"~100 km/h and could include sideways movement and circling"*). Three legs at 28 m/s and 1 s
  polls, over a scene of the user's density: three groups 2–3 km apart, first seen at 3–5 km.
  1. A straight approach (the baseline the revisit formula describes).
  2. A sideways leg: heading held, track 90° off.
  3. An orbit of 2.5 km radius around one group, with the others off-centre.

  One group in the scene is watched. Measured and reported for each leg: **no unwatched contact
  gets a location-only look** (fifth pass: priority 1 needs none); the watched contact gets one
  where its gain admits it and is not location-glassed twice at the same range inside
  `GLASS_STALL_COOLDOWN_S`; the worst wait from first sighting
  to a glass step covering the contact (≤ 20 s at ≤ 2°/s); the worst eye revisit, with the
  rotational aliasing case reported rather than asserted; the fraction of polls with a swept
  contact "estimated"; and no flank re-acquisition churn. The straight leg alone keeps the
  existing assertions (worst revisit ≤ `WORST_REVISIT_S`).
- `location_gain_m`: 0 without a `PositionEstimate`, and 0 beyond binocular presence range; equal to
  `range_uncertainty_m − σ_b` otherwise; ≈ 0 after a binocular fuse (the table above, as a test).
- *(Group reduction test dropped, fifth pass: no group reduction.)*
- A **watched** location-only target (outside its classification window) starts a look, and the
  look does not end on its first poll. It ends once the fuse drops the gain. The same target
  **unwatched** is not admitted, whatever its gain.
- `choose_glass_look` (fifth pass): a `class` contact in its type window beats a `presence`
  contact in its class window, even one with more coverage or watched; a classification target
  beats a watched exact-location target; inside a bucket, `choose_look`'s order (watched →
  coverage → nearest) is unchanged. The sight's `choose_sighting_look` gives the same answer as
  before on its own existing tests (shared bucket function).
- Fifth pass, `test_estimation.py`, the rough-location fence (Stage 1, "Priority 1"): over R in
  0.5–6 km and height above the unit 0–800 m, ground (`surface_range_estimate`) and air
  (`look_sigma_m`), the naked eye's own declared σ_down ≤ 0.2 · R and its cross-range
  angle ≤ 15°. The assertion message says what failing means: priority-1 binocular looks would
  then be needed, which this plan does not build (Decision 10).
- A failed location look (gain unchanged, level unchanged) is not re-admitted before
  `GLASS_STALL_COOLDOWN_S`, unless the range has closed to 80%.
- Sector margin: a contact 3° outside the swept sector's edge is a target, 5° outside is not;
  a boundary contact is glassed once, not twice.
- Look follows its contact: under a 2°/s body rotation, the chosen contact stays inside the
  envelope for the whole look, and every step moves by the same delta; an absent chosen contact
  leaves the steps unchanged.
- **Stage 0a, in `test_position_belief.py`** (Decision 7 ANSWERED (a)): binocular fix, then six
  naked fuses at the same geometry, at 16 s spacing. **Growth 0 (installation component):** 1σ
  range never rises above the post-fix value. **Armour (8 m/s):** after each fuse, 1σ ≤ the
  prior's inflated 1σ, and it reaches naked grade no sooner than ~6 fuses (the fourth pass's
  "never rises above the post-fix value" is false for a class with growth, so it is split). A
  naked-only dwell converges as today (the cap never binds there). A founding look is unchanged.
  BL-B108's own tests are run before and after, per Stage 0a: **if any fence or assertion moves,
  stop and report.**

**Stage 2, seventh-pass redesign (2026-11-10): not built in BL-B110 unless the user chooses
otherwise (Decision 13).** The design below it is kept for the record and for option (b).

*Effort/value (`AGENTS.md`).*
- **The challenge is not the code.** That is small: a keyword on `passes_gate`, one pure predicate,
  a believed-distinct pair on `ContactStore`, and one skip in the merge-echo check, about one
  implementer pass.
- **The challenge is that the trigger has almost nothing to act on.** The honest grid shows the
  gate cannot tell two groups 1.5 km apart on one bearing from one group seen twice. Each is about
  2σ under the eye's 0.17 R range error, and no rearrangement of the same numbers adds information.
  What the pilot would get:
  - one cell family (far group glassed, near group seen by eye) drops from 70–86% unannounced to
    58–79%;
  - nothing in eye → bino;
  - nothing on the larger merge-echo path, 50–60 points in eye → eye.
- **What he might assume he gets, and would not:** "two groups on one bearing are called as two".
  E1 is **not** delivered by Stage 2 on honest numbers. Only a look adds the missing information:
  `[[BL-B111]]`'s check of A's area, which can see A there.

*The redesign, recommended (Decision 13 (a)):*
1. **BL-B110 closes on what it shipped** (Stages 0a, 0, 1), plus Stage 5's docs and card, and this
   honest grid recorded on `BL-B110.md` as the measured residual. That is Stage 2b's own "record the
   residual and stop", except the rule's other branch also fires (point 3).
2. **The believed-distinct pair and the merge-echo skip move to `[[BL-B111]]`.** That is the first
   mechanism that can conclude "different" from new information. Its "A seen in its area, so B is
   different" verdict needs exactly these two pieces. They are built once, where they carry weight,
   not twice.
3. **Stage 2b's anchor follow-on and BL-B111's look are the same question now**: what new
   information separates two groups on one bearing? BL-B111's own goal check should take both.
   Opening a third entry would split it.
4. **The merge-echo gap gets its own entry (Decision 14).** It is the larger silent path, and it is
   not this feature's mechanism.

*If the user chooses (b), build Stage 2 one-sided as written below, with these acceptance numbers
replacing every earlier one* (production trigger in place of the stand-in, the same grid and harness
as the honest grid, fences at `n = 300`):
- **Same group, trigger-added split ≤ 2% in every cell** of {`u_u`, `b_b`, `u_b`, `b_u`} × {2.0,
  3.0, 4.5 km} × {6, 700 s} × {`s-125`, armour}, plus the ground cells. Measured ≤ 0.3%.
- **Same group, total duplicate the pilot hears ≤ today's rate + 2 points per cell.** Today's rate
  is the honest grid's first column. This fence is the one that answers the user's ~10% question
  with BL-B113 included. It does not fence BL-B113 itself, which the user deferred.
- **Characterisations, not gates:** bino → eye, B nearer, 4.5/3.0 and 5.0/3.5: unannounced
  ≤ 85% (measured 58–79%). Every other different-groups cell unchanged from today within the CI.
- `test_expected_area_trigger.py`'s re-measured floors (`_FAR_BINOCULAR_NEAR_UNAIDED_RESIDUAL_
  FLOOR`, the 20% long-gap ceiling) are replaced by these. They are already marked "premise gone".
- `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact`: the Decision 3 restatement
  as a fence still applies. Re-measure it on the fixed harness. Do not carry the 90–96% figure.

*Original Stage 2 (second to sixth pass), kept for the record:*

**Stage 2 — Never fold an ambiguous memory-only match (E1 delivered, Q3 as the default).**
- **Trigger** (`ContactStore.ingest`, gate branch only, never continuity), all of:
  - the percept resolves through the gate onto A: the single passing candidate, or the
    within-group ambiguous-fold target;
  - A is not claimed by any observation in this poll (A was not in this look);
  - `passes_gate(percept, A, now, as_if_optic_class=<Stage 0 choice>)` is **False**. That means:
    had A been in this very look, this percept would read as a different thing.
  - **(Stage 1b, sixth pass) B reads nearer than A should be:** `percept.range_m <` the range from
    this observer to A's believed position (the gate's own `hypothesis_range_m`). Same-group false
    split 3–6% instead of 15–20%. *(Superseded numbers. Honest: ≤ 0.3% instead of 2–5%.)*

  Perceived quantities and model parameters only, the same correlation helper as BL-B108, no new
  constant. All four conditions are evaluated in **one** pure predicate in
  `association_over_time.py`, which `ingest` calls (the "when" in one place). The Stage 0 variant
  is fixed: Variant 2, with only the correlation class set to the tighter optic. The direction
  condition is a separate clause in that predicate, not folded into `passes_gate`, which stays a
  gate.
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
    → (sixth pass) It is Stage 1b's fence instead: ≤ 10% per cell, over Stage 1b's grid, with the
    production trigger in place of the stand-in. The sweep's fence ceilings are lowered from the
    **resampled** harness (Stage 1b step 1), never from the fixed-draw numbers.
  - E1a in `test_relative_distance_scenarios.py` asserts two callouts **spoken**, cross-optic and
    memory-only.
  - A merge-echo test: a believed-distinct B is spoken.
- **`test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact` asserts exactly 100%.**
  Under Stage 2, the gate-only harness measures 90–96% at the cross-optic cells. That guarantee
  is restated as a fence (Decision 3, approved: *"ok"*). It is the one E2/E3 trade this stage
  makes, and it is the direction the user chose in Q3. Until `[[BL-B111]]` ships its "same"
  verdict, this 4–10% false split is what the pilot lives with.

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

#### Stages 3–4 — moved to `[[BL-B111]]` (not built in this feature)

User Decision 2, *"as recommended"*: these are a separate entry, `body-layer/ROADMAP/BL-B111.md`,
opened now and depending on BL-B110. The visibility source is **option (a), a point line-of-sight
query through the existing LOS Hook.** The design below is kept as BL-B111's starting point. That
entry gets its own goal check and architect pass, which must re-read it against what Stages 0–2
actually shipped (the Stage 0 trigger choice, the final glass budget and its rolling window).
Numbers below are updated for the third pass's four-sector scan.

**Stage 3 — Was A's expected place visible? (BL-B111; source: option (a).)**

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

**Stage 4 — The expected-area check proper (BL-B111, after Stage 3).** All of the user's Q2–Q5
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
  - free scan (four 4 s sectors, third pass): ≤ remaining sweep (≤ 4 s) + B's look and A's area
    look (≤ 2 × `MAX_LOOK_S` = 12 s; `area_check` targets rank first in the step) + 1 s
    ≈ **17 s worst**, about 5–8 s typical (one shared look, ended early);
  - if the rolling glass budget does not admit a look when the step comes, the check resolves
    "cannot look" at that step's end (≈ 5 s): B is released as new, per Q3;
  - one o'clock hour: 2 + 12 + 1 ≈ 15 s worst.

  *(Second pass: ≈ 11 s, on a 4 s per-step cap the user rejected.)* This bound sits well above
  `CALLOUT_MAX_AGE_S` (10 s), so the age-from-release rule below is required. BL-B111's own pass
  should decide whether area-check looks are exempt from the glass budget, which would trade the
  "cannot look" release for a longer flank revisit.

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
| area seen empty (Stage 3), composition compatible, displacement plausible | same: `relocate(A, from=B)`, remove B | Q4a: A's line with its new place, worded neutrally, ≈ *"A now at …"* (user Decision 4) |
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
- **Wording (user Decision 4, *"~"A now at...""*):** the relocation line is neutral, along the
  lines of *"That group, now two o'clock, three kilometres."* It never says "has moved", because
  Petrovich cannot tell a move from a misjudged range, and "now at" is true of both. Settle the
  exact template together with `[[BL-B109]]`'s wording `/explore`.
- Tests (scenario, 1 s polls): one per verdict row, the 11 s bound, age-from-release, the hold
  never dropping, a masked area ⇒ "cannot look" (not "empty"), the ATGM pause, a threat B spoken
  immediately, and every row of the Co-moving Fields table.

**Stage 5 — Docs, entry, test card (BL-B110, after Stages 0–2).** `STRUCTURE.md`; regenerate
`defaults.toml` and read the **rendered** first sentences; `BL-B110.md` updated with what shipped
and the measured residual and false-split rates; the test card names `main` and `#needs-flight`. The card also carries (re-check 3 Question 3, user 2026-11-03): *while circling or sidestepping,
watch for a contact that goes unspoken for ~30–40 s as it crosses a sector edge; report it if
noticed, and it gets its own entry then.*
Cards:
- free scan, listening for the ahead → left → ahead → right rhythm: a 4 s eye sweep, binoculars
  on what is worth it there, the next sector. Note too how soon a new contact dead ahead is picked
  up (alignment re-check finding 4);
- free scan with several contacts in binocular range, watching that no look is cut short and that
  a contact already glassed at the same range is not glassed again every minute;
- free scan, two groups on one bearing, far one glassed first, then crest a ridge (expect two
  callouts);
- a commanded o'clock scan, listening for binocular cadence;
- (fourth pass) the user's own approach: ~100 km/h toward two or three groups at 3–5 km, then a
  sidestep and an orbit at a safe distance. Watch for binoculars going to each group once while
  it is far (location), and again once inside classification range, but not every minute. Watch
  too that a look holds its group through the turn.

The "group moves out of its area while hidden" card belongs to `[[BL-B111]]`.

### Co-moving Fields

Built from construction sites, re-grepped on the third pass (`grep -n 'OpticState('
body-layer/src`): two fresh constructions in `optic_policy.py`, the SEARCHING entry (~2927) and
the GLASSING entry (~3006), plus every `replace(…)` of the optic state (26 in `optic_policy.py`,
and the sites in `body.py`). **Three new fields:**
- `scan_sector_index`
- `glass_step_started_sim` (the current step's clock)
- `glass_recent_steps_s: tuple[float, ...]`, the glass time of the last n−1 completed steps (the
  rolling budget; replaces the scalar `glass_cycle_spent_s` that alternative (b) named, for the
  reason given in Stage 1)

Both fresh-construction sites must carry all three forward explicitly, the BL-B71 lesson.

**Fourth and fifth pass: no new `OpticState` field.** Exact-location looks add one `LookTarget`
field (`location_gain_m`; the fourth pass's `group_id` is dropped), a per-poll input and not
state. `watched` already exists. Stage 0a adds no state either: the cap reads the prior the fuse
already has. There are two `LookTarget(` sites in `src`: `look_target_for`, and
`_target_in_current_look`'s probe centre, which takes the defaults. Look-follow moves four
existing fields together, so it gets the two rows at the end of the table. The delta needs the
chosen contact's previous azimuth/elevation, and that is already on the state: it is the current
envelope centre, which is updated each poll. The
budget check reads `sum(glass_recent_steps_s) + (now − glass_step_started_sim)`.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `phase_started_sim`, `scan_sector_index`, `glass_recent_steps_s` | first poll (`phase_started_sim is None`) | start | sector 0, sweep anchored now, window empty `()` |
| `scan_sector_index`, `glass_step_started_sim` | internal (`decide`) | sector sweep ends, ≥ 1 target in sector **and** the budget admits a look | phase GLASSING, step clock = now, sector index **unchanged** until the step ends |
| `glass_step_started_sim`, `glass_recent_steps_s` | internal | look ends naturally or at `MAX_LOOK_S`, next in-sector target, budget admits another | new GLASSING entry (fresh construction) carries the step clock (**not** reset) and the window unchanged; pending marks committed for the finished look only |
| `scan_sector_index`, `phase_started_sim`, `glass_recent_steps_s` | internal | step ends (nothing left, or the budget does not admit another look) | window ← last n−1 of (window + `now − step clock`); index + 1 mod n; `SCANNING` anchored now; step clock `None` |
| same | internal | sweep ends with nothing to glass, or targets but no budget | window ← last n−1 of (window + 0.0); index + 1 mod n; `SCANNING` anchored at **previous anchor + sector period** (no drift); step clock stays `None` |
| same | **external**: `lower_binoculars` (player command) while GLASSING | interrupt | as the "step ends" row (the time spent counts); pending marks dropped (Fix B1) |
| `scan_sector_index`, `phase_started_sim` | **external**: `lower_binoculars` while SEARCHING | interrupt | advance as the "nothing to glass" row; SEARCHING time is not counted (window + 0.0) |
| same | **external**: `lower_binoculars` while SCANNING-at-home | none | unchanged (existing `test_lowering_while_already_scanning_changes_nothing` stands) |
| `scan_sector_index`, `phase_started_sim`, `glass_recent_steps_s` | **external**: scan command issued or cancelled (`command_t_sim`/sector identity changes; *not* compass legs recomputed from heading) | plan change | index 0; window cleared `()`; if SCANNING, anchored now; if GLASSING, the step finishes (its time is dropped with the cleared window), then index 0 |
| `scan_sector_index`, `glass_recent_steps_s` | **external**: OBSERV off (`body.py` observed edge, `_force_observ_off`) | SIGHTING → SCANNING home | index 0, anchored now, step clock `None`, window cleared `()` |
| `scan_sector_index`, `glass_recent_steps_s` | **external**: OBSERV on | SCANNING → SIGHTING home | unchanged and unread while SIGHTING; step clock `None` |
| `hands_busy_until_sim` | external | any | no sector/step/window change (a suppressed poll advances nothing, as today) |
| `search_pattern_steps`, `look_envelope_azimuth_deg`, `look_azimuth_deg`, `look_elevation_deg` (fourth pass, look-follow) | internal (`GLASSING` poll) | chosen contact (`look_contact_id`) present in this poll's targets | every step and the envelope centre shifted by the **same** azimuth/elevation delta (the contact's change since last poll); `look_envelope_half_width_deg`, `phase_started_sim` and the step index unchanged, so the step clock is not reset |
| same | internal | chosen contact absent this poll | all unchanged (hold, as today) |

`n` is the sector count from the partition (4 with the default table). The window is truncated to
the new n−1 whenever n changes, which only happens on the plan-change row, where it is cleared
anyway. **Clearing on the two "index 0" rows is a deliberate gap in the budget's bound:** a pilot
who issues scan commands back to back could get more than 12 s of binoculars inside one window.
That is pilot-driven, rare, and the eye path restarts there anyway, so a revisit bound across it
means little. Stated rather than closed.

Stage 4 (**`[[BL-B111]]`**) adds a second set: the contact-removal set for `relocate(A, from=B)`,
to be grep-verified at implementation.
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
- **(Seventh pass) The duplicate the pilot hears is mostly `[[BL-B113]]`, not the trigger.** Past
  120 s a same-optic re-sighting is announced as a new group 10–12% of the time by eye, with or
  without Stage 2. The user deferred it (*"If this becomes a problem in missions, we'll investigate
  more, but not now."*). A SAM site called twice after a long gap is the flight signature.
- **(Seventh pass) Merge-echo silencing hides real second groups** (50–60 points, eye → eye, A not
  lost). It is unattributed. Decision 14. If flights show a nearer group on a remembered bearing
  never called, look here before at the gate.
- **(Seventh pass) The harness's cross-range systematic bias is a fixed draw.** `bias:1` and
  `bias:2` hash to −1.43 and −1.40, and the hash is not salted. Both looks carry nearly the same
  −0.56σ cross offset in every trial, so it cancels in the innovation. That is realistic for one
  object seen twice, and optimistic for two groups that would have independent biases. Not
  resampled here. It biases the different-groups rows slightly toward folding.
- *(Superseded numbers, seventh pass)* **The Stage 0 false-trigger rate is the duplicate rate the pilot hears** after Stage 2. Gate-path
  same-group re-sightings occur only past the 600 s continuity window or when clusters re-form.
  How often that happens in flight is unmeasured. `sortie-log-triage` can count gate-path
  foundings near a remembered contact.
- **(Sixth pass) The trigger is one-sided.** A different group that reads *farther* than a
  remembered one on its bearing folds at BL-B108's rate (~28% in the measured cell). That is
  unchanged from today, and only `[[BL-B111]]` reaches it. If flights show a far second group
  being swallowed, that is where to look (Decision 12).
- **(Sixth pass) BL-B108's own sweep fences were measured with the same fixed look-to-look draw**
  (Stage 1b step 1). Re-measuring them resampled may move a fence. If it does, the work stops
  and the user hears both outputs. It is a test-correctness fix, but it touches a merged entry's
  guarantees.
- **(Sixth pass) Ground cells are unmeasured.** The 3–6% is air-path. A SAM site is ranged through
  the depression cue, which has its own field and correlation. Stage 1b measures it before Stage 2
  is built.
- **The far-unaided → near-binocular residual (up to 26%)** survives Stage 2, and Stage 4 does not
  touch it: no trigger, no check. Only a tighter trigger (Stage 0) or anchors (Stage 2b) reach it.
- **Stage 3 on the recommended option is cross-subproject Lua with a Windows-only verification.**
  It fails closed. The 1 Hz Hook cadence adds ~1 s to the hold.
- **Stage 4 introduces contact removal**, which this store has never had (architect memory
  `contact-dup-continuity-of-track`: "`ContactStore` has no contact-deletion mechanism at all").
  Every consumer of a contact id is a place a dangling id can surface.
- **Wording (Q4a):** Petrovich cannot tell "A moved" from "A was misjudged in range". Both
  produce the same verdict. "Has moved" asserts motion he did not see. Resolved by user Decision
  4 (neutral "now at").
- **Worst revisit 28 s nominal, 32 s with poll slack, against `POSITION_HALF_LIFE_S` (30 s)**
  in a window where the whole 12 s budget is spent. Accepted under Decision 6 (ANSWERED, *"ok"*): a flank contact
  not glassed in that window reads "estimated" for ≤ 2 s. The only spoken effect is a watched
  contact's kilometre-crossing line arriving ≤ 2 s late. How often the full budget is spent is
  unmeasured until flight; the Stage 1 scenario test reports the synthetic figure.
- **Binocular time roughly doubles in a busy scene** (12 s per 16 s cycle against today's ≤ 6 s
  per 22 s). Selectivity is meant to keep that rare. If flights show binoculars up most of the
  time anyway, the levers are `GLASS_BUDGET_PER_CYCLE_S` and `GLASS_STALL_COOLDOWN_S`, both
  tunable.
- **`GLASS_STALL_COOLDOWN_S` (180 s) is unflown**, and it is the first time `GLASSING` gets a
  stall rule. Too long, and a contact that failed once because of a transient cause (aspect, a tree
  line, a manoeuvre) is not glassed again for three minutes unless the aircraft closes on it. The
  80% range escape is the guard.
- **Start-gated budget leaves time unused:** once more than 6 s is spent in a window, no look
  starts, so a busy window may glass only 6–12 s. This is the price of never cutting a look short
  (user re-check). Stated, not tuned away.
- **The budget window is cleared on a scan command or "Observ off"**, so repeated commands can
  exceed 12 s in one window (Co-moving Fields). It is pilot-driven and stated.
- **No naked-eye detection timing changes**: the table and the 16 s cycle stay. The
  `_ACQUISITION_RETENTION_WINDOW_S` move (16 → 32 s) is what keeps the longer busy revisit from
  turning into re-acquisition churn. The Stage 1 scenario test must show no new-object churn on a
  flank object across a busy cycle before Stage 1 merges.
- **A binocular look is worth little for position, in the model (effort/value, fourth pass,
  narrowed by the fifth).** It tightens range by ~30 % (≈ 0.05 R: ±510 → ±357 m at 3 km) and
  bearing not at all. That is why priority 1 needs no look, and why exact location is limited to
  watched contacts. The whole gain is `BINOCULAR_RANGE_SIGMA_SCALE` = 0.7, kept by the user
  (*"keep the current"*) and still `#needs-flight`. The build is cheap: one predicate through an
  existing parameter, one bucket, one `LookTarget` field.
- **The rough-location conclusion rests on `RANGE_FRACTIONAL_SIGMA` = 0.17 being under the 0.2 ·
  R allowance** (and on the eye's bearing being well inside an o'clock). A later change to the
  naked-eye model that widens it would silently make priority 1 need binoculars. The
  `test_estimation.py` fence is what makes that visible (Decision 10).
- **Type-before-class ordering can delay a watched contact's classification** behind an
  unwatched contact's identification in the same glass step. Rare (the windows barely overlap:
  type 250–750 m, class 500–1750 m for a vehicle) and one step long. It is the user's priority
  order; watched still wins inside each bucket.
- **Stage 0a (Decision 7 (a)) touches BL-B108's fold, merged the day before.** The cap only ever
  binds when a prior is tighter than this look's own floor, which is the better-optic-then-eye case
  and the triangulated-then-same-geometry case. The second case is the one the cap changes beyond
  location looks: a triangulated estimate would no longer be pulled back to single-geometry
  precision. That is arguably also right ("new evidence never makes the belief less certain"),
  but it is a BL-B108 behaviour change. Hence BL-B108's tests are re-run first, and any moved
  fence stops the work.
- **Rotational eye aliasing (pre-existing):** ~28 s quiet, ≈ 40 s with a full glass budget, for
  a contact crossing a leg boundary against the sweep at 0.5–2°/s. That is the user's own approach
  profile. It stays below the group-expiry and lost cliffs. `_ACQUISITION_RETENTION_WINDOW_S` at
  `WORST_REVISIT_S` (32 s) does not span it, so a flank re-acquisition debounce can re-run in that
  case. The cost is a debounce delay, not a new contact (object permanence 600 s). The scenario
  test reports it. A perception-side cone overlap is the fix, and it is not in this entry.
- **Look-follow tracks the *belief*, not truth.** When a fuse moves the believed mean, the look
  moves with it. That is where Petrovich believes the group is, so it is honest. A large jump
  could swing the look off the real group for the rest of that look. That is bounded by
  `MAX_LOOK_S`, and the attempted marks stop it repeating.
- *(Superseded, fifth pass: the fourth pass's group-reduction straggler risk; there is no group
  reduction. A watched contact's own fix still mixes into its group's mean centroid with
  naked-grade siblings, which is harmless at rough-location grade.)*
- *(Superseded, third pass: the second pass's "revisit 26 s (29 s with slack) / glass budget 4 s"
  and "reshaping `SCAN_PLAN` to 9 → 3, ahead once per cycle" risks no longer apply.)*
- **Stages 3–4 (`[[BL-B111]]`), when built:** cross-subproject Lua with a Windows-only
  verification, and the first contact removal in `ContactStore`. Both risks are listed above and
  move with the entry.

### Second-order effect

Seventh pass:
- **`[[BL-B109]]` is not unblocked by BL-B110.** The precondition it named was "two groups on one
  bearing reliably two contacts across optics", and on honest numbers no gate-side trigger delivers
  that. Its precondition moves to `[[BL-B111]]` (and to Decision 14's entry for the same-optic,
  short-gap half).
- **`[[BL-B111]]`'s value rises and its scope grows by two small pieces**: the believed-distinct
  pair and the merge-echo skip. It is now the only planned mechanism for E1.

*(Earlier passes; the first sentence below is superseded by the seventh pass.)*
Stage 2 makes two groups on one bearing reliably two contacts across optics. That is the
precondition `[[BL-B109]]` ("second group, beyond") named for itself, so this unblocks it.
`[[BL-B111]]`'s Q4a line is the same wording problem, and the two should be explored together.
**Stage 1 lengthens BL-B111's hold.** With no per-step cap, B's look and A's area look can take
up to 2 × 6 s in one step, so the structural hold bound becomes ≈ 17 s worst, ≈ 5–8 s typical.
The second pass had ≈ 11 s on a 4 s step cap. That is still bounded and still structural, but it
is well past `CALLOUT_MAX_AGE_S` (10 s): BL-B111's age-from-release rule moves from "required" to
"load-bearing". BL-B111 must also decide whether area-check looks spend the shared glass budget.
If they do, a spent budget releases B as new ("cannot look"). If they are exempt, the flank
revisit bound loosens. The `GLASSING` stall cooldown is the first binocular-side use of
`BL-B85`'s mechanism; a later wish to retune both together has one pattern to follow. Stage 1's
per-sector glass step is also the slot a future 9K113-at-home check (OBSERV on) would reuse
through `choose_sighting_look`.

Sixth pass:
- **`[[BL-B112]]` is unaffected, and it is not a fix for the trigger.** A stationary contact
  already has zero growth. BL-B112 would extend zero growth to observed-stationary armour, which
  moves those contacts into the regime Stage 1b's stationary cells already fence. BL-B112's own
  pass should cite that fence rather than re-derive it.
- **`[[BL-B111]]` gains a target.** The far-B fold the one-sided trigger leaves is a case only its
  look can settle. That adds to its value, not its scope.

Fourth pass:
- **Decision 7 (a) reaches beyond binoculars.** A 9K113 stadiametric fix (k = 0.5/0.3) reverts
  under naked-eye looks today by the same mechanism. The cap keeps it, which helps attack-run
  alignment on a contact last ranged through the sight.
- **`[[BL-B112]]`** (motion-aware certainty) and location looks pull the same way. A stationary
  group's covariance does not grow, so once located it stays located, and BL-B112 would keep its
  label "tracked" to match.
- **Stage 0 must be measured on the post-floor code** (now Stage 0a, built first).

Fifth pass:
- **`[[BL-B12]]` gains a hook, not work.** When believed side exists, "believed enemy" joins the
  exact-location predicate beside `watched` (the user's *"for enemy units especially"*), and type
  identification, already ranked second, becomes its input. Noted on BL-B12.
- **A mission-target notion does not exist in body-layer.** When the Mission Interpreter hands one
  over (after filtering author-only knowledge), it joins the same predicate. Nothing is built.

### How each alignment item is answered

- **E1 (seventh pass): not delivered by BL-B110.** On honest numbers the trigger moves one cell
  family by 5–15 points, and a nearer group on a remembered bearing stays unannounced 58–86%
  cross-optic and 63–73% eye → eye (merge echo). E1 now rests on `[[BL-B111]]` and Decision 14's
  entry. Plan-aligner should treat it as moved, not met.
- *(Superseded, seventh pass)* **E1**: Stage 2, for the cases the trigger catches; residuals in Stage 0's table.
- **E2**: Stage 2 trades a 4–10% gate-only false split, per Q3. Stage 4's "same" verdict removes
  it. Spread units found to be A's join A through the existing group cohesion.
- **E3**: Stage 2: no hold, immediate. Stage 4: structural bound and age-from-release.
- **E4**: Stage 1's single resolved plan feeds the eyesight view. Stage 4 area looks are ordinary
  looks.
- **Re-check finding 3 (order was the architect's reading):** answered by the user. Ahead first,
  sides alternating, which is today's table. Stage 5's card listens for that rhythm.
- **Re-check finding 4 (ahead seen once per cycle):** resolved by the order answer. 12 o'clock is
  swept every 8 s, as today, and ahead gets two glass steps per cycle. The card still asks the
  pilot to notice ahead pickup, since nothing else measures it before flight.
- **Re-check Q3 (glass budget):** Decision 5 ANSWERED (b). The budget gates starts, not lengths,
  and selectivity is the main bound (Stage 1, "Selectivity").
- **Optics priority, refined (user, 2026-11-02, fifth pass; supersedes the fourth pass's
  "a) where b) iff c) classification" reading):**
  1. *Detection and rough location, looser far out, tighter close in*: the naked-eye scan.
     Allowance 0.2 · R down-range and half an o'clock across; a naked-eye look is
     never outside it (Stage 1, "Priority 1", measured table). No binocular look for it.
  2. *IFF*: not modelled, `[[BL-B12]]` deferred, not built. Identification to type serves it and
     ranks before classification in the glass step.
  3. *Classification*: the existing ladder.
  4. *Exact location*: watched contacts only (what the player asked about), after
     classification. Enemy units and mission targets: neither exists in body-layer today. Stage 0a
     makes such a fix last.
  *"Exact position is not even needed for all units"*: so no unwatched contact gets a
  location-only look (scenario test asserts it).
- **Mission density (*"a handful of groups a few km apart"*):** the design case for the budget
  and revisit figures. Busy windows are rare. Exact-location looks are watched-only, so they
  add little.
- **Approach profile (*"~100 km/h … sideways movement and circling"*):** checked under "Body
  rotation". Added: the sector margin, look-follow, and a scenario test flying the profile.
  Pre-existing eye aliasing is reported, not fixed.
- **Tracked vs estimated for stationary units:** `[[BL-B112]]`, queued after this entry (user:
  *"own item, queue after this"*). It is not built here, and it makes Decision 6 moot for
  stationary contacts.
- **E5**: Stage 3. Fail closed. Not seen ≠ empty.
- **E6**: `plausible_speed_mps` growth.
- **E7**: `COMPOSITION_MATCH_RATIO`, used only after a look.
- **E8**: Q2 and Q5 rows. `hold_routine` unchanged.

Open assumptions answered:
- **Trigger**: gate path, A not in this look, fails the as-if-same-look gate.
- **Which "remembered"**: any contact in the store, lost included. All are gate candidates already.
- **Hold**: none in BL-B110 (B is founded and called at once). In BL-B111: per sector, ≈17 s worst
  with the third pass's uncapped step (≈11 s in the second pass).
- **Bound runs out**: Q3, B is new.
- **Optic**: the binocular glass step. The naked eye already had its chance in the sweep; the 9K113
  is the Q5 pause.
- **Area size**: A's σ plus speed growth, capped by `EXPECTED_AREA_MAX_HALF_WIDTH_DEG`.
- **Speed**: `plausible_speed_mps`.
- **Composition**: believed intervals.
- **Anchors**: Stage 2b.

### Decisions

Decisions 1–4 were asked after the plan check and answered by the user on 2026-11-01
(`explore-notes.md`, "Plan-check decisions", verbatim). The original questions stay below each
answer. Decision 5 is new, raised by the three-sector arithmetic. The plan re-check's questions
were answered on 2026-11-02 (`explore-notes.md`, "Plan re-check answers", verbatim): Decision 1a
and Decision 5 below. Decision 6 is new, raised by that arithmetic. Fourth pass (2026-11-02,
`explore-notes.md`'s last two sections): Decision 6 answered; Decision 7 open (needs the user);
Decisions 8–9 proceed on their defaults unless the user says otherwise. Fifth pass (2026-11-02,
`explore-notes.md`, "Decision 7 and the refined priority" and its follow-up): Decision 7 answered
(a); Decision 8 REVERSED by the refined priority; Decision 9 stands; Decision 10 is new (default
proceeds); Decision 11 records the binocular range-sense answer.

**Decision 1, ANSWERED:** *"third of full scan. So basically left right and ahead. Multiple looks
per glass is ok and expected."* This **supersedes** the half-sweep recommendation. Stage 1 now
reshapes `SCAN_PLAN` to `(9,10,11,12,1,2,3)` with three sectors: left 9–10, ahead 11–1, right
2–3, swept left → ahead → right. Several looks per glass step are built in.
→ **The order and the table reshape are REVISED by Decision 1a.** The regions and the
several-looks answer stand.

**Decision 1a, ANSWERED 2026-11-02 (revises the order in Decision 1):** *"I meant regions, not
order. For order, always start from ahead and sweep to left/right alternating. That way direction
of flight is checked more often."* So the order is ahead → left → ahead → right, repeating.
Today's default `SCAN_PLAN` `(12,11,10,9,12,1,2,3)` is already that eye path, so **the table is
not reshaped**. The thirds partition gives four 4 s sectors (ahead-left half, left, ahead-right
half, right). 12 o'clock is swept every 8 s and ahead gets two glass steps per cycle. The
full-ahead "pendulum" `(1,12,11,10,9,11,12,1,2,3)` was considered and not chosen: it adds 4 s to
every flank revisit for 11/1 coverage that the stated reason (direction of flight) does not need.
It stays available as a `SCAN_PLAN` override, and the coupling check accepts it.

**Decision 2, ANSWERED:** *"as recommended"*. Per the plan check's split of the question, that means
two things. (i) Stages 0–2 ship under BL-B110. (ii) A follow-on entry for the point
line-of-sight query (option a) plus Stages 3–4 is opened **now**, regardless of what flights show:
`[[BL-B111]]`. The flight duplicate count sets its priority only.

**Decision 3, ANSWERED:** *"ok"*. The five `TestPhaseCycle` full-cycle-lockout tests and the
exact-100% fold test are rewritten. Stage 1 ships as its own merge ahead of Stage 2. The tests that
only pin the old default table's numbers are a data update, not part of this approval. Stage 1
says what to do if one of them breaks on premise. (Third pass: with the table unchanged, that
data update all but disappears.)

**Decision 4, ANSWERED (BL-B111):** *"~"A now at...""*. The relocation line is neutral, ≈ *"That
group, now two o'clock, three kilometres."*, never "has moved". Recorded in Stage 4 for BL-B111.

**Decision 5, ANSWERED 2026-11-02: alternative (b), 12 s per cycle.** User: *"four is too
short. Binoculars should be used to look closer when there is good probability that using them
brings a benefit — detection, classification or identification. There's no use raising them on
contacts where additional information is not available at current distance. Then when binoculars
are used, it's better to not limit the time too tightly. The 12 s sounds ok."* As built in Stage 1:
- `GLASS_BUDGET_PER_CYCLE_S` = 12.0 s;
- the budget gates a look's **start** (it must fit a full `MAX_LOOK_S`), never its length, so no
  look is cut short;
- **no per-step cap** (the 6 s per-step cap in (b) as written is dropped, per "not limit the time
  too tightly");
- counted over the last n glass steps (rolling), not reset once per cycle. That is a correction to
  (b) as written, because a reset lets two budgets land in one flank revisit window (40 s worst);
- selectivity is the main bound. Classification and identification at the current range were
  already gated. The one gap, a failed look retried at the same range, is closed with
  `GLASS_STALL_COOLDOWN_S`.

*Original Decision 5 (second pass), kept for the record:*
**Decision 5, OPEN, with a default the Implementer may proceed on: the glass budget per step.**
Three glass steps per cycle at the earlier 6 s budget give a worst revisit of 32 s (35 s with poll
slack), which **exceeds the 30 s position half-life**. Recommended: `GLASS_STEP_MAX_S` = 4.0 s,
which gives 26 s, or 29 s with slack. The cost: no single binocular look lasts more than 4 s, so a
slow recognition is cut off and waits a cycle. Alternative (b), a 12 s per-cycle budget with 6 s
per step, keeps full-length looks but lets a busy left sector starve ahead and right. It is a
tunable and reversible, so per `AGENTS.md`'s escalation rule the Implementer proceeds on 4.0 s
unless the user picks (b). The user should still hear about it, because it changes how long he
will see Petrovich's binoculars stay up.
→ **Answered above: (b), as revised.**

**Decision 6, ANSWERED 2026-11-02: (a).** User: *"For the overrun - ok."* The ≤ 2 s overrun is
accepted. I1 is kept, and I2 is added on the real cliffs, as built in Stage 1. The user added, in
the same answer: *"Tracking vs estimated. Again, the unit movement should be considered.
Stationary unit can be expected to remain stationary. Therefore even if no one looked at it for 30s
it's not likely to have moved."* That is opened as `[[BL-B112]]`, queued after this entry. It
would make this overrun moot for stationary contacts. The fourth pass's rotation check found a
rarer, larger overrun from the eye's own aliasing (≈ 40 s worst, pre-existing; Risks). The same
reasoning applies to it: it stays below the expiry and lost cliffs.

*Original Decision 6, kept for the record:*
**Decision 6, OPEN, with a default the Implementer may proceed on: accept a brief overrun of the
position half-life in a full-budget window.** With the user's 12 s budget, the worst revisit for a
leg that is not glassed in that window is 28 s nominal and **32 s with poll slack**, against
`POSITION_HALF_LIFE_S` = 30 s. The second pass's coupling check was built to forbid that.

What the pilot would notice past 30 s, from the consumers in the code: no callout is added or
dropped, nothing goes lost (120 s), no contact or group is re-founded. The one spoken effect is a
*watched* flank contact's kilometre-crossing line arriving up to ~2 s late. It needs a full 12 s
of glassing inside one 16 s cycle, which selectivity should confine to the first cycle or two of
a busy multi-group contact.

Options:
- **(a) Recommended: accept it, and restate the coupling on the real cliffs.** Keep I1 (quiet
  sweep < half-life). Add I2 (worst revisit < lost threshold and < group-expiry window, five keys).
  Document the ≤ 2 s overrun. I2 also closes a hole the old check never covered:
  `LOST_THRESHOLD_S`'s own `lo` (30) can be set below the busy revisit by a single in-bounds
  override, which would make flank contacts go lost → reacquired every busy cycle.
- (b) Raise `POSITION_HALF_LIFE_S` to ~35–40 s. That changes the certainty of every contact in
  the store, group expiry (2×) and every `position_confidence` reading, to cover a ≤ 2 s edge
  case. Not recommended. It is a single tunable if flights say otherwise.
- (c) Lower the budget to ~10 s (nominal 26 s, 30 s with slack). This is against the user's "12 s
  sounds ok" for a cosmetic gain. Not recommended; also a single tunable.
- (d) The pendulum table makes it worse (36 s); shortening ahead passes conflicts with Decision 1a.

It is reversible and local, so per `AGENTS.md`'s escalation rule the Implementer proceeds on (a).
The user should hear about it, because it is the one place the plan knowingly lets a contact's
certainty sag between looks.
→ **Answered above: (a), "ok".**

**Decision 7, ANSWERED 2026-11-02: (a).** User: *"Option a"*. A new look never leaves the belief
less certain than just before it. Built as **Stage 0a**, first: BL-B108's tests re-run before and
after, any moved fence stops the work, Stage 0's measurements are taken after it. Growth at the
class's plausible speed still applies (Stage 0a, "What it does not do").

*Original Decision 7, kept for the record:*
**Decision 7, OPEN, needs the user: should a binocular location fix stick?** Measured on the
shipped `fold_position` (Stage 1, "Location looks"): after a binocular look at 3 km, the belief's
range 1σ goes 501 → 357 m, holds for one more naked-eye sweep, then returns to 486 m. That is
because `_apply_floor` scales its floor by the *immediate* prior anchor's optic only, and a
naked-eye fuse replaces that anchor. BL-B108 named this "one-anchor approximation" and said
*"escalate rather than add a second anchor"*, so it comes to you.
- **(a) Recommended: a fuse never leaves the belief less certain than it was just before it.**
  Cap the floor at the prior's own inflated covariance. Growth from elapsed time and plausible
  speed still applies, so a *moving* group still loosens. This is not a second anchor: it is one
  `min` in `_apply_floor`, plus a parameter. A located group stays located until it moves or the
  geometry changes a lot, and a 9K113-ranged contact keeps its range too. **The cost:** it changes
  BL-B108's fold one day after it merged, and Stage 0's trigger numbers. So BL-B108's tests are
  re-run first, and if any fence moves the work stops and comes back to you.
- (b) Build location looks on today's floor. Each fix lasts ~30 s, and the group is then
  re-glassed once per stall cooldown (180 s) for another ~30 s. That is binoculars raised for
  nothing lasting, against your *"no use raising them on contacts where additional information is
  not available"*.
- (c) Do not build location looks in Stage 1. Open an entry for the floor question and location
  looks together, after BL-B108's fold has been looked at on its own.

Until this is answered, 1-scan proceeds and 1-floor/1-locate wait (Stage 1, build order).
→ **Answered above: (a).**

**Decision 8 REVERSED 2026-11-02, by the user's refined priority:** *"1 detection and rough
location (the further away we are, the more imprecise the location is allowed to be. At close
distances a more specific location can and should be obtained) 2 IFF, though that needs expected
enemy territory and unit identification (eg. T-72 vs leopard) 3 classification 4 exact location
(for enemy units especially and mission target units or anything the player asks for)"*, and
*"Exact position is not even needed for all units."* So: exact location ranks **after**
classification, and only for watched contacts; type identification ranks before classification;
watched still comes first inside each bucket. Priority 1 needs no binocular look (Stage 1,
"Priority 1"). The fourth pass's "≥ 100 m tighter, every group" criterion
(`LOCATION_LOOK_MIN_GAIN_M`) and its group reduction are dropped; `EXACT_LOCATION_MIN_GAIN_M`
(25 m, watched only) replaces it.

*Original Decision 8, kept for the record:*
**Decision 8, default proceeds (local, reversible): location before a *watched* contact's
classification.** `choose_glass_look` ranks location-worthy targets first, then `choose_look`'s
watched → coverage → nearest inside each bucket. So an unwatched group's location look comes
before a watched contact's classification look. That follows your order (*"a) knowing where the
groups are … c) classification"*). The alternative is watched-first across both, which keeps the
2026-09-25 *"even more so watched contacts"*. Both are a one-line change in one function. Say if
you want the watched contact first.

**Decision 9, default proceeds (scope, stated): a binocular look follows its contact through a
turn.** Today a look's aim is fixed relative to the airframe for its up to 6 s. At the 0.5–3°/s of
your circling approach, the group drifts out of the field before the look ends. Fixing it is
small: the four existing fields shift together each poll, with no new state. It is a pre-existing
gap rather than part of the sector scan, so it is named here as scope added. Without it, location
looks during an orbit are unreliable. Veto it if you want it as its own entry.
→ **Stands (fifth pass).** It now serves classification and identification looks during an orbit
as much as exact-location ones.

**Decision 10, default proceeds (local, reversible): the rough-location allowance is a test fence,
not a tunable.** The brief asked for it as a tunable (X-T26 pattern). It is not declared in
`tuning.py`, because nothing in flight would read it: priority 1 needs no binocular look, so no
code path compares a belief to the allowance. A key in `defaults.toml` that changes nothing would
tell anyone tuning it something false. And no shipped tuning key can break the conclusion (Stage 1,
"Priority 1"); only a code change to the naked-eye model can, which is what a test catches. So the
allowance, 0.2 · R down-range and half an o'clock across, lives in
`test_estimation.py` as the fence. If flight or a later model change ever makes priority-1 looks
real, the allowance becomes a tunable then, read by the predicate that needs it. Say if you want
the knob anyway.

**Decision 11, ANSWERED 2026-11-02: binocular range sense unchanged.** User: *"Binoculars range
sense - keep the current."* `BINOCULAR_RANGE_SIGMA_SCALE` stays 0.7 (`#needs-flight` as before).

---

*Original questions (2026-11-01, first pass), kept for the record:*

1. **What is a "sector" in free scan?** Recommended: the two halves of today's table, `12→9` and
   `12→3`, 8 s each. That gives a glass step after every half-sweep, and the worst revisit is 28 s.
   The alternative, per o'clock cone (a glass step every 2 s), would keep binoculars up most of the
   time, push the revisit well past 30 s, and break the decay coupling. Also: within one glass step
   Petrovich may glass several contacts back to back, with no eye sweep in between. Is that what
   *"binoculars on new contacts"* means (recommended: yes, capped at 6 s per step)?
   → **Superseded** by Decision 1, ANSWERED above.
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
   → Answered above: ship (c) now, and open (a) plus Stages 3–4 now as `[[BL-B111]]`.
3. **Tests rewritten, not extended (`AGENTS.md` escalation).** `TestPhaseCycle`'s
   full-cycle-lockout premise (five tests) is replaced by per-sector equivalents, one of them
   reversed. `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact`'s exact 100% is
   restated as a measured fence (90–96% in the gate-only harness). Also confirm Stage 1 ships as its
   own merge ahead of Stage 2.
4. **(Stage 4 only) Wording of Q4a.** Petrovich cannot tell a move from a misjudged range.
   Recommended neutral form: *"That group — now two o'clock, three kilometres."* rather than "has
   moved". Settle it together with `[[BL-B109]]`'s `/explore`.
   → Answered above: ≈ *"A now at …"*.

**Decision 12, ANSWERED 2026-11-09: (a). User: *"go with (a)"*. The trigger catches only a group
that reads nearer than the remembered one.** Stage 1b measured three ways to bring the same-group
false split under your ~10%. Only one keeps the catch:
- **(a) Recommended: one-sided.** Petrovich splits B off from a remembered A only when B reads
  **nearer** than where A should be. Same-group false split 3–6% in every measured cell (SAM site
  re-seen after 10+ min: about one in twenty is announced as new). A nearer group on A's bearing is
  still called out 97–99% of the time. **The cost:** a different group reading *farther* than A
  still folds silently, as it does today (~28% in the measured cell). That is no regression, and
  it is the direction you are not flying into first. `[[BL-B111]]`'s look is what fixes it.
- (b) Two-sided, with its own stricter threshold (4.5–5σ, a new tunable). The false split is
  6.6–9.4%, but the nearer group is missed 15–55% of the time instead of 1–3%. That gives back
  much of what Stage 2 is for.
- (c) Two-sided as built, with the duplicate gate raised to ~20%. A known SAM site would be called
  "new" about one time in five when it is re-seen after ten minutes.

The ground-unit cells are still to be measured (Stage 1b step 4). If they break (a), this comes
back to you before Stage 2 is built.
→ **The figures above are superseded** (seventh pass): they were measured on the indefinite-`S`
gate. The user's answer stands, and Decision 12a restates it on honest numbers.

**Decision 12a, seventh pass (2026-11-10): the one-sided direction still holds, for a different
reason. It applies only if Stage 2 is built (Decision 13).** Honest numbers:
- One-sided and two-sided catch the same groups, within 1 point in every cell. Every trigger catch
  is a "B nearer" case.
- Two-sided adds 2–5 points of same-group duplicates (bino → eye). One-sided adds ≤ 0.3.
- So one-sided costs nothing in catch and removes the trigger's own duplicates.
- The sixth pass's trade, giving up the farther group to cut duplicates from 20% to 6%, no longer
  exists. The farther group was never caught by either variant. Ground cells (100 m AGL) agree.
No new question for the user. This records that (a) survives the re-measure.

**Decision 13, OPEN, needs the user: build Stage 2 at all?** On honest numbers the trigger moves
one cell family by 5–15 points (far group glassed, near group by eye: 70–86% → 58–79% unannounced).
It moves nothing else. What the pilot would notice: a nearer group on a remembered bearing is still
missed most of the time, either way.
- **(a) Recommended: do not build Stage 2 in BL-B110.** Close BL-B110 on Stages 0a/0/1 plus Stage 5,
  and record the honest residual on `BL-B110.md`. The believed-distinct pair and merge-echo skip
  move to `[[BL-B111]]`, the one mechanism that can supply the missing information (a look at A's
  area). BL-B111 absorbs Stage 2b's anchor question too. Consider raising BL-B111's priority, since
  it is now the only planned route to "two groups called as two".
- (b) Build Stage 2 one-sided now, as a small partial: one implementer pass, acceptance numbers in
  Stage 2's seventh-pass redesign. It buys 5–15 points in one cell family at ≤ 0.3 points of
  duplicates. It is not wasted, because BL-B111 reuses the pair and the skip. But it ships a
  mechanism whose headline claim (E1) it does not meet, and the card would have to say so.
- (c) Build it two-sided. Same catch as (b), plus 2–5 points of duplicates. Dominated by (b), so
  not recommended.

**Decision 14, OPEN, needs the user: open an entry for merge-echo silencing of real second
groups?** `callouts._is_merge_echo_of_earlier_contact` silences B's first callout when an earlier,
not-lost contact is "plausibly same" by `contacts_plausibly_same`. In the honest grid that test
accepts 50–60 points of different-group pairs the gate itself had correctly split. Eye → eye at a
6 s gap: gate fold 4–15%, but B is unannounced 63–73%. The rule exists to silence echoes (it is also
what keeps BL-B113's short-gap splits down to ≤ 0.5% heard), so tightening it trades one error for
the other.
- **(a) Recommended: open it as a body-layer backlog entry, measure first, `/explore` before any
  fix, deferred like BL-B113.** The flight signal is "a group on a remembered bearing never called".
  The 6 s memory-only geometry is the harness worst case. In flight, two groups on one bearing seen
  within one sweep are separated by the same-poll claim rule. How often the memory-only case arises
  is unmeasured: `sortie-log-triage` can count CONTACT_DETECTED events suppressed as merge echoes.
- (b) Fold it into `[[BL-B111]]`. Not recommended. It is a callout rule, not the look, and it would
  make BL-B111's goal check carry two unrelated questions.
- (c) Leave it unrecorded. Not recommended. This is the larger silent path, and it was invisible
  until this pass measured what is heard rather than what folds.

**Plan re-check 3 questions, ANSWERED 2026-11-03.** User: *"go with recommendations"*.
1. The rough-location fence is **0.2 · R** with no 250 m floor (edited throughout).
2. "Anything the player asks for" = **watched contacts** for now; a one-off query without
   "watch" does not trigger an exact-location look (brain-layer path, later).
3. The circling sector-edge blind spot (~28 s, ~40 s with a full glass budget) is a **test-card
   watch item** (Stage 5), its own entry only if noticed in flight.
