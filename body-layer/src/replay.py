"""BL-0 replay harness.

Feeds a recorded (or synthetic) sequence of ownship telemetry frames through
any `PerceptionSource` implementation's `poll()`, in `t_sim` order, with no
live DCS/aircraft-layer connection required. This is what makes every later
body-layer milestone testable offline (`plans/body-layer/plan.md` §2's
"hard design requirement" that everything be replayable from a recorded
observation stream) and is `plans/pb1-perception-logger/plan.md` stage 6's
planned venue for the interface-swap smoke test (not built by this plan --
that needs a second concrete `PerceptionSource` to swap in).

`PerceptionSource.poll()` only takes `(now_sim, ownship_state)` -- a
concrete source fetches whatever tier-specific data it needs (a Petrovich
feed string, or the aircraft layer's `world_objects` endpoint) on its own,
typically through an injected client a caller can swap for a fixture-backed
fake. This harness therefore only has to drive the ownship half of the loop;
it does not need to know about `world_objects` or any other tier-specific
payload shape.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

from perception.source import Observation, OwnshipState, PerceptionSource


def load_ownship_frames(path: Path) -> list[OwnshipState]:
    """Load a JSON array of ownship telemetry frames (the aircraft-layer
    `GET /telemetry/latest` wire shape, one object per frame -- see
    `aircraft-layer/src/schema/__init__.py`) and convert each to an
    `OwnshipState`, sorted by `t_sim`."""
    raw = json.loads(path.read_text())
    frames = [OwnshipState.from_telemetry_dict(item) for item in raw]
    return sorted(frames, key=lambda frame: frame.t_sim)


def replay(
    source: PerceptionSource, frames: Sequence[OwnshipState]
) -> Iterator[tuple[OwnshipState, list[Observation]]]:
    """Drive `source.poll()` once per frame, in `frames`' given order,
    yielding each frame's `OwnshipState` alongside whatever `Observation`s
    that poll produced. Does not sort or otherwise reorder `frames` --
    callers wanting `t_sim` order should pass frames already sorted (e.g.
    `load_ownship_frames`'s output)."""
    for frame in frames:
        yield frame, source.poll(frame.t_sim, frame)
