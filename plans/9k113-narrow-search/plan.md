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

### Goal

With `observ on`, make the 9K113 actually search with the narrow setting instead of only
inspecting already-detected contacts, give the idle sight a real aim that is always inside its
±60°/+20°/−15° field of regard (closing the F5 defect where the sight's magnification was applied
at whatever the head's o'clock scan happened to be pointing), and make a look through the sight use
whichever of wide/narrow already achieves the recognition gain it is for, rather than always
narrow.

### What's already built (read before assuming any of this is new work)

`BL-B64` (the perception entry) and `BL-B71` (attack-run guidance overrides) already shipped the
machinery this plan reuses: two `Optic` rows (`SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`,
`body-layer/src/perception/optics.py`), `within_field_of_regard` (already enforced at the *look
target selection* point — a 2026-09 security fix, `plans/9k113-sight/security.md` required fix 1),
`home_phase`/`SIGHTING` as a parameterised resting phase (`body-layer/src/belief/optic_policy.py`),
`advance_sight_aim`/`actual_aim_azimuth_deg` (the desired-vs-actual aim split, still an identity
pass-through pending the effector stage), and `_LADDER`/`least_capable_sufficient_optic`/
`guidance_request_for` (`BL-B71`, for attack-run guidance only). **F5's defect is a fresh gap in
code that already exists, not unbuilt functionality** — `_decide_sighting`'s own idle branch
(`optic_policy.py:1432-1447`) already says *"rest wide, pointed ahead"* in a comment and then does
not set an aim at all. §13 found and closed one instance of this invariant (look-target selection);
this plan closes two more (idle rest, and the guidance-override path), and adds search.

### Affected Modules / Files

- `body-layer/src/belief/optic_policy.py` — the bulk of the change:
  - `_decide_sighting`'s idle branch (no target worth a look) gains a real aim and, when a
    commanded sector is active and inside regard, an active narrow search sweep.
  - `_back_to_home` becomes aim-aware for `home_phase is SIGHTING` (preserve the sight's last aim
    rather than nulling it — this *is* "stays at last position").
  - `_apply_guidance`'s existing ladder-cap gains one more condition (never elevate to a sight
    optic over a decision with no aim).
  - New: a `sight_look_optic` helper (generalises `improvement_window_m`'s own pattern to wide-vs-
    narrow); `OpticState.look_optic` field; `search_pattern`'s new optional `max_half_width_deg`
    parameter; two new tunable constants (search band near/far).
- `body-layer/src/logger.py` — a new `_sight_search_sweep` function (sibling of the existing
  `_search_sweep`), imports for `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`, threading the new
  `sight_search` sequence into `decide_optic`.
