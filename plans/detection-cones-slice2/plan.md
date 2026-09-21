### Goal

Turn detection from "an all-seeing predicate with one magnification number" into "a directed,
per-tier, distinctiveness-aware act" — implementing the three settled model decisions
(`body-layer/research/2026-09-21-slice2-model-decisions.md`) across four independently mergeable
sub-slices, each of which leaves the system flyable.

**The three decisions are settled input, not open questions.** This plan is about how and in what
order, and about the structural problems they create that the decisions themselves do not answer:
where gaze state lives, why the attention gate *is* the optimisation, what must be allowed to bypass
it, what a moving cone breaks downstream, how a scan loop stays replay-deterministic, and which
existing mechanisms already govern the same concepts.

**Revised 2026-09-21 (user), after 2A was already in flight.** Naked eyesight is **two channels**,
not one: a narrow **focus** cone that sees well and itself scans within a sector, and a wide
**peripheral** channel with poor acuity but excellent change detection. 2A is unaffected and is not
changed by this revision; the two-channel model sharpens 2B, 2C and 2D.

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
| **2B** | Gaze as a filter; `Optic.peripheral`; the stimulus seam; F10 scan commands steer perception | **No** — default gaze is the forward hemisphere, i.e. today | In flight: "scan left" demonstrably changes which contacts are detected; with no command issued, the BL-9 trace is byte-identical to 2A's |
| **2C** | Default gaze becomes the o'clock-cone scan loop `12, 11, 10, 9, 12, 1, 2, 3` (2 s each, 16 s cycle); peripheral structure with no triggers wired | **Yes** — this is the big one | A sortie judged by the user on *feel*: does he find things at a plausible rate, and does the callout language stay stable as contacts cycle in and out of gaze |
| **2D** | Dwell as an act: fix on it, check for more nearby, then glass up or resume | **Yes** | Conditional — only built if 2C's sortie shows a real need (see effort/value below) |

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
  `FULL_GAZE` (0°, 90° — the forward hemisphere, i.e. no narrowing), `within_gaze(gaze, azimuth_deg)`,
  `gaze_for(object_id, gaze, stimulus_ids, optic)`, and **the `RelativeSector` vocabulary moved down
  from `belief/attention.py`**: the `Literal`, `RELATIVE_SECTORS`, and `_RELATIVE_SECTOR_WEDGE_DEG`.
  Also the o'clock-cone table: with a 30° focus cone and 30° per o'clock hour, **the cone is the
  o'clock position**, so `RelativeSector` (used by F10 commands) and the o'clock cones (used by free
  scan) are two granularities over the same wedge arithmetic.
- `body-layer/src/belief/attention.py` — re-imports `RelativeSector` / the wedge table from
  `perception.gaze` instead of defining them. `belief → perception` is the allowed direction (it
  already imports `perception.geometry`); the reverse is forbidden, which is exactly why the
  vocabulary has to move down rather than the gate move up. **This is the one refactor the plan
  requires, and it removes a real duplication** — otherwise ahead/left/right/full wedge angles would
  exist in two modules that must agree and have no mechanism forcing them to.
- `body-layer/src/perception/geometry.py` — gains the two-line `angular_delta_deg` helper
  (`abs((a - b + 180) % 360 - 180)`), currently private in `belief/attention.py` as
  `_angular_delta_deg`; both modules import it from there. This is the *only* thing the gaze test
  and `area_contains` genuinely share — see "Gaze cannot reuse `area_contains`" below.
- `body-layer/src/perception/visibility.py` — `check_visibility` gains `gaze: Gaze | None = None`,
  **evaluated first in the gate chain, ahead of the cockpit mask** (see "Attention is the
  optimisation" below for why the ordering is load-bearing rather than incidental). `None` = no
  restriction = today. The three directional gates then read: gaze (where he is looking) → cockpit
  mask (what the airframe permits at all) → optic FOV (what the instrument shows once pointed). The
  effective envelope is their intersection, exactly as `todo/todo.md`'s "Scan commands should drive
  naked-eye perception" entry already framed it; the gates are **not nested** (the gaze wedge is a
  pure azimuth test with no elevation term, so it admits targets the mask's depression limits
  reject), so all three are genuinely needed and the order affects only cost and trace attribution.
