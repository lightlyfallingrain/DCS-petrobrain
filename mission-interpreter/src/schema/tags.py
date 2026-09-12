"""`Tagged[T]`: the one epistemic-tagging mechanism every `MissionUnderstanding`
field (and every `mission_phases`/`important_locations` list item) uses to
carry provenance alongside its value -- see the plan's "Epistemic tag
mechanism" section for why this shape was chosen over a per-field-name
dict-map (world-model's `StoredFeature` precedent): `MissionUnderstanding`
is a nested tree whose *list items* (not just its top-level fields) need
independent epistemic status, which a flat `dict[str, str]` keyed by field
name cannot express.

`FACT`/`OBSERVATION` are given stage-specific meanings for MI-3, a
deliberate, stated broadening of `PETROBRAIN_SYSTEM.md`'s "observation ==
perceived during the mission" wording (MI-3 runs entirely pre-mission) --
see `understanding.py`'s module docstring and the plan for the full
reasoning. `INFERENCE`/`ASSUMPTION` are declared here for the full intended
vocabulary (MI-4 onward) but MI-3 itself never produces them -- see
`tests/test_schema_understanding.py`'s invariant test.

`confidence` (MI-4, `plans/mi4-capable-model-synthesis/plan.md`) is a
separate axis from `epistemic_status`: `epistemic_status` says *how* a
value was arrived at (mechanically mapped vs. model-inferred), `confidence`
says *how sure* the model was, and only ever means anything once a model --
not a deterministic mapping -- produced the value. Defaults to `None` so
every already-shipped MI-1-MI-3 `FACT`/`OBSERVATION` `Tagged` value stays
valid without a confidence judgment that was never asked of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar

EpistemicStatus = Literal["FACT", "OBSERVATION", "INFERENCE", "ASSUMPTION", "UNKNOWN"]
Confidence = Literal["low", "medium", "high"]

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Tagged(Generic[T]):
    """Wraps one value with how it was arrived at.

    `basis` is a short, human-readable provenance trail (e.g.
    `("miz:unit.skill",)`, `("world_model:find_place_by_name",)`) -- always
    non-empty for anything MI-3 populates, since "how do you know" should
    never be silently blank even at the FACT tier.

    Round-trips through `dataclasses.asdict()` -> `json.dumps` the same way
    world-model's `src/api/server.py` `asdict()`-only convention does:
    `asdict` recurses through nested dataclasses regardless of `Generic`,
    since the wrapped `value` is still a concrete dataclass/primitive/tuple
    at runtime -- no custom `to_dict` needed.
    """

    value: T
    epistemic_status: EpistemicStatus
    basis: tuple[str, ...] = field(default=())
    confidence: Confidence | None = None
