### Performance Review

Whole-feature pass (`BL-B71`, the least-capable-optic guidance ladder), immediately before DoD.
Scope: `7f5fd54d` (feature), `b72d4153`/`91b3c489` (two review-fix rounds), against the plan at
`plans/attack-run-sortie-fixes/plan.md` §6/§7.

Budget this sits inside (`body-layer/ROADMAP/BL-11.md`, measured not assumed): median realised
tick period 1.017-1.020 s against a 1 Hz target over three real sorties, **p90 1.8-4.9 s** —
the honest residual a new per-tick cost is judged against.

### Findings

#### `least_capable_sufficient_optic` / `guidance_request_for` — bounded, gated, not a tick-wide cost

- **Location:** `body-layer/src/belief/optic_policy.py:842-953` (`least_capable_sufficient_optic`,
  `guidance_request_for`), called from `belief/attack_run.py:722-732` (`decide`'s new
  `requested_optic` update).
- **Cost and how it was obtained (measured by code-reading, not profiling — no reachable path
  into `describe_contact` or any I/O to profile):**
  - **Call frequency: once per poll, at most, and only while an attack run is engaged.**
    `crew_console.drain_attack_run` (`crew_console.py:2295`) is the *only* call site
    (`logger.py:2006`), and it is a true no-op the instant `state is None` — confirmed by reading
    the early return. An attack run is pilot-initiated (`engage`) and bounded in duration, so this
    cost does not run across the whole flight the way `group_salient_ids` or `describe_position`
    do (`BL-11.md`'s own table) — it runs only while the pilot has actively committed to guiding
    on one target.
  - **Per call: at most 4 `tier_ranges` evaluations** (`_LADDER` has 4 rungs;
    `least_capable_sufficient_optic` loops it once, `guidance_request_for` calls the
    `presence_threshold_m` closure at most twice — once for `baseline`, once for `lower` on the
    de-escalation branch). `tier_ranges` (`perception/visibility.py:596`) is pure arithmetic —
    `min()`/division/no I/O, no allocation beyond small tuples — confirmed by reading its body.
  - **`profile_for` is `functools.cache`d** (`object_model.py:558`), measured elsewhere in this
    codebase at 0.04 us/call warm (`body-layer/research/2026-10-05-performance-review.md`).
    `apparent_extent_m`/`distinctiveness_of` are likewise pure, uncached but trivial (a handful of
    comparisons and a dict `.get`).
  - **No reach into `describe_contact`/`describe_position`** — the plans/group-collapse 63 ms-cold
    enrichment path this review was told to watch for. Confirmed: `optic_policy.py` and
    `attack_run.py`'s new code touch only `tier_ranges`, `profile_for`, `apparent_extent_m`,
    `distinctiveness_of` and `GeoPosition`/`range_m` — none of which calls into
    `belief.enrichment` or world-model's `query.describe`.
- **Does it reach the live tick:** only while an attack run is engaged, and even then it is O(4)
  pure arithmetic calls per poll, not per candidate and not per contact in the store.
- **Verdict:** **Measured-by-inspection clean.** No allocation, no I/O, no quadratic surface. The
  plan's own worry ("a per-candidate cost would be a different order of magnitude from a per-tick
  one") does not apply — this is per-*engaged-run*, strictly less frequent than per-tick.
- **Action:** none.

#### `_apply_guidance` / `decide`'s own dispatch — same allocation shape as before the feature

- **Location:** `body-layer/src/belief/optic_policy.py:1801-1901` (`_apply_guidance`),
  `optic_policy.py:1904-1941` (`decide`).
- **Cost:** one or two `dataclasses.replace()` calls per poll (`OpticState`, `OpticDecision`),
  each a small frozen-dataclass allocation — the same shape `decide` already had before this
  feature; `OpticState`/`OpticDecision` were already replaced every poll regardless of guidance.
  `_apply_guidance` adds no loop, no collection, and reads only scalar fields
  (`state.guidance_optic`, `state.guidance_optic_since_sim`, `state.home_phase`) plus one
  `_LADDER.index()` lookup (a 4-element tuple scan — O(1) in practice).
- **Does it reach the live tick:** every poll, but at identical allocation cost to the
  pre-existing per-poll `decide` call — this is not new allocation pressure, it is a few extra
  scalar comparisons inside work that was already happening.
- **Verdict:** clean. No action.

#### `_no_look_cause` with a varying `optic` — no memoisation to invalidate (measured by inspection)

- **Location:** `body-layer/src/belief/attack_run.py:450-538` (`_no_look_cause`, now parameterised
  on `optic` instead of a fixed `UNAIDED_OPTIC`).
- **What the task asked to check:** whether a varying optic breaks memoisation or constant-folding
  the fixed-optic form permitted.
- **Finding:** there was none to break. `tier_ranges` is a plain function call, never cached
  (confirmed by reading `visibility.py:596` — no `@cache`/`@lru_cache` decorator, no
  module-level memo dict), so passing a varying `optic` argument changes nothing about its cost
  profile; it was already recomputed from scratch on every call, fixed-optic or not. The only
  thing cached on this path is `profile_for(object_type)`, keyed on the object type string, which
  `optic` never touches.
- **Action:** none — the premise (an invalidated memoisation) does not hold.

#### Threading through `crew_console.drain_attack_run` / `logger.py`'s `runner.optic` read

- **Location:** `body-layer/src/belief/crew_console.py:2236-2251` (new `resolving_optic` keyword),
  `body-layer/src/logger.py:575-589` (`guidance_request=` kwarg to `decide_optic`),
  `logger.py:2006-2029` (`resolving_optic=runner.optic` to `drain_attack_run`).
- **Cost:** a single attribute read (`runner.optic`, `self.attack_run_state.requested_optic`) per
  poll, each already-computed this same poll by pre-existing code
  (`optic_decision.optic`/`AttackRunState.requested_optic`). No new computation, no new object
  construction beyond what the findings above already counted.
- **Action:** none.

#### `GUIDANCE_OPTIC_MIN_INTERVAL_S` / `HANDS_BUSY_DURATION_S` — a documented tuning footgun, not a tick-cost risk

- **Location:** `body-layer/config/defaults.toml:58-69`;
  `optic_policy.py:230-252` (declared bounds).
- **What was asked:** what the declared `lo`/`hi` extremes do to the tick and to the pilot's
  experience, given the module's own docstring says nothing enforces the coupling
  `GUIDANCE_OPTIC_MIN_INTERVAL_S > HANDS_BUSY_DURATION_S`.
- **Finding (reasoned, not measured — this requires a pilot-set `tuning.toml` combination that
  does not exist on this branch, so there is no running case to measure):** at the declared
  extremes (`GUIDANCE_OPTIC_MIN_INTERVAL_S = 1.0`, its `lo`; `HANDS_BUSY_DURATION_S = 5.0`, its
  `hi`), guard 3 would permit a fresh grant to re-charge the 1 s/5 s hands-busy suppression before
  the previous charge has finished — not a CPU-budget violation (the tick still runs at its
  ordinary ~O(1) cost), but an **availability** risk: observation could be suppressed on a large
  fraction of polls while an attack run is engaged, which the pilot would experience as Petrovich
  going silent/blind mid-run. This is a behavioural risk, not a performance one, and it is already
  named in the constant's own docstring as a known, accepted gap with "same posture as
  `belief.decay.py`'s own residual coupling note" — i.e. the project has already decided
  single-key tuning is the protected case and multi-key tuning is not, for this constant family
  generally.
- **Action:** **MONITOR**, not NOW. No code change requested — this is the same accepted residual
  the project already carries elsewhere, and raising it again here would be re-litigating a
  standing decision rather than finding something new. Worth a one-line mention to the user only
  if `GUIDANCE_OPTIC_MIN_INTERVAL_S` is ever tuned in practice.

### Verdict

**APPROVED.**

No per-candidate cost, no full-dataset iteration, no new I/O, no blocking call, and no reach into
the known-heavy `describe_contact`/`describe_position` paths. The entire feature's added
per-tick cost is bounded at O(4) pure-arithmetic calls, gated to run only while an attack run is
pilot-engaged — strictly rarer than the always-on 1 Hz tick cost this budget is measured against.
The one residual (`GUIDANCE_OPTIC_MIN_INTERVAL_S`/`HANDS_BUSY_DURATION_S` cross-key coupling) is a
pilot-experience footgun under a specific manual tuning combination, not a performance risk, and
is already documented as an accepted gap consistent with this project's existing posture on
single-key-vs-multi-key tuning bounds. Nothing here blocks DoD.
