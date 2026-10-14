"""BL-14's attack-run alignment derivation -- `plans/attack-run/plan.md`,
Stages 2-6. This module and `percept.py` are the **only** two files under
`belief/` allowed to mention `Percept.relative_direction` -- grep-fenced by
`test_attack_run.py`, mirroring `belief.contacts`'s own `derived_world_
position` fence. See that field's own docstring (`perception/source.py`)
for the no-omniscience argument this boundary protects: the datum carries
true relative geometry, so the protection here is structural, not merely
informational.

**As of Stage 3, this module derives tier 1 only** -- a live look, via the
ownship-relative observation. Tier 2 (lost sight, the `"obstructed"`
qualifier) is Stage 6 (Decision 17 REVISED) and is not built here; `decide`
below returns `(state, None)` -- silence, holding the last spoken state --
whenever tier 1's own inputs are unavailable, which is exactly Stage 5's
own documented behaviour for a run flown before tier 2 exists.

**Pure functions plus one frozen dataclass; no I/O.** `AttackRunState` is
modelled on `belief.optic_policy.OpticState`/`decide()`: replaced wholesale
each call, never mutated, so replay determinism holds. `decide` reads a
`belief.contacts.Contact`'s `last_percept` field (the whole `Percept`,
kept so this module has one place to read `relative_direction` from
without `belief.contacts` needing to store or even mention that field by
name itself) and the current `perception.source.OwnshipState`; it performs
no store I/O and is fully testable against hand-built fixtures of both.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from belief.contacts import Contact
from belief.enrichment import CLOCK_BUCKET_DEG
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
    "always emit the first utterance.\""""

    last_spoken_azimuth_deg: float | None = None
    last_spoken_elevation_deg: float | None = None
    last_spoken_text: str | None = None


def _tier1_alignment(
    ownship: OwnshipState, contact: Contact, now_sim: float
) -> tuple[float, float] | None:
    """Tier 1's alignment, or `None` when no fresh relative observation
    exists (Decision 17's tier change, though tier 2 itself is Stage 6 --
    here, `None` simply means "nothing to guide on yet").

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


def _should_emit(
    state: AttackRunState, azimuth_deg: float, elevation_deg: float, text: str
) -> bool:
    """Decision 7's change-driven cadence: emit when the rendered text
    differs from the last *spoken* text, or either axis has moved by more
    than `ATTACK_RUN_CHANGE_THRESHOLD_DEG` since the last spoken value --
    not the previous sample, which is the slow-drift guard §10 itself
    names."""
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
) -> tuple[AttackRunState, OutgoingSpeech | None]:
    """One tick of attack-run guidance: `(new_state, speech)`, `speech`
    `None` when nothing should be said this tick -- either because tier
    1 has no fresh relative observation to guide on (silence, holding the
    last spoken state, exactly as Stage 5 describes for a run flown before
    tier 2 exists), or because the change-driven rule says the rendered
    text has not moved enough to repeat itself (Decision 7).

    **No I/O, no store access beyond the `contact` handed in** -- this is
    the pure core `plans/attack-run/plan.md` Stage 3 calls for, testable
    against hand-built `OwnshipState`/`Contact` fixtures with no
    `ContactStore` in the loop at all."""
    alignment = _tier1_alignment(ownship, contact, now_sim)
    if alignment is None:
        return state, None
    azimuth_deg, elevation_deg = alignment
    speech = render_alignment(
        azimuth_deg,
        elevation_deg,
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    if not _should_emit(state, azimuth_deg, elevation_deg, speech.text):
        return state, None
    new_state = AttackRunState(
        last_spoken_azimuth_deg=azimuth_deg,
        last_spoken_elevation_deg=elevation_deg,
        last_spoken_text=speech.text,
    )
    return new_state, speech
