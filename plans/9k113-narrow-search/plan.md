# 9K113 narrow search, idle aim, least-capable-optic looks

> **Branch note.** This plan was written in a worktree whose base had diverged from
> `feature/9k113-narrow-search` (unrelated `main`-side commits — BL-15 acceptance, notes split,
> RUN.md — landed on each side independently; neither is an ancestor of the other). A `git
> merge --ff-only` was not possible. The two input documents this plan depends on
> (`docs/acceptance/2026-10-20-sortie-feedback.md`, `body-layer/ROADMAP/BL-B83.md`) were read via
> `git show feature/9k113-narrow-search:<path>` instead — a snapshot read, not a merge. This file
> itself was written and committed on this worktree's own branch
> (`worktree-agent-ac8359307ef16512f`); the harvest step needs a real merge (or a rebase/cherry-pick)
> onto `feature/9k113-narrow-search` rather than the usual fast-forward. Flagged for the
> coordinator/user, not resolved here.

> **Amendment, 2026-10-20 (architect pass, same day).** Three user decisions
> (`docs/acceptance/2026-10-20-sortie-feedback.md`, "F4/F5 — plan amendments") revise Stages 2–4
> below. Summary of what changed and why:
>
> 1. **Split straddling sectors** (was: Stage 3's whole-sector in/out judgement call, now removed).
>    A commanded sector that straddles ±60° is split into an in-regard sub-span (sight) and
>    out-of-regard sub-span(s) (binoculars), computed geometrically rather than judged
>    sector-by-sector.
> 2. **Default search is active, not idle rest**, and uses both sight settings: with no commanded
>    sector, the sight sweeps a synthesized full-regard sector centred on flight direction, wide
>    then narrow — not a fixed stare. This, plus requirement 3 below, turned out to need the same
>    mechanism as the split, so Stages 2 and 3 are now one unified three-leg search cycle
>    (wide → narrow → binocular-excursion-if-applicable) rather than two separate stages.
> 3. **The near band (2.3–5.6 km) is searched too**, by the sight's own wide setting — closing the
>    "accepted gap" the first version of this plan flagged. Narrow now only ever covers the far
>    band (5.6–13.6 km); wide covers the near band and serves as a quick orientation pass before
>    narrow's slower one, directly realising the user's "wide is for orientation to know where to
>    point the narrow, or for close distance."
>
> A fourth, independent fix is added to Stage 4 (not requested verbatim, but the concrete place
> "prefer sight-wide over binoculars" already binds in the shipped code): `_apply_guidance`'s
> existing down-cap (sight tier → binoculars when not `SIGHTING`) gains a symmetric up-cap
> (binoculars → sight-wide when `SIGHTING`). Flagged as a Decision Requiring User Input, not
> silently folded in as settled, because it touches a flight-tested, already-once-reviewed function
> and its "quick look" carve-out cannot yet be built on real numbers (see that stage).
>
> **A pre-existing defect was found while designing the split, not introduced by it**: `logger.
> _search_sweep` discards the commanded sector's own centre entirely (`search_pattern` had no
> centre parameter at all before this amendment) — so today, the *existing*, shipped binocular
> search for `left`/`right`/`full` sectors sweeps around 0° (dead ahead) regardless of which sector
> was commanded. This plan fixes it only at the new call sites it adds (`search_pattern` gains a
> `center_azimuth_deg` parameter, default `0.0`, a true no-op for the untouched existing caller).
> `_search_sweep`'s own `SCANNING`-at-home caller is deliberately left exactly as it is — out of
> this plan's scope — and the finding is carried into Risks with a recommendation to file it as its
> own backlog item.

### Goal

With `observ on`, make the 9K113 actually search with both its settings instead of only inspecting
already-detected contacts — wide as a quick orientation pass and the near-band search, narrow as
the far-band search — give the idle sight a real aim that is always inside its ±60°/+20°/−15°
field of regard (closing the F5 defect), split a commanded sector that straddles that boundary
between the sight (in-regard) and eyes/binoculars (out-of-regard) rather than routing it whole to
one or the other, and make a look through the sight — and, within regard, a guidance grant during
an attack run — use whichever instrument already achieves the recognition gain it is for, rather
than always narrow or ever falling back to binoculars when the sight can reach the target.

### What's already built (read before assuming any of this is new work)

