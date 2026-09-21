### Goal

Turn detection from "an all-seeing predicate with one magnification number" into "a directed,
per-tier, distinctiveness-aware act" — implementing the three settled model decisions
(`body-layer/research/2026-09-21-slice2-model-decisions.md`) across four independently mergeable
sub-slices, each of which leaves the system flyable.

**The three decisions are settled input, not open questions.** This plan is about how and in what
order, and about the four structural problems they create that the decisions themselves do not
answer: where gaze state lives, what a moving cone breaks downstream, how a scan loop stays
replay-deterministic, and which existing mechanisms already govern the same concepts.

### No investigator pass needed, and why

Everything this plan depends on is already verified: ED's dwell/scan/recognition constants
(`aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`, findings 1/2/3/6/7,
file-read against DCS 2.9.29.27278), the cockpit envelope (`perception/cockpit_mask.py`, live
cockpit test 2026-09-20), and the multipliers/distinctiveness (the user's own 2026-09-21 sortie).
The unresolved DCS unknowns that remain — fog, unit velocity, `Unit.getDesc().box` — all sit behind
the unprobed mission-sandbox bridge and are explicitly out of scope below. No claim in this plan
rests on an unverified DCS internal.

---

## Slicing

Four sub-slices. **2A is first**, and the reason is the slice-1 lesson restated: *the valuable part
is not the part the slice is named for.* Slice 1 was named for the cone test and its real payload
was the naked-eye default. Here the milestone is named for scanning and dwell, but:

- **Decision 3 (distinctiveness + the clamp) changes the default naked-eye path today**, with no new
  state, no new module, and no attention machinery. It fixes the infantry ratio (measured 1.00,
  modelled 0.13) and most of the residual S-300 class error (2.6× after the aspect fix).
- **Decision 1 (per-tier multipliers) is inert until an optic is selectable** — every multiplier is
  1.0 for `UNAIDED_OPTIC` by construction — but it deletes a model the measurements have *proven
  false*, and leaving a known-false formula in the code while shipping other corrections is worse
  than landing an inert table.
- **2C's calibration is unreadable until 2A has landed.** 2A changes *whether* something is
  detected; 2C changes *when*. Flown together, a sortie cannot attribute a changed range to either.

So the ordering is forced by measurability, not preference.

| | Slice | Default behaviour changes? | Gate to the next slice |
|---|---|---|---|
| **2A** | Per-tier multipliers, distinctiveness, the clamp, clustering floor fix | **Yes** — class-tier ranges move for infantry and radars | A sortie with BL-9 tracing: infantry class ≈ presence; S-300 class within ~1.5× of 4500 m; vehicle class/presence unchanged within noise |
| **2B** | Gaze as a filter; F10 scan commands steer perception | **No** — default gaze is the forward hemisphere, i.e. today | In flight: "scan left" demonstrably changes which contacts are detected; with no command issued, the BL-9 trace is byte-identical to 2A's |
| **2C** | Default gaze becomes the scan loop `ahead → left → ahead → right` | **Yes** — this is the big one | A sortie judged by the user on *feel*: does he find things at a plausible rate, and does the callout language stay stable as contacts cycle in and out of gaze |
| **2D** | Dwell as an act: binoculars onto a specific contact | **Yes** | Conditional — only built if 2C's sortie shows a real need (see effort/value below) |

---

### Affected Modules / Files

**2A**
- `body-layer/src/perception/optics.py` — `Optic` loses `magnification`, gains
  `presence_range_mult` / `class_range_mult` / `type_range_mult`. Values from the decisions doc:
  `UNAIDED_OPTIC` 1.0/1.0/1.0 (the baseline, by definition); `BINOCULAR_OPTIC` 2.42/3.50/3.00.
  Deleting `magnification` removes the second source of truth that slice 1's own Decision 1 worried
  about, and — because `BINOCULAR_RANGE_MULTIPLIER` goes with it — **dissolves the
  `optics ↔ visibility` circular import**, so `visibility.py`'s `TYPE_CHECKING` dance and its
  function-local `from perception.optics import ...` can both become an ordinary module import.
- `body-layer/src/perception/object_model.py` — `ObjectTypeProfile` gains
  `distinctiveness: float | None = None` (the per-type *exception*); a new
  `_OP_CLASS_DISTINCTIVENESS: dict[str, float]` supplies the per-class *default*, with
  `_DEFAULT_DISTINCTIVENESS = 1.0`. New `distinctiveness_of(profile) -> float`.
- `body-layer/src/perception/visibility.py` — `_achieved_tier` takes the `Optic` (not one float) and
  the profile's distinctiveness; the three thresholds use their own multipliers; the class threshold
  gets the clamp; `check_visibility`'s admission gate uses `presence_range_mult`.
  `BINOCULAR_RANGE_MULTIPLIER` is deleted.
- `body-layer/src/perception/clustering.py` — `cluster_candidates` takes the active optic's
  `presence_range_mult`; `_separable`'s floor (A) stops importing `BINOCULAR_RANGE_MULTIPLIER`.
  **This is not cosmetic — see "The clustering floor is no longer benign" below.**
- `body-layer/src/perception/naked_eye_source.py` — passes the active optic's presence multiplier
  into `cluster_candidates`. No other change.
- Tests: `test_visibility.py`, `test_vision_calibration.py`, `test_clustering.py`, `test_optics.py`,
  plus a new tier-monotonicity property test (below).

**2B**
- `body-layer/src/perception/gaze.py` (**new**) — `Gaze(center_azimuth_deg, half_width_deg, label)`,
  `FULL_GAZE` (0°, 90° — the forward hemisphere, i.e. no narrowing), and **the `RelativeSector`
  vocabulary moved down from `belief/attention.py`**: the `Literal`, `RELATIVE_SECTORS`, and
  `_RELATIVE_SECTOR_WEDGE_DEG`.
- `body-layer/src/belief/attention.py` — re-imports `RelativeSector` / the wedge table from
  `perception.gaze` instead of defining them. `belief → perception` is the allowed direction (it
  already imports `perception.geometry`); the reverse is forbidden, which is exactly why the
  vocabulary has to move down rather than the gate move up. **This is the one refactor the plan
  requires, and it removes a real duplication** — otherwise ahead/left/right/full wedge angles would
  exist in two modules that must agree and have no mechanism forcing them to.
- `body-layer/src/perception/visibility.py` — `check_visibility` gains `gaze: Gaze | None = None`, a
  cheap angular gate placed *after* the cockpit mask and *before* the optic FOV (the mask is what
  the airframe permits, gaze is where he is looking within that, the optic is what the instrument
  shows once pointed — the intersection, exactly as `todo/todo.md`'s "Scan commands should drive
  naked-eye perception" entry already framed it). `None` = no restriction = today.
- `body-layer/src/perception/detection_trace.py` — new `GateOutcome.GAZE`, preserving BL-9's
  one-entry-per-call invariant (the same defect slice 1's merge note records for `OPTIC_FOV`).
- `body-layer/src/perception/optics.py` — `within_optic_fov` takes the boresight as a parameter
  (the gaze center) rather than reading `Optic.boresight_azimuth_deg`; that field is deleted. An
  optic is pointed by the head, not bolted to the airframe.
- `body-layer/src/perception/naked_eye_source.py` — new field `gaze: Gaze | None = None`, passed
  through to every `check_visibility` call.
- `body-layer/src/logger.py` — the runner is the only place belief and perception meet, and it
  already is (`_build_sources`, `store.ingest`). Before each poll it resolves the active commanded
  sector from the `TaskStore`/`ContactStore` (a pending `scan_area` task whose area carries a
  `relative_sector`) and assigns a frozen `Gaze` onto the naked-eye source — the same
  write-thread/read-thread single-assignment pattern `last_t_sim` already uses safely.
- Closes `todo/todo.md`'s standing **"Scan commands should drive naked-eye perception"** item.

**2C**
- `body-layer/src/perception/gaze.py` — `ScanPlan` (frozen: the commanded sector or `None`, plus the
  sim time the command was issued) and `gaze_at(t_sim, plan) -> Gaze`. **A pure function of sim
  time, not a state machine** (see "Determinism" below).
- `body-layer/src/perception/naked_eye_source.py` — holds a `ScanPlan` instead of a `Gaze`, computes
  `gaze_at(now_sim, plan)` per poll; **and its acquisition sets become time-based**
  (`frozenset[int]` → `dict[int, float]` of object_id → last-seen sim time, evicted after a
  retention window). This is the concrete downstream break, detailed below.
- `body-layer/src/belief/decay.py` — `OBSERVED_WINDOW_S` is re-derived from the scan cycle period
  rather than left at 5.0. See "The scan period is not a free parameter".
- `body-layer/src/logger.py` — assigns a `ScanPlan` rather than a `Gaze`.

**2D (conditional)**
- `body-layer/src/perception/gaze.py` — a dwell `Gaze` is just a narrow gaze at a specific bearing;
  no new type needed.
- `body-layer/src/belief/` + `logger.py` — dwell *target selection* (which contact is worth a long
  look) is belief's decision; the dwell's *effect* (a narrow gaze + `BINOCULAR_OPTIC`) is a value
  passed down. No new belief→perception import.

**Not touched in any slice**: `cockpit_mask.py` (measured, retune only from a fresh cockpit
measurement), `hybrid_source.py`, `association.py`, `belief/contacts.py`.

---

### The four hard parts, confronted

#### 1. Where gaze state lives — and the answer is "nowhere"

`perception` must not import `belief` (`perception/source.py`'s own docstring). Gaze looks like it
wants to be belief state — it is driven by commands, which are belief-level intents — but it is a
*perceptual act*, and putting it in belief would force the forbidden import.

The resolution is that **gaze needs no state at all**. `gaze_at(t_sim, plan)` is a pure function:
the free-scan cycle is a function of sim time modulo the cycle period, and a commanded scan is a
function of sim time relative to the command time carried in the frozen `ScanPlan`. Belief owns the
*intent* (`PendingIntent` + `AttentionArea.relative_sector`, both of which already exist); the
runner reads it and hands perception a frozen value; perception owns the *act*. The boundary holds
in the direction it already runs, and there is no state machine to get out of sync, to reset on a
telemetry gap, or to serialise for replay.

This is the single most important decision in the plan, and it dissolves the determinism risk rather
than managing it.

#### 2. The geometry proves direction and dwell must be separate mechanisms

Decision 2 settles this by the user's own reasoning. The numbers independently confirm it, and it is
worth stating because it constrains 2D's design: the scan sectors are **60° wide** (`ahead` ±30°,
`left`/`right` ±30°), and `BINOCULAR_OPTIC.fov_half_angle_deg = 4.25` is an **8.5° field**. A
binocular cannot scan a sector — it covers a fourteenth of one. So "scan left through binoculars" is
not expressible, and any design that tried to make optic selection a property of the scan sector
would be geometrically incoherent. Dwell must be a narrow gaze at a *specific bearing*, which is
precisely the user's "looking at something with intent."

A corollary worth carrying: **2D is the slice that finally gives `BINOCULAR_OPTIC` a caller.**
Without it, the binocular table entry and its measured 2.42/3.50/3.00 multipliers stay unreachable
forever — the exact failure mode slice 1's scope cut was written to avoid.

#### 3. What a moving cone breaks: `naked_eye_source.py`, specifically

Both acquisition modes are **poll-indexed, and a moving cone makes poll-indexing wrong**:

- `_acquire_on_change`: `_previously_visible_ids` is "visible on the previous poll." When the cone
  sweeps off a sector and back, every object in it is "newly visible" again → a fresh burst of
  `Observation`s **every scan cycle, forever**. The debounce this set exists to provide is defeated.
- `_acquire_every_poll` (what `--console` and `--crew-text` actually run): `self._acquired_ids &
  currently_visible_ids` **drops acquisition the instant the cone moves off**. Every object must be
  re-acquired on every sweep, and `NAKED_EYE_MAX_NEW_PER_POLL = 3` re-throttles it each time — so a
  sector holding six vehicles never emits all six.

Fix, in 2C: both sets become `dict[int, float]` of object_id → last-seen `t_sim`, with eviction
after a retention window ≥ one scan cycle. "Still acquired" then means "seen within the current
sweep," which is what it always physically meant; the poll-indexed version was only ever correct
because the cone never moved.

**`NAKED_EYE_MAX_NEW_PER_POLL = 3` is an existing mechanism governing the same concept.** It is
already an attention-bandwidth model — a cap on how many new things he can take in at once — written
before any attention machinery existed. Do not add a second bandwidth limiter in 2C or 2D without
first deciding whether this one is the same thing under another name. (Recommendation: keep it
in 2C unchanged, and re-examine it only if the 2C sortie shows sectors being under-reported.)

**`clustering.py`**: clusters are built per-poll from whatever is visible, so a gaze edge that
bisects a group splits it into two clusters reported separately at different times — against the
diagram's explicit "group of units at same location → treat as a single threat, do not report
individually." At 60° sector width this is rare (a group tight enough to cluster is rarely
astride a sector boundary); at 2D's 8.5° binocular field it is routine. Flagged as a 2C acceptance
item and a 2D design constraint, not fixed pre-emptively.

#### 4. The clustering floor is no longer benign — verified, not assumed

`_separable`'s floor (A) hardcodes `BINOCULAR_RANGE_MULTIPLIER`. Slice 1 flagged it benign twice.
Under per-tier multipliers the proof has to be redone, and it does not survive intact.

The slackness proof is: admission gives `θ_size · M_presence ≥ LOWRES` for each member, so
`θ_size ≥ LOWRES / M_presence`; with (S) `θ_sep ≥ ½(θ_a + θ_b)`, the floor's left side is
`θ_sep · 4.0 ≥ (LOWRES / M_presence) · 4.0`, which clears `LOWRES` **iff `M_presence ≤ 4.0`**.

| optic | `presence_range_mult` | floor (A) slack? |
|---|---|---|
| unaided | 1.00 | yes |
| binocular | 2.42 | yes |
| 9K113 wide | 3.55 | yes |
| **9K113 narrow** | **5.81** | **no — binding, and wrong** |

So (A) stays benign for every optic in the table *today*, and becomes a real fault — two genuinely
separable contacts silently merged into one — the moment the narrow sight is wired. The honest fix
is one parameter: pass the active optic's `presence_range_mult` in place of the constant, which
makes the floor slack **by construction for every optic**, present and future. Three lines, done in
2A while the multipliers are being introduced, rather than left as a trap for the 9K113 slice.

#### 5. The scan period is not a free parameter — it is bounded from both sides

`logger.py`'s poll interval is **1.0 s**. Two independent constraints squeeze the cycle period:

- **Lower bound, from aliasing.** A sector dwelt on for less than ~2 poll intervals can be sampled
  zero times on some cycles — entire sectors silently skipped. With four legs, that is a floor of
  roughly **8 s per full cycle**.
- **Upper bound, from `belief/decay.py`.** `OBSERVED_WINDOW_S = 5.0` is what makes
  `certainty_of` return `"observed"`. If a full cycle exceeds 5 s, **every contact drops out of
  "observed" certainty between visits**, and the crew layer starts hedging its language about
  contacts he is in fact tracking perfectly well. `POSITION_HALF_LIFE_S = 30.0` and
  `LOST_THRESHOLD_S = 120.0` are comfortable at any plausible cycle; `OBSERVED_WINDOW_S` is not.

**These bounds conflict: ≥8 s versus ≤5 s.** The resolution is that `OBSERVED_WINDOW_S`'s 5.0 was
chosen when Petrovich looked everywhere at once, where "seen in the last 5 s" and "currently seen"
were the same statement. Once he scans, the physically correct meaning of "observed" is *"seen
within the current scan cycle"*, so the constant should be **derived from the cycle period rather
than left independent** — `belief/decay.py` may import `perception.gaze` (the allowed direction).

Recommended: **2 s per leg → 8 s cycle**, `OBSERVED_WINDOW_S = SCAN_CYCLE_PERIOD_S`. The `ahead` leg
appears twice per cycle, so the forward arc is sampled every 4 s and each flank every 8 s — the
diagram's forward weighting, preserved. A test should assert `SCAN_CYCLE_PERIOD_S < POSITION_HALF_LIFE_S`
so a later tuning pass cannot silently push contacts into decay.

This is the item most likely to have been discovered mid-implementation rather than during design,
and it is why the decay constants were read before this plan was written rather than after.

#### 6. Determinism and replay

The pure-function design makes free scanning exactly reproducible: `replay.py` drives
`source.poll(frame.t_sim, frame)` from recorded frames, and `gaze_at(t_sim, plan)` returns the same
gaze for the same `t_sim` on every run. Nothing reads wall clock; nothing accumulates.

One honest limitation: recorded ownship streams carry no F10 commands, so **replay reproduces
free-scan only** — a replayed sortie will not reproduce a commanded "scan left" that happened live.
That is a property of what the recording contains, not of this design, and it is unchanged from
today (commands are already absent from replay). Worth stating in `replay.py`'s docstring.

The time-based acquisition dicts in 2C are keyed on `t_sim` and are therefore still deterministic;
they are state, but they are a pure function of the frame sequence.

---

### Implementation Plan

**2A — the model corrections (no new state, default path changes)**

1. `optics.py`: replace `magnification` with the three per-tier multipliers; delete
   `boresight_azimuth_deg` is *not* done here (2B); delete `BINOCULAR_RANGE_MULTIPLIER` from
   `visibility.py` and collapse the now-unnecessary circular-import workaround.
2. `object_model.py`: `distinctiveness` field + `_OP_CLASS_DISTINCTIVENESS` + `distinctiveness_of`.
   Values, derived rather than invented — put the arithmetic in the docstring so nobody re-derives it:
   - **Ordinary (1.0), the default for every `op_class`.** Cross-check: BTR-60 modelled class range
     is `7.0 / 0.014 = 500 m` against 400 m observed. Consistent with 1.0; no correction warranted.
   - **`OP_INFANTRY` → 5.0.** Modelled `1.8 / 0.014 = 128 m` against 600 m observed needs ≈4.7 to
     reach presence range; presence is `1.8 / 0.003 = 600 m`, which the research notes is the one
     place model and reality agree exactly. **The exact value does not matter**: anything above ~4.7
     saturates the clamp, and all four measured infantry rows then fall out of it. 5.0 is chosen as
     the round number just clear of the knee, and the clamp is what makes it robust.
   - **The two S-300 radars → per-type exception, 2.6.** From `4500 / 1714` (observed class against
     the post-aspect-fix model). This is a **per-type** value and not an `op_class` default
     specifically because `OP_LRSAM` covers launchers as well as radars — which is the concrete
     justification for decision 3 having two levels rather than one.
3. `visibility.py`: `_achieved_tier` takes the `Optic` and the distinctiveness. Thresholds become
   - `presence = size_m / LOWRES × presence_range_mult` (aspect-invariant `size_m`, unchanged)
   - `class = min(presence, extent_m / MEDRES × class_range_mult × distinctiveness)`
   - `type = extent_m / HIRES × type_range_mult` — **distinctiveness does not apply to the type
     tier**, because it is measured not to: infantry type range is 0.2 km against 0.6 km presence, a
     third, not equal. Distinctiveness is a *recognition-of-kind* term; identifying the specific type
     still needs resolved detail.
   Each threshold keeps its independent `NAKED_EYE_RANGE_CAP_M` clamp as today.
4. **Tier monotonicity, as an explicit invariant and a property test.** The clamp pushes the class
   threshold down, so a distinctive object can end up with `type_threshold > class_threshold` and
   the ladder inverts — `_achieved_tier`'s `if range ≤ hires ... elif range ≤ medres` would then
   report `hires` for a target that has not achieved `medres`. Clamp the type threshold to the class
   threshold, and add a test asserting `type ≤ class ≤ presence` across **every** profile in
   `object_model.py` × every optic in `optics.py`. This is a correctness requirement, not a nicety.
5. `clustering.py` + `naked_eye_source.py`: the floor-(A) parameterisation from hard part 4.
6. Run the existing calibration suites and expect movement — `test_vision_calibration.py` grades
   against the 2026-09-17 screenshot ladder, which the sortie note records as **optimistic** (DCS
   detection-aid dots were enabled). Expect infantry and radar rows to move; **vehicle rows must
   not**, and that is the regression guard worth writing explicitly.

**2B — gaze as a filter (default behaviour preserved)**

7. `gaze.py` with `Gaze`, `FULL_GAZE`, and the `RelativeSector` vocabulary moved down from
   `belief/attention.py`; `belief/attention.py` re-imports it. Verify `belief` tests are untouched.
8. `check_visibility` gains the gaze gate + `GateOutcome.GAZE`; `within_optic_fov` takes its
   boresight as a parameter; `Optic.boresight_azimuth_deg` deleted.
9. `NakedEyePerceptionSource.gaze` field; `logger.py` resolves the commanded sector each poll and
   assigns it. Default stays `FULL_GAZE`.
10. Regression test: with no command issued, the BL-9 trace over a fixture stream is identical to
    2A's. New tests: a commanded `left` gaze rejects a contact at 12 o'clock and admits one at
    10 o'clock; the gate fires *after* the mask (a contact behind the rear cutoff is still attributed
    to `COCKPIT_MASK`, not `GAZE`, so the trace keeps naming the real reason).
11. Update `todo/todo.md`: close "Scan commands should drive naked-eye perception."

**2C — the scan loop**

12. `ScanPlan` + `gaze_at`; `SCAN_CYCLE_PERIOD_S` and the leg table (`ahead`, `left`, `ahead`,
    `right`, 2 s each).
13. Time-based acquisition dicts in `naked_eye_source.py` (hard part 3).
14. `OBSERVED_WINDOW_S` derived from `SCAN_CYCLE_PERIOD_S` in `belief/decay.py`; the
    `SCAN_CYCLE_PERIOD_S < POSITION_HALF_LIFE_S` assertion test.
15. Determinism test: the same recorded stream replayed twice yields identical observations; and a
    contact sitting at a fixed bearing is detected on the cycles when its sector is gazed and not
    on the others, with the period matching `SCAN_CYCLE_PERIOD_S`.
16. Fly it. This slice is judged on feel, not on a number.

**2D — dwell as an act (conditional, see below)**

17. Belief selects a dwell target (highest-attention contact not yet resolved to `type`); the runner
    passes down a narrow `Gaze` at its bearing plus `BINOCULAR_OPTIC`; sustaining it for a period
    informed by ED's `average_det_time_max_dist_*` ground figures yields the class/type upgrade the
    binocular multipliers provide. The scan loop resumes when the dwell ends.

---

### Explicitly out of scope

- **The 9K113 as a selectable optic** — remains its own deferred backlog item
  (`todo/todo.md`, "Model the 9K113 Raduga-Sh as a selectable optic"). Its measured multipliers are
  recorded in the decisions doc for whichever slice picks it up. **Two prerequisites this plan
  uncovered and that item must inherit**: the clustering floor fix (hard part 4 — its narrow-field
  `presence_range_mult = 5.81` is the one value that breaks the old proof), and
  `NAKED_EYE_RANGE_CAP_M = 10000.0`, which contradicts the measured 18 km narrow-sight presence
  range outright and must be replaced (ED's altitude-dependent curve, deep-read finding 7, is the
  ready-made replacement) before the sight can be honestly modelled.
- **Threshold recalibration beyond what the decisions doc fixes.** `LOWRES`/`MEDRES`/`HIRES` keep
  their current values. Consequence to state plainly: **2A does not fix the measured 1.33× presence
  shortfall for vehicles**, and the 2A sortie comparison must not read that as a 2A failure.
- **Anything needing the unprobed mission-sandbox bridge** — fog, unit velocity, `Unit.getDesc().box`
  characteristic sizes.
- **Movement detection** (both our "is it moving" gate and ED's `motion_factor`).
- **The ownship-processed-every-poll fault** (sortie note: 4113 rows for `object_id=16777472`). It is
  a Windows-side collector bug, not a perception-layer one — but it will appear in every 2A/2C trace
  as a near-miss and should be recognised rather than re-investigated.
- **The hybrid/HelperAI channel.** `HybridPerceptionSource` is wired alongside the naked-eye source
  in `_build_sources` and has no geometric gate chain, so **gaze does not constrain it** — Petrovich
  can still report something ED told him about while looking the other way. That is a real remaining
  omniscience seam, and it is ED's detection rather than ours. Out of scope here; worth a backlog
  entry after 2C shows how visible it is in practice.
- **Behaviour-change reporting, engagement envelopes, "danger"/"safe from" callouts, IFF** — all from
  the diagram, none of them cones work.

---

### Risks & Unknowns

- **2C is the one slice that can make Petrovich feel broken.** Cutting his instantaneous 260°
  awareness down to a 60° cone visiting each flank every 8 s is a large subjective change, and no
  amount of unit testing predicts whether it reads as "realistic" or "blind." It is deliberately the
  third slice so that 2A and 2B are already banked if 2C needs several tuning passes.
- **The scan cycle conflicts with `OBSERVED_WINDOW_S` (hard part 5).** Resolved by derivation above,
  but it changes crew-facing language, so the 2C sortie must listen for hedging on contacts he is
  actually holding.
- **Group splitting at gaze edges (hard part 3)** — rare at 60°, routine at 2D's 8.5°.
- **`NAKED_EYE_MAX_NEW_PER_POLL` may double-count with the scan loop** — both limit intake rate.
  Do not add a third such limiter without deciding which of these two is the real one.
- **The 2026-09-17 screenshot ladder is compromised** (detection-aid dots enabled), so
  `test_vision_calibration.py` grades against optimistic ground truth. 2A will move rows in that
  suite; a moved row is not automatically a regression, and each change needs judging against the
  sortie data rather than the fixture.
- **The one unexplained measurement stays unexplained**: infantry *type* through the 9K113 wide
  predicted 1.3 km against 0.6 km observed. Recorded, not fitted to. It sits in 9K113 territory and
  does not affect 2A.
- **The presence-multiplier residual is unmodelled** (binocular 2.42 for the BTR against 3.33 for
  infantry — contrast-limited versus acuity-limited). A single per-optic constant will be somewhat
  wrong for one class of object either way; the decisions doc accepted this knowingly.

---

### Effort/value: build 2D as *dwell-the-act*, not as ED's detection-time accumulator

Decision 2 is settled and this does not reopen it — it is about a mechanism the user did not ask
for and that ED's constants make tempting.

ED's `average_det_time_max_dist_*` (10 s → 60 s for ground units) describes a *per-candidate
stochastic timer*: each target takes a while to be found even in full view. Implementing that
faithfully means per-object accumulator state inside `perception`, a reset/forget rule for
partially-accumulated time, a defined interaction with the cone sweeping off mid-accumulation, and
either a random draw (destroying replay determinism) or a deterministic surrogate that is no longer
ED's model.

**Why the value is smaller than it looks:** the scan loop already produces "detection takes time" —
a contact entering the envelope waits on average half a cycle to be looked at — and
`NAKED_EYE_MAX_NEW_PER_POLL` already throttles intake. A third delay mechanism would be physically
double-counting the same lag, and separating the three would need its own calibration sortie.
ED's figures are also quoted for a different skill model under its own stated ideal conditions, so
they are not directly transplantable.

**The alternative, which is what 2D above builds:** read "dwell" as the user defined it — *"looking
at something with intent"* — an act, not a timer. That version earns its keep for a reason the timer
version does not: it is the only thing that ever gives `BINOCULAR_OPTIC` a caller, and it uses ED's
numbers where they are genuinely informative (how long a deliberate look must be held) instead of
where they are not (whether a passive glance finds a tank).

**And 2D should be gated on 2C's sortie**, not built speculatively: if the scan loop already makes
detection feel gradual, the cheapest correct outcome is that 2D is never needed in this milestone.

---

### Second-order effect

2B's `perception/gaze.py` is the module that makes Petrovich's *pointing* a first-class, testable
value — which unblocks three later milestones that currently have no place to attach: the diagram's
"watched units: keep scanning but frequently come back to watched targets" (a scan-loop modifier,
not a belief flag), `scan <location>` against a waypoint or world-model landmark (a bearing is a
bearing once gaze takes one), and the deferred range-uncertainty work, whose settled rule — that
certainty should *narrow* when he uses the sight — is only expressible once "which optic is he using
right now" is a real runtime value rather than a default argument.

It complicates exactly one thing: every future perception channel must now decide whether gaze
applies to it, and the hybrid/HelperAI channel's answer is already "no." That asymmetry is honest
but it is a seam that will need re-examining rather than a settled boundary.

---

### Decisions Requiring User Input

**One question, and it is the one that needs lived experience rather than analysis.**

- **How long should he look at each sector?** The plan recommends **2 s per leg — an 8 s cycle, the
  forward arc revisited every 4 s and each flank every 8 s.** 2 s is the floor imposed by the 1 Hz
  poll rate (below it, sectors get aliased away entirely); there is no ceiling short of contacts
  going stale, and the knock-on is that `OBSERVED_WINDOW_S` is re-derived from whatever this number
  becomes, which changes how confidently Petrovich phrases contacts he is cycling past.

  This is not a number that can be derived — it is how a real crewman's head moves, which is
  the user's knowledge and not the code's. If 8 s feels sluggish in the cockpit, 6 s (1.5 s per leg)
  is the practical floor at the current poll rate; if it feels frantic, 12 s is fine mechanically and
  simply means slower reaction to flank contacts.

  Answerable after flying 2A if preferred — 2C is two slices away, and a guess now can be corrected
  by the 2C sortie without rework.
