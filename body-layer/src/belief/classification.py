"""The classification specificity lattice -- `plans/classification-refinement/
plan.md` Stage 1 (this module's creation, a pure move) and Stage 2 (the
lattice + fusion mechanism added on top).

**Stage 1 content: `_op_class_of`/`class_compatibility`, re-homed from
`belief.association_over_time` verbatim.** They move here because Stage 2
would otherwise create a second class-resolution function in this module --
the lattice's `parent_class_of` needs exactly the same ED-vocabulary
resolution `_op_class_of` already does. `association_over_time.py` imports
both names from here so every existing caller and test import path
(`from belief.association_over_time import class_compatibility`) keeps
working unchanged. See that module's own docstring for the full rationale
behind the three-valued compatibility result -- unchanged by this move.
"""

from __future__ import annotations

from typing import Literal

from perception import object_model

ClassCompatibility = Literal["compatible", "unknown", "incompatible"]


def _op_class_of(classification_raw: str) -> str | None:
    """Resolve `classification_raw` (either an already-bucketed naked-eye
    `OP_*` string, or scope/hybrid free text) to an `OP_*` bucket, or `None`
    if unknown. See module docstring."""
    if classification_raw.startswith("OP_") and (
        classification_raw != object_model.DEFAULT_OP_CLASS
    ):
        return classification_raw
    profile = object_model.profile_for(classification_raw)
    if profile.op_class == object_model.DEFAULT_OP_CLASS:
        return None
    return profile.op_class


def class_compatibility(a_raw: str, b_raw: str) -> ClassCompatibility:
    """Three-valued class compatibility between two `classification_raw`
    strings. See module docstring."""
    a_class = _op_class_of(a_raw)
    b_class = _op_class_of(b_raw)
    if a_class is None or b_class is None:
        return "unknown"
    return "compatible" if a_class == b_class else "incompatible"
