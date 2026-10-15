### Performance Review — 9K113 cone, pre-wiring gate measurement

**Not the once-per-feature performance review.** That still happens before DoD, on the whole of
`BL-B64`. This is the measurement the plan places between the optics table landing (Stage 1,
already merged) and the player-bubble cone being written (`plan.md` §12/§12a/§12b), to settle one
question before code commits to a design: does the plan's own cost estimate (+20–40% on a 12.6 ms
tick) hold, given what the code actually does today.

Branch `feature/9k113-sight`, tip `b9c8ecbaf1d310a53f757f349e1a6ff9a4b0ccaf` (HEAD matched exactly,
no merge needed). Isolated worktree outside the repo; `body-layer/.venv` rebuilt pinned
(`ruff==0.16.6`, `mypy==2.3.1`, `pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`).

### Headline finding: the plan's own cost model is stale, by ~125×, and the error is in the project's favour

`plans/9k113-sight/plan.md` §12b carries forward `plans/player-bubble/performance.md`'s **540
µs/candidate** terrain-LOS cost (the 1000× gap behind the "+20–40%" estimate). That figure was
measured against `check_visibility` calling world-model's offline `sample_grid` sqlite primitive
directly. **That code path is dead on this branch.** `visibility.py`'s own docstring says so in as
many words ("World-model's offline `line_of_sight_clear` primitive is no longer reachable from this
live gate at all") — `BL-11` Stage 4's fail-closed rewrite (`plans/bl11-stage4-fail-closed/plan.md`)
replaced the sqlite raycast with a plain boolean read off `candidate.live_los_clear`, already joined
onto every raw candidate upstream (`naked_eye_source._resolve_los_by_unit_name`, a cheap per-object
dict join, same shape as the velocity join) **before** the gate loop runs at all. The actual
terrain/building raycast now happens in the DCS-side Lua Hook (`plans/dcs-driven-los/plan.md`,
X-B29), bounded at `MAX_SIGHTLINES_PER_CALL = 128` — a different subsystem, already measured safe
(agent memory `dcs-driven-los-cone-scoping`), and outside this review's scope (association.py /
visibility.py).

**Measured, this venv, this code** (`check_visibility`, `UNAIDED_OPTIC`, a candidate that clears
every gate through `ADMITTED`, 200 000 calls):

| path | cost |
|---|---|
| full gate chain, `live_los_clear=True` (reaches `ADMITTED`) | **4.345 µs/call** |
| rejected at gate 4, `live_los_clear=False` | 3.419 µs/call |
| rejected at gate 4, `live_los_clear=None` (fail-closed) | 3.424 µs/call |

So "reaching the LOS step" in body-layer's own Python today costs **~4.3 µs**, not 540 µs — a
~125× reduction, because the expensive work moved to a bounded DCS-side mechanism before BL-B64
was ever planned. The plan cites both the stale 540 µs figure and "the realised whole-tick work
median at 12.6 ms after BL-11" in the same paragraph without noticing the two are inconsistent — the
12.6 ms figure already reflects the cheap post-BL-11 gate, the 540 µs figure doesn't.

**This changes the answer the plan asked for before any geometry is considered.** Rebuilding
§12b's whole estimate on the real per-candidate cost (below) puts the cone's net effect at
hundredths of a percent of the tick budget, not 20–40%.

### What was measured, and against what data

Real engagement trace at `/Users/sg/dcs-detection-trace.jsonl` — **not** the 2 072 630-row trace
`plans/player-bubble/performance.md` used; this one is newer (6 218 807 rows, 3 905 distinct polls)
and already reflects live `gaze`/`optic_fov` gates firing (`outcome_counts`: `gaze=1 354 986`,
`optic_fov=9 867`, `cockpit_mask=1 118 205`, `range_or_size=52 603`, `admitted=22 048`,
`terrain_los=1 616`, `player_bubble=3 659 482`). Harness: a streaming aggregator
(`/private/tmp/.../scratchpad/trace_density.py`, committed below), probed against a synthetic
5-row fixture with hand-verified expected counts *before* running it on the real file (assertions
passed) — the benchmarks-must-be-able-to-fail check this role's own memory names.