- `body-layer/tests/test_optic_policy.py` — one pinned-bug test rewritten (it currently asserts the
  F5 defect), several range-sensitive assertions re-checked against the new wide-vs-narrow look
  selection, new tests for the idle-aim invariant, the search sweep, the out-of-regard deferral, and
  the guidance-override edge case.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`) for the
  two new tunables.
- Not touched: `BL-B83` (mission objective area in the idle-aim priority) stays deferred, no
  objective-area datum exists at runtime; nothing here builds toward it.

---

## What the settled direction requires (summary — the doc is authoritative)

From `docs/acceptance/2026-10-20-sortie-feedback.md`, F4/F5, "settled" section:

1. **Narrow carries the search**: sweeps at distance are narrow; wide is brief (orientation, or
   close range).
2. **Idle aim priority**: commanded scan sector → flight direction (default). Mission objective area
   is skipped (`BL-B83`, deferred — no objective datum at runtime).
3. **A commanded sector beyond ±60°** is scanned with eyes/binoculars; **the sight stays at its last
   position**, not re-aimed to the regard edge.
4. **A look uses the least capable optic that suffices**: naked eye < binoculars < sight wide <
   sight narrow. Today every sight look is narrow unconditionally — this question was specifically
   about wide-vs-narrow (*"should narrow also take over the close looks... or would wide be
   enough"*), not about dropping below wide to binoculars during an active sight dwell, which stays
   out of scope here.

---

## Implementation Plan

### Stage 1 — the idle sight always has an in-regard aim (closes F5, all three paths)

**Three places can hand out `optic=SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` with `look_azimuth_deg is
None`, and all three need fixing — not just the one F5's log happened to show.**

1. `_decide_sighting`'s idle branch (`chosen is None`, `optic_policy.py:1432-1447`). Fix: compute an
   idle aim instead of omitting one.
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
  set (the "last position" case), else `idle_aim` (computed by the caller from the commanded sector
  or the flight-direction default, see Stage 2) — always within regard by construction (see below).
- `_back_to_home`, when `state.home_phase is OpticPhase.SIGHTING`: **do not null
  `look_azimuth_deg`/`look_elevation_deg`** the way the `SCANNING`-home branch does — carry them
  through unchanged (this *is* "stays at last position," for free, once this one function stops
  erasing it), defaulting to `(0.0, 0.0)` (dead ahead) only if they were never set at all (e.g. the
  very first poll after "Observ on"). Returns `OpticDecision(optic=SIGHT_WIDE_OPTIC,
  look_azimuth_deg=<that>, look_elevation_deg=<that>)`. `home_phase is SCANNING` path: byte-for-byte
  unchanged.
- `_decide_sighting`'s idle branch: same aim logic (see Stage 2 for what the aim actually is when a
  commanded sector is involved).
- `_apply_guidance`: extend the existing condition at line 1850 —
  `(state.home_phase is not OpticPhase.SIGHTING or decision.look_azimuth_deg is None)` — so a sight
  tier is never granted over a decision that carries no aim, for whatever reason. This is the one
  change outside `_decide_sighting`/`_back_to_home`, and it is the general, structural form: it
  protects every future path that could reach this function with a bare decision, not just the
  glance-away case found by inspection.

**Why fix it at the choice point, not at `_apply_active_gaze`'s consumption side (the task's own
instruction).** `_apply_active_gaze` cannot tell "no aim because this optic is legitimately
unrestricted (`UNAIDED_OPTIC`)" from "no aim because the sight forgot to set one" — both look
identical from its side (`decision.look_azimuth_deg is None`). The invariant can only be enforced
where the choice is made.

**Required test**: one test exercising `decide()`/`_decide_without_guidance` across every
SIGHTING-reaching transition (idle rest, resume-from-interruption, resume-from-search,
guidance-override-during-glance-away) asserting: whenever `decision.optic in
(SIGHT_WIDE_OPTIC, SIGHT_NARROW_OPTIC)`, `decision.look_azimuth_deg is not None` and
`within_field_of_regard(decision.optic, decision.look_azimuth_deg, decision.look_elevation_deg or
0.0)`. This operationalises "must be impossible after this change" directly rather than trusting
the stage-by-stage reasoning above.

**Test impact, pinned bug:** `test_idle_sighting_rests_wide_with_nothing_worth_looking_at`
(`tests/test_optic_policy.py:1592`) currently asserts `decision.look_azimuth_deg is None` — that
*is* the defect, pinned. Rewrite to assert `decision.look_azimuth_deg == 0.0` (no commanded sector
in that test's fixture, so flight-direction default applies).

### Stage 2 — idle aim priority and the in-regard narrow search

**Priority, scope restricted to `scan_plan.commanded_sector` the same way `_search_sweep` already
is** (its own docstring: *"a bare o'clock hour or a converted compass-sector scan gets no binocular
search band... left for a later stage if wanted"*) — inherited, not a new limitation:

1. **Commanded sector, if its full span (`center ± half_width`) is entirely inside the sight's own
   `regard_azimuth_half_deg` (±60°)**: actively **search** that sector with **narrow**, not merely
   rest pointed at its centre. This is requirement 1 (*"narrow carries the search"*).
2. **No commanded sector** (or one that is `commanded_legs`-only, same scope restriction): **rest**
   wide, pointed at flight direction (`0.0, 0.0`) — the F5 fix's own default.
3. **Commanded sector whose span exceeds ±60°**: Stage 3.

**New function, `logger._sight_search_sweep` (sibling of the existing `_search_sweep`):**

```python
def _sight_search_sweep(
    scan_plan: ScanPlan, ownship: OwnshipState
) -> list[tuple[float, float]]:
    if scan_plan.commanded_sector is None:
        return []
    center_deg, half_width_deg = SECTOR_WEDGE_DEG[scan_plan.commanded_sector]
    regard = SIGHT_WIDE_OPTIC.regard_azimuth_half_deg or 0.0
    if abs(center_deg) + half_width_deg > regard:
        return []  # exceeds regard -- Stage 3 (binocular `search`) covers it instead
    fov_full_width_deg = (SIGHT_NARROW_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    return search_pattern(
        sector_half_width_deg=half_width_deg,
        near_m=SIGHT_SEARCH_NEAR_M,
        far_m=SIGHT_SEARCH_FAR_M,
        altitude_agl_m=max(ownship.alt_agl_m, 0.0),
        fov_full_width_deg=fov_full_width_deg,
        max_half_width_deg=regard,
    )
```

`search_pattern` gains an optional `max_half_width_deg: float =
MAX_SEARCH_SECTOR_HALF_WIDTH_DEG` parameter (default preserves the binocular caller unchanged — a
true no-op); the sight caller passes the sight's own `regard_azimuth_half_deg` (60.0), **a genuine
physical bound, not an invented UX cap the way the binocular 15° one is** (that one exists because
"there's no wide area binocular scan," a usability choice; the sight genuinely cannot be pointed
past ±60°). Filter the generated steps through `within_field_of_regard` defensively for the
elevation envelope too (at ordinary helicopter altitudes the computed depression is under 2°, well
inside −15°, so this should never actually drop a step — but geometry should not be trusted to keep
it that way at every altitude the aircraft might fly this at).

**Two new tunables** (`belief.optic_policy`, following the module's existing per-scalar pattern —
`SIGHT_MAX_DWELL_S`/`SIGHT_GLANCE_AWAY_S` are separate scalars, not a tuple — rather than
`_SEARCH_BAND_M`'s older, pre-`X-T26` plain-tuple shape):

- `SIGHT_SEARCH_NEAR_M` — default `5_647.0` (where `BINOCULAR_OPTIC`'s own presence reach ends for
  a mid-sized vehicle — the same "start where the previous tier's reach ends" convention
  `_SEARCH_BAND_M` already uses, even though nothing is actively covering that band with binoculars
  while OBSERV is on; flagged as a judgement call below, not a measurement).
- `SIGHT_SEARCH_FAR_M` — default `13_556.0` (`SIGHT_NARROW_OPTIC`'s own presence reach for a 7 m
  vehicle — `2333 × 5.81`, the same figure `plans/9k113-sight/plan.md` §17 already computed and
  verified).

Both `status="judgement"`, `lo`/`hi` bounds analogous to `SIGHT_MAX_DWELL_S`'s own (e.g.
`lo=2_000.0, hi=10_000.0` / `lo=8_000.0, hi=20_000.0`).

**Driving the sweep, inside `_decide_sighting` (reusing existing fields and constants, not new
ones):** entered from the idle branch exactly as the existing look-start does — via `replace(state,
...)`, never a fresh `OpticState(...)`, so `home_phase`/`hands_busy_until_sim`/`actual_aim_*`/
`guidance_optic*` all carry forward automatically (the same reason `_decide_sighting`'s own
docstring already gives for preferring `replace`). Continuation reuses `search_pattern_steps`/
`search_step_index` (already shared across phases) and `look_started_sim` (already the "current
narrower sub-activity's own clock, distinct from the whole dwell's `phase_started_sim`" — a search
sweep is exactly that kind of sub-activity, so this is a generalisation of the field's existing
contract, not a second meaning bolted on; update its docstring to say so explicitly rather than
leaving a reader to infer it). Distinguish "mid-search" from "mid-look" the same way the two states
are already distinguished elsewhere: `look_contact_id is None`. Step timing reuses `SEARCH_STEP_S`
(0.8 s — the existing binocular search's own per-step duration, and the right one here too: *"this
should be fast, not dwelling on any spot"* applies identically to a narrow search), **not**
`SIGHT_MAX_DWELL_S`-derived step timing the way the look-continuation computes its own steps — a
search has no envelope to finish inside a given dwell, a look does.

When the sweep's steps run out: clear `search_pattern_steps`/`look_started_sim` and fall through to
the idle branch again on the very next evaluation, which re-enters the sweep immediately if the
commanded sector is still active — the same re-entry shape `SCANNING`-at-home's own `SEARCHING`
already uses (nothing here invents a new "finished, now what" state).

**Mid-sweep interruption**: `_decide_sighting`'s own `if not sight_steady: return
_force_observ_off(...)` already runs first, before any of this — an unsteady poll during the search
forces OBSERV off entirely, same as during a look or idle rest. No separate steadiness gate needed;
the function's existing gate already covers every sub-state inside it.

### Stage 3 — commanded sector beyond ±60°: eyes/binoculars, sight parked

**Reuses the existing `OpticPhase.SEARCHING` machinery unchanged** (`optic_policy.py:1564-1579`,
entered today only from `SCANNING`-at-home) — the user's own words are literally "scanned with
eyes/binoculars," i.e. the mechanism that already exists for exactly that, not a sight-specific
variant.

**Entered from `_decide_sighting`'s idle branch** when `sight_search` (Stage 2) is empty **and** the
existing `search` sequence (the unconditional binocular sweep `_search_sweep` already computes for
*any* commanded sector, unchanged) is non-empty — i.e. a commanded sector exists but exceeds regard.
Transition via `replace(state, phase=OpticPhase.SEARCHING, phase_started_sim=now_sim,
search_pattern_steps=tuple(search), search_step_index=0, look_contact_id=None, look_started_sim=None,
pending_attempted_at_range_m={}, look_envelope_azimuth_deg=None, look_envelope_half_width_deg=None)`
— **deliberately omitting `look_azimuth_deg`/`look_elevation_deg` from this `replace()` call**,
leaving them exactly as they were. This *is* "the sight stays at its last position": those two
fields are what `_decide_sighting`'s own idle/look logic treats as the sight's remembered aim, and
simply not touching them while a different optic (binoculars) is active this dwell is the whole of
the mechanism — no new field, no explicit "parked position" tracked separately.

`OpticPhase.SEARCHING`'s own dispatch (`optic_policy.py:1564-1579`) is **unchanged** — it already
hardcodes `optic=BINOCULAR_OPTIC`, which is correct for both its existing caller (`SCANNING`-at-home)
and this new one, so no `search_optic` field is needed. Its `not steady` check uses the ordinary
binocular threshold, also correct — this interlude really is "use binoculars," gyro-tolerance is
irrelevant to it. When it exits (pattern exhausted, or unsteady), `_back_to_home` returns to
`_HOME_OPTIC[state.home_phase]` = `SIGHTING`, and per Stage 1's fix, resumes from the preserved
`look_azimuth_deg`/`look_elevation_deg` — not nulled, not re-derived, not clamped to the regard
edge.

**Judgement call, made rather than escalated (local, reversible — Decision Heuristics):** a
commanded sector is treated as **entirely** in-regard or entirely out-of-regard, never split. `left`/
`right` (center ±60°, half-width 30° — spans 30°–90°) and `full` (0°±90°) all straddle the ±60°
boundary in reality, and this design sends the *whole* sector to binoculars in those cases, buying
no narrow-sight coverage of the portion that would actually be reachable. Only `ahead` (0°±30°,
fully inside) gets the narrow treatment today. Reversible later (the two sweep-building functions
would just be called twice, over the in-regard and out-of-regard sub-spans, each feeding its own
optic) without any architectural change — not done now because the user's own two-case framing
("within ±60°" / "beyond ±60°") does not ask for a third, split case, and simplification is
explicitly authorised project-wide for this feature area (`docs/acceptance/
2026-10-15-9k113-sight-direction.md` §4: *"simplification is expected"*).

### Stage 4 — looks use the least capable optic that suffices (wide vs. narrow)

**Not a reuse of `least_capable_sufficient_optic`/`_LADDER` (`BL-B71`)** — that function answers "can
this instrument *see* the target at all" (a presence-tier threshold), which is a weaker bar than
"does this instrument deliver the *specific* recognition gain this look exists for" (the next
classification tier `can_still_improve`/`is_worth_a_look` already computed to decide the look was
worth starting). Plugging the ladder function in directly would pick wide for targets that clear
wide's presence threshold but not its class/type threshold — the wrong answer, silently, since
nothing would fail loudly. `least_capable_sufficient_optic`'s own docstring already states this
distinction for its own reason not to generalise `improvement_window_m`; the same reasoning applies
in the other direction here.

**Instead, generalise `improvement_window_m`'s own pattern** (same `profile_for`/
`apparent_extent_m`/`distinctiveness_of`/`tier_ranges` calls, substituting `SIGHT_WIDE_OPTIC`/
`SIGHT_NARROW_OPTIC` for `UNAIDED_OPTIC`/`BINOCULAR_OPTIC`):

```python
def sight_look_optic(target: LookTarget) -> Optic:
    """Which of the sight's two settings already delivers the recognition
    gain this look is for -- the same question `improvement_window_m` asks
    of binoculars vs. the naked eye, asked here of narrow vs. wide
    (direction, 2026-10-20: "use least capable optic that suffices").
    Scoped to wide/narrow only -- the settled question was specifically
    about the sight's own two settings, not about dropping below wide to
    binoculars during an active sight dwell."""
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

(`target.current_level == "type"` never reaches here — `can_still_improve` already excludes it from
`worth_looking`, same precondition `improvement_window_m` relies on.)

**New field, `OpticState.look_optic: Optic = SIGHT_NARROW_OPTIC`** — default preserves the old
hardcoded behaviour for any pre-existing caller/test that never threads it (true no-op). Set once,
at look-start, to `sight_look_optic(chosen)`; **read, not recomputed, at look-continuation** — a
look's optic must not flip-flop mid-sweep if the contact's range happens to cross the wide/narrow
threshold between polls (continuation only steps through the pre-built sweep, it does not
re-evaluate `chosen`). Both the look-start `OpticDecision` (`optic_policy.py:1489-1496`) and the
look-continuation `OpticDecision` (`optic_policy.py:1399-1411`, currently both hardcode
`SIGHT_NARROW_OPTIC`) read `state.look_optic`/the freshly-computed value instead. The sweep's own
`fov_full_width_deg` (`optic_policy.py:1461`) uses `look_optic.fov_half_angle_deg` instead of
`SIGHT_NARROW_OPTIC`'s — **`regard_optic=SIGHT_WIDE_OPTIC` stays unchanged** for the regard clamp
(both sight optics share one identical field of regard, per the existing comment at that call site;
only the FOV differs by setting).

**Test impact, range-sensitive:** `_target()`'s default (`range_m=1_000.0`, `object_type="T-72"`,
`current_level="presence"`) is well inside `SIGHT_WIDE_OPTIC`'s own class-tier threshold once this
lands (wide's `class_range_mult` is double binoculars', and binoculars' own class threshold for this
profile is 1750 m per `improvement_window_m`'s docstring — wide's is roughly double that). Several
existing tests (`test_a_worthwhile_target_is_picked_immediately_no_scan_boundary`,
`test_the_look_continues_on_the_next_poll`, `test_a_resolved_look_commits_and_immediately_picks_the_
next_target`) currently assert `decision.optic is SIGHT_NARROW_OPTIC` unconditionally for this
target and **will need re-checking against the new wide-vs-narrow selection** — either their
fixture's range moves beyond wide's own threshold (if the test's intent is "narrow is in use"), or
the assertion changes to `SIGHT_WIDE_OPTIC` (if the test's intent is just "a look started/
continued"). Add a new, explicit pair of tests: one target close enough that wide suffices, one far
enough that narrow is needed, both asserting `optic_policy.sight_look_optic` directly and through
`decide()`.

---

## Co-moving Fields

Trigger: a phase/mode state machine (`OpticState.phase`/`home_phase`) with more than one co-moving
field, at least one pilot-written (`home_phase`, via "Observ on"/"Observ off") and at least one
internally decided (`phase`, `look_azimuth_deg`/`look_elevation_deg`, `look_optic`). Built by
grepping every construction site (`OpticState(` ×2, `replace(state` × many — see the list in the
opening research), not by enumerating transitions from the narrative above.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `look_azimuth_deg`/`look_elevation_deg` | internal (`decide()`'s dispatch) | `_back_to_home`, `home_phase is SCANNING` | both `None` (unchanged — `UNAIDED_OPTIC` is unrestricted, free-scans) |
| `look_azimuth_deg`/`look_elevation_deg` | internal | `_back_to_home`, `home_phase is SIGHTING` | **both non-`None`** — preserved from before the transition, or `(0.0, 0.0)` if never set; **never nulled** (this is "stays at last position") |
| `look_azimuth_deg`/`look_elevation_deg` | internal | `_decide_sighting` idle branch, no commanded sector | `(0.0, 0.0)` |
| `look_azimuth_deg`/`look_elevation_deg` | internal | `_decide_sighting` idle branch, in-regard commanded sector | the sweep's current step (narrow search) |
| `look_azimuth_deg`/`look_elevation_deg` | internal | `_decide_sighting` idle branch, out-of-regard commanded sector → `SEARCHING` | **untouched by this transition** (omitted from the `replace()` call — this is the "stays at last position" mechanism itself, not a side-effect to verify after the fact) |
| `decision.optic` | internal (`_apply_guidance`, `BL-B71`) | guidance request elevates to a sight tier | **requires** `decision.look_azimuth_deg is not None` on the decision it is overriding — enforced by the extended cap condition (Stage 1), not merely hoped for |
| `look_optic` | internal | look starts (`chosen is not None`) | set to `sight_look_optic(chosen)` |
| `look_optic` | internal | look continues | **read, not recomputed** — must not flip wide/narrow mid-sweep from a later poll's range |
| `look_optic` | internal | look ends/interrupted | irrelevant (default `SIGHT_NARROW_OPTIC` is harmless — never read outside an active look) |
| `home_phase` | external (pilot "Observ on"/"Observ off", `logger.py`'s poll loop) | either direction | every phase-dispatch branch re-checks it, same discipline `_decide_sighting`'s own `state.home_phase is not OpticPhase.SIGHTING` guard already established for the look path — Stage 1–3's new branches inherit this by construction (they all live inside `_decide_sighting`, which already carries that guard at its own entry) |

---

### Risks & Unknowns

- **`SIGHT_SEARCH_NEAR_M`/`SIGHT_SEARCH_FAR_M` are judgement calls, not measurements** — like every
  perception constant before its first sortie. The specific judgement worth flagging: the near bound
  (5,647 m, "where binoculars would run out") assumes a continuity with the binocular band's own
  reasoning, even though binoculars are not actually covering that band while OBSERV is on (the
  brief naked-eye glance-away does not run a search sweep, by design — §9's "the naked eye is the
  interruption"). A gap between roughly 2,333 m (naked eye's own reach) and 5,647 m may go
  unsearched by anything while OBSERV is on, for however long the dwell lasts. Not fixed here —
  flagged as a real, accepted gap rather than silently assumed away.
- **The whole-sector in/out-of-regard simplification** (Stage 3) drops narrow coverage of the
  ±60°-and-under portion of `left`/`right`/`full` commanded sectors. Stated as a judgement call
  above, not re-litigated here.
- **`_decide_sighting` is already the most behaviour-critical function in the belief layer**
  (`plans/9k113-sight/plan.md` §16 said so for the `home_phase` refactor alone), and this plan adds
  a third sub-state to it (search, alongside look and idle-rest) without adding a new phase enum
  value. Pinned-behaviour tests for the `home_phase is SCANNING` path (unaffected by any of this)
  are cheap insurance that the refactor really is additive.
- **`_apply_guidance`'s extended cap condition is the one change outside `_decide_sighting`/
  `_back_to_home`**, and it is also the only change this plan makes to a function `BL-B71`'s own
  review already flagged as carrying one known, accepted narrow gap (the first-grant hands-busy
  overcharge, `optic_policy.py:1879-1888`) — worth a second, careful read since this function is
  evidently a recurring source of one-case-at-a-time gaps, not a one-off.
- **Mechanism and calibration should not share a commit** (body-layer invariant) — the two new
  tunables (Stage 2) and the field-of-regard-reuse mechanism (Stage 2/3) are a natural pairing to
  keep as separate commits during implementation.

### Second-order effect

Closes the remaining scope of `BL-B64`'s own "aim the sight correctly" obligation that the earlier
security fix only partly closed (target selection, not idle rest or the guidance-override path) —
so the next 9K113 entry to actually need a clean idle-aim contract, `BL-B66` (effectors, when it
lands), inherits a `look_azimuth_deg`/`look_elevation_deg` pair that is *always* populated and
in-regard whenever a sight optic is assigned, which is exactly the precondition a real slew
controller needs (it always has somewhere to converge toward, never a `None` to special-case). It
also gives `sight_look_optic` a second consumer worth watching for: if the ATGM run (`BL-B67`,
not yet planned) ever needs "which sight setting is currently resolving the guided target," this is
the function to extend rather than duplicate — note it stops at wide/narrow by design (see Stage 4),
so a future caller needing the full eye→binocular→wide→narrow ladder still wants
`least_capable_sufficient_optic`, not this.

---

### Decisions Requiring User Input

None blocking. One judgement call was made rather than escalated (Stage 3's whole-sector
simplification) because it is local and reversible per the project's own escalation heuristics —
flagged above and in Risks, not silently assumed.
