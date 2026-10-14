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
altitude at the last look, not the target's. Tier 2's utterance carries an
`", obstructed"` qualifier appended to whatever tier 1 would have said in
coarse form (the user's own words, 2026-10-14 second direction pass:
`"lined up, obstructed"` composes exactly like `"right, obstructed"` --
one rule, not a per-utterance table), including the `"lined up"` case,
spoken once on entering it and then silent, mirroring tier 1's own
`"Lined up."`-then-silence (§4) -- see `render_alignment`'s own docstring
for why no special-case code is needed to make that true.

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

from belief.association_over_time import contact_growth_rate_mps
from belief.contacts import Contact
from belief.enrichment import CLOCK_BUCKET_DEG
from belief.groups import Group
from belief.speech import OutgoingSpeech, render_alignment
from perception.geometry import (
    GeoPosition,
    alignment_direction,
    signed_angular_delta_deg,
)
from perception.source import OwnshipState

#: The 12 o'clock sector's own half-width (Decision 6: one clock hour is
#: 30 degrees, so the sector is the +/-15 degree wedge about the nose) --
#: derived from the same `CLOCK_BUCKET_DEG` the o'clock report vocabulary
#: already uses, not a second constant for the identical geometric fact.
_SECTOR_HALF_DEG: Final[float] = CLOCK_BUCKET_DEG / 2.0

#: Three constants, one place each, stated as assumptions (Decision 11,
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
ATTACK_RUN_LINED_UP_AZIMUTH_DEG: Final[float] = 5.0
#: `ATTACK_RUN_ELEVATION_GATE_DEG` (10.0): deliberately wide (§11: "it's
#: there to make me aim at the correct unit, not wrong one"), so a lofted
#: nose stays inside it. §17 declined the discrimination-test alternative
#: and specified the two-vector mechanism instead; the plan's Risks record
#: the resulting tension (a gate wide enough to ignore ballistic loft is
#: wider than the vertical separation it is meant to resolve) as a known
#: consequence, not an open fork -- a flight decides the number.
ATTACK_RUN_ELEVATION_GATE_DEG: Final[float] = 10.0
#: `ATTACK_RUN_CHANGE_THRESHOLD_DEG` (3.0): `BEARING_SIGMA_DEG` again --
#: do not re-speak until the error has moved by more than belief's own
#: noise would. Tier 1 has zero noise, so this constant's real job under
#: design A is channel economy (how often to re-speak an unchanged-enough
#: error), not noise rejection -- kept at 3.0 anyway rather than lowered,
#: since a sortie, not this implementation, decides the cadence.
ATTACK_RUN_CHANGE_THRESHOLD_DEG: Final[float] = 3.0