`BL-B64` (the perception entry) and `BL-B71` (attack-run guidance overrides) already shipped the
machinery this plan reuses: two `Optic` rows (`SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`,
`body-layer/src/perception/optics.py`), `within_field_of_regard` (already enforced at the *look
target selection* point — a 2026-09 security fix, `plans/9k113-sight/security.md` required fix 1),
`home_phase`/`SIGHTING` as a parameterised resting phase (`body-layer/src/belief/optic_policy.py`),
`advance_sight_aim`/`actual_aim_azimuth_deg` (the desired-vs-actual aim split, still an identity
pass-through pending the effector stage — **this remains true after the amendment and is why
Stage 4's "quick look" carve-out cannot be built yet, see below**), and `_LADDER`/
`least_capable_sufficient_optic`/`guidance_request_for` (`BL-B71`, for attack-run guidance only).
**F5's defect is a fresh gap in code that already exists, not unbuilt functionality** —
`_decide_sighting`'s own idle branch (`optic_policy.py:1432-1447`) already says *"rest wide,
pointed ahead"* in a comment and then does not set an aim at all. §13 found and closed one instance
of this invariant (look-target selection); this plan closes two more (idle rest, and the
guidance-override path), and adds search.

Also load-bearing for the amendment: `logger._search_sweep`/`belief.optic_policy.search_pattern`
(the existing binocular search sweep, `_SEARCH_BAND_M = (2_333.0, 5_647.0)`), `perception.gaze.
SECTOR_WEDGE_DEG` (`{"ahead": (0.0, 30.0), "left": (-60.0, 30.0), "right": (60.0, 30.0), "full":
(0.0, 90.0)}` — the four commanded sectors' own `(center_deg, half_width_deg)`), and `belief.
attack_run.decide`'s unconditional `guidance_request_for(..., floor=UNAIDED_OPTIC,
ceiling=SIGHT_NARROW_OPTIC)` call, which has no `home_phase` awareness at all — `_apply_guidance`
is the *only* place in the codebase where `home_phase` and a guidance-ladder result meet, which is
why Stage 4's new fix lives there and nowhere else.

### Affected Modules / Files

- `body-layer/src/belief/optic_policy.py` — the bulk of the change:
  - `_decide_sighting`'s idle branch (no target worth a look) gains a real aim and an active
    three-leg search cycle (wide / narrow / binocular-excursion) instead of resting.
  - `_back_to_home` becomes aim-aware for `home_phase is SIGHTING` (preserve the sight's last aim
    rather than nulling it — unchanged from the original plan, still "stays at last position").
  - `_apply_guidance`'s existing ladder-cap gains **two** more conditions: never elevate to a sight
    optic over a decision with no aim (unchanged from the original plan, Stage 1), and never leave
    a guidance grant on binoculars while `home_phase is SIGHTING` (new, Stage 4).
  - New: `OpticState.sight_search_leg: Literal["wide", "narrow", "binocular"] = "wide"` (new
    co-moving field, see table below); `OpticState.look_optic` field (unchanged from the original
    plan); `search_pattern`'s two new optional parameters, `center_azimuth_deg: float = 0.0` and
    `max_half_width_deg: float = MAX_SEARCH_SECTOR_HALF_WIDTH_DEG`; three tunable constants
    (search band near/mid/far, was two).
- `body-layer/src/logger.py`:
  - A new `_split_sector_by_regard` helper (geometry: splits a `(center, half_width)` sector by a
    symmetric regard bound into an in-regard sub-span and zero/one/two out-of-regard sub-spans).
  - A new `_commanded_or_default_sector` helper (the priority rule: commanded sector if one exists,
    else a synthesized full-regard sector centred on flight direction — amendment 2).
  - New sibling sweep-builders (replacing the original plan's single `_sight_search_sweep`):
    `_sight_in_regard_sweep` (parameterised by optic and near/far band, used for both the wide and
    narrow legs) and `_sight_out_of_regard_sweep` (binocular, concatenating up to two remainder
    pieces for `full`).
  - Three new sequences (`sight_wide_search`, `sight_narrow_search`, `sight_binocular_search`)
    threaded into `decide_optic` alongside the existing, unchanged `search` parameter.
- `body-layer/tests/test_optic_policy.py` — one pinned-bug test rewritten (currently asserts the F5
  defect; now asserts the invariant generally, and separately asserts the default search's first
  step is *some* in-regard step of the wide leg, not a fixed `(0.0, 0.0)` — see Stage 3's Test
  impact note), several range-sensitive assertions re-checked against the new wide-vs-narrow look
  selection, new tests for the idle-aim invariant, the three-leg cycle, the split-sector case, the
  default-sector case, and the guidance-override edge cases (both directions of the cap).
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`) for the
  three tunables (was two).
- Not touched: `BL-B83` (mission objective area in the idle-aim priority) stays deferred, no
  objective-area datum exists at runtime; nothing here builds toward it. `BL-B74` (SAM launch
  smoke) stays in the backlog, reconfirmed by the user's own 2026-10-20 follow-up ("later, leave").

---

## What the settled direction requires (summary — the two acceptance docs are authoritative)

From `docs/acceptance/2026-10-20-sortie-feedback.md`, F4/F5 "settled" and "plan amendments"
sections, read together:

1. **Narrow carries the far search; wide carries the near search and orientation**: sweeps past
   5.6 km are narrow; sweeps from 2.3–5.6 km, and a quick first pass before narrow, are wide.
2. **Idle aim priority**: commanded scan sector → flight direction (default, now an active
   wide+narrow sweep of the sight's own full field of regard, not a stare). Mission objective area
   is skipped (`BL-B83`, deferred — no objective datum at runtime).
3. **A commanded sector that straddles ±60° is split**, not routed whole to one side: its in-regard
   portion is searched by the sight (wide then narrow, same as above); its out-of-regard portion is
   searched by binoculars (unchanged band, 2.3–5.6 km); **the sight stays at its last position**
   while the binocular excursion runs, exactly as the original (now-superseded) whole-sector design
   already did for the fully-out case.
4. **A look uses the least capable optic that suffices**: naked eye < binoculars < sight wide <
   sight narrow. Today every sight look is narrow unconditionally — this question was specifically
   about wide-vs-narrow (*"should narrow also take over the close looks... or would wide be
   enough"*), not about dropping below wide to binoculars during an active sight dwell — **except
   that the amendment's own wording ("if OBSERV is ON, and looking at there 9K113 can, prefer wide
   over binoculars... binoculars are good for quick look") now explicitly reaches into exactly that
   previously-out-of-scope case, for the one place in the shipped code where it currently binds: the
   attack-run guidance ladder (Stage 4).**

---

## Implementation Plan

### Stage 1 — the idle sight always has an in-regard aim (closes F5, all three paths)

**Unchanged from the original plan — still holds exactly as written.**

**Three places can hand out `optic=SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` with `look_azimuth_deg is
None`, and all three need fixing — not just the one F5's log happened to show.**

1. `_decide_sighting`'s idle branch (`chosen is None`, `optic_policy.py:1432-1447`). Fix: compute an
   idle aim instead of omitting one. (Stage 3, below, now supplies that aim as the current step of
   whichever search leg is active, rather than a fixed rest point — the invariant this stage
   establishes does not care which.)
2. `_back_to_home` (`optic_policy.py:1165-1206`) and the first-poll branch
   (`_decide_without_guidance`, `optic_policy.py:1545-1554`) both return
   `OpticDecision(optic=_HOME_OPTIC[state.home_phase])` with no aim — correct when
   `home_phase is SCANNING` (`UNAIDED_OPTIC` has no field of regard, free-scans via the ordinary
   scan plan), **wrong when `home_phase is SIGHTING`**. This is the path the *resume-from-
   interruption* case hits every time (an unsteady poll, `lower_binoculars`, a completed
   GLASSING/SEARCHING look, `_force_observ_off`) — one poll of bare-sight-no-aim on every one of
   those transitions, today.
3. **`_apply_guidance` (`BL-B71`) can elevate `decision.optic` to a sight tier without ever touching
   `decision.look_azimuth_deg`** (its own docstring: *"only ever changes `decision.optic` plus the
   two `guidance_*` fields... `look_azimuth_deg`... left exactly as the dispatch decided"*). Its
   existing cap (`optic_policy.py:1850-1854`, *"never escalate to a sight tier while
   `home_phase is not SIGHTING`"*) does not protect the one remaining case: `home_phase is SIGHTING`
   **but** `state.phase` is mid-glance-away (the brief scheduled naked-eye interruption,
   `_start_glance_away`), whose own decision is bare `OpticDecision(optic=UNAIDED_OPTIC)` — no aim,
   because `UNAIDED_OPTIC` never needs one. If an attack run concurrently requests sight-tier
   guidance during that glance, `_apply_guidance` would hand back `optic=SIGHT_NARROW_OPTIC` with
   the glance's own `look_azimuth_deg=None` untouched — the exact defect shape, through a fourth
   path this entry's own F5 report never exercised.

**Fix shape:**

- A small helper, e.g. `_sighting_idle_aim(state: OpticState, idle_aim: tuple[float, float]) ->
  tuple[float, float]`: returns `state.look_azimuth_deg`/`look_elevation_deg` if both are already
  set (the "last position" case), else `idle_aim` (computed by the caller — Stage 3 — from the
  commanded sector, split, or flight-direction default) — always within regard by construction.
- `_back_to_home`, when `state.home_phase is OpticPhase.SIGHTING`: **do not null
  `look_azimuth_deg`/`look_elevation_deg`** the way the `SCANNING`-home branch does — carry them
  through unchanged (this *is* "stays at last position," for free, once this one function stops
  erasing it), defaulting to `(0.0, 0.0)` (dead ahead) only if they were never set at all (e.g. the
  very first poll after "Observ on"). Returns `OpticDecision(optic=SIGHT_WIDE_OPTIC,
  look_azimuth_deg=<that>, look_elevation_deg=<that>)`. `home_phase is SCANNING` path: byte-for-byte
  unchanged.
- `_decide_sighting`'s idle branch: same aim logic (Stage 3 supplies the aim).
- `_apply_guidance`: extend the existing condition at line 1850 —
  `(state.home_phase is not OpticPhase.SIGHTING or decision.look_azimuth_deg is None)` — so a sight
  tier is never granted over a decision that carries no aim, for whatever reason.

**Required test**: one test exercising `decide()`/`_decide_without_guidance` across every
SIGHTING-reaching transition (idle rest, resume-from-interruption, resume-from-search,
guidance-override-during-glance-away) asserting: whenever `decision.optic in
(SIGHT_WIDE_OPTIC, SIGHT_NARROW_OPTIC)`, `decision.look_azimuth_deg is not None` and
`within_field_of_regard(decision.optic, decision.look_azimuth_deg, decision.look_elevation_deg or
0.0)`.

**Test impact, pinned bug:** `test_idle_sighting_rests_wide_with_nothing_worth_looking_at`
(`tests/test_optic_policy.py:1592`) currently asserts `decision.look_azimuth_deg is None` — that
*is* the defect, pinned. **Amended rewrite** (differs from the original plan, which expected a
fixed `(0.0, 0.0)`): with Stage 3's active default search, the idle branch no longer rests at a
single point at all — rewrite to assert `decision.look_azimuth_deg is not None` and
`within_field_of_regard(SIGHT_WIDE_OPTIC, decision.look_azimuth_deg, ...)`, and add a dedicated,
separate test asserting the default sweep's *first* step specifically (whatever `search_pattern`
actually computes for the default sector — not assumed to be exactly `0.0`, since a symmetric
±60° sweep at the wide FOV in general has no step exactly at centre; compute the expected value
from `search_pattern` directly in the test rather than hand-deriving it).

---

### Stage 2 — geometry: splitting a sector by regard, and the flight-direction default

**New, replaces the original plan's Stage 2 opening paragraph (the "scope restricted to
`scan_plan.commanded_sector`" framing still holds, inherited unchanged — a bare o'clock hour or
`commanded_legs`-only scan still gets no sight search, same limitation `_search_sweep` already
has).**

**`logger._split_sector_by_regard(center_deg, half_width_deg, regard_half_deg)`** — pure geometry,
no DCS/ownship dependency:

```python
def _split_sector_by_regard(
    center_deg: float, half_width_deg: float, regard_half_deg: float
) -> tuple[tuple[float, float] | None, list[tuple[float, float]]]:
    """Splits a sector's full span into its in-regard sub-span (a single
    (center, half_width), or None if the span and the regard do not
    overlap at all -- never actually reached by any of the four named
    `RelativeSector` values, every one of which straddles or contains
    azimuth 0) and zero, one, or two out-of-regard sub-spans (two only
    for `full`, whose span strictly contains the whole regard band)."""
    span_low, span_high = center_deg - half_width_deg, center_deg + half_width_deg
    in_low, in_high = max(span_low, -regard_half_deg), min(span_high, regard_half_deg)
    in_span = ((in_low + in_high) / 2.0, (in_high - in_low) / 2.0) if in_low < in_high else None
    out_spans: list[tuple[float, float]] = []
    if span_low < -regard_half_deg:
        lo, hi = span_low, -regard_half_deg
        out_spans.append(((lo + hi) / 2.0, (hi - lo) / 2.0))
    if span_high > regard_half_deg:
        lo, hi = regard_half_deg, span_high
        out_spans.append(((lo + hi) / 2.0, (hi - lo) / 2.0))
    return in_span, out_spans
```

Worked against `SECTOR_WEDGE_DEG` and `regard_half_deg=60.0`: `ahead` (0°,30°) → in-span (0°,30°),
no out-spans (fully inside, matches the original plan's one case that was already correct). `left`
(−60°,30°) → in-span (−45°,15°), one out-span (−75°,15°). `right` (60°,30°) → in-span (45°,15°), one
out-span (75°,15°). `full` (0°,90°) → in-span (0°,60°), **two** out-spans, (−75°,15°) and (75°,15°).
**Every one of the four named sectors straddles the boundary except `ahead`** — the original plan's
whole-sector simplification therefore routed `left`/`right`/`full` *entirely* to binoculars, never
giving the sight any of their in-regard portion; this is exactly the gap decision 1 closes.

**`logger._commanded_or_default_sector(scan_plan, regard_half_deg) -> tuple[float, float]`** — the
priority rule (requirement 2, "commanded sector → flight direction default"):

```python
def _commanded_or_default_sector(
    scan_plan: ScanPlan, regard_half_deg: float
) -> tuple[float, float]:
    if scan_plan.commanded_sector is not None:
        return SECTOR_WEDGE_DEG[scan_plan.commanded_sector]
    return 0.0, regard_half_deg
```

**A commanded sector is respected at its own commanded width** (`ahead`'s 30° stays 30°, never
widened); **only the no-commanded-sector default widens to the sight's full regard** — there is no
commanded width to respect there, and "a genuine physical bound, not an invented UX cap" (the
original plan's own justification for using `regard` rather than the binocular convention's 15°)
applies identically to the default case. This is the whole of requirement 2's "search along the
flight direction" — center `0.0`, same convention `_back_to_home`'s `(0.0, 0.0)` fallback already
uses for "dead ahead."

**A necessary, minimal fix found while designing this split, not a new feature**: neither
`search_pattern` nor its caller `_search_sweep` has ever taken a sector's *centre* — `search_pattern`
always produced azimuths symmetric about `0.0` regardless of which sector was requested, and
`_search_sweep` (`logger.py:960`, `_, half_width_deg = SECTOR_WEDGE_DEG[...]`) discards the centre
it unpacks. This was harmless by accident under the original (now-superseded) whole-sector design,
only because that design routed every sector that would have exposed it (`left`/`right`/`full`)
entirely to the *same* unsplit `_search_sweep` call it already used, and nobody had reason to
notice the centre was never applied. **It cannot stay harmless once sub-spans with genuinely
non-zero centres (−75°, −45°, 45°, 75°) are the whole point.** Fix: `search_pattern` gains
`center_azimuth_deg: float = 0.0` (added to every generated azimuth, default `0.0` a true no-op for
every existing caller including `_search_sweep`'s own unchanged, unsplit use at
`SCANNING`-at-home). **`_search_sweep` itself is not touched or fixed for its own existing caller**
— its `left`/`right`/`full` behaviour (searching around 0° regardless of sector) stays exactly as
shipped, a pre-existing defect outside this plan's scope; see Risks for the recommendation to file
it separately.

---

### Stage 3 — the search cycle: wide (near, orientation) → narrow (far) → binocular excursion (out-of-regard)

**Replaces the original plan's Stage 2 (`_sight_search_sweep`, narrow-only) and Stage 3 (whole-
sector in/out judgement call) together** — both turned out to be one mechanism once "default search
is active" and "split the sector" are both true: the sight now always has *something* to search
whenever `home_phase is SIGHTING` and nothing is worth a closer look, cycling through up to three
legs depending on what the (commanded-or-default) sector actually contains.

**Three new tunables** (`belief.optic_policy`, same per-scalar pattern as `SIGHT_MAX_DWELL_S`):

- `SIGHT_SEARCH_NEAR_M` — **changed from 5,647.0 to 2,333.0** (where the naked eye's own reach
  ends — `logger._SEARCH_BAND_M[0]`, reused by value, not import, since the two are independent
  tunables that happen to share a default). This is what closes requirement 3's "no unsearched near
  band": the wide leg now starts exactly where the naked eye's own reach stops, instead of where
  binoculars' reach stops.
- `SIGHT_SEARCH_MID_M` — **new**, default `5,647.0` (the *old* `SIGHT_SEARCH_NEAR_M` value —
  `_SEARCH_BAND_M[1]`, where binoculars' own reach ends). The wide/narrow boundary: wide covers
  `[NEAR, MID]` (binocular-equivalent range, "wide is... for close distance"), narrow covers
  `[MID, FAR]` ("narrow much more," "narrow carries the far search").
- `SIGHT_SEARCH_FAR_M` — **unchanged**, default `13,556.0` (`SIGHT_NARROW_OPTIC`'s own presence
  reach, `2333 × 5.81`, `plans/9k113-sight/plan.md` §17).

All three `status="judgement"`; `lo=1_000.0, hi=4_000.0` / `lo=4_000.0, hi=10_000.0` /
`lo=8_000.0, hi=20_000.0` respectively. **Known residual coupling, not caught by per-key bounds**
(the same shape as `belief.decay`'s own documented `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S`
coupling, `body-layer/CLAUDE.md` "Tuning"): nothing stops `NEAR` being tuned above `MID`, or `MID`
above `FAR`, independently within each one's own declared bounds. Flag in the tunable's own comment,
same convention.

**Sweep builders (`logger.py`, siblings of `_search_sweep`):**

```python
def _sight_in_regard_sweep(
    scan_plan: ScanPlan, ownship: OwnshipState, *, optic: Optic, near_m: float, far_m: float
) -> list[tuple[float, float]]:
    regard = SIGHT_WIDE_OPTIC.regard_azimuth_half_deg or 0.0
    center_deg, half_width_deg = _commanded_or_default_sector(scan_plan, regard)
    in_span, _ = _split_sector_by_regard(center_deg, half_width_deg, regard)
    if in_span is None:
        return []
    in_center_deg, in_half_width_deg = in_span
    fov_full_width_deg = (optic.fov_half_angle_deg or 0.0) * 2.0
    if fov_full_width_deg <= 0.0:
        return []
    return search_pattern(
        center_azimuth_deg=in_center_deg,
        sector_half_width_deg=in_half_width_deg,
        near_m=near_m,
        far_m=far_m,
        altitude_agl_m=max(ownship.alt_agl_m, 0.0),
        fov_full_width_deg=fov_full_width_deg,
        max_half_width_deg=regard,
    )


def _sight_out_of_regard_sweep(
    scan_plan: ScanPlan, ownship: OwnshipState
) -> list[tuple[float, float]]:
    """Binoculars, for the portion of a *commanded* sector the sight
    cannot reach -- empty for the no-commanded-sector default (whose
    synthesized sector is exactly the regard width, by construction, so
    it never has an out-of-regard remainder)."""
    if scan_plan.commanded_sector is None:
        return []
    regard = SIGHT_WIDE_OPTIC.regard_azimuth_half_deg or 0.0
    center_deg, half_width_deg = SECTOR_WEDGE_DEG[scan_plan.commanded_sector]
    _, out_spans = _split_sector_by_regard(center_deg, half_width_deg, regard)
    fov_full_width_deg = (BINOCULAR_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    if fov_full_width_deg <= 0.0:
        return []
    near_m, far_m = _SEARCH_BAND_M  # unchanged binocular band -- amendment 3 only touches the sight's own
    steps: list[tuple[float, float]] = []
    for out_center_deg, out_half_width_deg in out_spans:
        steps.extend(
            search_pattern(
                center_azimuth_deg=out_center_deg,
                sector_half_width_deg=out_half_width_deg,
                near_m=near_m,
                far_m=far_m,
                altitude_agl_m=max(ownship.alt_agl_m, 0.0),
                fov_full_width_deg=fov_full_width_deg,
            )
        )
    return steps
```

(`full`'s two out-spans are concatenated into one list — `OpticPhase.SEARCHING`'s existing dispatch
just steps through whatever sequence it is given, so two remainder pieces need no new state, only a
longer list.)

Three sequences computed every poll (mirroring `search`'s own existing unconditional computation,
`logger.py:639`) and threaded into `decide_optic`:

```python
sight_wide_search=_sight_in_regard_sweep(
    self.scan_plan, ownship, optic=SIGHT_WIDE_OPTIC,
    near_m=SIGHT_SEARCH_NEAR_M, far_m=SIGHT_SEARCH_MID_M,
),
sight_narrow_search=_sight_in_regard_sweep(
    self.scan_plan, ownship, optic=SIGHT_NARROW_OPTIC,
    near_m=SIGHT_SEARCH_MID_M, far_m=SIGHT_SEARCH_FAR_M,
),
sight_out_of_regard_search=_sight_out_of_regard_sweep(self.scan_plan, ownship),
```

**New field, `OpticState.sight_search_leg: Literal["wide", "narrow", "binocular"] = "wide"`** —
which leg of the cycle is current. Default `"wide"` is a true no-op for every pre-existing
caller/test: the field is read only inside `_decide_sighting`'s idle branch, never by
`SCANNING`/`GLASSING`/`SEARCHING`-at-home, which have their own, unrelated, single-optic sweeps.
**Not `look_optic`** (Stage 4) — a different question asked of a different activity (which *search*
leg is running, vs. which sight setting resolves *a specific contact already found*), kept as two
fields for the same reason `_LADDER`'s own module docstring already gives for not sharing one number
across two questions (`least_capable_sufficient_optic`'s docstring, quoted in the original Stage 4).

**Driving the cycle, inside `_decide_sighting`'s idle branch** (entered via `replace(state, ...)`,
never a fresh `OpticState(...)`, same reason as the original plan): pick the sequence named by
`state.sight_search_leg` (`sight_wide_search` / `sight_narrow_search` / `sight_out_of_regard_search`,
passed through from `logger.py` the same way `search` already is); if it is empty, advance to the
next leg in the cycle (`wide → narrow → binocular → wide`, skipping `binocular` whenever
`sight_out_of_regard_search` is empty — the default-sector and `ahead` cases, where the cycle is
just `wide ↔ narrow` forever) and retry, defensively, so a geometry edge case that empties one leg
can never stall the cycle. The `wide`/`narrow` legs set `optic=SIGHT_WIDE_OPTIC`/
`SIGHT_NARROW_OPTIC` with the current step's azimuth/elevation (same `look_contact_id is None`
distinguisher the original plan used to tell "mid-search" from "mid-look"); `look_started_sim`
is reused as the per-leg clock exactly as the original plan's Stage 2 already established for a
single search leg, generalised to whichever leg is current; step timing is `SEARCH_STEP_S` (0.8 s)
for every leg, unchanged reasoning.

**Entering the `binocular` leg**: transition via `replace(state, phase=OpticPhase.SEARCHING,
phase_started_sim=now_sim, search_pattern_steps=tuple(sight_out_of_regard_search),
search_step_index=0, look_contact_id=None, look_started_sim=None,
pending_attempted_at_range_m={}, look_envelope_azimuth_deg=None, look_envelope_half_width_deg=None,
sight_search_leg="wide")` — **deliberately omitting `look_azimuth_deg`/`look_elevation_deg`**,
leaving them exactly as they were (this *is* "the sight stays at its last position," unchanged
mechanism from the original plan's Stage 3), and **setting `sight_search_leg` back to `"wide"`
immediately at entry** rather than on exit, so that whenever this excursion ends (pattern exhausted,
or unsteady) and `_back_to_home` resumes `SIGHTING`, the very next idle-branch evaluation starts a
fresh `wide` pass without needing to distinguish "just returned from binoculars" from any other
resume. `OpticPhase.SEARCHING`'s own dispatch (`optic_policy.py:1564-1579`) is **unchanged** — still
hardcodes `BINOCULAR_OPTIC`, correct for this new caller too.

**Mid-sweep interruption**: unchanged from the original plan — `_decide_sighting`'s own
`if not sight_steady: return _force_observ_off(...)` already runs first, before any of this.

**Test impact:** every scenario in the original plan's Stage 2/3 test lists still applies, widened
to the three-leg shape: `ahead` and the no-commanded-sector default never enter the `binocular` leg
(assert the cycle alternates exactly `wide ↔ narrow`); `left`/`right`/`full` enter all three legs in
order over a long enough run; the out-of-regard sweep for `full` covers both remainder pieces
(assert azimuths appear on both sides of the regard boundary); `search_pattern`'s own new
`center_azimuth_deg` parameter gets a direct unit test (non-zero centre shifts every generated
azimuth by exactly that amount, `max_half_width_deg` still caps correctly around a non-zero centre).

---

### Stage 4 — looks and guidance grants use the least capable optic that suffices

**Part A (wide vs. narrow for an actual look at a resolved contact): unchanged from the original
plan.** Reproduced for completeness, since nothing here changes it:

**Not a reuse of `least_capable_sufficient_optic`/`_LADDER` (`BL-B71`)** — that function answers "can
this instrument *see* the target at all" (a presence-tier threshold), which is a weaker bar than
"does this instrument deliver the *specific* recognition gain this look exists for."

**Instead, generalise `improvement_window_m`'s own pattern** (same `profile_for`/
`apparent_extent_m`/`distinctiveness_of`/`tier_ranges` calls, substituting `SIGHT_WIDE_OPTIC`/
`SIGHT_NARROW_OPTIC` for `UNAIDED_OPTIC`/`BINOCULAR_OPTIC`):

```python
def sight_look_optic(target: LookTarget) -> Optic:
    profile = profile_for(target.object_type)
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)

    def next_tier_threshold_m(optic: Optic) -> float:
        _, class_m, type_m = tier_ranges(
            presence_size_m=profile.size_m,
            recognition_extent_m=extent,
            optic=optic,
            distinctiveness=distinctiveness,
        )
        return type_m if target.current_level == "class" else class_m

    if target.range_m <= next_tier_threshold_m(SIGHT_WIDE_OPTIC):
        return SIGHT_WIDE_OPTIC
    return SIGHT_NARROW_OPTIC
```

**New field, `OpticState.look_optic: Optic = SIGHT_NARROW_OPTIC`** — set once, at look-start, to
`sight_look_optic(chosen)`; read, not recomputed, at look-continuation. Both the look-start and
look-continuation `OpticDecision`s read `state.look_optic` instead of hardcoding
`SIGHT_NARROW_OPTIC`. `regard_optic=SIGHT_WIDE_OPTIC` stays unchanged for the regard clamp (both
sight optics share one field of regard).

**Test impact, range-sensitive**: unchanged from the original plan — several existing tests assert
`SIGHT_NARROW_OPTIC` unconditionally for a target now inside wide's own class-tier threshold and
need re-checking.

**Part B (sight-wide vs. binoculars during an attack-run guidance grant): new, from the
amendment.** The settled wording — *"if OBSERV is ON, and looking at there 9K113 can, prefer wide
over binoculars... binoculars are good for quick look because 9K113 slew takes time"* — names a
concrete preference between two optics that, in the shipped code, compete at exactly one place:
`belief.attack_run.decide`'s unconditional `guidance_request_for(..., floor=UNAIDED_OPTIC,
ceiling=SIGHT_NARROW_OPTIC)` call can return `BINOCULAR_OPTIC` (the ladder's "least capable that
still resolves the target" answer, for a close guidance target) regardless of `home_phase` — that
function has no `home_phase` awareness by design (its own docstring: *"tracking what the target's
geometry alone would ask for, independent of whether `optic_policy` chose to grant it"*).
`_apply_guidance` is the one place `home_phase` and a guidance-ladder result meet, and it already
has one asymmetric cap (sight tier → `BINOCULAR_OPTIC` when **not** `SIGHTING`); this adds the
symmetric one:

```python
effective_request = guidance_request
if (
    _LADDER.index(guidance_request) > _LADDER.index(BINOCULAR_OPTIC)
    and state.home_phase is not OpticPhase.SIGHTING
):
    effective_request = BINOCULAR_OPTIC
elif (
    guidance_request is BINOCULAR_OPTIC
    and state.home_phase is OpticPhase.SIGHTING
):
    effective_request = SIGHT_WIDE_OPTIC
```

**Scoped to the `BINOCULAR_OPTIC` rung only** — a request that resolves to `UNAIDED_OPTIC` (the
target is close enough that the naked eye already suffices) is left untouched; pointing the mount
at something resolvable with the naked eye is not what "prefer wide over binoculars" asked for, and
the user's own wording names binoculars specifically, not the naked eye.

**The "quick look" carve-out is *not* implemented — deferred, named here for when it can be.**
`advance_sight_aim` is still an identity pass-through (desired aim := actual aim, unconditionally;
"What's already built," above) — there is no real slew duration anywhere in the codebase to weigh
against a look's own expected duration, so "binoculars are good for quick look because slewing
takes time" has no number to act on yet. Building a placeholder constant now (e.g. a fixed "quick
look" duration threshold) would be worse than not building it: it would read as load-bearing in
`defaults.toml` while comparing against a quantity (slew time) that is unconditionally zero today,
so it could never actually fire — a tunable that looks live and is not. **The criterion for when
BL-B66 (the 9K113 effector entry, not yet planned) gives `advance_sight_aim` a real slew duration**:
prefer binoculars over sight-wide only when the time to slew from `actual_aim_azimuth_deg` to the
requested direction would exceed the expected useful duration of the look itself; otherwise prefer
sight-wide. Flagged in Decisions Requiring User Input and Second-order effect below, not built here.

**Test impact**: new tests, both directions of `_apply_guidance`'s cap — a `BINOCULAR_OPTIC` request
while `home_phase is SIGHTING` raised to `SIGHT_WIDE_OPTIC`; a sight-tier request while
`home_phase is not SIGHTING` still capped to `BINOCULAR_OPTIC` (existing, re-asserted unchanged); a
`UNAIDED_OPTIC` request while `SIGHTING` left untouched.

---

## Co-moving Fields

Trigger: a phase/mode state machine (`OpticState.phase`/`home_phase`) with more than one co-moving
field, at least one pilot-written (`home_phase`, via "Observ on"/"Observ off") and at least one
internally decided (`phase`, `look_azimuth_deg`/`look_elevation_deg`, `look_optic`,
`sight_search_leg` — new in this amendment). Built by grepping every construction site
(`OpticState(` ×2, `replace(state` × many).

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `look_azimuth_deg`/`look_elevation_deg` | internal (`decide()`'s dispatch) | `_back_to_home`, `home_phase is SCANNING` | both `None` (unchanged — `UNAIDED_OPTIC` is unrestricted, free-scans) |
| `look_azimuth_deg`/`look_elevation_deg` | internal | `_back_to_home`, `home_phase is SIGHTING` | **both non-`None`** — preserved from before the transition, or `(0.0, 0.0)` if never set; **never nulled** |
| `look_azimuth_deg`/`look_elevation_deg` | internal | `_decide_sighting` idle branch, `sight_search_leg` is `wide`/`narrow` | the current step of that leg's in-regard sweep (default sector or commanded sector's in-regard sub-span) |
| `look_azimuth_deg`/`look_elevation_deg` | internal | `_decide_sighting` idle branch → `sight_search_leg` is `binocular` → `SEARCHING` | **untouched by this transition** (omitted from the `replace()` call — the "stays at last position" mechanism itself) |
| `sight_search_leg` | internal | a leg's steps run out | advances `wide → narrow → binocular → wide`, **skipping `binocular` whenever `sight_out_of_regard_search` is empty** (the default-sector and `ahead` cases: cycle is `wide ↔ narrow` only) |
| `sight_search_leg` | internal | entry into `SEARCHING` (the `binocular` leg) | set to `"wide"` **immediately at entry**, not on exit — so any return path (steps exhausted, or `not steady`) resumes `SIGHTING` already primed for a fresh `wide` pass |
| `sight_search_leg` | internal | a look starts (`chosen is not None`) | untouched — irrelevant while a look is in progress; resumes the cycle from wherever it was once the look ends |
| `decision.optic` | internal (`_apply_guidance`, `BL-B71`) | guidance request elevates to a sight tier while `home_phase is not SIGHTING` | capped to `BINOCULAR_OPTIC` (unchanged, existing) |
| `decision.optic` | internal (`_apply_guidance`, new in this amendment) | guidance request is `BINOCULAR_OPTIC` while `home_phase is SIGHTING` | raised to `SIGHT_WIDE_OPTIC` |
| `decision.optic` | internal (`_apply_guidance`) | guidance request elevates to a sight tier | **requires** `decision.look_azimuth_deg is not None` on the decision it is overriding (Stage 1, unchanged) |
| `look_optic` | internal | look starts (`chosen is not None`) | set to `sight_look_optic(chosen)` |
| `look_optic` | internal | look continues | **read, not recomputed** |
| `look_optic` | internal | look ends/interrupted | irrelevant (default `SIGHT_NARROW_OPTIC` is harmless — never read outside an active look) |
| `home_phase` | external (pilot "Observ on"/"Observ off") | either direction | every phase-dispatch branch re-checks it, inherited by construction |

---

### Risks & Unknowns

- **`logger._search_sweep`'s own `SCANNING`-at-home caller still discards the commanded sector's
  centre** — a pre-existing defect found while designing the split (Stage 2), not introduced or
  fixed by this plan. Today's shipped, OBSERV-off binocular search for `left`/`right`/`full`
  sweeps around 0° (dead ahead) rather than around that sector's own centre. Recommend filing this
  as its own backlog item rather than folding a fix into this plan, since fixing it changes
  OBSERV-off behaviour this plan has no mandate to touch.
- **Tunable coupling, `SIGHT_SEARCH_NEAR_M < SIGHT_SEARCH_MID_M < SIGHT_SEARCH_FAR_M`** is not
  enforced by the per-key `lo`/`hi` bounds — the same shape as `belief.decay`'s documented
  `OBSERVED_WINDOW_S`/`POSITION_HALF_LIFE_S` coupling. Single-key tuning is safe; tuning more than
  one of the three together is not protected.
- **`_decide_sighting` now cycles four sub-states** (look, wide-search, narrow-search, and a
  binocular excursion reached via a full `OpticPhase.SEARCHING` detour) instead of the original
  plan's three (look, idle rest, search), still without a new phase enum value. Pinned-behaviour
  tests for the `home_phase is SCANNING` path (entirely unaffected by any of this) remain cheap
  insurance that the refactor really is additive.
- **`_apply_guidance` gains a second new condition in this one plan** (Stage 1's "no aim, no
  escalation" cap, and now Stage 4's "binoculars while SIGHTING, raise to wide" cap) on top of a
  function the original plan's own Risks already flagged as "a recurring source of one-case-at-a-
  time gaps, not a one-off" (`BL-B71`'s own review found the first-grant hands-busy overcharge
  there). Worth an especially careful second read of this function specifically, given two
  independent teams of eyes have now each found one gap in it.
- **The guidance-ladder "prefer wide over binoculars" fix changes attack-run behaviour that has
  already been flight-tested and reviewed** (`BL-B71`). A close guidance target that previously
  received `BINOCULAR_OPTIC` now receives `SIGHT_WIDE_OPTIC` unconditionally while `SIGHTING` —
  including the hands-busy charge semantics (`_apply_guidance`'s own "charge iff the optic actually
  in use is changing" logic), which may now fire differently for the same sequence of guidance
  requests than it did before. See Decisions Requiring User Input.
- **The "quick look" binocular carve-out is deferred, not built** — see Stage 4 Part B. The
  preference is unconditional until BL-B66 gives `advance_sight_aim` a real, nonzero slew duration.

### Second-order effect

Closes the remaining scope of `BL-B64`'s own "aim the sight correctly" obligation, as the original
plan already noted, and widens it: `BL-B66` (the 9K113 effector entry, when it lands) now inherits
not just an always-populated, always-in-regard `look_azimuth_deg`/`look_elevation_deg` pair, but
also `sight_search_leg` as a condition its real slew model needs to be aware of — a slew that is
interrupted by a leg transition (wide→narrow, or either→binocular-excursion) behaves differently
from one that completes undisturbed, and that is new surface this amendment adds for BL-B66 to
reckon with, not present before it. It also gives BL-B66 the one unresolved thread from Stage 4
Part B directly: the moment `advance_sight_aim` has a real slew duration, the "quick look" criterion
named there (slew time vs. look duration) becomes buildable, and should be built then rather than
guessed at now. `sight_look_optic` remains the function to extend for a future "which sight setting
is currently resolving the guided target" question (`BL-B67`, not yet planned); it still stops at
wide/narrow by design, so a caller needing the full eye→binocular→wide→narrow ladder still wants
`least_capable_sufficient_optic`, not this. Separately: the `_search_sweep` centre-dropping finding
(Risks) is worth its own backlog item regardless of this plan's fate, since it affects OBSERV-off
binocular search today, independent of anything built here.

---

### Decisions Requiring User Input

- **Confirm Stage 4 Part B's scope and timing.** The fix changes already-flight-tested attack-run
  behaviour (a close guidance target now gets sight-wide instead of binoculars, unconditionally,
  while `SIGHTING`) ahead of any real slew-time model to weigh it against. Is an unconditional
  preference acceptable to ship now, with the "quick look" exception arriving only once BL-B66
  lands real slew dynamics — or should this wait until BL-B66, so the preference and its exception
  land together?
- **Confirm the default (no-commanded-sector) search sector is the sight's full ±60° regard,
  centred on flight direction** (`_commanded_or_default_sector`'s synthesized sector), rather than
  some narrower default band. This is the one place this plan invents a width rather than reading
  one off a commanded sector or an existing constant.
- `BL-B83` (mission objective area) and `BL-B74` (SAM launch smoke) both stay deferred/backlog,
  reconfirmed by the user's own 2026-10-20 words ("skip for now" / "later, leave") — not re-raised
  as open questions, listed here only so a reader of this plan does not mistake their absence for
  an oversight.
