### Goal

Give the naked-eye channel a **group detectability** term, by splitting the single presence
threshold into two — *resolution* (can the eye register a mark at all) and *salience* (would a lone
mark be noticed while scanning) — and letting membership of a cohesive group admit a candidate at
the resolution threshold instead of the salience one.

---

### The model, and why this shape

The dots-off ladder (`body-layer/research/2026-09-22-four-column-calibration-ladder.md`) and the
single-unit sortie (`2026-09-21-first-cones-sortie-results.md`) are not in conflict once the two
questions are separated. Current code answers only one of them, with one constant.

| | angular radius | 7 m vehicle | evidence |
|---|---|---|---|
| **resolution** (new) | `RESOLUTION_ANGULAR_RADIUS_RAD ≈ 0.0013` | 5385 m | dots still seen at **5.44 km** ("barely visible group if I look intently") |
| **salience** (existing `LOWRES`) | `0.003` today, **~0.0024 after recalibration** | 2333 m → ~2917 m | lone BMD-1 **2.8 km**, lone BTR-60 **3.1 km** |

A candidate is admitted when it is **resolvable AND salient**. A lone unit must clear the salience
threshold on its own. A member of a salient group only has to clear the resolution threshold — the
group supplies the salience that a single dot at that range does not have. This is the finding's own
framing turned into two constants instead of one, with no tuned curve anywhere.

**The model then predicts rungs it was not fitted to.** Infantry (`object_model` `size_m = 1.8`) has
a group-admitted ceiling of `1.8 / 0.0013 = 1385 m` — below the 1.91 km rung where the pilot reports
"detection + unit count (**no infantry**)" for the same twelve-unit complex. Infantry is not rescued
by its conspicuous neighbours, because it is not *resolvable* at that range, which is exactly what
the ladder shows. That row was never used to fit either constant.

**What the group contributes is cohesion and mass — not pattern, and not a count curve.** The
dataset contains exactly one group (twelve units, one 200 m line, one spacing). A regularity or
linearity term, or any monotone function of count, would be fitted to n=1 and is therefore
invention. The pilot's *"not in perfect line, I can see some geometry"* is spoken at **3.00 km**,
where he is describing what he can now **resolve**, not what made him notice the group at 5.44 km —
it is evidence about resolution, not about salience. So the group predicate is deliberately binary
and cheap:

- **cohesion** — neighbouring members are within `GROUP_COHESION_GAP_UNIT_WIDTHS` (proposed **10.0**)
  of their own mean apparent angular size, single-link. Dimensionless, in the same "unit widths"
  currency `clustering._extent_count` already uses, so it is automatically range- and size-correct
  with no new angular constant. Against the data: 200 m / 12 units ≈ 18 m spacing on a 7 m vehicle ≈
  **2.6 unit widths**, so 10.0 is ~4× slack.
- **mass** — at least `GROUP_MIN_MEMBERS` (proposed **3**) resolvable members. Two dots are a pair,
  not a formation. Stated assumption, one-line change.

Both are stated assumptions, not measurements, and are labelled as such in the code.

**Why not reuse `clustering.py`'s grouping.** Its predicate is the *opposite* end of the same axis:
two candidates merge when they are **not** angularly separable (separation under one mean unit
width). A salience group is made of members that *are* separable but still read as one structure —
a much wider angular scale. Same algorithm (single-link union-find over an angular predicate), a
different threshold, a different question. Reuse the pure helpers `angular_separation_rad` /
`angular_size_rad`, not the threshold.

---

### Affected Modules / Files

- `body-layer/src/perception/visibility.py` — add `RESOLUTION_ANGULAR_RADIUS_RAD`; add a
  `group_salient: bool = False` keyword to `check_visibility` and a matching parameter on
  `_achieved_tier`; select the effective presence angular radius from it in **both** the admission
  gate and the `presence_threshold_m` computation (these two must stay arithmetically identical —
  the module already carries an explicit comment saying so). `threshold_bound` gains the value
  `"group_resolution"`.
- `body-layer/src/perception/group_salience.py` — **new**, ~90 lines, pure. One public function:
  `group_salient_ids(candidates, observer, optic) -> frozenset[int]`. Imports
  `clustering.angular_separation_rad` / `angular_size_rad`, `object_model.profile_for`, and the two
  visibility constants. No state, no clock, no `belief` import.
- `body-layer/src/perception/clustering.py` — floor **(A)** must reference
  `RESOLUTION_ANGULAR_RADIUS_RAD`, not `LOWRES_ANGULAR_RADIUS_RAD` (see Risks — this is a real
  regression, not bookkeeping). Docstring updated accordingly.
