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
from belief.speech import (
    OutgoingSpeech,
    _unit_type_display,
    alignment_clock_hour,
    alignment_phrase,
    render_alignment,
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
from perception.optics import UNAIDED_OPTIC
from perception.source import OwnshipState
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

    `last_spoken_unresolved` (§10, BL-B70) is whether `last_spoken_text`
    was produced while the target's cause was `"too_far"` -- the baseline
    for the "losing sight"/"regaining sight" transition sentences
    (`belief.speech.render_attack_run_lost_sight`/`render_attack_run_
    regained_sight`): `decide` speaks the full remembered-sighting claim
    only on the `False` -> `True` edge, and `"Eyes on, ..."` only on the
    `True` -> `False` edge (tier 1 resolving again). A `MASKED` tick
    leaves this untouched, same reasoning as `last_spoken_text` -- going
    behind the cockpit mask mid-episode must not end or restart the
    episode, since §2 is silent on both edges by design.

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


def _tier1_alignment(
    ownship: OwnshipState, contact: Contact, now_sim: float
) -> tuple[float, float] | None:
    """Tier 1's alignment, or `None` when no fresh relative observation
    exists -- Decision 17's tier change, handled by `decide` falling
    through to `_tier2_alignment` below.

    **Re-derives the current azimuth/elevation from a carried offset,
    never a frozen one** (Decision 16's "why a finished angle cannot be
    carried"). `contact.last_percept.relative_direction` is yaw-removed
    *at the observing poll's own heading* -- recovering the world-frame
    offset therefore means undoing that specific rotation (not the
    *current* heading), adding ownship's own translation since the look
    (the target is assumed stationary for tier 1's short window -- both
    ownship translation and target motion are an order below the lined-up
    band, per the plan's own figures), and re-rotating by *current*
    attitude via `geometry.alignment_direction` (bank removed)."""
    percept = contact.last_percept
    if percept is None or percept.relative_direction is None:
        return None
    if now_sim - percept.t_sim > ATTACK_RUN_RELATIVE_MAX_AGE_S:
        return None

    observed = percept.ownship_at_observation
    relative = percept.relative_direction
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

    # Ownship's own displacement since the look -- a telemetry delta, not
    # an absolute position (Decision 16's "the offset is relative on
    # purpose").
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
#: BL-B70's cause taxonomy):
#:
#: - `"masked"` -- behind the cockpit mask. Silence (§2); the run stays
#:   engaged.
#: - `"obstructed"` -- a fresh DCS live LOS verdict says blocked by
#:   terrain or buildings. `", obstructed"` -- the word's only remaining
#:   caller (§8).
#: - `"too_far"` -- naked-eye presence range exceeded. The remembered-
#:   sighting transition register (§10).
#: - `"unknown"` -- no fresh live LOS verdict either way. Fail-open, no
#:   qualifier at all (F2) -- the same posture `ContactStore.tick`'s own
#:   engagement term already takes for a missing/stale verdict.
NoLookCause = Literal["masked", "obstructed", "too_far", "unknown"]


def _no_look_cause(
    ownship: OwnshipState, contact: Contact, now_sim: float
) -> NoLookCause:
    """`plans/attack-run-sortie-fixes/plan.md` BL-B70's cause taxonomy --
    pure, computed from the same primitives `perception.visibility.
    check_visibility`'s gates already use (`cockpit_mask.is_visible`,
    `Contact.live_los_clear`, `visibility.tier_ranges`), never from
    `perception.detection_trace.DetectionTrace` (a diagnostic channel;
    using it as a control input would make the log load-bearing).

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

    **Range uses the naked eye's own presence threshold** (`UNAIDED_
    OPTIC`) -- `BL-B71`'s optic ladder (a different optic lowering this
    bound) is out of scope for this entry."""
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
    if (
        contact.live_los_clear is False
        and (now_sim - contact.last_seen_sim) <= ATTACK_TARGET_LOS_MAX_AGE_S
    ):
        return "obstructed"
    profile = profile_for(contact.last_class_raw)
    # Aspect is unknown for a belief the same way `improvement_window_m`
    # treats it -- the profile's own extent, not a guess from a stale
    # heading.
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)
    presence_threshold_m, _class_threshold_m, _type_threshold_m = tier_ranges(
        presence_size_m=profile.size_m,
        recognition_extent_m=extent,
        optic=UNAIDED_OPTIC,
        distinctiveness=distinctiveness,
    )
    if range_m(observer, contact.last_position) > presence_threshold_m:
        return "too_far"
    return "unknown"


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
) -> tuple[AttackRunState, OutgoingSpeech | None]:
    """One tick of attack-run guidance: `(new_state, speech)`.

    Tries tier 1 first (`_tier1_alignment`); falls through to tier 2
    (`_tier2_alignment`) whenever tier 1 has no fresh relative observation.
    `group` is tier 2's own input (Decision 10's projection, via `Group.
    heading_deg`) -- the caller (`belief.crew_console.drain_attack_run`)
    resolves it from `self.store.group_for_contact(contact.id)`; tier 1
    never reads it, since a live look needs no projection.

    **`plans/attack-run-sortie-fixes/plan.md` BL-B70's cause taxonomy
    (`_no_look_cause`) decides three things on top of the tier, in this
    order:**

    1. **`"masked"` -> silence** (§2): `speech` is `None` and neither
       `last_spoken_text`, `last_spoken_clock_hour` nor `last_spoken_
       unresolved` move -- the run stays engaged, but a suppressed-for-
       masking tick must not look like a spoken one to the next tick's
       comparison. Memory (`last_known_target_alt_m`,
       `current_azimuth_deg`/`current_elevation_deg`) still updates, same
       as any other tick.
    2. **Tier 2's qualifier is cause-keyed, not tier-keyed** (§8, revising
       Stage 6's "tier 2 always says obstructed"): `"obstructed"` ->
       `", obstructed"`; `"too_far"` -> the §10 transition register
       below; `"unknown"` -> no qualifier at all (fail-open, F2). Tier 1
       never carries a qualifier regardless of what `_no_look_cause`
       says about the *previous* tick's geometry.
    3. **§10's "losing sight"/"regaining sight" announcements key on
       resolvability, not on having been masked** (direction §11, user's
       own words: *"losing sight is expected in a break after a gun/
       rocket run... the important question is whether Petrovich sees
       the target when we turn to see what is happening"*).
       `AttackRunState.last_spoken_unresolved` tracks whether the cause
       behind `last_spoken_text` was `"too_far"`; a `"masked"` tick never
       touches it, so a break that masks the target mid-episode neither
       starts nor ends one, and pulling off target (which masks on every
       pass) does not announce a loss once per pass -- only the
       resolvable/unresolvable edge does, which is `"too_far"`'s edge
       alone.

       - `False -> True` (newly too far): `render_attack_run_lost_sight`
         -- the full remembered-sighting claim, once.
       - steady `True`: ordinary bare guidance, no appended clause.
       - `True -> False` (back inside acquisition range, i.e. tier 1
         resolves again): `render_attack_run_regained_sight` -- `"Eyes
         on, ..."`, once.
       - steady `False`: ordinary rendering (§8/§4 as usual).

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
    exactly the gap this finding describes (`logger.py`'s own reset only
    fires on an explicit `engage` transition, never on a bare
    reselection). The reset clears `last_known_target_alt_m` (closes the
    reported bug: the new target's elevation can no longer be computed
    from the old target's remembered altitude), the `last_spoken_*`
    cadence baseline/tier/clock-hour (so the first utterance about the
    newly selected target always speaks and is never read as a sector
    crossing), and `last_spoken_unresolved` (a new target's first callout
    must never open with `"Eyes on, ..."` or inherit a last-seen clause
    from the previous target, per direction §10)."""
    if state.last_contact_id != contact.id:
        state = AttackRunState(last_contact_id=contact.id)

    cause = _no_look_cause(ownship, contact, now_sim)

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

    # Memory updates every tick regardless of tier/cause/emit -- see
    # `AttackRunState`'s own docstring on why this must not wait for a
    # spoken tick.
    state = replace(
        state,
        last_known_target_alt_m=target_alt_m,
        current_azimuth_deg=azimuth_deg,
        current_elevation_deg=elevation_deg,
    )

    if cause == "masked":
        # §2: silence, run stays engaged, cadence/sector/unresolved
        # baselines all untouched (direction §11 -- a break that masks
        # the target must not itself count as losing or regaining sight).
        return state, None

    announce_twelve = (
        abs(azimuth_deg) <= _SECTOR_HALF_DEG
        and state.last_spoken_clock_hour is not None
    )

    # §10/§11: keyed on whether the target is resolvable *now*
    # (`cause == "too_far"`), never on tier directly and never on having
    # been masked -- direction §11, the user's own words: "the important
    # question is whether Petrovich sees the target when we turn to see
    # what is happening," not whether a break masked him in the
    # meantime. `tier == 1` with `cause == "too_far"` is not reachable in
    # practice (a fresh relative percept implies naked_eye_source already
    # admitted it within presence range), but the condition is written
    # against `cause` rather than `tier` so a range closing while tier
    # stays 2 (still no fresh percept, but no longer too far) correctly
    # announces "eyes on" too, not only a tier flip.
    now_unresolved = cause == "too_far"
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
    elif losing_sight:
        phrase = alignment_phrase(
            azimuth_deg,
            elevation_deg,
            azimuth_table=azimuth_table,
            elevation_table=elevation_table,
        )
        what = _unit_type_display(
            contact.classification.value, contact.classification.level.name.lower()
        )
        where_hour = alignment_clock_hour(azimuth_deg)
        where = f"{where_hour} o'clock" if where_hour is not None else "ahead"
        speech = render_attack_run_lost_sight(
            phrase, what, where, now_sim - contact.last_seen_sim
        )
    else:
        qualifier: str | None = None
        if tier == 2 and cause == "obstructed":
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