- `body-layer/src/perception/detection_trace.py` — new `GateOutcome.GAZE`, preserving BL-9's
  one-entry-per-call invariant (the same defect slice 1's merge note records for `OPTIC_FOV`).
- `body-layer/src/perception/optics.py` — `within_optic_fov` takes the boresight as a parameter
  (the gaze center) rather than reading `Optic.boresight_azimuth_deg`; that field is deleted. An
  optic is pointed by the head, not bolted to the airframe. **New field `peripheral: bool`** —
  `UNAIDED_OPTIC` `True`, `BINOCULAR_OPTIC` `False` (hard part 2a). Not in 2A, which is already in
  flight; this rides with 2B, where the rule that consumes it also lands.
- `body-layer/src/perception/naked_eye_source.py` — new fields `gaze: Gaze | None = None` and
  `peripheral_stimulus_ids: frozenset[int] = frozenset()` (the peripheral channel's output, hard
  parts 2a and 4), resolved per candidate through `gaze.gaze_for(...)` before each
  `check_visibility` call.
- `body-layer/src/logger.py` — the runner is the only place belief and perception meet, and it
  already is (`_build_sources`, `store.ingest`). Before each poll it resolves the active commanded
  sector from the `TaskStore`/`ContactStore` (a pending `scan_area` task whose area carries a
  `relative_sector`) and assigns a frozen `Gaze` onto the naked-eye source — the same
  write-thread/read-thread single-assignment pattern `last_t_sim` already uses safely.
- Closes `todo/todo.md`'s standing **"Scan commands should drive naked-eye perception"** item.

**2C**
- `body-layer/src/perception/gaze.py` — `ScanPlan` (frozen: the commanded sector or `None`, plus the
  sim time the command was issued) and `gaze_at(t_sim, plan) -> Gaze`. **A pure function of sim
  time, not a state machine** (see "Determinism" below). The free-scan plan is an **ordered table of
  o'clock cones with one dwell each** — `12, 11, 10, 9, 12, 1, 2, 3` at 2 s — so `gaze_at` is a
  modulo and a table index. Constants `FOCUS_CONE_HALF_WIDTH_DEG = 15.0`, `FOCUS_DWELL_S = 2.0`,
  `SCAN_CYCLE_PERIOD_S = 16.0` (hard part 8). This is *less* machinery than the continuous
  within-sector sweep an earlier revision planned, not more.
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

### The hard parts, confronted

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

The user's focus/peripheral model (hard part 2a) turns this into a clean three-level nesting rather
than a two-term mismatch: **scan leg 60-90° → focus cone 30° (one o'clock) → binocular 8.5°.** Each
level is a deliberate narrowing bought at a cost, and the binocular's cost is now more than field of
view.

A corollary worth carrying: **2D is the slice that finally gives `BINOCULAR_OPTIC` a caller.**
Without it, the binocular table entry and its measured 2.42/3.50/3.00 multipliers stay unreachable
forever — the exact failure mode slice 1's scope cut was written to avoid.

#### 2a. Two channels, not one — and it is the principled answer to the bypass seam

User, 2026-09-21: focus is *"a narrow cone that sees really well,"* and within a sector it is itself
a smaller cone moving in a scan pattern; peripheral is *"very wide FOV, fairly poor focus, but
excellent change detection"* — movement, light changes, muzzle flash, tracers, launches, explosions
— which *"grabs attention immediately and snaps focus there,"* unless the change was expected, in
which case *"mind overrides instinct."*

This replaces the bypass seam's design (hard part 4) with something better than an exemption list.
An enumerated list of things that bypass attention ("missiles, flares, tracers…") answers *what*
and never *why*, and every future addition is an arbitration. A second channel with its own physics
— wide field, change-only, no acuity — answers *why*, and the list falls out of it. **Peripheral
vision is what the bypass seam was groping for.**

It also gives binoculars a real cost. Not merely 8.5° against a 30° focus cone, but **the loss of
change detection entirely**: glass up and you stop noticing the launch flash behind your shoulder.
That makes "raise binoculars or keep scanning" a genuine trade rather than a free acuity upgrade,
which is what 2D's decision point was missing.

**Does peripheral destroy the optimisation? No — and the reason is the important part.** A wide
change-detection channel sounds like it re-introduces the full-envelope sweep that hard part 3 just
removed. It does not, because **peripheral is event-driven, not scan-driven**. The focus channel
runs the full gate chain over candidates because it is *looking for* things; the peripheral channel
responds to things that *change*, and the number of change events per poll is bounded by the event
rate, not by the ~74 candidates in view. Today that rate is zero (no change channel exists). So the
cost model is: full chain on the focus cone's small share, plus a cheap azimuth + LOS test on
whatever changed. The two-channel model is *cheaper* than one wide channel, not more expensive —
and that is a consequence of the physics being right, which is the same point hard part 3 makes.

**What to build now, and what not to — settled by the user, 2026-09-21.** Build the structure, wire
the triggers later. The structural split determines the shape of the attention gate, so getting it
wrong now is expensive later; but peripheral fires on change events and there is
no behaviour-change channel in this codebase at all (`body-layer/ROADMAP.md` records movement
detection as designed-not-built, gated on the unprobed mission bridge). So: build the structure in
2B/2C with **no triggers wired**, and make it operative today through one field —

**`Optic.peripheral: bool`** (unaided `True`, binocular `False`). This is not inert table data, the
failure slice 1's scope cut was written to avoid, because it carries a live rule:

> **Salience bypasses the gaze gate only when the active optic has peripheral vision.**

That single rule makes the whole two-channel model testable with an empty stimulus set — supply a
salient object id and assert it is admitted under `UNAIDED_OPTIC` and rejected under
`BINOCULAR_OPTIC`. The binocular's real cost becomes an executable fact rather than a prose claim,
today, with no change channel in existence.

**Deferred deliberately: expectation suppression** (*"unless it is an expected change, in which case
mind overrides instinct"*). It requires belief-side knowledge of what is expected, which would run
the import the forbidden way and needs its own design pass. Recorded, not designed.

#### 3. Attention is the optimisation — they are the same change, seen from two sides

User direction, 2026-09-21: *"Attention direction also allows for optimisation: units that cannot be
seen, i.e. are out of attention area, do not need any calculations, other than being outside
attention area."*

**This is not a performance pass to be added after the model works — it is how the attention gate
works.** If an out-of-attention candidate is still fully evaluated, then either its result is
discarded (waste) or it is detected anyway (the model is not doing its job). Skipping the
computation and being unable to see it are the same statement. The speed is a consequence of the
model becoming correct, which is why it is specified here rather than deferred to a later
optimisation slice, and why **the attention wedge is the first gate in the chain, ahead of the
cockpit mask**.

The ordering is justified on its own terms — one bearing comparison against a wedge is the cheapest
test available and by far the most selective — and it is measurable. From the real 2026-09-21 sortie
trace (`~/cones-sortie.jsonl`: 350,913 candidate evaluations over 4,719 polls, ~74 candidates per
poll):

| outcome today | count | share |
|---|---|---|
| rejected by cockpit mask | 84,948 | 24.2% |
| rejected by range/size | 248,478 | 70.8% |
| admitted | 17,487 | 5.0% |

**265,965 evaluations (75.8%) currently reach the range gate**, each paying a profile lookup, aspect
arithmetic and a threshold comparison, with terrain-LOS sampling behind the survivors. A 60° wedge
inside the ~260° cockpit envelope keeps roughly 23% of them — **about 61,000 instead of 266,000**.

**The o'clock cone sharpens this, and the basis is now arithmetic rather than a scaling guess.**
The user's decision that the scan steps cone by cone (hard part 8) makes the gate **exactly 30°
wide** — one o'clock hour — inside a ~260° cockpit azimuth envelope:

```
30 / 260 = 11.5%  ->  265,965 x 0.115 ~= 31,000 evaluations
```

**The assumption to name, because step 16 is what tests it:** that candidates are distributed
uniformly in azimuth. They are not — a mission is flown *toward* things, so the 12 o'clock cone
holds more than its share, and the scan plan below visits 12 twice per cycle. Both effects push
real retention **above** 11.5%. Treat ~31,000 as a floor, not a forecast. This is the only per-poll
hot path in the body layer, and the one place in this plan where a cost claim rests on measurement
rather than estimate.

Two consequences to build in rather than discover:

- **The saving arrives with 2C, not 2B.** 2B's default is `FULL_GAZE` (±90°), which by construction
  rejects nothing the cockpit mask would not. 2B is therefore behaviour-preserving *and*
  cost-neutral; the behaviour change and the saving land together in 2C, which is the same point
  restated.
- **Gaze-first costs the trace its cockpit-mask rejection rate.** A candidate behind the rear cutoff
  that is also outside the wedge will now record `GAZE`, not `COCKPIT_MASK`, so the 24.2% figure
  above stops being observable from a live trace. Accept this rather than reordering back: the mask
  is a static, already-measured envelope that can be characterised offline, while the gaze rejection
  count is the number that will actually be tuned. Say so in `detection_trace.py`'s docstring so a
  future reader does not "fix" the ordering.

#### 4. The bypass seam: what captures attention, and what it must never grant

A blanket "skip everything outside the focus cone" would make Petrovich unable to notice things a
real crewman certainly would. `docs/concept/STATE_TRANSITIONS.md` is explicit that a missile or
gunfire aimed at ownship is an **urgent** report, and lists lights and flashes — strobes, tracers,
explosions, flares — as attention-grabbing; the 2026-09-20 movement design adds that high speed
grabs attention rather than merely being detectable.

**Hard part 2a supplies the principle: this is the peripheral channel's output, not an exemption
list.** The bypass set is therefore small, event-driven, and defined by the *stimulus* rather than
by the object — never "missiles always bypass," which would be a standing omniscience exemption
keyed on object type, and never a list that has to be arbitrated every time something is added.

**The seam, built in 2B and 2C, is one parameter and one rule:** `NakedEyePerceptionSource` takes a
`peripheral_stimulus_ids: frozenset[int]` (default empty, a true no-op) — the output of the
attention-capture channel, which does not exist yet. The per-candidate gaze passed to
`check_visibility` is `None` for a stimulus candidate **when the active optic has peripheral
vision**, and the current focus `Gaze` otherwise. One pure function:

```
gaze_for(object_id, gaze, stimulus_ids, optic) -> Gaze | None
```

The `optic.peripheral` term is what makes this operative today rather than dormant (hard part 2a):
with binoculars raised, a stimulus is *not* bypassed, because there is no peripheral channel to
catch it.

**The invariant that keeps the seam honest: a bypass skips the gaze gate only — never the cockpit
mask, never range/size, never terrain LOS.** Salience redirects attention; it does not grant vision.
A flash behind the ±130° rear cutoff, or behind a ridge, is still not seen. Without this rule the
bypass becomes a back door through the no-omniscience invariant, which is exactly the shape of
leak this milestone exists to close.

**What is unprotected until the capture channel exists, stated plainly:** from 2C onward, an
incoming missile or a muzzle flash outside the current 30° focus cone is simply not noticed. This does
not regress anything that works today — nothing in the codebase detects incoming weapons at all;
`UrgentCall` exists as a mechanism with `!inject-urgent` as its only trigger — but it adds a second,
independent reason it will not work, and the capture channel must land alongside whatever finally
builds the weapon detector, not after it.

#### 5. Gaze cannot reuse `area_contains` — and that is not a duplication

Worth settling explicitly, because it looks like the same predicate and is not. `belief.attention.
area_contains` tests an **absolute** bearing from *the area's own centre* to a world position, plus
a radius. The gaze test is a **body-relative azimuth** — the same quantity `cockpit_mask.is_visible`
already consumes, derived from ownship's heading/pitch/bank — compared against a wedge centred on
where his head is pointed. Different frame, different origin, no radius. Sharing one function would
mean passing an ownship pose into what is deliberately a pure absolute-geometry predicate, which
`plans/f10-command-vocabulary/plan.md` D2 already rejected once for the same reason.

What *is* genuinely shared is the two-line shortest-angle helper (`_angular_delta_deg`). That moves
down to `perception/geometry.py` as `angular_delta_deg` and both modules import it — the allowed
direction, and the only piece small and frame-independent enough to be common. `perception` gets its
own wedge test in `gaze.py`; that is one `if`, not a parallel implementation of an abstraction.

#### 6. What a moving cone breaks: `naked_eye_source.py`, specifically

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
individually." At the 30° o'clock cone this is occasional (a group tight enough to cluster is
rarely astride a cone boundary, but 30° is half the width the earlier design assumed); at 2D's 8.5°
binocular field it is routine. Flagged as a 2C acceptance
item and a 2D design constraint, not fixed pre-emptively.

#### 7. The clustering floor is no longer benign — verified, not assumed

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

#### 8. The scan plan, worked: o'clock cones, and the fork that moves a derived constant

**Two user decisions, 2026-09-21.** *"2 s per o'clock sector for a quick scan"*, and *"let's start
with this: scan per o'clock cone. It's an easy simplification and we can iterate later."*

The second one removes an invented geometry rather than adding one. A focus cone is 30° and an
o'clock hour is 30°, so **the cone *is* the o'clock position** — there is no separate
within-sector sweep to model. The scan plan becomes an ordered list of o'clock positions with a
dwell each: a table, which is less machinery than the continuous sweep this plan previously carried,
not more.

##### The fork

`docs/concept/STATE_TRANSITIONS.md` gives `ahead = 11-1`, `left = 9-11`, `right = 1-3`. As *cones*
that double-counts 11 and 1, because the diagram is describing arcs with shared **boundaries**, not
sets of cones. Four readings are available, and they do not cost the same:

| plan | cones covered | cycle | worst gap | middle certainty band | after one missed sweep |
|---|---|---|---|---|---|
| **A** — `ahead={12}`, `left={11,10,9}`, `right={1,2,3}` | 9-3 (7) | **16 s** | 14 s | **14 s wide** | **30.0 s — just inside** |
| C — partition, `ahead={11,12,1}`, flanks `{10,9}`/`{2,3}` | 9-3 (7) | 20 s | 18 s | 10 s wide | 38 s — band skipped |
| B — literal, overlapping `ahead={11,12,1}` | 9-3 (7) | 24 s | 22 s | 6 s wide | 46 s — band skipped |
| D — A extended to the measured mask | 8-4 (9) | 24 s | 22 s | 6 s wide | 46 s — band skipped |

**Adopt A**, and the deciding argument is not tidiness — it is `belief/decay.py` pricing the choice:

1. **A is the *unique* 16 s plan** at 2 s per cone covering the diagram's 9-3. Sixteen seconds is
   eight slots; seven distinct cones leaves exactly one to double, and 12 is the right one.
2. **16 s is the largest cycle for which a single missed sweep still lands inside
   `POSITION_HALF_LIFE_S`.** A missed visit costs `2 x CYCLE - FOCUS_DWELL`; at 16 s that is exactly
   30.0 s, at 20 s it is 38 s. **Above 16 s, one dropped sweep skips an entire certainty band** —
   terrain-LOS flicker or the `NAKED_EYE_MAX_NEW_PER_POLL` cap would make a contact jump two levels
   of confidence at once. That is a real behavioural cliff, not a rounding concern.
3. The middle band is `POSITION_HALF_LIFE_S - CYCLE` wide: 14 s under A, 6 s under B or D. A 6 s
   band between two certainty levels is close to no band at all.

**What adopting A costs, stated rather than glossed.** The diagram's `ahead` is the 11-1 *arc*, and
A revisits only the nose (12), so 11 and 1 get flank-level attention. C is the faithful reading of
the diagram's forward weighting and costs 4 s of cycle and the missed-sweep property. If the 2C
sortie shows the forward arc being under-scanned, C is the pre-worked alternative and
`OBSERVED_WINDOW_S` moves to 20.0 with it — which is the whole reason the table above exists.

##### The constants, and why `OBSERVED_WINDOW_S` survives unchanged

```
FOCUS_CONE_HALF_WIDTH_DEG = 15    (one o'clock hour, 30 deg wide)
FOCUS_DWELL_S             = 2
SCAN_PLAN                 = 12, 11, 10, 9, 12, 1, 2, 3
SCAN_CYCLE_PERIOD_S       = 16    (8 slots x 2 s)
```

`belief/decay.py`'s `certainty_of` returns `"observed"` while
`now_sim - contact.last_seen_sim <= OBSERVED_WINDOW_S`, currently **5.0**. The worst case is a flank
cone: visited for 2 s, not returned to for a full cycle.

```
max_unobserved_gap_s = SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S = 16 - 2 = 14 s
```

against a 5.0 s window — **a flank contact is out of "observed" for 14 of every 16 seconds** while
he tracks it perfectly well, and the crew layer hedges its language about it on nearly every tick.
The 5.0 was chosen when he looked everywhere at once, where "seen in the last 5 s" and "currently
seen" were the same statement; once he scans, the physically correct meaning of "observed" is *"seen
within the current scan cycle."*

The **upper** bound is the band-collapse above: if `OBSERVED_WINDOW_S` reaches
`POSITION_HALF_LIFE_S` the middle band vanishes silently. So

```
SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S  <  OBSERVED_WINDOW_S  <  POSITION_HALF_LIFE_S
                              14  <  OBSERVED_WINDOW_S  <  30
```

**`OBSERVED_WINDOW_S = SCAN_CYCLE_PERIOD_S` = 16.0** — reads as exactly what it means, clears the
lower bound with 2 s of margin for a poll landing awkwardly, leaves a real 16-30 s band.
`belief/decay.py` imports `perception.gaze` for the period (the allowed direction). Two assertions,
each testing a real failure:

- `SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S < OBSERVED_WINDOW_S` — a later tuning pass cannot silently
  push contacts he is holding out of "observed".
- `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` — the middle certainty band cannot be collapsed.

At 1.0 s polls a 2 s dwell is two samples per cone, so the aliasing floor is cleared at the finest
level of the plan, which is the level that matters. **And the acquisition retention window is the
same number**: hard part 6's eviction window is `SCAN_CYCLE_PERIOD_S`, not an invented constant.

##### The coverage gap this creates — flagged, not fixed

Seven cones spans **9-3, i.e. 210°**. But `cockpit_mask.py`'s measured envelope admits **8-4
(260°)**, and the implemented voice vocabulary already speaks `report_clock_8` and `report_clock_4`
— `docs/concept/STATE_TRANSITIONS.md` records that this exact conflict was already resolved once
**in favour of the mask**, because the diagram's 9-3 is the coarser earlier statement.

So under A, Petrovich can *report* a contact at 8 o'clock if attention is directed there, but while
free-scanning he will never *find* one. Closing it is plan D: 9 cones, 24 s, and both decay
properties lost. That is a real price for 50° of coverage, and it is the user's own "iterate later"
call to make after flying 2C — recorded here with its cost so the 2C sortie can judge it rather
than rediscover it.

This is the item most likely to have been discovered mid-implementation rather than during design,
and it is why the decay constants were read before this plan was written rather than after.

#### 9. Determinism and replay

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
8. `check_visibility` gains the gaze gate **as the first gate in the chain** +
   `GateOutcome.GAZE`; `within_optic_fov` takes its boresight as a parameter;
   `Optic.boresight_azimuth_deg` deleted. Document the ordering and its trace-attribution cost in
   `detection_trace.py` (hard part 3).
9. `Optic.peripheral`; `NakedEyePerceptionSource.gaze` + `peripheral_stimulus_ids` fields and
   `gaze_for`; `logger.py` resolves the commanded sector each poll and assigns it. Default stays
   `FULL_GAZE` and an empty stimulus set, so both are no-ops.
10. Regression test: with no command issued, the BL-9 trace over a fixture stream is identical to
    2A's. New tests: a commanded `left` gaze rejects a contact at 12 o'clock and admits one at
    10 o'clock; a candidate in `peripheral_stimulus_ids` clears the gaze gate at any azimuth **and
    is still rejected by the cockpit mask behind the rear cutoff** — the invariant that keeps the
    bypass from becoming an omniscience back door (hard part 4); and the same candidate is **not**
    bypassed under `BINOCULAR_OPTIC`, because `peripheral` is `False` — the one test that makes the
    binocular's real cost executable rather than prose (hard part 2a).
11. Update `todo/todo.md`: close "Scan commands should drive naked-eye perception."

**2C — the scan loop**

12. `ScanPlan` + `gaze_at` over the o'clock-cone table `12, 11, 10, 9, 12, 1, 2, 3` at
    `FOCUS_DWELL_S = 2.0`, giving `SCAN_CYCLE_PERIOD_S = 16.0` and a 30°
    (`FOCUS_CONE_HALF_WIDTH_DEG = 15.0`) gate. Keep the table a named constant, not an inlined
    literal — hard part 8's plan C is the pre-worked alternative if the 2C sortie says the forward
    arc is under-scanned, and swapping it must be a table edit plus one constant, nothing more.
13. Time-based acquisition dicts in `naked_eye_source.py` (hard part 6), eviction window
    `SCAN_CYCLE_PERIOD_S`.
14. `OBSERVED_WINDOW_S = SCAN_CYCLE_PERIOD_S` (16.0) in `belief/decay.py`, plus **both** assertion
    tests from hard part 8 — the lower bound against the worst-case flank gap, and the upper bound
    against collapsing the middle certainty band.
15. Determinism test: the same recorded stream replayed twice yields identical observations; and a
    contact sitting at a fixed bearing is detected on the cycles when its sector is gazed and not
    on the others, with the period matching `SCAN_CYCLE_PERIOD_S`.
16. Measure the saving the same way the baseline was measured — gate-outcome counts over a full
    sortie trace against the 350,913-evaluation baseline in hard part 3. It is the one number in
    this milestone that can be checked rather than judged.
17. Fly it. Everything else about this slice is judged on feel, not on a number.

**2D — dwell as an act (conditional, see below)**

18. **The user's own loop, which is a better definition than this plan previously carried**: focus
    detects something → dwell on it to see what it is *and whether there are more things nearby* →
    then, by available categorisation and expected threat, either raise binoculars or resume
    scanning; if it turns out dangerous, watch it.

    Three parts, each landing where it belongs. *Fix on it*: belief selects the target (highest
    attention, lowest classification level), the runner passes down a narrow `Gaze` at its bearing.
    *Check for more nearby*: the dwell widens to the contact's neighbourhood before deciding —
    `cluster_candidates` already computes exactly this over what is visible, so it is a reuse, not
    a new mechanism. *Glass up or resume*: a belief-side decision from categorisation and threat,
    executed as `BINOCULAR_OPTIC` + its 8.5° field **and `peripheral=False`** — the trade is real in
    both directions. Hold duration is informed by ED's `average_det_time_max_dist_*` ground figures.

    Note what this does not need: no new module, no new state, no new belief→perception import. The
    two-channel work in 2B/2C is what makes it a small slice.

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
- **The attention-capture channel itself** — what actually computes a peripheral stimulus (flashes,
  tracers, explosions, a weapon tracking ownship, high angular speed). It needs the diagram's
  behaviour-change channel, which does not exist. **The seam it plugs into is built here** (hard
  parts 2a and 4); the channel is not.
- **Expectation suppression** — the user's *"unless it is an expected change, in which case mind
  overrides instinct."* It needs belief-side knowledge of what is expected, which would run the
  import the forbidden way, and it deserves its own design pass rather than a corner of this one.
  Recorded, not designed. Until it exists, every peripheral stimulus captures attention equally,
  including ones he had every reason to anticipate.
- **Behaviour-change reporting, engagement envelopes, "danger"/"safe from" callouts, IFF** — all from
  the diagram, none of them cones work.

---

### Risks & Unknowns

- **2C is the one slice that can make Petrovich feel broken.** Cutting his instantaneous 260°
  awareness down to a 60° cone visiting each flank every 8 s is a large subjective change, and no
  amount of unit testing predicts whether it reads as "realistic" or "blind." It is deliberately the
  third slice so that 2A and 2B are already banked if 2C needs several tuning passes.
- **The scan cycle conflicts with `OBSERVED_WINDOW_S` (hard part 8).** Resolved by derivation above,
  but it changes crew-facing language, so the 2C sortie must listen for hedging on contacts he is
  actually holding.
- **Group splitting at gaze edges (hard part 6)** — occasional at the 30° focus cone, routine at
  2D's 8.5° binocular field. The 30° o'clock cone makes this more likely than the earlier 60° design
  did, and 2D's "check for more nearby" step is partly a mitigation as well as a behaviour.
- **From 2C onward, nothing outside the current sector can capture his attention** — no flash, no
  tracer, no missile. The seam exists and is empty. This regresses no working behaviour (nothing
  detects weapons today; `UrgentCall`'s only trigger is `!inject-urgent`) but it means the gap now
  has two independent causes, and the capture channel must ship with the weapon detector rather
  than after it.
- **The attention wedge has no elevation term.** It is a pure azimuth test, which is what makes it
  the cheapest and most selective first gate — but it means a steep dive or climb does not narrow
  what he is looking at, and the cockpit mask (which does have depression limits) is what catches
  that. Correct for a head that turns rather than tilts; worth revisiting only if the 2C sortie
  shows it reading wrong in hard manoeuvring.
- **Free scan covers 9-3 (210°) while the cockpit mask admits 8-4 (260°)** and the voice vocabulary
  already speaks 8 and 4 (hard part 8). He can report an 8 o'clock contact if directed there, but
  will never find one unprompted. Closing it costs a 24 s cycle and both decay properties; recorded
  with its price for the 2C sortie to judge.
- **Plan A weights only the nose, not the diagram's 11-1 forward arc.** Plan C is pre-worked and
  costs 4 s of cycle plus the missed-sweep property; if 2C shows the forward arc under-scanned, the
  change is a table edit and `OBSERVED_WINDOW_S` 16 → 20.
- **A missed sweep drops a contact two certainty bands at once** (hard part 8: `2 × CYCLE −
  FOCUS_DWELL` = 30 s, exactly `POSITION_HALF_LIFE_S`). Defensible but it will read as abrupt; first
  thing to check if 2C shows confidence flickering.
- **`NAKED_EYE_MAX_NEW_PER_POLL = 3` is tighter than it looks under a 2 s cone dwell.** Two polls
  per o'clock cone means at most six new objects taken in per visit to that bearing, and the rest
  wait a full 16 s cycle. A dense sector will under-report. Do not raise it reflexively — it is the
  pre-existing attention-bandwidth model (hard part 6) and the scan loop is the new one; decide
  which is real before touching either.
- **The measured saving assumes candidate counts stay near ~74 per poll.** A denser mission moves
  the absolute numbers but not the ~23% retention ratio, which is a property of the wedge geometry.
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

**Why the value is smaller than it looks, and the o'clock-cone plan makes this stronger:** the scan
loop already produces "detection takes time," and now produces a lot of it — a contact at a flank
o'clock waits up to 14 s for the focus cone to reach it (hard part 8), not the few seconds the
earlier 8 s design implied. `NAKED_EYE_MAX_NEW_PER_POLL` throttles intake on top of that. A third
delay mechanism would be physically double-counting the same lag, and separating the three would
need its own calibration sortie. ED's figures are also quoted for a different skill model under its
own stated ideal conditions, so they are not directly transplantable.

**The alternative, which is what 2D above builds:** read "dwell" as the user defined it — *"looking
at something with intent"* — an act, not a timer. That version earns its keep for a reason the timer
version does not: it is the only thing that ever gives `BINOCULAR_OPTIC` a caller, and it uses ED's
numbers where they are genuinely informative (how long a deliberate look must be held) instead of
where they are not (whether a passive glance finds a tank).

**And 2D should be gated on 2C's sortie**, not built speculatively: if the scan loop already makes
detection feel gradual, the cheapest correct outcome is that 2D is never needed in this milestone.
The o'clock-cone plan raises the odds of that outcome considerably, which is worth saying now
rather than after 2D is half-built.

One thing does argue the other way and should be weighed at the 2C gate rather than pre-judged:
with `Optic.peripheral` landing in 2B, **2D is the only slice that ever exercises `peripheral=False`
in the live path.** Until something raises binoculars, the binocular's real cost is proven by a test
and never by a sortie. That is not sufficient reason to build 2D — a tested rule with no live caller
is still better than an untested one — but it is the honest counterweight.

---

### Second-order effect

2B's `perception/gaze.py` is the module that makes Petrovich's *pointing* a first-class, testable
value — which unblocks three later milestones that currently have no place to attach: the diagram's
"watched units: keep scanning but frequently come back to watched targets" (a scan-loop modifier,
not a belief flag), `scan <location>` against a waypoint or world-model landmark (a bearing is a
bearing once gaze takes one), and the deferred range-uncertainty work, whose settled rule — that
certainty should *narrow* when he uses the sight — is only expressible once "which optic is he using
right now" is a real runtime value rather than a default argument.

It also changes the economics of every later perception term. Landcover LOS, light level, fog,
movement — each was costed against a gate chain that evaluates ~266,000 candidates per sortie
against the range test. After 2C that is ~61,000, so terms previously judged too expensive to run
per candidate deserve re-costing rather than being carried forward as settled. This is the clearest
case of the optimisation and the model being the same change: making him less omniscient is what
makes the expensive realism terms affordable.

The two-channel split narrows a future milestone usefully too. The attention-capture channel, the
behaviour-change channel and movement detection were three separately-scoped items that all
turn out to feed **one** thing — `peripheral_stimulus_ids` — so whichever is built first defines
the interface for the other two, and none of them needs to negotiate with the attention gate again.

It complicates exactly two things: every future perception channel must now decide whether gaze
applies to it, and the hybrid/HelperAI channel's answer is already "no"; and every future
attention-grabbing stimulus must decide whether it is a peripheral stimulus, which the two-channel
physics constrains but does not fully decide. Both are honest seams that will need re-examining
rather than settled boundaries.

---

### Decisions Requiring User Input

**None outstanding.** The one question this plan carried — how long he should look at each sector —
was answered by the user on 2026-09-21: **2 s per o'clock cone**, with the scan stepping cone by
cone, which works out to a 16 s cycle (hard part 8). That is recorded as a decision, not a
recommendation, and the two constants derived from it (`OBSERVED_WINDOW_S`, the acquisition
retention window) follow arithmetically rather than by taste. The one genuine fork the decision left
open — which cones belong to which leg, since the diagram's arcs share boundaries — is resolved to
plan A in hard part 8 on a decay-ladder argument, with plan C pre-worked as the alternative.

Two things are **flagged rather than asked**, because they are consequences the user should see
land rather than decisions needing an answer now:

- **`OBSERVED_WINDOW_S` moves 5.0 → 16.0**, which changes how confidently Petrovich phrases
  contacts he is cycling past. It is derived, but it is audible, and the 2C sortie is where it
  gets judged.
- **From 2C onward nothing outside the focus cone can capture his attention** until the
  attention-capture channel exists (hard part 4). The seam is built and empty. Worth knowing before
  flying 2C rather than after.
- **Free scan covers 9-3, the cockpit admits 8-4** (hard part 8). He will not find an 8 o'clock
  contact unprompted, though he can report one if directed. Closing it costs a 24 s cycle and both
  decay properties — an "iterate later" call for after 2C flies, priced here so it need not be
  rediscovered.
