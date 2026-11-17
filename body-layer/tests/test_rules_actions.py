"""`rules.actions` -- the allowlisted action registry's own Python-level
logic (`plans/speech-rules/plan.md` D5/D20): `ActionParam`'s widened
`kind`/`optional` shape, `Action.__post_init__`'s ordering guard, and
`_write_effector`'s own degrade-on-no-registry behaviour. The Lua-call
boundary (arity/type validation inside `_make_action_wrapper`) is
exercised through the real sandbox in `test_rules_engine.py` and
`test_rules_effector_action.py`, not re-tested here against a bare
Python call."""

from __future__ import annotations

import pytest

from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from rules.actions import ACTION_NAMESPACES, Action, ActionContext, ActionParam


def _ctx(**kwargs: object) -> ActionContext:
    return ActionContext(console=CrewConsole(store=ContactStore()), **kwargs)  # type: ignore[arg-type]


def test_effector_namespace_is_registered() -> None:
    assert "effector" in ACTION_NAMESPACES
    assert {a.name for a in ACTION_NAMESPACES["effector"]} == {"write"}


def test_action_rejects_a_required_param_after_an_optional_one() -> None:
    with pytest.raises(ValueError, match="follows an optional one"):
        Action(
            name="bad",
            params=(
                ActionParam(name="a", kind="str", optional=True),
                ActionParam(name="b", kind="str"),
            ),
            invoke=lambda ctx, args: {"ok": True, "reason": None},
        )


def test_write_effector_degrades_when_no_closure_is_wired() -> None:
    """A bare `ActionContext` with no `request_effector_write` (e.g.
    `--print-rules`'s own standalone load) must never crash -- it
    degrades the same way an unknown effector would."""
    from rules.actions import _write_effector

    result = _write_effector(_ctx(), {"name": "observ", "value": "on", "says": None})
    assert result == {"ok": False, "reason": "UNKNOWN_EFFECTOR"}


def test_write_effector_calls_the_injected_closure_with_validated_args() -> None:
    from rules.actions import _write_effector

    calls: list[tuple[str, str, str | None]] = []

    def fake_request(name: str, value: str, says: str | None) -> dict[str, object]:
        calls.append((name, value, says))
        return {"ok": True, "reason": None}

    ctx = _ctx(request_effector_write=fake_request)
    result = _write_effector(
        ctx, {"name": "observ", "value": "on", "says": "Observ on."}
    )
    assert result == {"ok": True, "reason": None}
    assert calls == [("observ", "on", "Observ on.")]


def test_write_effector_passes_through_the_closures_own_reason() -> None:
    """The action never invents its own reason beyond the no-closure
    case above -- an unknown effector/value is the closure's own call
    (`body.py`'s `_request_effector_write`, which knows the live
    registry), passed straight through."""
    from rules.actions import _write_effector

    def fake_request(name: str, value: str, says: str | None) -> dict[str, object]:
        return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}

    ctx = _ctx(request_effector_write=fake_request)
    result = _write_effector(ctx, {"name": "nope", "value": "on", "says": None})
    assert result == {"ok": False, "reason": "UNKNOWN_EFFECTOR"}


def test_write_effector_caps_says_at_the_same_length_say_enforces() -> None:
    """Stage 3d review Required Fix 3 (`plans/speech-rules/
    review-stage3d.md`) -- D20's own text promised `says` is "a
    free-text, length-capped string (the same cap `say()` already
    enforces)," but nothing enforced it until this fix. Same silent-
    truncation behaviour as `rules.engine._SinkHolder.say`'s own
    overflow handling, not a rejection."""
    from rules.actions import MAX_SAY_LEN, _write_effector

    calls: list[tuple[str, str, str | None]] = []

    def fake_request(name: str, value: str, says: str | None) -> dict[str, object]:
        calls.append((name, value, says))
        return {"ok": True, "reason": None}

    ctx = _ctx(request_effector_write=fake_request)
    overlong = "x" * (MAX_SAY_LEN + 50)
    result = _write_effector(ctx, {"name": "observ", "value": "on", "says": overlong})
    assert result == {"ok": True, "reason": None}
    assert calls == [("observ", "on", overlong[:MAX_SAY_LEN])]
    assert calls[0][2] is not None and len(calls[0][2]) == MAX_SAY_LEN


def test_write_effector_says_within_the_cap_is_untouched() -> None:
    from rules.actions import _write_effector

    calls: list[tuple[str, str, str | None]] = []

    def fake_request(name: str, value: str, says: str | None) -> dict[str, object]:
        calls.append((name, value, says))
        return {"ok": True, "reason": None}

    ctx = _ctx(request_effector_write=fake_request)
    result = _write_effector(
        ctx, {"name": "observ", "value": "on", "says": "Observ on."}
    )
    assert result == {"ok": True, "reason": None}
    assert calls == [("observ", "on", "Observ on.")]