**Measured directly from the trace (naked eye's own reaching-LOS baseline, today, live):**

| | per tick |
|---|---|
| median | 6 |
| p90 | 22 |
| p99 | 60 |
| max (combat burst) | 4 732 |

At 4.3 µs/candidate: median 25.8 µs/tick (0.20% of 12.6 ms), p99 258 µs/tick (2.05%). This is the
real cost the naked eye already pays today — the number the sight's cone has to beat or justify,
per the user's own §13 framing ("does the narrower FOV gate offset the longer reach").

**Measured directly from the trace (raw population, 10–20 km band, all 360° of azimuth — the pool
a sight cone would newly reach into, since these rows are `player_bubble`-outcome, recorded before
`check_visibility` ever ran):**

| | per tick |
|---|---|
| median | 57 |
| p90 | 295 |
| p99 | 349 |
| max (combat burst) | 269 149 |

### What had to be projected, and why

The cone is not wired, so admission cannot be measured live — this part is projection, stated as
such. Two filters apply to that raw 10–20 km population, and only one is a geometric assumption:

**1. Azimuth (assumption, stated as one).** `DetectionTrace.true_bearing_deg` is a **true/geographic**
bearing (`geometry.bearing_deg`, clockwise from north), not the body-relative azimuth
`within_optic_fov`/the cockpit mask actually gate on — the trace never records ownship heading, so
body-relative azimuth cannot be reconstructed from it. Projection uses the same uniform-density-in-
azimuth assumption the plan's own §12b area argument used (and the player-bubble review before it)
— cone width / 360°: **6°/360° = 1.667%** narrow, **11.5°/360° = 3.194%** wide. This is the one
number that would need a flown-and-logged sight pass (with heading recorded) to turn into a real
measurement; everything else below is derived from the shipped code and the real trace.

**2. Object-type reachability (measured, not assumed).** The sight's own presence-range multiplier
has to actually clear 10 km before the cone buys anything for a given object type — this is a
direct computation against `object_model.profile_for` and the real `Optic` table, not a guess:

| type width | narrow (×5.81) threshold | wide (×3.55) threshold | reaches past 10 km? |
|---|---|---|---|
| 1.8 m (soldiers, manpads, infantry) | 3 486 m | 2 130 m | never, either sight mode |
| 6 m (Shilka, GAZ-66, AA8, technicals) | 11 620 m | 7 100 m | narrow only |
| 7 m (T-55/72/80, BTR, BMP, Tigr) | 13 557 m | 8 283 m | narrow only |
| 9 m (5p73/snr/p-19 s-125 TEL/radar) | 17 430 m | 10 650 m | both, wide barely |

Applied to the real 10–20 km bucket's object-type histogram (868 440 rows across the trace,
dominated by `Soldier M4 GRG` 199 150 and `Infantry AK Ins` 95 156 — infantry are the majority of
what sits out there): **57.1%** of that population is a type narrow sight could ever admit past
10 km; **4.72%** for wide. Wide's 20 km reach is close to moot for this mission's actual unit mix —
only the 9 m SAM-launcher/radar class clears 10 km under wide's own multiplier, and only to
10.65 km, not meaningfully toward 20.

### The net number

Combining both filters (type-reachable fraction × azimuth fraction) against the measured raw
10–20 km counts, then costing at the measured 4.3 µs/candidate:

| | extra candidates/tick (narrow) | cost (narrow) | % of 12.6 ms tick | extra candidates/tick (wide) | cost (wide) | % of tick |
|---|---|---|---|---|---|---|
| median | 0.54 | 2.3 µs | 0.018% | 0.09 | 0.4 µs | 0.003% |
| p90 | 2.81 | 12.1 µs | 0.096% | 0.44 | 1.9 µs | 0.015% |
| p99 | 3.32 | 14.3 µs | 0.113% | 0.53 | 2.3 µs | 0.018% |
| max (burst) | 2 562 | 11.0 ms | 87% | 404 | 1.7 ms | 14% |

**Sustained traffic: negligible, at every percentile, for both cones.** Even p99 narrow (the
"should we worry" row) costs 14 µs — three orders of magnitude under the plan's own "+20–40%"
estimate, for two independent reasons: the per-candidate cost was 125× too high (stale 540 µs vs.
measured 4.3 µs) and the admitted-candidate count was itself overestimated (the plan's own
geometric area argument didn't have the object-type filter, which removes 43–95% of the raw
population depending on cone width before azimuth is even applied).

**Burst ticks are the one row that looks alarming, and the project's own methodology already
discounts them.** `plans/player-bubble/performance.md` flagged the same burst-tick shape
("explosions/debris, not sustained load") on the same kind of trace; this burst (269 149 rows in one
poll, 10–20 km band alone) is that same artifact class. Narrow's projected 11 ms on that one tick is
real exposure if it is NOT debris — worth a cap regardless of the cone (see Verdict) — but it is not
evidence the cone is unsafe for ordinary engagement density.

