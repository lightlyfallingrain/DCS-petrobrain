"""Tests for `belief.threat` -- `plans/watch-reporting/plan.md` Stage 4.

Exercises the real `body-layer/data/threat_envelopes.json` payload (no
fixture double), since the whole point of this module is what that real
data does under the null-handling/rollup rules -- a synthetic table would
not catch a real S-300/S-125/SA-2-shaped surprise."""

from __future__ import annotations

from belief.classification import ClassificationBelief, SpecificityLevel
from belief.threat import _CLASS_ENVELOPES, _HEADER, envelope_for


def _belief(
    value: str | None, level: SpecificityLevel, confidence: float = 0.5
) -> ClassificationBelief:
    return ClassificationBelief(
        value=value, level=level, confidence=confidence, established_sim=0.0
    )


def test_unknown_level_has_no_envelope() -> None:
    assert envelope_for(_belief(None, SpecificityLevel.UNKNOWN)) is None


def test_presence_level_has_no_envelope() -> None:
    """A dot has no envelope -- the no-omniscience boundary in one line."""
    assert envelope_for(_belief("ground", SpecificityLevel.PRESENCE)) is None


def test_module_imports_nothing_from_perception_source() -> None:
    """The signature is the guard -- `belief.threat` cannot be handed
    ground truth because it does not accept the type that carries it.
    This asserts the module's own *import lines* never name the
    ground-truth module, per the plan's own required regression test
    (prose mentioning it, e.g. in this module's docstring, is fine)."""
    import inspect
    import re

    import belief.threat as threat_module

    import_re = re.compile(r"^(import [\w.]+|from [\w.]+ import [\w., ]+)$")
    import_lines = [
        line
        for line in inspect.getsource(threat_module).splitlines()
        if import_re.match(line)
    ]
    assert import_lines  # sanity: the module does have real imports
    assert not any("perception.source" in line for line in import_lines)
    assert not any(
        line.startswith("from perception import") and "source" in line
        for line in import_lines
    )


def test_type_level_resolves_a_real_row() -> None:
    envelope = envelope_for(_belief("S-300PS", SpecificityLevel.TYPE))
    assert envelope is not None
    assert envelope.range_max_m > 70000.0
    assert envelope.range_min_m > 0.0


def test_type_level_with_no_matching_row_returns_none() -> None:
    """No fallback to the class rollup -- an identified type absent from
    the extracted table produces no warning, per module docstring."""
    assert envelope_for(_belief("T-72", SpecificityLevel.TYPE)) is None


def test_class_level_returns_the_derived_worst_case() -> None:
    """`_CLASS_ENVELOPES` is derived, not hand-written -- whatever it
    resolved to at import time is what this must match, not a hand-copied
    number that could silently drift from the join."""
    for op_class, expected in _CLASS_ENVELOPES.items():
        result = envelope_for(_belief(op_class, SpecificityLevel.CLASS))
        assert result == expected


def test_class_level_with_no_rows_returns_none() -> None:
    """A class with no threat rows at all (ground armour/trucks -- 4b's
    own reasoning: no envelope worth modelling against a helicopter beyond
    gun range) produces no warning."""
    assert envelope_for(_belief("OP_ARMORED", SpecificityLevel.CLASS)) is None
    assert envelope_for(_belief("OP_TRUCK", SpecificityLevel.CLASS)) is None


def test_class_level_envelope_has_no_inner_hole_or_floor() -> None:
    """Decision 4c: the class-level envelope is conservative on every
    axis, not just range -- a member's own protective inner hole or
    altitude floor must not be inherited at class level."""
    for envelope in _CLASS_ENVELOPES.values():
        assert envelope.range_min_m == 0.0
        assert envelope.alt_min_m == 0.0


def test_the_sa5_entry_is_dropped_entirely() -> None:
    """S-200/SA-5 has every numeric field null in the source table --
    `range_max_m is None` means the entry is dropped at load, so it can
    never resolve at type level."""
    assert envelope_for(_belief("S-200", SpecificityLevel.TYPE)) is None


def test_sa2_keeps_its_real_reach_despite_null_inner_bounds() -> None:
    """4f-i's own worked example: S-75/SA-2 has a null `range_min_m` and a
    null `alt_min_m` but a real ~51.9 km `range_max_m` -- must resolve
    with `range_min_m=0.0`/`alt_min_m=0.0` (the conservative direction),
    not be thrown away entry-wide by a blanket "any null -> silence"
    rule."""
    envelope = envelope_for(_belief("S-75 Devina", SpecificityLevel.TYPE))
    assert envelope is not None
    assert envelope.range_min_m == 0.0
    assert envelope.alt_min_m == 0.0
    assert envelope.range_max_m > 50000.0


def test_header_carries_the_payload_own_provenance() -> None:
    """`threat.py` reads the JSON's own header rather than restating it as
    a literal -- this pins that the header is actually read through, not
    hand-copied and left to drift."""
    assert "hoggitworld" in str(_HEADER["source"]).lower()
    assert "community wiki" in str(_HEADER["provenance"]).lower()
