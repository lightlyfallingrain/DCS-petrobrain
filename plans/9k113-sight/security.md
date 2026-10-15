## Security Deep Analysis: BL-B64 (9K113 sight perception)

Reviewed `feature/9k113-sight` @ `f3668e8eebc8d10e0ae6e067b739952516691680` (tip matched the
dispatch brief exactly; no merge needed, worktree created directly from the branch at
`/tmp/claude-wt-9k113-security`). Scope: whole feature, immediately before DoD — Stage 1 (two
sight `Optic` rows, field-of-regard fields, `BL-B55` per-optic sigma), Stage 1b, and Stage 2
(OBSERV on/off, the `SIGHTING` phase, the 1 s hands-busy suppression, the §7 directional
player-bubble cone, the optic-aware range cap, and the §14 `UNAIDED_OPTIC` FOV change) — all of
which is present on this branch and already Reviewer-approved across three passes.

### Dependency Status

No dependency change. Nothing in the diff touches `pyproject.toml`, imports a new third-party
package, or adds a new file-system/network surface — confirmed by `/extract-plan-deps` having
nothing to check (no new dependency claim in the plan) and by reading the diff itself: every new
import is intra-project (`tuning`, `perception.optics`, `perception.association`).

### Scope note

Single-user, LAN-only, single-player DCS. No new credential, no new network listener, no new
file write path. The question this review actually turns on, per the dispatch brief, is the
no-omniscience invariant: this feature is the largest single increase in what Petrovich can
perceive that the project has made (10 km → 20 km, plus a directional exemption to the filter
that used to bound him), so that is where the findings are.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/optic_policy.py` `_decide_sighting`/`choose_look`/`is_worth_a_look` (reused unmodified) | Field of regard (`Optic.regard_azimuth_half_deg`/`regard_elevation_up_deg`/`regard_elevation_down_deg`, ±60°/+20°/−15°) is carried as data on the two sight `Optic` rows but is never read as a bound anywhere in the selection path. | **Confirmed exploitable, not theoretical — demonstrated by direct execution** (see below). `_decide_sighting` can and does pick a look target at an azimuth the physical 9K113 cannot reach, and the resulting cone then admits candidates at up to 20 km in that direction. This is exactly the omniscience leak the dispatch brief names: "a sight aimed where it physically cannot aim." | **Required fix before merge.** |
| `body-layer/src/perception/optics.py:148-191` (docstring on `regard_*` fields) | Documentation drift | The docstring still reads "Nothing reads these yet — the field of regard is unenforced data until `BL-B64` Stage 2 (or `[[BL-B66]]`) adds the check." Stage 2 is exactly what has now landed on this branch, and no check was added — the comment describing an open gap shipped unchanged alongside the code that was supposed to close it. Not itself a vulnerability, but it is why three review passes did not catch the gap: the comment reads as "deferred, not yet due" rather than "missed." | Informational — fix the comment regardless of how the required fix above is resolved, so it stops asserting a future tense that is now false. |
| `body-layer/src/logger.py:977-994` (`sight_cone` construction) | Cone pointed at `actual_aim_azimuth_deg`, gated on `optic.regard_azimuth_half_deg is not None` | Confirmed correct for the specific thing it checks — the brief's concern #1 (actual vs. desired aim) and #2 (cone must not outlive the sight) are both solid; see "Verified clean" below. `regard_azimuth_half_deg is not None` is used only as "is this a pointable optic at all" (a boolean), never compared against the *value* of the chosen azimuth/elevation. | Covered by the required fix above — once `_decide_sighting` cannot select an out-of-regard target, this site needs no change. |
| `body-layer/src/belief/optic_policy.py` four new `tuning.real(...)` constants | Pilot-overridable config | `HANDS_BUSY_DURATION_S` (0.1–5.0), `SIGHT_STEADY_RATE_LIMIT_DEG_S` (12.0–90.0), `SIGHT_MAX_DWELL_S` (5.0–120.0), `SIGHT_GLANCE_AWAY_S` (1.0–15.0). None of these bound anything the no-omniscience invariant cares about — they govern workload/dwell timing, not reach, FOV, or field of regard. `SIGHT_STEADY_RATE_LIMIT_DEG_S`'s floor of 12.0 is exactly `STEADY_RATE_LIMIT_DEG_S`, which structurally prevents the sight being configured *less* tolerant of manoeuvring than binoculars — a correctly-chosen bound, not an oversight. The cone depth (20 km), FOV half-angles, and field of regard itself are plain `float` literals on `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`, not `tuning.real(...)` — not pilot-configurable at all. | False positive / no action — noted per the brief's request, no finding. |
| `body-layer/src/perception/visibility.py` (optic-aware range cap), `association.py` (`SightCone`/`filter_player_bubble`) | Range cap / cone pairing | Verified by reading and by direct test execution (`test_sight_narrow_range_cap_admits_past_the_naked_eye_cap`, `test_unaided_optic_range_cap_is_unaffected_...`): `UNAIDED_OPTIC`/`BINOCULAR_OPTIC` both default `range_cap_m=None → NAKED_EYE_RANGE_CAP_M` unchanged; only the two sight optics get 20 km. The cone and the cap are correctly a pair (Pass 3's own mutation test already proved "either alone is a no-op," re-read here rather than re-tested). | No action — confirmed clean. |
| `body-layer/src/perception/estimation.py` (`look_sigma_m`, per-optic sigma) | Error model | `UNAIDED_OPTIC`/`BINOCULAR_OPTIC` reproduce the pre-change formula exactly via `dict.get(..., 1.0)` default — pinned by `test_binocular_optic_gets_the_same_sigma_as_the_naked_eye`. Group-ranged-once (§11) is structurally guaranteed by `Observation` having no per-member position slot, not an incidental call-count — re-confirmed from the data model, not re-argued from the implementer's claim. | No action. |
| `body-layer/src/belief/optic_policy.py` `OpticState` (frozen, `replace()`-only) | Mutation-in-place | Every new construction site (`_back_to_home`, `_start_glance_away`, `_force_observ_off`, `_decide_sighting`'s branches, `logger.py`'s `replace(runner.optic_state, ...)` for OBSERV on/off) uses `replace()`, never in-place mutation or a bare `OpticState(...)` that would silently drop `actual_aim_*`/`home_phase`/`hands_busy_until_sim`. The two fresh-construction sites inside `decide()` (`SEARCHING`, `GLASSING` entry) carry all three forward explicitly, confirmed in the diff and consistent with Pass 1's own mutation test (temporarily removing the carry-forward broke `TestOpticStateActualAimCarriesForward`). | No action. |
| New input surface | — | None. `observ_on`/`observ_off` are new crew-console command tokens, dispatched exactly like `engage`/`disengage` — same trust boundary as every existing voice/text command (local, single-user, LAN-only), no new parsing of untrusted data. No new file, socket, or subprocess surface anywhere in the diff. | No action. |
| Grep-fence (ground-truth confinement) | — | `SightCone`/`filter_player_bubble` read `WorldObjectCandidate.x`/`z` (true position) — the same ground-truth access the bubble filter already had before this feature; `look_sigma_m` reads `true_range_m` at the same one call site `naked_eye_sigma_m` already used. No new leak of ground-truth fields into belief-layer code that is supposed to see only perceived/estimated values. | No action. |
| Process restart / persistence | — | `OpticState` (including the new `actual_aim_*`/`home_phase`/`hands_busy_until_sim` fields) is held only in `ConsolePerceptionRunner.optic_state`, in memory, with a single assignment site (`logger.py:597`) — no serialization/deserialization path exists for it. A restart produces a fresh default (`home_phase=SCANNING`, `actual_aim_*=None`), not stale state. | No action. |

### Confirmed by direct execution (not just reading)

Built the two sibling checkouts' `src` paths into `PYTHONPATH` and called the real functions
directly against a synthetic contact 25° beyond the sight's physical field of regard:

```
target = LookTarget(contact_id="c1", azimuth_deg=85.0, elevation_deg=0.0,
                     range_m=500.0, object_type="generic_vehicle",
                     current_level="class", watched=False)
