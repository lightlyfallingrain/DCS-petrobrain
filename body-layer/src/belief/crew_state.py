"""`CrewState` -- the one state type shared between the rule-category
dispatch gate (`rules.gates`, dispatch-time, `[[BL-17]]` D16) and the
state-dependent speech-to-text hint (Stage 3c, D17), per the plan's own
framing: "one shared state type, read by both the gate and the
speech-to-text hint... per the coordinator's own instruction."

`CrewConsole.current_crew_state()` builds this fresh from fields the
console already holds (`parked_flight_state`) on every call, never a
second source of truth -- see that method's own docstring.

A leaf module: this imports nothing from `belief.crew_console`/
`rules.*`, so it can be imported from either side without creating a
cycle (`rules.gates`'s own docstring explains why that matters)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CrewState:
    """`has_controls` mirrors `belief.ai_pilot_wheel.ParkedFlightState.
    parked_active`. `settling` is the takeover-settle window every
    flight handler used to check individually before D16 (`has_controls
    and held_heading is None`) -- promoted here to one place a gate can
    read instead of each action re-deriving it.

    `seat`/`hands_free`/`eyes_free` are named stubs, not guesses,
    pending `[[BL-B123]]`'s seat/hands/eyes-busy model -- they exist so
    a gate can read them once that milestone lands, and every gate this
    batch declares simply never sees anything but their stub values:
    `seat` is always `"copilot"` (the only seat Petrovich has ever
    occupied in this codebase); `eyes_free` is always `True` (nothing
    narrows it yet -- naked-eye scanning stays available while flying,
    per the goal check's Q8); `hands_free` is the one real derivation
    this batch needs -- `has_controls` already means his hands are on
    the stick, so flying implies `hands_free=False`."""

    has_controls: bool
    settling: bool
    seat: Literal["pilot", "copilot"]
    hands_free: bool
    eyes_free: bool
