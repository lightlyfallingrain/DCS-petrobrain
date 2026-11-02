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
  `SCAN_CYCLE_PERIOD_S`. Reset the sector on a scan-command change.
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
  `test_callouts.py`, and a new `test_expected_area_trigger.py`.
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

*Revised 2026-11-02, third architect pass* (`explore-notes.md`, "Plan re-check answers", which
govern). The order is ahead first, then sides alternating; the glass budget is 12 s per cycle and
looks are not cut short; selectivity, not a tight timer, is what bounds binocular time. **The
default `SCAN_PLAN` no longer changes**: today's table already is the order the user described
(below). That removes the second pass's table reshape and all of its knock-on test-data churn.

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
- **Glass step**, at the sector's end: targets are contacts whose believed body azimuth lies in
  the swept sector's wedge (union of its legs' ±15° cones) and that pass `is_worth_a_look` (with
  the stall cooldown below). **Several looks per step are expected** (user Decision 1). Looks run
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
  cross it by 6 s. Decision 6 below is whether to accept that, and how the invariant is restated.
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
    state. A quiet scene is the bare 16 s sweep. The Stage 1 scenario test measures it (below).
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
  - **Not an invariant, per Decision 6:** worst revisit < `POSITION_HALF_LIFE_S`. It is written
    down as an accepted overrun (≤ 2 s at defaults), with the consequences listed above.

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
and the measured residual and false-split rates; the test card names `main` and `#needs-flight`.
Cards:
- free scan, listening for the ahead → left → ahead → right rhythm: a 4 s eye sweep, binoculars
  on what is worth it there, the next sector. Note too how soon a new contact dead ahead is picked
  up (alignment re-check finding 4);
- free scan with several contacts in binocular range, watching that no look is cut short and that
  a contact already glassed at the same range is not glassed again every minute;
- free scan, two groups on one bearing, far one glassed first, then crest a ridge (expect two
  callouts);
- a commanded o'clock scan, listening for binocular cadence.

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

Both fresh-construction sites must carry all three forward explicitly, the BL-B71 lesson. The
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
  produce the same verdict. "Has moved" asserts motion he did not see. Resolved by user Decision
  4 (neutral "now at").
- **Worst revisit 28 s nominal, 32 s with poll slack, against `POSITION_HALF_LIFE_S` (30 s)**
  in a window where the whole 12 s budget is spent. Accepted under Decision 6: a flank contact
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
- *(Superseded, third pass: the second pass's "revisit 26 s (29 s with slack) / glass budget 4 s"
  and "reshaping `SCAN_PLAN` to 9 → 3, ahead once per cycle" risks no longer apply.)*
- **Stages 3–4 (`[[BL-B111]]`), when built:** cross-subproject Lua with a Windows-only
  verification, and the first contact removal in `ContactStore`. Both risks are listed above and
  move with the entry.

### Second-order effect

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

### How each alignment item is answered

- **E1**: Stage 2, for the cases the trigger catches; residuals in Stage 0's table.
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
and Decision 5 below. Decision 6 is new, raised by that arithmetic.

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