state = OpticState(home_phase=OpticPhase.SIGHTING, phase_started_sim=0.0)

is_worth_a_look(target, state, now_sim=1.0)        -> True
_decide_sighting(state, 1.0, [target], True)       -> decision.optic = sight_narrow
                                                       decision.look_azimuth_deg = 85.0
SIGHT_WIDE_OPTIC.regard_azimuth_half_deg            -> 60.0
```

`_decide_sighting` selected and pointed the narrow sight at 85° — 25° past the sight's own
mechanical limit (±60°, sourced from the manual's §3.4). This value flows unchanged into
`logger._apply_active_gaze`: `advance_sight_aim` is a pure pass-through in this stage
(`actual := desired`, by the user's own §12a direction, correct for now since the slew
controller is deferred to `[[BL-B66]]`), so `OpticState.actual_aim_azimuth_deg` becomes 85.0,
and the `SightCone` built from it is centred on 85° too. Any real contact sitting near that
bearing, inside the narrow FOV (±3°) and within 20 km, is then admitted by
`filter_player_bubble` and can pass every downstream gate in `check_visibility` (gaze ±90°
and the optic FOV test both test against this same 85° look direction, so neither one catches
it) — all the way to an `Observation`.

**What this means in the project's own terms:** Petrovich perceives, at up to 20 km, through
an instrument he could not have been looking through, because the thing in the cockpit that
mechanically limits where the 9K113 can point has no code-side equivalent. This is not a
hypothetical "what if a future caller misuses this" — `_decide_sighting` is the one and only
caller that selects a sight optic, and it does this on its very first look whenever the most
promising contact happens to sit outside ±60° azimuth or outside +20°/−15° elevation, which
is unremarkable geometry (a contact to the side or below the horizon is ordinary, not an edge
case).

### Why three review passes did not catch this

Each pass verified a true and narrower claim: that the cone reads `actual_aim_*` rather than
desired aim (true), that the cone and the range cap are correctly paired (true), and that
OBSERV-off correctly tears the cone down (true, after Pass 2's required fix). None of those
claims is "the aim the cone is built from was ever checked against what the sight can
mechanically reach" — the field-of-regard data was added in Stage 1 with a docstring saying
enforcement was deferred, and nothing in Stage 2's own task list named closing that deferral,
so it was never on a checklist for a reviewer to tick.

### Verdict

**NEEDS FIXES.**

### Required Fixes

1. **Clamp or reject a `SIGHTING` look target outside the active optic's field of regard**,
   before it is committed as `look_azimuth_deg`/`look_elevation_deg` —
   `body-layer/src/belief/optic_policy.py`, `_decide_sighting` (the `worth_looking`
   filter/`choose_look` call, or `is_worth_a_look` itself gains a field-of-regard test keyed on
   the optic currently selectable for `SIGHTING`). Whichever of clamp-vs-reject is chosen is an
   implementer/architect judgement call (clamping to the envelope edge is arguably the more
   honest model — a real gunner would point as close as the mount allows and keep looking,
   rather than refusing to look at all — but that is a design decision, not a security one);
   either closes the leak. Add a test that pins a target outside ±60°/+20°/−15° and asserts the
   sight does not end up pointed there.
2. **Update `perception/optics.py`'s `regard_*` docstring** once (1) lands, so it no longer
   reads as a still-open deferral.

Per `AGENTS.md`'s re-entry rule, fix (1) is implementation work and goes back through
Implementer → Reviewer (on the fix) → DoD, not straight to DoD.
