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
    parked_active`. `held_heading`/`held_altitude`/`held_speed` mirror
    that same state's own `held_*` fields -- the AI's own current values,
    read-only here, same as there.

    **Per-parameter, not one shared `settling` bool** (`[[BL-17]]` Stage 4,
    `plans/speech-rules/review-stage3b.md` Required Fix 1): Stage 3b's
    original `settling` field (`has_controls and held_heading is None`)
    was claimed to be "the same proxy every flight handler already checks
    today" -- false for five of the seven ported commands, which each
    check a *different* `held_*` field (or, for the absolute-set forms,
    none at all). Carrying the three raw values lets each category's own
    gate function (`rules.gates`) decide which field it needs, rather
    than collapsing them into one proxy that only happens to be correct
    for the one rule (`turn_heading_relative`) that shipped before this
    was caught.

    `seat`/`hands_free`/`eyes_free` are named stubs, not guesses,
    pending `[[BL-B123]]`'s seat/hands/eyes-busy model -- they exist so
    a gate can read them once that milestone lands, and every gate this
    batch declares simply never sees anything but their stub values:
    `seat` is always `"copilot"` (the only seat Petrovich has ever
    occupied in this codebase); `eyes_free` is always `True` (nothing
    narrows it yet -- naked-eye scanning stays available while flying,
    per the goal check's Q8); `hands_free` is the one real derivation
    this batch needs -- `has_controls` already means his hands are on
    the stick, so flying implies `hands_free=False`.

    `commands_ready` (BL-16 fail-loud, 2026-11-20) mirrors `body.
    ConsolePerceptionRunner.command_reset_confirmed` -- `False` only for
    the brief process-start window (or the degenerate case where it
    never confirms at all) before `Export.lua`'s own seq-carrying
    channels have echoed this process's reset epoch back. Defaults
    `True` so every existing construction site (a bare `CrewState(...)`
    with no opinion on reset state) reads as ready, same as it always
    has."""

    has_controls: bool
    held_heading: float | None
    held_altitude: float | None
    held_speed: float | None
    seat: Literal["pilot", "copilot"]
    hands_free: bool
    eyes_free: bool
    commands_ready: bool = True
