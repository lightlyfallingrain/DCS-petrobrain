"""BL-14's attack-run alignment derivation -- `plans/attack-run/plan.md`,
Stages 2-7. This module and `percept.py` are the **only** two files under
`belief/` allowed to mention `Percept.relative_direction` -- grep-fenced by
`test_attack_run.py`, mirroring `belief.contacts`'s own `derived_world_
position` fence. See that field's own docstring (`perception/source.py`)
for the no-omniscience argument this boundary protects: the datum carries
true relative geometry, so the protection here is structural, not merely
informational.

**Two tiers, as of Stage 6/7.** Tier 1 is a live look, via the
ownship-relative observation (Stage 3). Tier 2 (Decision 17 REVISED) is
the degraded fallback: no fresh relative observation this tick, so
guidance continues from world-anchored belief (projected forward if the
target's own `motion` says it was moving, Decision 10/Stage 7) for the
horizontal, and the **remembered** relative height (Decision 4 REVISED)
for the vertical -- never `Contact.last_alt_m`, which is the ownship's own
altitude at the last look, not the target's.

**The cause taxonomy (`plans/attack-run-sortie-fixes/plan.md`, BL-B70
§1/§2/§8/§9) replaces the old "tier 2 always says obstructed" rule.**
`_no_look_cause` answers *why* Petrovich has no fresh look right now, in
`check_visibility`'s own gate order: `"masked"` (behind the cockpit mask --
silence, the run stays engaged, §2), `"obstructed"` (a fresh DCS live LOS
verdict says blocked by terrain or buildings -- `", obstructed"`, the
word's only remaining caller, §8), `"too_far"` (naked-eye presence range
exceeded -- the remembered-sighting age phrase, §5's fallback), or
`"unknown"` (no fresh verdict either way -- fail-open, no qualifier at
all, same posture `ContactStore.tick`'s own engagement term already
takes). The qualifier is appended only on a tier-2 tick -- tier 1 is a
live look and speaks bare, regardless of what `_no_look_cause` would say
about last tick's geometry.

**Pure functions plus one frozen dataclass; no I/O.** `AttackRunState` is
modelled on `belief.optic_policy.OpticState`/`decide()`: replaced wholesale
each call, never mutated, so replay determinism holds. `decide` reads a
`belief.contacts.Contact`'s `last_percept` field (the whole `Percept`,
kept so this module has one place to read `relative_direction` from
without `belief.contacts` needing to store or even mention that field by
name itself), the current `perception.source.OwnshipState`, and (tier 2
only) the contact's `belief.groups.Group`, for `Group.heading_deg` --
Decision 10's "the sole direction-of-travel estimate in belief." It
performs no store I/O itself; the caller (`belief.crew_console.
drain_attack_run`) resolves both the `Contact` and its `Group` from the
store before calling in.

**`BL-B71` (`plans/attack-run-sortie-fixes/plan.md` §6/§7) adds the
least-capable-optic guidance ladder on top of the cause taxonomy above.**
`decide` now also maintains `AttackRunState.requested_optic` -- the
contact's own standing answer to "the least capable optic that can still
resolve it," continuous and bidirectional, frozen on a `MASKED` tick
(guard 1). This module only ever *requests*; `belief.optic_policy.decide`
is the one that grants or refuses (the hard gate on the 9K113, the
hands-busy cost, the minimum-interval guard) -- see that module's own
`_apply_guidance` for why the split is drawn there.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final, Literal

import tuning
from belief.association_over_time import contact_growth_rate_mps
from belief.contacts import Contact
from belief.enrichment import CLOCK_BUCKET_DEG
from belief.groups import Group
from belief.optic_policy import guidance_request_for
from belief.percept import Percept
from belief.speech import (
    OutgoingSpeech,
    _unit_type_display,
    alignment_clock_hour,
    alignment_phrase,
    render_alignment,
    render_attack_run_behind_terrain,
    render_attack_run_lost_sight,
    render_attack_run_regained_sight,
)
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT, is_visible
from perception.geometry import (
    GeoPosition,
    alignment_direction,
    body_relative_direction,
    range_m,
)
from perception.naked_eye_source import ATTACK_TARGET_LOS_MAX_AGE_S
from perception.object_model import apparent_extent_m, distinctiveness_of, profile_for
from perception.optics import SIGHT_NARROW_OPTIC, UNAIDED_OPTIC, Optic
from perception.source import OwnshipState, RelativeDirection
from perception.visibility import tier_ranges

#: The 12 o'clock sector's own half-width (Decision 6: one clock hour is
#: 30 degrees, so the sector is the +/-15 degree wedge about the nose) --
#: derived from the same `CLOCK_BUCKET_DEG` the o'clock report vocabulary
#: already uses, not a second constant for the identical geometric fact.
_SECTOR_HALF_DEG: Final[float] = CLOCK_BUCKET_DEG / 2.0

#: Two constants, one place each, stated as assumptions (Decision 11,
#: kept unchanged by Decision 11 REVISED/§17's amendment) -- a stated
#: guess with its bounds named, not a measurement, tuned from flying. **Do
#: not tune these as part of implementing this plan** -- see the plan's
#: "What a sortie must decide".
#:
#: `ATTACK_RUN_LINED_UP_AZIMUTH_DEG` (5.0): above `estimation.
#: BEARING_SIGMA_DEG` (3.0, tier 2's own bearing-statement noise), so
#: belief noise alone cannot chatter the band; below half a clock hour
#: (`_SECTOR_HALF_DEG`, 15.0), so the band sits strictly inside the 12
#: o'clock sector. The real driver is the crosswind offset §5 names and is
#: unmeasured. Tier 1 (this stage) has no bearing noise at all, so here
#: the band's job is purely "does this read as pointed at it."
ATTACK_RUN_LINED_UP_AZIMUTH_DEG: Final[float] = tuning.real(
    "belief.attack_run.ATTACK_RUN_LINED_UP_AZIMUTH_DEG",
    5.0,
    lo=0.5,
    hi=14.0,
    status="agreed-guess",
)
#: `ATTACK_RUN_ELEVATION_GATE_DEG` (10.0): deliberately wide (§11: "it's
#: there to make me aim at the correct unit, not wrong one"), so a lofted
#: nose stays inside it. §17 declined the discrimination-test alternative
#: and specified the two-vector mechanism instead; the plan's Risks record
#: the resulting tension (a gate wide enough to ignore ballistic loft is
#: wider than the vertical separation it is meant to resolve) as a known
#: consequence, not an open fork -- a flight decides the number.
ATTACK_RUN_ELEVATION_GATE_DEG: Final[float] = tuning.real(
    "belief.attack_run.ATTACK_RUN_ELEVATION_GATE_DEG",
    10.0,
    lo=1.0,
    hi=45.0,
    status="agreed-guess",
)
#: How stale a relative observation may be and still be trusted for tier 1
#: (Decision 16) -- two polls at the crew loop's `_DEFAULT_POLL_INTERVAL_S`
#: (1.0 s), so a single missed poll does not immediately drop to silence.
ATTACK_RUN_RELATIVE_MAX_AGE_S: Final[float] = tuning.real(
    "belief.attack_run.ATTACK_RUN_RELATIVE_MAX_AGE_S",
    2.0,
    lo=0.5,
    hi=10.0,
    status="judgement",
)

#: How far above a seen target's reported ground point the 9K113 sight
#: aims, in metres -- zero aims at the vehicle's base, too large rides the
#: crosshair over the top of a small vehicle at close range; the default
#: 1.2 m is half a BTR-80's 2.4 m hull height. `seen_world_direction`'s own
#: aim-point correction (`[[BL-B80]]`, plan Decision 6, pilot 2026-10-22,
#: verbatim: *"no idea. let's assume on ground"*). The associated object's
#: reported position is the DCS unit's reference point, likely near
#: ground/base level -- this raises the seen elevation by the angle the
#: offset subtends at the look's own range. One flat offset, no per-class
#: table yet (the plan's own Decision 6, left for a later, separate change
#: if Flight B's screenshot shows it is still off). The default is an
#: agreed guess pending that flight.
SEEN_AIM_HEIGHT_OFFSET_M: Final[float] = tuning.real(
    "belief.attack_run.SEEN_AIM_HEIGHT_OFFSET_M",
    1.2,
    lo=0.0,
    hi=3.0,
    status="agreed-guess",
)

#: One row of an alignment word table: `(threshold_deg, positive_phrase,
#: negative_phrase)`, descending by `threshold_deg` -- `belief.speech.
#: render_alignment`'s own `_AlignmentWordRow` type, restated here as a
#: plain tuple so this module does not need to import that private name.
#: Both `AZIMUTH_WORD_TABLE`/`ELEVATION_WORD_TABLE` are declared here and
#: passed into `render_alignment` as data (Decision 11 REVISED, rule 1) --
#: `belief.speech` never imports this module, which is what keeps `belief.
#: speech` -> `belief.attack_run` -> `belief.speech` from being a circular
#: import.
_WordTableRow = tuple[float, str, str]

#: The large/small azimuth split is **derived, not a fourth constant**
#: (Decision 11): "a bit" from the lined-up band out to half the sector
#: (`_SECTOR_HALF_DEG / 2`), "come" beyond it.
AZIMUTH_WORD_TABLE: Final[tuple[_WordTableRow, ...]] = (
    (_SECTOR_HALF_DEG / 2.0, "come right", "come left"),
    (ATTACK_RUN_LINED_UP_AZIMUTH_DEG, "a bit right", "a bit left"),
)
#: One row only -- the vertical word carries no large/small split (the
#: spoken vocabulary table has exactly `"Higher."`/`"A little lower."`),
#: so the table's one row *is* the gate (Decision 11 REVISED, rule 1).
#: Going fine-grained later is adding rows above this one, never a new
#: renderer or a branch (rule 3) -- nothing in `render_alignment` assumes
#: this table has only one row.
ELEVATION_WORD_TABLE: Final[tuple[_WordTableRow, ...]] = (
    (ATTACK_RUN_ELEVATION_GATE_DEG, "higher", "a little lower"),
)

#: Tier 2's own azimuth table (Decision 17 REVISED, §19) -- **not** a
#: subset of `AZIMUTH_WORD_TABLE` reached by withholding a row, but a
#: separate, narrower table: one row, at the same gate
#: (`ATTACK_RUN_LINED_UP_AZIMUTH_DEG`) tier 1 uses for its own last row,
#: with the bare direction words rather than `"come"`/`"a bit"`. The
#: user's own example drops the magnitude word entirely
#: (`"right, obstructed"`, never `"come right, obstructed"`) -- tier 2's
#: ~3.9 degree residual (plan Decision 17's recomputed figure) cannot
#: support a word that means "within a few degrees" anyway, so this table
#: reaches the same place the struck sticky-band mechanism was reaching
#: for, by vocabulary instead of a rule.
#:
#: The elevation axis needs no equivalent table: `ELEVATION_WORD_TABLE`
#: already has exactly one row with no large/small split, so tier 1 and
#: tier 2 share it unchanged -- `"higher"`/`"a little lower"` either way,
#: confirmed by the plan's own spoken-vocabulary table.
TIER2_AZIMUTH_WORD_TABLE: Final[tuple[_WordTableRow, ...]] = (
    (ATTACK_RUN_LINED_UP_AZIMUTH_DEG, "right", "left"),
)


@dataclass(frozen=True, slots=True)
class AttackRunState:
    """The run's frozen per-tick phase (`plans/attack-run/plan.md`
    Decision 2) -- carried on `logger.ConsolePerceptionRunner` beside
    `optic_state` once Stage 5 wires the loop (not done by this stage).
    Replaced wholesale by `decide`, never mutated.

    `last_spoken_text` is the change-driven emit rule's own baseline
    (Decision 7, revised by `plans/attack-run-sortie-fixes/plan.md` BL-B70
    §1): the *last spoken* rendered text, never the previous sample's
    angles -- the angular change-driven clause is deleted entirely (F1:
    no threshold can fix a comparison finer-grained than the vocabulary it
    guards), so this is now the **whole** of `_should_emit`'s own
    baseline. `None` (nothing spoken yet) means "always emit the first
    utterance." **Never written on a `MASKED` tick** (§2) -- a suppressed-
    for-masking tick must not move the baseline, or coming back round the
    turn with the words unchanged would wrongly stay silent.

    `last_spoken_tier` is `decide`'s own record of which tier produced
    `last_spoken_text` (`1`/`2`, `None` before anything has been spoken) --
    read back by `belief.crew_console.drain_attack_run` for the speech
    log's `attack_run_tier` field, and by tests that pin which tier
    produced a given utterance. It plays no part in the emit decision
    itself.

    `last_spoken_clock_hour` (§4, BL-B70) is the hour `decide` last spoke
    in the o'clock register, or `None` if the last spoken utterance was in
    the qualitative register -- the baseline `decide` compares against to
    decide whether *this* tick is a fresh entry into the 12 o'clock sector
    (any entry, not literally 1->12/11->12 -- a hard turn can skip the
    adjacent sector). Reset to `None` on a re-point (below): a new
    target's first callout must never read as a sector crossing.

    `last_spoken_unresolved` (`plans/attack-run-los/plan.md` F2, revising
    BL-B70 §10) is whether `last_spoken_text` was produced while `tier !=
    1` -- i.e. no genuine live look, regardless of what `_no_look_cause`
    says about why. **Not** `cause == "too_far"` any more: that keying
    let "eyes on" fire on the mere expiry of a stale `"obstructed"`
    verdict (the target falls through to `"unknown"`, which reads as
    "resolved" under the old rule) with no fresh look at all -- the
    reported bug this plan fixes. `tier != 1` is the honest test, since
    tier 1 already *is* "has LOS and a fresh look" by construction. This
    is the baseline for the "losing sight"/"regaining sight" transition
    sentences (`belief.speech.render_attack_run_lost_sight`/
    `render_attack_run_regained_sight`/`render_attack_run_behind_
    terrain`): `decide` speaks a losing-sight sentence only on the
    `False` -> `True` edge, and `"Eyes on, ..."` only on the `True` ->
    `False` edge (tier 1 resolving again). A `MASKED` tick leaves this
    untouched, same reasoning as `last_spoken_text` -- going behind the
    cockpit mask mid-episode must not end or restart the episode, since
    §2 is silent on both edges by design.

    `current_azimuth_deg`/`current_elevation_deg` are **not** a cadence
    baseline -- updated unconditionally on *every* call, spoken or not,
    exactly like `last_known_target_alt_m` below. They exist so `belief.
    crew_console.drain_attack_run`'s speech-log fields always read "this
    tick's" angles rather than a stale spoken baseline (the removed
    `last_spoken_azimuth_deg`/`last_spoken_elevation_deg`'s only other
    reader, besides the deleted cadence clause).

    `last_known_target_alt_m` is Decision 4 REVISED's "remember the
    relative height from the last look instead [of reading `Contact.
    last_alt_m`]" -- the target's own altitude (MSL), reconstructed as
    `percept.ownship_at_observation.alt_m + relative.up_m` the last time
    tier 1 held a fresh relative observation (`_remembered_target_alt_m`
    below). Updated on **every** tick tier 1 succeeds, whether or not that
    tick actually speaks -- it is memory, not a speech baseline, so it
    must not go stale just because a steady run stays under the
    change-driven cadence's threshold. `None` only before the very first
    tier-1 look *this contact* has ever had within the current `(state,
    contact)` pairing (possible for a handful of polls right after
    `engage` or right after a mid-run re-point, before the gaze claim's
    first look lands for the new target); tier 2's own elevation axis
    fails open in that case (no elevation word at all) rather than
    fabricating a value -- see `_tier2_alignment`.

    `requested_optic` (`BL-B71`, `plans/attack-run-sortie-fixes/plan.md`
    §6/§7) is this contact's own standing answer to "the least capable
    optic that can still resolve it" (`belief.optic_policy.
    guidance_request_for`'s own hysteresis, not the naive per-tick lookup)
    -- `decide` updates it every non-`MASKED` tick and threads it into
    `OpticDecision` via `optic_policy.decide`'s `guidance_request`
    keyword (`body.py`'s poll loop). **Frozen on a `MASKED` tick**
    (guard 1, §7's "do not re-evaluate while masked"): the field is only
    ever touched after the `cause == "masked"` early return below, so a
    tick that returns there leaves it exactly as it was, which is what
    "falls out of §2" means in the plan -- no separate check needed.
    `None` before the first non-masked tick this contact has ever had.

    `terrain_blocked_held` (`plans/attack-run-los/plan.md` Decision 2,
    user 2026-10-24: *"until a genuine live look"*) is whether a fresh
    `cause == "obstructed"` verdict has been seen for this contact and
    not yet superseded by a live look -- held across the verdict's own
    freshness window ageing out, rather than decaying to silent
    `"unknown"` the instant `ATTACK_TARGET_LOS_MAX_AGE_S` elapses (the
    same staleness mechanism F2 itself exhibits one level up). Set `True`
    on a tier-2 tick whose `cause` is `"obstructed"`; cleared `False` on
    any tier-1 tick (a genuine live look is the one thing that ends the
    hold, regardless of what `cause` would otherwise say -- tier 1 never
    reads `cause` for wording at all); left unchanged on a tier-2 tick
    whose `cause` is `"too_far"` or `"unknown"` (neither confirms nor
    contradicts a terrain-blocked belief). Read, never written, by
    `query` (F3) via the same `effective_cause` substitution `decide`
    uses. `False` by default -- no construction site needs an explicit
    update (every `AttackRunState(` site, including `drain_where_is_it`'s
    own throwaway instance, gets this for free).

    `last_contact_id` is the run-level/per-contact seam itself (the
    security-fix review's finding 5, `plans/attack-run/review.md`): every
    other field above describes *this contact's* last look, never the
    run's in general, so `decide` resets the whole state to fresh the
    moment the task it is called for names a different contact than the
    one that produced the carried-forward state -- see `decide`'s own
    docstring for why that reset lives there and not at the call site.
    `None` only for a state that has never been passed through `decide`."""

    last_spoken_text: str | None = None
    last_spoken_tier: Literal[1, 2] | None = None
    last_spoken_clock_hour: int | None = None
    last_spoken_unresolved: bool = False
    current_azimuth_deg: float | None = None
    current_elevation_deg: float | None = None
    last_known_target_alt_m: float | None = None
    last_contact_id: str | None = None
    requested_optic: Optic | None = None
    terrain_blocked_held: bool = False


def _seen_world_offset(
    percept: Percept, *, relative: RelativeDirection | None = None
) -> tuple[float, float, float] | None:
    """The world-frame offset (north_m, east_m, up_m), from the ownship
    position *at the observing poll* to the target -- `None` when there is
    no relative observation to re-derive from. Factored out of `_tier1_
    alignment` (`[[BL-B80]]`, `plans/9k113-sight-pointing/plan.md`, "Aim
    source") as the first half of that function's own derivation: undoing
    the observation's own yaw-only rotation (`contact.last_percept.
    relative_direction` is yaw-removed *at the observing poll's own
    heading*, Decision 16's "why a finished angle cannot be carried").

    **Two callers, two different second halves.** `_tier1_alignment`
    continues by adding ownship's own translation *since* the look and
    re-rotating into the *current* body frame (`alignment_direction`) --
    appropriate for guidance, which needs where the target is *now*
    relative to the nose. `seen_world_direction` below stops here and
    reads off the world-true azimuth/elevation directly, with no ownship-
    displacement adjustment and no attitude at all -- appropriate for the
    sight goal, which wants the direction *as seen at the look* (the rate
    `sight_head.select_sight_goal` derives from consecutive looks already
    covers both ownship translation and target motion since; adding a
    displacement correction here too would double-count it, per the
    plan's "Aim source" notes).

    `relative` (`[[BL-B67]]` Stage 2, "Single unit, never a cluster") lets
    `seen_world_direction` substitute `percept.aim_unit_direction` for the
    cluster-centroid `percept.relative_direction` this function would
    otherwise read -- `None` (the default) means "read `percept.
    relative_direction`", which is every pre-existing caller's unchanged
    behaviour, `_tier1_alignment` included: that function never reads
    `aim_unit_direction` and never will, since guidance aligns on the
    cluster the same way it always has."""
    if relative is None:
        relative = percept.relative_direction
    if relative is None:
        return None
    observed = percept.ownship_at_observation
    heading_obs_rad = math.radians(observed.heading_true_deg)
    # Undo the observing poll's own yaw-only rotation to recover the
    # world-frame offset (north/east); `up_m` was never rotated by yaw.
    north_m = relative.forward_m * math.cos(
        heading_obs_rad
    ) - relative.right_m * math.sin(heading_obs_rad)
    east_m = relative.forward_m * math.sin(
        heading_obs_rad
    ) + relative.right_m * math.cos(heading_obs_rad)
    up_m = relative.up_m
    return north_m, east_m, up_m


def _tier1_alignment(
    ownship: OwnshipState, contact: Contact, now_sim: float
) -> tuple[float, float] | None:
    """Tier 1's alignment, or `None` when no fresh relative observation
    exists -- Decision 17's tier change, handled by `decide` falling
    through to `_tier2_alignment` below.

    **Re-derives the current azimuth/elevation from a carried offset,
    never a frozen one** (Decision 16's "why a finished angle cannot be
    carried"), via `_seen_world_offset` (the yaw-undoing half shared with
    `seen_world_direction`) plus ownship's own translation since the look
    (the target is assumed stationary for tier 1's short window -- both
    ownship translation and target motion are an order below the lined-up
    band, per the plan's own figures), re-rotated by *current* attitude
    via `geometry.alignment_direction` (bank removed)."""
    percept = contact.last_percept
    if percept is None:
        return None
    if now_sim - percept.t_sim > ATTACK_RUN_RELATIVE_MAX_AGE_S:
        return None
    offset = _seen_world_offset(percept)
    if offset is None:
        return None
    north_m, east_m, up_m = offset

    # Ownship's own displacement since the look -- a telemetry delta, not
    # an absolute position (Decision 16's "the offset is relative on
    # purpose").
    observed = percept.ownship_at_observation
    adjusted_north_m = north_m - (ownship.x - observed.x)
    adjusted_east_m = east_m - (ownship.z - observed.z)
    adjusted_up_m = up_m - (ownship.alt_m - observed.alt_m)

    direction = alignment_direction(
        GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        GeoPosition(x=adjusted_north_m, z=adjusted_east_m, alt_m=adjusted_up_m),
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
    )
    return direction.azimuth_deg, direction.elevation_deg


@dataclass(frozen=True, slots=True)
class SeenDirection:
    """The world-true direction to a contact *as seen at the look*
    (`[[BL-B80]]`, "Aim source") -- `seen_world_direction`'s own return
    type. `az_true_deg` is a compass bearing (`[0, 360)`), `el_deg` is
    above the world-horizontal plane; neither carries any attitude or
    ownship-displacement correction (see `_seen_world_offset`'s own
    docstring for why not). `t_look` is `percept.t_sim`, the look's own
    timestamp -- `sight_head.select_sight_goal`'s freshness test compares
    this against `last_sight_look_sim`."""

    az_true_deg: float
    el_deg: float
    t_look: float


def seen_world_direction(
    contact: Contact, *, single_unit: bool = False
) -> SeenDirection | None:
    """The world-true direction to `contact`, *as seen* at its last look
    through a sight-tier optic -- `[[BL-B80]]`'s sanctioned second
    consumer of `Percept.relative_direction` (`plans/9k113-sight-pointing/
    plan.md`, "Aim source": *"Petrovich can see the target and point
    sight at it even if belief about world location is incorrect"*).

    `None` when `contact.last_percept` carries no relative observation at
    all (never observed through an optic that reports exact relative
    geometry -- unaided/binocular looks also set it, so **this function
    alone does not know whether the look came through the sight**; that
    is `sight_head.select_sight_goal`'s own `last_sight_look_sim` check,
    per the plan's "Notes on the rule").

    **`single_unit` (`[[BL-B67]]` Stage 2, "Single unit, never a
    cluster") prefers `percept.aim_unit_direction` over `percept.
    relative_direction`** when the former is set -- the one-member
    direction an ATGM run needs rather than the cluster centroid an
    ordinary sight look is content with. Falls back to `relative_
    direction` when `aim_unit_direction` is `None` (no sight-tier look
    admitted this cluster the moment it was last seen), so a caller
    passing `single_unit=True` never loses the look merely because the
    one-member signal happened not to be populated that poll -- it only
    ever *narrows* what tier 1 would have used anyway. `False` (the
    default) is every pre-existing caller's unchanged behaviour.

    **No staleness check** -- unlike `_tier1_alignment`, which gates on
    `ATTACK_RUN_RELATIVE_MAX_AGE_S`. Freshness for the sight goal is an
    exact-equality test against `last_sight_look_sim` in `select_sight_
    goal`, not an age threshold; this function simply reports what the
    last percept said, however old."""
    percept = contact.last_percept
    if percept is None:
        return None
    offset = _seen_world_offset(
        percept, relative=percept.aim_unit_direction if single_unit else None
    )
    if offset is None:
        return None
    north_m, east_m, up_m = offset
    horizontal_m = math.hypot(north_m, east_m)
    # `SEEN_AIM_HEIGHT_OFFSET_M`: the reported position is assumed to be
    # at ground level, so the aim point is raised by the angle a
    # half-nominal-vehicle-height offset subtends at this range.
    az_true_deg = math.degrees(math.atan2(east_m, north_m)) % 360.0
    el_deg = math.degrees(math.atan2(up_m + SEEN_AIM_HEIGHT_OFFSET_M, horizontal_m))
    return SeenDirection(az_true_deg=az_true_deg, el_deg=el_deg, t_look=percept.t_sim)


def _remembered_target_alt_m(contact: Contact) -> float | None:
    """Decision 4 REVISED's honest crew reconstruction of the target's own
    altitude (MSL): `percept.ownship_at_observation.alt_m + relative.
    up_m`. **Not** `Contact.last_alt_m`, which is the ownship's own
    altitude at the last look, never the target's (Decision 4's finding,
    kept standing). `None` when `contact.last_percept` carries no
    `relative_direction` at all -- never observed through tier 1, the one
    case `_tier2_alignment`'s own fail-open rule exists for.

    Deliberately not staleness-checked the way `_tier1_alignment` is: this
    is memory, called by `decide` only once tier 1 has already confirmed
    the percept's `relative_direction` is fresh, so the one call site
    already guarantees it."""
    percept = contact.last_percept
    if percept is None or percept.relative_direction is None:
        return None
    return percept.ownship_at_observation.alt_m + percept.relative_direction.up_m


def _tier2_alignment(
    ownship: OwnshipState,
    contact: Contact,
    now_sim: float,
    last_known_target_alt_m: float | None,
    group: Group | None,
) -> tuple[float, float | None]:
    """Tier 2's alignment (Decision 17 REVISED/Decision 10) -- the
    horizontal from world-anchored belief, projected forward if the
    target was moving; the vertical from the remembered relative height.
    Returns `(azimuth_deg, elevation_deg)`, `elevation_deg` is `None` only
    when `last_known_target_alt_m` is itself `None` (no tier-1 look has
    ever succeeded for this contact) -- Decision 4 REVISED's "the vertical
    half's fail-open rule applies to... no relative observation": the
    honest answer is no elevation word at all, never a guessed one.

    **Horizontal: last known, unconditionally, unless `Contact.motion`
    says moving** (Decision 10). `contact.motion is None` means "never
    observed for movement" and is held exactly like `"stopped"` -- never
    treated as moving. Direction comes from `group.heading_deg`, the sole
    direction-of-travel estimate belief holds (group-level, held only
    while `Group.movement_state == "moving"` with enough samples -- see
    `belief.groups._update_heading`); `heading_deg is None` (not enough
    samples yet, or the group itself is not moving) means no usable
    direction, so this also falls back to last known. Speed comes from
    `belief.association_over_time.contact_growth_rate_mps`, the same
    per-class speed table the position-fusion/group-matching paths already
    share (`BL-B51`'s "one table, not two"), rather than a second one.
    **Never written back to `Contact.position`** -- the plan's own "a
    read-time derivation for guidance only."""
    target_x = contact.position.x
    target_z = contact.position.z
    if (
        contact.motion is not None
        and contact.motion.state == "moving"
        and group is not None
        and group.heading_deg is not None
    ):
        speed_mps = contact_growth_rate_mps(contact)
        elapsed_s = max(0.0, now_sim - contact.position.fused_at_sim)
        heading_rad = math.radians(group.heading_deg)
        target_x += speed_mps * elapsed_s * math.cos(heading_rad)
        target_z += speed_mps * elapsed_s * math.sin(heading_rad)

    target_alt_m = (
        last_known_target_alt_m
        if last_known_target_alt_m is not None
        else ownship.alt_m
    )
    direction = alignment_direction(
        GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m),
        GeoPosition(x=target_x, z=target_z, alt_m=target_alt_m),
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
    )
    elevation_deg = (
        direction.elevation_deg if last_known_target_alt_m is not None else None
    )
    return direction.azimuth_deg, elevation_deg


#: Why Petrovich has no fresh look at the attack target right now,
#: computed in `check_visibility`'s own gate order so the two cannot
#: disagree about precedence (`plans/attack-run-sortie-fixes/plan.md`
#: BL-B70's cause taxonomy). **Gate order matters**: `check_visibility`
#: (`visibility.py:997-1023`) checks range/size (gate 3) *before* terrain
#: LOS (gate 4), so a contact beyond presence range is "too far" even if
#: its last live LOS verdict happened to be a fresh `False` -- a reviewer
#: (`plans/attack-run-sortie-fixes/review.md`) found this module's first
#: cut inverted that order, confirmed reachable by mutation (swapping the
#: two checks back left the full suite passing, since nothing exercised a
#: contact simultaneously fresh-LOS-blocked and beyond presence range):
#:
#: - `"masked"` -- behind the cockpit mask. Silence (§2); the run stays
#:   engaged.
#: - `"too_far"` -- naked-eye presence range exceeded. The remembered-
#:   sighting age clause, once the loss/regain edge fires (`plans/
#:   attack-run-los/plan.md` F2: the edge now keys on `tier != 1`, not on
#:   this cause specifically -- see `AttackRunState.last_spoken_
#:   unresolved`'s own docstring).
#: - `"obstructed"` -- a fresh DCS live LOS verdict says blocked by
#:   terrain or buildings. `", obstructed"` -- and, held across staleness
#:   by `AttackRunState.terrain_blocked_held` (Decision 2), the losing-
#:   sight edge's `"Behind the ridge, ..."` line (§8, F2).
#: - `"unknown"` -- no fresh live LOS verdict either way. Fail-open, no
#:   qualifier at all (F2) -- the same posture `ContactStore.tick`'s own
#:   engagement term already takes for a missing/stale verdict, unless
#:   `terrain_blocked_held` overrides it to `"obstructed"` for wording
#:   (`effective_cause`, Decision 2).
NoLookCause = Literal["masked", "obstructed", "too_far", "unknown"]


def _no_look_cause(
    ownship: OwnshipState,
    contact: Contact,
    now_sim: float,
    optic: Optic = UNAIDED_OPTIC,
) -> NoLookCause:
    """`plans/attack-run-sortie-fixes/plan.md` BL-B70's cause taxonomy --
    pure, computed from the same primitives `perception.visibility.
    check_visibility`'s gates already use (`cockpit_mask.is_visible`,
    `Contact.live_los_clear`, `visibility.tier_ranges`), never from
    `perception.detection_trace.DetectionTrace` (a diagnostic channel;
    using it as a control input would make the log load-bearing).

    `optic` is the optic that actually resolved this tick's look -- `BL-
    B71`'s review asked for `OpticState.guidance_optic` here, but that is
    the ladder's own *grant*, not necessarily the optic admitting this
    tick's percepts: ordinary glassing (`OpticPhase.GLASSING`, no
    guidance request at all) raises binoculars with `guidance_optic`
    left `None`, and a guidance grant can itself go stale for a poll the
    way `requested_optic` already does elsewhere in this module. `decide`
    below threads through `runner.optic` instead -- `logger.
    ConsolePerceptionRunner`'s own record of which optic's `source.optic`
    assignment this poll's percepts were actually filtered through
    (`body._apply_active_gaze`'s `optic = decision.optic`) -- defaulting
    to `UNAIDED_OPTIC` when the caller passes nothing (no optic ladder at
    all, e.g. a direct test). **User direction, 2026-10-16, asked directly
    whether the naked-eye-only range test was a test artefact or real
    behaviour: "actual behavior must measure by used optic."** Range (gate
    3 below) must therefore test against the instrument actually admitting
    percepts this tick, not a fixed `UNAIDED_OPTIC` -- see that gate's own
    comment for why using the wrong one is a live misattribution, not a
    cosmetic gap.

    **Checks range (gate 3) before terrain LOS (gate 4), matching
    `check_visibility`'s real order** (`visibility.py:997-1023`): mask,
    then range/size, then terrain LOS, then forest. A contact beyond the
    naked eye's presence range is `"too_far"` even when its last live LOS
    verdict happened to be a fresh `False` -- that is the cause
    `check_visibility` itself would have rejected it on first, and
    reporting `"obstructed"` instead is the misattribution §5/§8 exist to
    end. (A first cut of this function checked LOS before range; a
    reviewer found the inversion and confirmed it reachable by mutation
    -- see the module docstring's cause-taxonomy comment.)

    **The mask test uses the true, banked body-relative direction**
    (`geometry.body_relative_direction` with `ownship.bank_deg`), *not*
    `decide`'s own `alignment_direction`-derived azimuth/elevation --
    those are deliberately bank-removed (a pilot control decomposition,
    `alignment_direction`'s own docstring), which would silently misjudge
    the mask during a banked turn. This mirrors `belief.contacts`'s own
    `_callout_may_speak` mask check exactly (same call shape, same
    `contact.last_position`).

    **LOS freshness uses `ATTACK_TARGET_LOS_MAX_AGE_S`, not the general
    `OBSERVED_WINDOW_S`/`LOS_MAX_AGE_S`** -- §9: the attack target gets a
    tighter bound than an ordinary watched contact, because at the
    measured ~60 m/s closing rate a 3 s-old verdict already describes a
    position 180 m behind the target.

    **Range uses the optic actually resolving the look, not a fixed
    naked-eye threshold** -- `BL-B71`'s optic ladder lowers this bound
    once binoculars (or a sight rung) are granted, and the range test
    below must track that grant or it misattributes a live, resolvable
    tier-1 look as `"too_far"` (see `decide`'s own docstring on why this
    combination is reachable, not inert, once the ladder is live)."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    body_direction = body_relative_direction(
        observer,
        contact.last_position,
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
        bank_deg=ownship.bank_deg,
    )
    co_pilot_mask = COCKPIT_MASKS[STATION_CO_PILOT]
    if not is_visible(
        co_pilot_mask, body_direction.azimuth_deg, body_direction.elevation_deg
    ):
        return "masked"
    profile = profile_for(contact.last_class_raw)
    # Aspect is unknown for a belief the same way `improvement_window_m`
    # treats it -- the profile's own extent, not a guess from a stale
    # heading.
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)
    presence_threshold_m, _class_threshold_m, _type_threshold_m = tier_ranges(
        presence_size_m=profile.size_m,
        recognition_extent_m=extent,
        optic=optic,
        distinctiveness=distinctiveness,
    )
    if range_m(observer, contact.last_position) > presence_threshold_m:
        return "too_far"
    if (
        contact.live_los_clear is False
        and (now_sim - contact.last_seen_sim) <= ATTACK_TARGET_LOS_MAX_AGE_S
    ):
        return "obstructed"
    return "unknown"


@dataclass(frozen=True, slots=True)
class _Alignment:
    """The computation `decide`'s steady-state rendering and `query`
    (`plans/attack-run-los/plan.md` F3, point 3) both need -- factored
    out so the two share one cause/tier/alignment/qualifier derivation
    rather than duplicating it. `cause` is `_no_look_cause`'s raw answer;
    `effective_cause` is Decision 2's substitution (`"obstructed"` in
    place of `"unknown"` while `terrain_blocked_held` is `True`), which
    is what both callers read for *wording* -- `cause` itself is never
    used for wording directly, only to decide `terrain_blocked_held`'s
    own next value. `terrain_blocked_held` here is the value *after*
    this tick's update rule (still unread/unwritten on `cause ==
    "masked"`, the same freeze `AttackRunState.requested_optic` already
    gets -- see `_current_alignment`'s own docstring)."""

    tier: Literal[1, 2]
    cause: NoLookCause
    effective_cause: NoLookCause
    azimuth_deg: float
    elevation_deg: float
    target_alt_m: float | None
    azimuth_table: tuple[_WordTableRow, ...]
    elevation_table: tuple[_WordTableRow, ...]
    terrain_blocked_held: bool


def _current_alignment(
    state: AttackRunState,
    *,
    now_sim: float,
    ownship: OwnshipState,
    contact: Contact,
    group: Group | None,
    resolving_optic: Optic | None,
) -> _Alignment:
    """Tier/cause/alignment/qualifier, shared by `decide` and `query`
    (`plans/attack-run-los/plan.md` F3, point 3) -- the tier-1/tier-2
    branch, `_no_look_cause`'s gate chain, and Decision 2's held-flag
    update rule and `effective_cause` substitution, in one place so a
    change to any of them cannot land in one caller and not the other.

    **`terrain_blocked_held`'s update rule** (Decision 2): `cause ==
    "masked"` freezes it at `state.terrain_blocked_held` -- the same
    posture `AttackRunState.requested_optic` already has for a masked
    tick (`decide`'s own early return there is what makes that freeze
    stick for `decide`'s caller; `query` never writes `state` at all, so
    for `query` this is simply "do not derive a new value to report").
    Otherwise `tier == 1` clears it, `cause == "obstructed"` sets it,
    and any other case (`"too_far"`/`"unknown"`) carries the previous
    value forward unchanged.

    **`effective_cause`** overrides `"unknown"` to `"obstructed"` while
    `terrain_blocked_held` (the *updated* value) is `True` -- the
    override is read-only input to rendering, never fed back into the
    update rule above (which always reads raw `cause`, never `effective_
    cause`), per Decision 2's own "never fed back" clause. A masked
    tick's `cause` is `"masked"`, which never matches `"unknown"`, so
    `effective_cause` passes it through unchanged -- `query`'s own
    "masked renders bare, like unknown" rule follows from `effective_
    cause` then being neither `"too_far"` nor `"obstructed"`, not from a
    separate masked branch here."""
    cause = _no_look_cause(
        ownship,
        contact,
        now_sim,
        optic=resolving_optic if resolving_optic is not None else UNAIDED_OPTIC,
    )

    tier: Literal[1, 2]
    alignment = _tier1_alignment(ownship, contact, now_sim)
    if alignment is not None:
        tier = 1
        azimuth_deg, elevation_deg = alignment
        target_alt_m = _remembered_target_alt_m(contact)
        azimuth_table: tuple[_WordTableRow, ...] = AZIMUTH_WORD_TABLE
        elevation_table: tuple[_WordTableRow, ...] = ELEVATION_WORD_TABLE
    else:
        tier = 2
        target_alt_m = state.last_known_target_alt_m
        azimuth_deg, elevation_deg_opt = _tier2_alignment(
            ownship, contact, now_sim, target_alt_m, group
        )
        elevation_deg = elevation_deg_opt if elevation_deg_opt is not None else 0.0
        azimuth_table = TIER2_AZIMUTH_WORD_TABLE
        elevation_table = ELEVATION_WORD_TABLE if elevation_deg_opt is not None else ()

    if cause == "masked":
        terrain_blocked_held = state.terrain_blocked_held
    elif tier == 1:
        terrain_blocked_held = False
    elif cause == "obstructed":
        terrain_blocked_held = True
    else:
        terrain_blocked_held = state.terrain_blocked_held

    effective_cause: NoLookCause = (
        "obstructed" if cause == "unknown" and terrain_blocked_held else cause
    )

    return _Alignment(
        tier=tier,
        cause=cause,
        effective_cause=effective_cause,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        target_alt_m=target_alt_m,
        azimuth_table=azimuth_table,
        elevation_table=elevation_table,
        terrain_blocked_held=terrain_blocked_held,
    )


def _should_emit(state: AttackRunState, text: str) -> bool:
    """`plans/attack-run-sortie-fixes/plan.md` BL-B70 §1: emit if and only
    if the rendered text differs from the last *spoken* text -- text
    equality is a **veto**, not one of two triggers. The angular
    change-driven clause this function used to also check is deleted
    entirely (F1): the emit threshold was finer-grained than the
    vocabulary's own quantisation (10/30/7.5/5.0 degrees), so it could
    only ever re-speak unchanged text -- measured at 47 of 125 attack-run
    utterances (38%) in the 2026-10-15 16:44 sortie. Compare what would be
    said, not what is believed (the user's own words, §1)."""
    return text != state.last_spoken_text


def decide(
    state: AttackRunState,
    *,
    now_sim: float,
    ownship: OwnshipState,
    contact: Contact,
    group: Group | None = None,
    resolving_optic: Optic | None = None,
    vertical: bool = True,
    guidance_floor: Optic = UNAIDED_OPTIC,
) -> tuple[AttackRunState, OutgoingSpeech | None]:
    """One tick of attack-run guidance: `(new_state, speech)`.

    Tries tier 1 first (`_tier1_alignment`); falls through to tier 2
    (`_tier2_alignment`) whenever tier 1 has no fresh relative observation.
    `group` is tier 2's own input (Decision 10's projection, via `Group.
    heading_deg`) -- the caller (`belief.crew_console.drain_attack_run`)
    resolves it from `self.store.group_for_contact(contact.id)`; tier 1
    never reads it, since a live look needs no projection.

    `resolving_optic` is the optic that actually admitted this tick's
    percepts -- **not** a guidance grant. User direction, 2026-10-16:
    "actual behavior must measure by used optic." A prior cut of this
    parameter was named `granted_optic` and wired to `OpticState.
    guidance_optic`, which reads `None` through all of ordinary glassing
    (`OpticPhase.GLASSING` with no standing guidance request) -- the
    caller (`body.py`'s poll loop, via `drain_attack_run`) now threads
    through `runner.optic` itself: the same value `logger.
    _apply_active_gaze` just assigned onto `source.optic` for this poll,
    i.e. the optic `perception.visibility.check_visibility` actually
    tested the percept against. Defaults to `None` (read as `UNAIDED_
    OPTIC` by `_no_look_cause`) for callers with no optic ladder at all.
    Passed straight through to `_no_look_cause`'s range gate, never read
    anywhere else in this function; `requested_optic`'s own ladder
    evaluation below is independent of it (one is what this run is
    asking for, the other is what actually resolved this look).

    **`plans/attack-run-sortie-fixes/plan.md` BL-B70's cause taxonomy
    (`_no_look_cause`), as revised by `plans/attack-run-los/plan.md` F2/
    Decision 2, decides three things on top of the tier, in this
    order (shared with `query` via `_current_alignment`):**

    1. **`"masked"` -> silence** (§2): `speech` is `None` and neither
       `last_spoken_text`, `last_spoken_clock_hour`, `last_spoken_
       unresolved` nor `terrain_blocked_held` move -- the run stays
       engaged, but a suppressed-for-masking tick must not look like a
       spoken one to the next tick's comparison. Memory (`last_known_
       target_alt_m`, `current_azimuth_deg`/`current_elevation_deg`)
       still updates, same as any other tick.
    2. **Tier 2's qualifier is keyed on `effective_cause`, not raw
       `cause`** (§8, revising Stage 6's "tier 2 always says obstructed",
       then F2/Decision 2 again): `"obstructed"` -> `", obstructed"`
       (including a stale `"unknown"` tick held over from a genuine
       `"obstructed"` verdict, Decision 2); `"too_far"` -> the §10
       transition register below; `"unknown"` with no hold -> no
       qualifier at all (fail-open, F2). Tier 1 never carries a
       qualifier regardless of what `_no_look_cause` says about the
       *previous* tick's geometry.
    3. **§10's "losing sight"/"regaining sight" announcements key on
       `tier`, not on `cause`** (F2: the reported bug was exactly this
       register treating any non-`"too_far"` cause as "sighted," which
       let a stale terrain-blocked verdict decaying to `"unknown"` read
       as a regained sighting with no fresh look at all). `tier == 1` is
       already "has LOS and a fresh look" by construction (module
       docstring), so `AttackRunState.last_spoken_unresolved` now tracks
       whether `last_spoken_text` was produced at `tier != 1`, not
       whether its cause was `"too_far"`. A `"masked"` tick never touches
       it, so a break that masks the target mid-episode neither starts
       nor ends one, and pulling off target (which masks on every pass)
       does not announce a loss once per pass -- only the tier-1/tier-2
       edge does.

       - `False -> True` (tier 1 -> tier 2) **and** `effective_cause ==
         "too_far"`: `render_attack_run_lost_sight` -- the full
         remembered-sighting claim, once.
       - `False -> True` **and** `effective_cause == "obstructed"`:
         `render_attack_run_behind_terrain` -- `"Behind the ridge,
         ..."`, once (F2 option C, Decision 2).
       - `False -> True` **and** `effective_cause == "unknown"` (never
         held, Decision 2): no transition line at all -- falls through
         to ordinary rendering below, which also carries no qualifier.
       - steady `True`: ordinary rendering (qualifier per point 2 above).
       - `True -> False` (back to a genuine live look, tier 1 again):
         `render_attack_run_regained_sight` -- `"Eyes on, ..."`, once.
       - steady `False`: ordinary rendering.

    `AttackRunState.last_known_target_alt_m`/`current_azimuth_deg`/
    `current_elevation_deg` update on **every** call regardless of tier,
    cause or emit (their own docstrings) -- `belief.crew_console.
    drain_attack_run`'s speech-log fields read `current_azimuth_deg`/
    `current_elevation_deg`, never a spoken baseline.

    **Resets `state` to fresh the moment `contact.id` differs from
    `state.last_contact_id`** (the security-fix review's finding 5): a
    mid-run re-point (BL-14's security fix made this a sanctioned,
    silent re-point rather than a refusal -- confirmed standing, user
    direction 2026-10-14) hands this function the *same* `AttackRunState`
    it was carrying for the old target, and every field on it describes
    that old target's last look, not the new one's. Resetting here, at
    the one place that already sees both `state` and `contact` together
    on every call, means the invariant holds regardless of which command
    path produced the re-point (`select target`, `engage <what> <where>`
    while already engaged, or any future caller) -- resetting at a call
    site instead would have to be repeated at every such path and was
    exactly the gap this finding describes (`body.py`'s own reset only
    fires on an explicit `engage` transition, never on a bare
    reselection). The reset clears `last_known_target_alt_m` (closes the
    reported bug: the new target's elevation can no longer be computed
    from the old target's remembered altitude), the `last_spoken_*`
    cadence baseline/tier/clock-hour (so the first utterance about the
    newly selected target always speaks and is never read as a sector
    crossing), and `last_spoken_unresolved` (a new target's first callout
    must never open with `"Eyes on, ..."` or inherit a last-seen clause
    from the previous target, per direction §10). It also resets
    `requested_optic` to `None` (`BL-B71`) -- a re-point must start its own
    ladder evaluation from `floor`, never inherit the old target's
    de-escalation baseline, which could otherwise hand the new target an
    optic its own range never earned -- and `terrain_blocked_held` to
    `False` (`plans/attack-run-los/plan.md` Decision 2), for the identical
    reason: a fresh target's terrain occlusion has nothing to do with the
    old one's, so this new instance's plain-dataclass default is already
    the right answer.

    `vertical` (`[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md` Stage 1) is
    a **flagged departure from shipped BL-14 behaviour, scoped to the
    ATGM run only**: `False` drops the elevation word table entirely (the
    azimuth half of the aligned conjunction still speaks) -- the 9K113's
    own guidance is azimuth-only, so there is nothing to call "higher"/
    "a little lower" about. Implemented by forcing `elevation_table` to
    the empty tuple regardless of tier, which `speech.alignment_phrase`'s
    own `_alignment_phrase_for` already treats as "the elevation axis
    found no phrase" (the exact mechanism tier 2's own fail-open
    elevation case already relies on) -- no second code path, only a
    different table. `True` (the default) is every pre-existing caller's
    unchanged behaviour.

    `guidance_floor` (`[[BL-B67]]` Stage 3, settling Stage 1/2's own
    flagged deferral -- "Keeping the look through launch": *"the
    guidance ladder's floor is `SIGHT_WIDE_OPTIC` (ATGM guidance is
    9K113-only, BL-14 explore)."*) is passed straight through to
    `guidance_request_for`'s own `floor` keyword, in place of the
    hardcoded `UNAIDED_OPTIC` every pre-existing caller still gets via
    the default. `guidance_request_for` already anticipates exactly this
    ("the floor itself was raised since the last request (e.g. an ATGM
    run's own floor/ceiling parameters) -- never hold a request below
    the current floor"), so no change was needed there -- only threading
    a non-default value in. The caller (`belief.crew_console.
    drain_attack_run`, `body.py`'s poll loop) passes `SIGHT_WIDE_OPTIC`
    while an ATGM run is engaged, `UNAIDED_OPTIC` (the default)
    otherwise -- the same `runner.atgm_run_state is not None`
    granularity `vertical` above already uses, not narrowed to `home_
    phase is SIGHTING`: the ladder's own standing request is continuous
    and bidirectional regardless of tier/phase (`BL-B71`'s own module
    docstring), so gating the floor more narrowly than `vertical` would
    let the ladder request below sight tier during Preparing, then jump
    on the very poll `SIGHTING` is reached -- a visible floor change
    mid-run for no behavioural reason, not a correctness bug either way."""
    if state.last_contact_id != contact.id:
        state = AttackRunState(last_contact_id=contact.id)

    alignment = _current_alignment(
        state,
        now_sim=now_sim,
        ownship=ownship,
        contact=contact,
        group=group,
        resolving_optic=resolving_optic,
    )
    cause = alignment.cause
    effective_cause = alignment.effective_cause
    tier = alignment.tier
    azimuth_deg = alignment.azimuth_deg
    elevation_deg = alignment.elevation_deg
    azimuth_table = alignment.azimuth_table
    elevation_table = alignment.elevation_table if vertical else ()

    # Memory updates every tick regardless of tier/cause/emit -- see
    # `AttackRunState`'s own docstring on why this must not wait for a
    # spoken tick.
    state = replace(
        state,
        last_known_target_alt_m=alignment.target_alt_m,
        current_azimuth_deg=azimuth_deg,
        current_elevation_deg=elevation_deg,
    )

    if cause == "masked":
        # §2: silence, run stays engaged, cadence/sector/unresolved/held
        # baselines all untouched (direction §11 -- a break that masks
        # the target must not itself count as losing or regaining sight).
        # `BL-B71` guard 1 / Decision 2: `requested_optic` and `terrain_
        # blocked_held` are also untouched -- this `return` is the only
        # reason either stays frozen (`_current_alignment` itself never
        # updates `terrain_blocked_held` on a masked tick, so there is
        # nothing to commit here even before the early return).
        return state, None

    # Decision 2: commit the held flag now that this tick is confirmed
    # non-masked -- `_current_alignment` already computed its next value;
    # this is the one place that writes it back onto `state`.
    state = replace(state, terrain_blocked_held=alignment.terrain_blocked_held)

    # `BL-B71`: the ladder's own standing request, re-evaluated every
    # non-masked tick regardless of tier/cause/emit, same posture as the
    # memory fields replaced just above -- continuous and bidirectional
    # (§7), not an escalation computed once at run start. Range is read
    # off `contact.last_position` (belief, not the fresh percept), the
    # same basis `_no_look_cause` above already uses for its own `TOO_FAR`
    # test, so the two cannot disagree about what "the current range" is.
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    state = replace(
        state,
        requested_optic=guidance_request_for(
            range_m(observer, contact.last_position),
            contact.last_class_raw,
            state.requested_optic,
            floor=guidance_floor,
            ceiling=SIGHT_NARROW_OPTIC,
        ),
    )

    announce_twelve = (
        abs(azimuth_deg) <= _SECTOR_HALF_DEG
        and state.last_spoken_clock_hour is not None
    )

    # F2 (`plans/attack-run-los/plan.md`): keyed on `tier`, not on
    # `cause` -- the reported bug was `cause`-keying treating a stale
    # `"obstructed"` verdict's decay to `"unknown"` as "resolved" with no
    # fresh look at all. `tier == 1` already *is* "has LOS and a fresh
    # look" by construction (module docstring), including the documented
    # case where tier 1 persists under `cause == "too_far"` once the
    # optic ladder (`BL-B71`) has granted a narrower optic -- that stays
    # a genuine sighting under `tier`-keying, which `cause`-keying got
    # wrong (it would have kept reporting the stale "too far" claim).
    now_unresolved = tier != 1
    regaining_sight = state.last_spoken_unresolved and not now_unresolved
    losing_sight = now_unresolved and not state.last_spoken_unresolved
    speech: OutgoingSpeech
    if regaining_sight:
        phrase = alignment_phrase(
            azimuth_deg,
            elevation_deg,
            azimuth_table=azimuth_table,
            elevation_table=elevation_table,
        )
        speech = render_attack_run_regained_sight(phrase)
    elif losing_sight and effective_cause in ("too_far", "obstructed"):
        phrase = alignment_phrase(
            azimuth_deg,
            elevation_deg,
            azimuth_table=azimuth_table,
            elevation_table=elevation_table,
        )
        if effective_cause == "obstructed":
            # F2 option C (Decision 2): "Behind the ridge, <phrase>.",
            # once -- no what/where/age clause, unlike the too-far case
            # below; `render_attack_run_behind_terrain`'s own docstring.
            speech = render_attack_run_behind_terrain(phrase)
        else:
            what = _unit_type_display(
                contact.classification.value,
                contact.classification.level.name.lower(),
            )
            # §10's `<where>` clause is suppressed, not worded, when it
            # would restate `phrase` verbatim (review's required fix 2):
            # outside the 12 o'clock sector `phrase` is itself a
            # clock-hour phrase (e.g. "Three o'clock"), via the same
            # `alignment_clock_hour` sector test `alignment_phrase` uses
            # internally -- a second `<where>` clause there would speak
            # the same position twice, once as a word and once as a
            # digit if it were not suppressed. Inside the sector `phrase`
            # is a qualitative word ("come left"/"lined up") that carries
            # no position at all, so `<where>` still earns its place
            # there, as "ahead".
            where = "ahead" if alignment_clock_hour(azimuth_deg) is None else None
            speech = render_attack_run_lost_sight(
                phrase, what, where, now_sim - contact.last_seen_sim
            )
    else:
        # Covers steady `True`/`False`, and `losing_sight` with
        # `effective_cause == "unknown"` (never held, Decision 2): no
        # transition line, ordinary rendering -- the edge stays silent
        # exactly as F2's own fail-open posture requires.
        qualifier: str | None = None
        if tier == 2 and effective_cause == "obstructed":
            qualifier = ", obstructed"
        speech = render_alignment(
            azimuth_deg,
            elevation_deg,
            azimuth_table=azimuth_table,
            elevation_table=elevation_table,
            qualifier=qualifier,
            announce_twelve=announce_twelve,
        )

    if not _should_emit(state, speech.text):
        return state, None

    new_clock_hour = alignment_clock_hour(azimuth_deg)
    new_state = replace(
        state,
        last_spoken_text=speech.text,
        last_spoken_tier=tier,
        last_spoken_clock_hour=new_clock_hour,
        last_spoken_unresolved=now_unresolved,
        last_contact_id=contact.id,
    )
    return new_state, speech


def query(
    state: AttackRunState,
    *,
    now_sim: float,
    ownship: OwnshipState,
    contact: Contact,
    group: Group | None = None,
    resolving_optic: Optic | None = None,
) -> OutgoingSpeech:
    """ "Where is it?" (`plans/attack-run-los/plan.md` F3) -- a
    point-in-time read of the standard attack-run guidance phrase, based
    on A) seeing the target and B) current belief, the pilot's own
    stated inputs. Pure: never writes `state`, never returns a new one,
    and cannot corrupt `decide`'s own `_should_emit` cadence baseline,
    the `requested_optic` ladder's hysteresis, or `terrain_blocked_
    held`'s own update rule -- `_current_alignment` (shared with
    `decide`) computes what the *next* `terrain_blocked_held` would be,
    but this function simply never commits it anywhere.

    **Decision 1 makes this answerable whether or not a run is engaged**
    -- the caller (`belief.crew_console.drain_where_is_it`) passes either
    the live, per-contact `AttackRunState` an engaged run is carrying, or
    a throwaway `AttackRunState(last_contact_id=contact.id)` it
    constructs on the spot when none is engaged. Only `last_known_
    target_alt_m`/`terrain_blocked_held` come from `state` itself (both
    default to `None`/`False` on a throwaway instance, which is exactly
    correct: no run means no accumulated per-contact memory, the same
    "first tick after `engage`" fail-open posture `_tier2_alignment`'s
    own elevation-axis comment already documents) -- `now_sim`/
    `ownship`/`contact`/`group`/`resolving_optic` all come from live
    telemetry/belief regardless of run state.

    **Always returns speech, never `None`, including on a masked tick**
    -- `cause == "masked"` silences *passive* guidance (§2: don't talk
    over a pilot who hasn't asked anything); an explicit question gets
    an answer either way. On a masked tick this renders the same bare-
    guidance phrase a `cause == "unknown"` tick would (`effective_cause`
    is `"masked"` there, which matches neither `"too_far"` nor
    `"obstructed"` below, so no qualifier is added) -- azimuth/elevation
    are already computed from belief independent of the mask, so this is
    still "B) current belief," not an invented sentence.

    **Deliberately no transition wording** (`"Eyes on"` / `"last seen
    ... ago"` / `"Behind the ridge"`) -- those describe *what just
    changed*, and this is a point-in-time query that may land well after
    any transition. Renders exactly what `decide`'s own steady-state
    (`else`) branch would: bare alignment phrase, `", obstructed"`
    qualifier for `tier == 2 and effective_cause == "obstructed"`
    (Decision 2's held flag included), nothing for `"too_far"`/
    `"unknown"`/`"masked"` (the same fail-open posture F2 settles for
    `decide`)."""
    alignment = _current_alignment(
        state,
        now_sim=now_sim,
        ownship=ownship,
        contact=contact,
        group=group,
        resolving_optic=resolving_optic,
    )
    qualifier: str | None = None
    if alignment.tier == 2 and alignment.effective_cause == "obstructed":
        qualifier = ", obstructed"
    announce_twelve = False  # a query is never read as a sector-crossing event.
    return render_alignment(
        alignment.azimuth_deg,
        alignment.elevation_deg,
        azimuth_table=alignment.azimuth_table,
        elevation_table=alignment.elevation_table,
        qualifier=qualifier,
        announce_twelve=announce_twelve,
    )