**Break-even density, as requested.** Narrow's extra cost reaches 5% of the 12.6 ms tick (630 µs) at
~147 post-filter candidates/tick, which requires ~15 400 raw candidates/tick in the 10–20 km band —
44× the measured p99 (349) and well above every sustained tick in this trace; only the debris-burst
outlier (269 149) clears it.

### Does the narrower FOV gate offset the longer reach? (§13's question, directly)

**Yes, decisively, at every percentile measured.** Naked eye's own reaching-LOS baseline today
(median 6, p90 22, p99 60 per tick) is larger than the sight cone's *entire projected admission*
(median 0.5, p90 2.8, p99 3.3 for narrow — smaller still for wide) at every one of those
percentiles. The brief's own hypothesis — that the sight's narrower FOV could reach LOS for *fewer*
candidates than the naked eye does today — is confirmed by both the real baseline and the projected
cone admission, independent of the stale-cost finding above.

### Findings

#### Plan §12b's cost model is built on a dead code path
- **Location:** `plans/9k113-sight/plan.md` §12b, citing `plans/player-bubble/performance.md`'s
  540 µs/candidate LOS figure.
- **Risk:** none to the cone itself — the risk was to the *decision*, not the running code: building
  bounding machinery (a candidate cap, a cheaper pre-filter) against a cost that no longer exists
  would have added real complexity to solve a problem that was already solved by `BL-11` Stage 4.
- **Action:** NOW, but as a plan correction, not a code change. §12b should cite the measured 4.3
  µs/candidate figure and drop the 540 µs one before anyone builds against it. No implementation
  follow-up needed — nothing in body-layer's code is wrong, the plan's narrative about it is.

#### The cone's own cost, correctly priced, is negligible
- **Location:** the not-yet-written `sight_cone` branch in `association.filter_player_bubble`, plus
  the downstream gate-chain cost for admitted candidates.
- **Risk:** none at sustained density (0.02–0.11% of tick at median/p90/p99, both cone widths). The
  one real exposure is the debris-burst tick class (~87% of tick for narrow on the single
  269 149-row outlier observed) — not unique to this feature; the existing pipeline already treats
  burst ticks as a known, discounted artifact class.
- **Action:** MONITOR for sustained traffic. Build as planned — no candidate cap or pre-filter is
  needed to make the cone safe at any density this trace or this project's roadmap has produced.

#### Wide cone's 20 km reach is nearly moot for this mission's unit mix
- **Location:** `optics.SIGHT_WIDE_OPTIC` (`presence_range_mult = 3.55`) against the real 10–20 km
  object-type histogram.
- **Risk:** none — this is a record-the-finding item, not a defect. Only 4.72% of the raw 10–20 km
  population (by row count) is a type wide's own multiplier could ever admit past 10 km, and even
  then only to ~10.65 km (the 9 m SAM-TEL/radar class), not toward 20 km. The 20 km depth exists for
  narrow, where 57.1% of that population (every 6–7 m+ vehicle) genuinely benefits.
- **Action:** MONITOR / informational. Both wide and narrow stay in phase 1 per user direction — this
  doesn't argue for dropping wide, only for not expecting its 20 km figure to do real work at
  today's unit density. Worth a line in the implementation plan so a future reviewer doesn't
  attribute cost savings to wide's reach that the data doesn't show.

#### Burst ticks remain the one unbounded risk, orthogonal to this feature
- **Location:** the whole candidate pipeline, not this feature specifically — `filter_player_bubble`,
  `check_visibility`'s gate chain, and now the projected cone all scale linearly with whatever a
  burst tick hands them.
- **Risk:** real but pre-existing (`plans/player-bubble/performance.md` already flagged it as
  "explosions/debris, not sustained load" on an earlier trace). The 9K113 cone adds its own small
  multiplier on top of an already-unbounded burst-tick cost, not a new unbounded axis.
- **Action:** LATER. A per-tick candidate cap (independent of the cone) would bound this for every
  feature on this path at once, which is a cleaner fix than a cone-specific one — raise to Architect
  if/when burst-tick cost is prioritized; not blocking for this feature.

### Verdict
**APPROVED — build the cone as planned, both wide and narrow, no bounding mechanism required at
this stage.** The plan's own "+20–40%, needs bounding" framing does not survive contact with the
current code: the per-candidate cost it relied on is 125× stale, and the candidate-count side it
reasoned about geometrically turns out (once filtered by real object-type reachability) to be
smaller than the naked eye's own existing per-tick LOS reach. Correct §12b's citation before
implementation starts, so the next reader doesn't rebuild bounding logic against a number that no
longer describes the code. The one open item — burst-tick cost — is pre-existing, project-wide, and
not a reason to withhold or complicate this specific feature.