- `body-layer/src/perception/naked_eye_source.py` — one call to `group_salient_ids` before the
  per-candidate loop; pass `group_salient=candidate.object_id in salient_ids` to `check_visibility`.
  Module docstring gains a numbered point.
- `body-layer/src/perception/detection_trace.py` — docstring only: document the new
  `threshold_bound` value.
- Tests: `body-layer/tests/test_group_salience.py` (new), plus edits to `test_visibility.py`,
  `test_clustering.py`, `test_vision_calibration.py`, `test_naked_eye_source.py`.
- `body-layer/ROADMAP.md` — milestone entry.

**Not touched:** `belief/speech.py`, `belief/crew_console.py`, `plans/callout-scheduling/`,
`perception/optics.py`, `object_model.distinctiveness_*`, `MEDRES`/`HIRES`.

---

### Where the set-ness lives (the boundary question)

`check_visibility` stays **per-candidate and pure**. It gains one more scalar input, exactly as
`distinctiveness` and `optic` already are — the *derivation* of that input is the caller's job, and
the caller already resolves a per-candidate `Gaze` this same way (`gaze_for`, one line above the
`check_visibility` call). Group membership is computed once per poll, over the whole candidate list,
in a new pure `perception` module. Nothing crosses the `perception`-must-not-import-`belief`
boundary; no state is introduced, so replay determinism is untouched (the function reads positions
and sizes only — no clock at all, not even sim time).

**The group pass runs on the un-gazed, un-LOS-filtered candidate set.** Two consequences, both
intentional and both following `gaze_for`'s established precedent that *a bypass clears one gate
only*:

- Group salience relaxes **the presence threshold only**. Cockpit mask, optic FOV, gaze and terrain
  LOS all still run per member and can still reject it. This is what keeps the term from being an
  omniscience back door.
- Groups exist independently of where Petrovich is looking, so a group straddling the 30° focus cone
  is **partially** detected — the members inside the cone are admitted, the members outside are
  rejected by the gaze gate, with no extra mechanism. That is the right answer, and it falls out.

On the brief's gaze question specifically: a 200 m group subtends 23° at 0.5 km and exceeds the
focus cone below ~0.4 km — but at those ranges **every member is individually salient anyway**
(7 m at 500 m is 0.014 rad, ~6× the salience threshold), so the group term is inert there. Group
salience only operates beyond ~2.9 km, where a 200 m group subtends under 4° and always fits inside
the cone. The interaction is structurally absent in the regime where the term does any work; the
design does not preclude revisiting it, because the group pass is a separate function with its own
inputs.

---

### Implementation Plan

**Stage 1 — the split, behaviour-preserving (mergeable alone).**
Add `RESOLUTION_ANGULAR_RADIUS_RAD = 0.0013` with the 5.44 km derivation in its docstring, flagged
as an **upper bound, not a measured boundary** (the same honesty `LOWRES` already carries — nothing
in the naked-eye column was observed beyond 5.44 km). Thread `group_salient: bool = False` through
`check_visibility` and `_achieved_tier`. No caller passes `True` yet, so the trace is byte-identical
to today — pin that with a regression test. Fix `clustering`'s floor (A) in the same stage, since it
is the constant's correctness condition, not a consequence of wiring.

**Stage 2 — `group_salience.py` and the wiring (the behaviour change).**
The seam is here: Stage 1 can merge and sit; Stage 2 is the merge that changes what Petrovich sees.
`group_salient_ids` filters to resolvable candidates, single-link unions by the cohesion predicate,
keeps clusters of `>= GROUP_MIN_MEMBERS`, returns their member ids. O(n²) over candidates — the same
cost `cluster_candidates` already pays on the same list.

**Stage 3 — validate against the ladder.**
Extend `test_vision_calibration.py` with the four naked-eye group rungs as ground truth: 5.44 km
admitted (marginal), 4.00 km admitted, 3.00 km admitted, and **infantry at 1.91 km still rejected**.
Add a lone-unit guard test: a single 7 m vehicle at 4 km is **not** admitted — the failure mode the
brief names explicitly. Assert `MEDRES`/`HIRES` behaviour is unchanged at 500 m / 250 m.

**Stage 4 — trace and docs.**
`threshold_bound = "group_resolution"` when the relaxed threshold was the binding term, so BL-9
traces show *why* a distant candidate was admitted. Roadmap entry.

---

### The recalibration that follows (explicitly not done here)

