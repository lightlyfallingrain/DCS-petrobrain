"""The one pure rule "category (+ AGL for helicopters) -> surface / air /
unknown" (`plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 1).

A new, small module rather than folding this into `association.py` or
`naked_eye_source.py`: both those sources, plus a dedicated test table, need
the rule, and neither source module should own the other's copy of it --
that would duplicate the enumeration and let the two drift apart silently.

The wsType enumeration below is **community-convergent, not yet read from
the installed `wsTypes.lua`** -- see
`aircraft-layer/research/2026-10-30-world-object-category-and-agl.md`
findings 3-5 for the cross-source corroboration and what remains unverified
live (whether a mission-editor-placed static unit reports `level1` 2 or 5;
whether every helicopter module reports `level2` 2).

`Flags.Static` (the mission-editor "placed without AI" flag) is **not**
read here and must never be used as the ground/air discriminator -- it is
an orthogonal placement-method flag, not a category (same research note,
finding 4). `wsType_Static` (level1 5) is included as surface regardless:
whatever lands there (airdromes, wrecks, mission-placed statics) is on the
ground either way, so the two readings of level1 5 never need to be told
apart for this rule's purposes.
"""

from __future__ import annotations

from typing import Final

import tuning

#: `Type.level1` values (wsType enumeration), per the research note above.
_WS_TYPE_AIR: Final[int] = 1
_WS_TYPE_GROUND: Final[int] = 2
_WS_TYPE_NAVY: Final[int] = 3
_WS_TYPE_WEAPON: Final[int] = 4
_WS_TYPE_STATIC: Final[int] = 5
_WS_TYPE_DESTROYED: Final[int] = 6

#: `Type.level2` value identifying a helicopter within `wsType_Air`.
_WS_TYPE_HELICOPTER: Final[int] = 2

#: A helicopter at or below this AGL is treated as a ground contact --
#: "landed or hovering a few metres up" (explore-notes Q4, user: "ground
#: rule"). Height only, no speed condition: the user's rule covers a low
#: hover as well as a touchdown, and a helicopter passing through a few
#: metres AGL is, for the pilot, at the ground in that moment.
HELI_SURFACE_AGL_MAX_M: Final[float] = tuning.real(
    #: How low a helicopter must be flying before Petrovich treats it as a
    #: ground contact (believed on the ground, not floating at its own
    #: flight altitude) rather than an air one. Raise it to call a higher
    #: hover "landed"; lower it toward 0 to require an actual touchdown.
    "perception.domain.HELI_SURFACE_AGL_MAX_M",
    10.0,
    lo=0.0,
    hi=50.0,
    status="judgement",
)


def surface_domain(
    category: int | None,
    subcategory: int | None,
    agl_m: float | None,
) -> bool | None:
    """`True` when `category`/`subcategory` (`WorldObjectSample.category`/
    `.subcategory`, i.e. `Type.level1`/`Type.level2`) describe a surface
    object, `False` for an air object, `None` when the category is
    missing, destroyed, or not one of the recognised values.

    **`None` is not itself a verdict** -- it is "domain unknown this poll",
    and every caller in this codebase treats it as air, today's flat model,
    bit for bit (Stage 1 fail direction: an un-redeployed `Export.lua`
    changes nothing rather than guessing). This function does not apply
    that fallback itself so a caller that *does* need to distinguish
    "known air" from "unknown" (logging, a one-shot warning) still can.

    `agl_m` is only consulted for a helicopter (`level1` Air, `level2`
    Helicopter) -- see `HELI_SURFACE_AGL_MAX_M`'s docstring. `None` AGL
    (no live verdict this poll, Stage 5's carrier not wired, or the
    candidate outside its wedge) resolves a helicopter to air, same
    unknown-stays-air posture as a missing category."""
    if category is None or category == _WS_TYPE_DESTROYED:
        return None
    if category in (_WS_TYPE_GROUND, _WS_TYPE_NAVY, _WS_TYPE_STATIC):
        return True
    if category == _WS_TYPE_WEAPON:
        return False
    if category == _WS_TYPE_AIR:
        if subcategory == _WS_TYPE_HELICOPTER:
            return agl_m is not None and agl_m <= HELI_SURFACE_AGL_MAX_M
        return False
    return None
