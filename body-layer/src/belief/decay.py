"""Per-attribute decay half-lives and the `certainty` lifecycle ladder --
`plans/pb2-contact-memory/plan.md` Stage 2, implementing `docs/concept/
PETROBRAIN_RUNTIME.md`'s "Uncertainty and memory decay" section (identity
slow, exact position fast, general area medium/slow, motion medium) as one
table, per that section's own framing: "those differences should come from
structured confidence, not improvised wording."

The concept doc does not name concrete seconds or a closed `certainty` enum
-- both are placeholder judgment calls made here, once, per the plan's
explicit instruction ("what matters structurally is that they live in one
table"; Stage 1's `SCOPE_UNCERTAINTY_M`/`GATE_GROWTH_RATE_MPS` in
`association_over_time.py` are the precedent for this kind of documented,
revisitable constant).

Only two of the four half-lives (`POSITION_HALF_LIFE_S`, and
`LOST_THRESHOLD_S` derived from it) are actually consumed by `certainty_of`
below -- `Contact` does not yet track a separate identity/general-area/
motion attribute to decay independently (that is BL-3/BL-4 territory: world
enrichment adds `general_area`, attention adds a motion estimate). The other
three constants are declared now so the *one table* this module's docstring
promises is complete from the start, and so BL-3/BL-4 extend this table
rather than starting a second one elsewhere (the plan's "Complicates BL-4"
second-order-effect note).

All functions here are pure functions of `(contact, now_sim)` -- no ticker,
no mutation, no wall-clock. `ContactStore.tick` (`contacts.py`) is the only
caller that turns `certainty_of`'s result into a state change.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from belief.contacts import Contact

#: Slowest-decaying attribute: what a contact *is*. A crew member does not
#: forget "that was a BMP" on the timescale it takes the BMP to drive out of
#: sight -- identity should long outlive position confidence. Not yet
#: consumed (no per-attribute identity confidence field exists on `Contact`
#: yet); declared for BL-3/BL-4 to extend this table into, per the plan's
#: "one table, nowhere else" rule for the certainty/decay constants.
IDENTITY_HALF_LIFE_S: Final[float] = 600.0

#: Fastest-decaying attribute: the exact perceived position. Chosen as the
#: order-of-magnitude time a ground vehicle needs to move roughly its own
#: uncertainty radius at `association_over_time.GATE_GROWTH_RATE_MPS`
#: (20 m/s) -- i.e. "trust the exact spot for about half a minute, then
#: start hedging." This is the one half-life `certainty_of` below actually
#: uses to separate "tracked" from "estimated".
POSITION_HALF_LIFE_S: Final[float] = 30.0

#: Medium decay: which way it was moving. Slower than exact position (a
#: heading estimate stays plausible longer than a point position does) but
#: faster than "roughly where it is" -- per the concept doc's own ordering.
#: Not yet consumed (no motion estimate exists on `Contact` yet; BL-4).
MOTION_HALF_LIFE_S: Final[float] = 60.0

#: Medium/slow decay: the general area, independent of the exact point.
#: Slower than motion -- "somewhere near that village" stays true long after
#: "moving north at that exact spot" has gone stale. Not yet consumed (no
#: `general_area` field exists on `Contact` yet; BL-3 adds it).
GENERAL_AREA_HALF_LIFE_S: Final[float] = 180.0

#: The window within which a contact counts as "currently being perceived"
#: rather than merely "recently tracked" -- deliberately close to one
#: polling interval (`body-layer/CLAUDE.md`'s "at 1 Hz" note), since
#: `certainty_of` has no direct signal for "was this contact in the most
#: recent poll's observation batch," only elapsed time since its last
#: recorded observation.
OBSERVED_WINDOW_S: Final[float] = 5.0

#: Past this much elapsed time since last observed, a contact is considered
#: lost outright rather than merely stale. Set to 4x `POSITION_HALF_LIFE_S`
#: -- long enough that "estimated" (stale-but-plausible) has had room to mean
#: something distinct from "tracked", short enough that a contact does not
#: linger indefinitely as "estimated" once the crew has plainly lost it.
LOST_THRESHOLD_S: Final[float] = 120.0

#: The certainty lifecycle ladder. Four levels, evaluated top-down in
#: `certainty_of` (first match wins) rather than as independent predicates:
#:
#:   observed  -- currently being perceived (within `OBSERVED_WINDOW_S`).
#:   tracked   -- recently seen; position still trustworthy (within
#:                `POSITION_HALF_LIFE_S`).
#:   estimated -- position has decayed past its half-life but the contact is
#:                not yet given up on (within `LOST_THRESHOLD_S`).
#:   lost      -- past `LOST_THRESHOLD_S` since last observed.
#:
#: `docs/concept/PETROBRAIN_RUNTIME.md`'s "Uncertainty and memory decay"
#: section names the four *wordings* this ladder must support ("I see him." /
#: "I think he was..." / "Last saw him..." / "I lost him.") without naming
#: the enum itself -- this is that enum, derived to match.
Certainty = Literal["observed", "tracked", "estimated", "lost"]


def certainty_of(contact: Contact, now_sim: float) -> Certainty:
    """The contact's current `Certainty`, evaluated top-down against elapsed
    time since `contact.last_seen_sim`. Pure -- does not read or write
    `contact.last_emitted_certainty`; that comparison is `events.
    lifecycle_event_kind`'s job, not this function's."""
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    if elapsed_s <= OBSERVED_WINDOW_S:
        return "observed"
    if elapsed_s <= POSITION_HALF_LIFE_S:
        return "tracked"
    if elapsed_s <= LOST_THRESHOLD_S:
        return "estimated"
    return "lost"


def position_confidence(contact: Contact, now_sim: float) -> float:
    """Numeric position confidence, `(0, 1]`, exponentially decaying with a
    half-life of `POSITION_HALF_LIFE_S` since `contact.last_seen_sim` --
    BL-3's (`plans/bl3-world-enrichment/plan.md` step 2) numeric counterpart
    to `certainty_of`'s discrete ladder above, and the one number `belief.
    enrichment`'s `position`/`semantic`/`motion_when_seen` fields all key
    off. Pure, like every other function in this module -- no ticker, no
    mutation, no wall-clock."""
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    return math.pow(0.5, elapsed_s / POSITION_HALF_LIFE_S)