Once Stage 2 lands, `LOWRES_ANGULAR_RADIUS_RAD` should be refitted to **single-unit** truth —
BMD-1 2.8 km and BTR-60 3.1 km, a 1.20×/1.33× stretch on today's 2333 m, landing near **0.0024**
(2917 m for a 7 m vehicle). It must **not** absorb the group's reach: fitting it to the 4 km group
rung would put a lone vehicle in open desert at 4 km, which the pilot says is extremely hard to
notice, and would silently re-merge the two questions this plan just separated.

Deliberately a separate change: the T-72B row (2.17×) and the Tor row (1.30×) disagree with the
median, the S-300 rows are a known `object_model` profile-table bug rather than a calibration error,
and `MEDRES` is independently ~20% too generous (class ratio median 0.82) — that is its own pass
with its own evidence. Shipping Stage 1+2 with `LOWRES` unchanged is coherent and strictly better
than today: groups become roughly right, lone units stay conservatively short.

---

### Risks & Unknowns

- **`clustering`'s floor (A) breaks without the constant swap — concrete, not theoretical.** (A)'s
  slack-by-construction proof assumes the channel admits at `LOWRES`. Group-admitted candidates are
  admitted at `RESOLUTION`, which is **smaller**, so a group-admitted pair can satisfy
  `theta_sep * M >= RESOLUTION` while failing `>= LOWRES` — silently merging two genuinely separable
  contacts, the exact defect that module exists to prevent. Pointing (A) at `RESOLUTION` (the
  loosest threshold any admission path can use) restores the theorem for every path. Stage 1.
- **The 5.44 km anchor is one rung of one sortie, on one target.** `RESOLUTION` is a bound, not a
  measurement, and a longer ladder would push it down again — same caveat `LOWRES` has carried since
  2026-09-17. The 9.28 km "nothing" rung **cannot** be used to bound it from the other side: it is a
  different target (the S-300 complex) and sits near the ~10.4 km atmospheric limit, so it may be
  haze rather than acuity.
- **Counting and individuation will over-claim on newly-admitted distant groups.** At 4 km the
  twelve units are angularly *separable*, so `cluster_candidates` will emit twelve `OP_1UNIT`
  contacts where the pilot reports "a group, cannot tell how many". This is the same
  resolution-vs-salience gap one level up — counting is a salience limit, not a resolution one.
  **Stated assumption: accept it in this plan.** Twelve presence-tier dots is a defensible reading of
  *"line of tiny dots"*, and building a "cannot count" mechanism is a materially larger change
  (a new uncertainty state in `belief.cardinality`, which this plan is forbidden to reach into) for
  a wording improvement. Named as the natural follow-up.
- **Both group constants are assumptions.** `GROUP_COHESION_GAP_UNIT_WIDTHS = 10.0` and
  `GROUP_MIN_MEMBERS = 3` have one dataset behind the first and none behind the second. Both are
  one-line edits and neither can extend detection beyond `RESOLUTION`, which bounds the blast radius.
- **A member hidden behind terrain can still confer salience**, because the group pass runs before
  the LOS gate. Running LOS first would invert the module's deliberate cheap-before-expensive gate
  order. The hidden member is still rejected itself; only its contribution to the count and extent of
  the group leaks. Accepted.
- **Detection volume grows.** More admitted candidates at long range means more clustering work
  (O(n²)) and more emission-cap pressure per poll. `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` already caps
  emission at cluster granularity, so the user-visible effect should be bounded, but it is untested
  at the new envelope and should be watched on the next sortie.

---

### Second-Order Effect

This **unblocks the conditions milestone and narrows the callout work**: once presence is split into
resolution and salience, the deferred weather/light/vegetation term has an obvious and correct place
to attach — it degrades *salience* (would you notice it) without touching *resolution* (the optics of
the eye), which a single conflated constant could never express. It also **complicates** the deferred
9K113 sight slice slightly: the sight's presence multipliers were measured against the old conflated
threshold, so the sight slice will need to say which of the two the 3.55/5.81 figures scale.

---

### Decisions Requiring User Input

- **`GROUP_MIN_MEMBERS = 3`** — does a pair of vehicles read as a group? No data either way; 3 is the
  conservative choice and is a one-line change.
- **Shipping Stage 1+2 with `LOWRES` unrecalibrated** — leaves lone units conservatively short
  (2333 m vs 2.8–3.1 km observed) for one more merge. Proposed deliberately, so the group term can be
  validated without a simultaneous constant change confounding it, but it means the next sortie flies
  a knowingly-short lone-unit range.