#: How stale a relative observation may be and still be trusted for tier 1
#: (Decision 16) -- two polls at the crew loop's `_DEFAULT_POLL_INTERVAL_S`
#: (1.0 s), so a single missed poll does not immediately drop to silence.
ATTACK_RUN_RELATIVE_MAX_AGE_S: Final[float] = 2.0

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

    `last_spoken_*` is the change-driven emit rule's own baseline
    (Decision 7): the *last spoken* azimuth/elevation/text, never the
    previous sample -- §10's own named guard against slow drift
    accumulating silently under a per-sample threshold. All three start
    `None` (nothing spoken yet), which `decide`'s own emit check treats as
    "always emit the first utterance."

    `last_spoken_tier` is `decide`'s own record of which tier produced
    `last_spoken_text` (`1`/`2`, `None` before anything has been spoken) --
    read back by `belief.crew_console.drain_attack_run` for the speech
    log's `attack_run_tier` field, and by tests that pin which tier
    produced a given utterance. It plays no part in the emit decision
    itself: a tier change always changes the *text* too (tier 2 appends
    `", obstructed"`), so `_should_emit`'s existing text-comparison already
    re-fires on a tier change with no tier-aware branch needed.

    `last_known_target_alt_m` is Decision 4 REVISED's "remember the
    relative height from the last look instead [of reading `Contact.
    last_alt_m`]" -- the target's own altitude (MSL), reconstructed as
    `percept.ownship_at_observation.alt_m + relative.up_m` the last time
    tier 1 held a fresh relative observation (`_remembered_target_alt_m`
    below). Updated on **every** tick tier 1 succeeds, whether or not that
    tick actually speaks -- it is memory, not a speech baseline, so it
    must not go stale just because a steady run stays under the
    change-driven cadence's threshold. `None` only before the very first
    tier-1 look this contact has ever had (possible for a handful of polls
    right after `engage`, before the gaze claim's first look lands); tier
    2's own elevation axis fails open in that case (no elevation word at
    all) rather than fabricating a value -- see `_tier2_alignment`."""

    last_spoken_azimuth_deg: float | None = None
    last_spoken_elevation_deg: float | None = None
    last_spoken_text: str | None = None
    last_spoken_tier: Literal[1, 2] | None = None
    last_known_target_alt_m: float | None = None


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


def _should_emit(
    state: AttackRunState, azimuth_deg: float, elevation_deg: float, text: str
) -> bool:
    """Decision 7's change-driven cadence: emit when the rendered text
    differs from the last *spoken* text, or either axis has moved by more
    than `ATTACK_RUN_CHANGE_THRESHOLD_DEG` since the last spoken value --
    not the previous sample, which is the slow-drift guard §10 itself
    names.

    **No tier-aware branch needed** (Stage 6): a tier change always
    changes `text` too -- tier 2 appends `", obstructed"` to whatever tier
    1 would have rendered, including the `"lined up"` case, so the first
    `text != state.last_spoken_text` check alone re-fires on every tier
    transition in both directions. This is the mechanism, not a
    coincidence worth re-deriving: the user's own direction (2026-10-14,
    second pass) is that `"lined up, obstructed"` is spoken once on
    entering it and `"lined up"` once on leaving it, exactly mirroring
    tier 1's own `"Lined up."`-then-silence (§4) -- which is exactly what
    falls out of comparing against the literal last-spoken text, with no
    special case for the lined-up state."""
    if text != state.last_spoken_text:
        return True
    if state.last_spoken_azimuth_deg is None or state.last_spoken_elevation_deg is None:
        return True
    azimuth_delta = abs(
        signed_angular_delta_deg(state.last_spoken_azimuth_deg, azimuth_deg)
    )
    elevation_delta = abs(elevation_deg - state.last_spoken_elevation_deg)
    return (
        azimuth_delta > ATTACK_RUN_CHANGE_THRESHOLD_DEG
        or elevation_delta > ATTACK_RUN_CHANGE_THRESHOLD_DEG
    )


def decide(
    state: AttackRunState,
    *,
    now_sim: float,
    ownship: OwnshipState,
    contact: Contact,
    group: Group | None = None,
) -> tuple[AttackRunState, OutgoingSpeech | None]:
    """One tick of attack-run guidance: `(new_state, speech)`, `speech`
    `None` when the change-driven rule says the rendered text has not
    moved enough to repeat itself (Decision 7) -- the one remaining
    silence, now that tier 2 (Stage 6/7) means there is always *something*
    to guide on once a target is selected: `Contact.position` always
    exists, so this function is silent only by the cadence rule, never
    because no tier had anything to say.

    Tries tier 1 first (`_tier1_alignment`); falls through to tier 2
    (`_tier2_alignment`) whenever tier 1 has no fresh relative observation.
    `group` is tier 2's own input (Decision 10's projection, via `Group.
    heading_deg`) -- the caller (`belief.crew_console.drain_attack_run`)
    resolves it from `self.store.group_for_contact(contact.id)`; tier 1
    never reads it, since a live look needs no projection.

    `AttackRunState.last_known_target_alt_m` is updated on every call
    where tier 1 succeeds, regardless of whether this call also speaks
    (`AttackRunState`'s own docstring) -- so the memory a later tier-2 tick
    reads is always as fresh as the most recent look, not merely the most
    recent *spoken* one.

    **No I/O, no store access beyond the `contact`/`group` handed in** --
    this is the pure core `plans/attack-run/plan.md` Stage 3 calls for,
    testable against hand-built `OwnshipState`/`Contact`/`Group` fixtures
    with no `ContactStore` in the loop at all."""
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

    speech = render_alignment(
        azimuth_deg,
        elevation_deg,
        tier=tier,
        azimuth_table=azimuth_table,
        elevation_table=elevation_table,
    )
    # Memory (the remembered target altitude) updates every tick tier 1
    # succeeds, independent of the emit decision below -- see
    # `AttackRunState`'s own docstring on why this must not wait for a
    # spoken tick.
    state = replace(state, last_known_target_alt_m=target_alt_m)
    if not _should_emit(state, azimuth_deg, elevation_deg, speech.text):
        return state, None
    new_state = AttackRunState(
        last_spoken_azimuth_deg=azimuth_deg,
        last_spoken_elevation_deg=elevation_deg,
        last_spoken_text=speech.text,
        last_spoken_tier=tier,
        last_known_target_alt_m=target_alt_m,
    )
    return new_state, speech
