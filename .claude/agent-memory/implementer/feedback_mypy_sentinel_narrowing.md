---
name: mypy-sentinel-narrowing
description: a bare object() identity sentinel defeats mypy --strict narrowing; use a dedicated marker class instead
type: feedback
---

A function returning `float | None | object` as a three-way sentinel (value / nil / "unresolved
expression, don't guess") cannot be narrowed by `mypy --strict` via `x is _SENTINEL` checks,
because `object` already subsumes every other arm of the union — mypy has nothing distinguishing
to narrow away. Every downstream use of the "resolved" value then fails `has-type`/`arg-type`
errors.

**Fix**: declare a dedicated zero-field marker class (`class _Unresolved: pass`, one module-level
instance) and type the return as `float | None | _Unresolved`. Check with `isinstance(x,
_Unresolved)`, not `x is _SENTINEL` — isinstance narrowing works reliably here, identity-check
narrowing against a bare-`object()` sentinel does not.

**Why**: found while adding a "settable value ranges" parser to
`body-layer/tools/generate_effector_registry.py` (2026-10-23 follow-up to `plans/
effector-sequences/plan.md`) — several Lua helper parameters (`arg_lim_`, `count_`, `gain_`, …)
needed a three-way parse (parsed value / `nil`-use-default / unparseable-expression-mark-unknown),
and the first cut used `_UNRESOLVED: Final[object] = object()` with `x is _UNRESOLVED` guards,
which produced ~20 mypy errors downstream (`"object" object is not iterable`, `Cannot determine
type of "lo"`, etc.) despite every runtime check being correct.

**How to apply**: any time a function needs a "could not resolve, don't guess" third state
alongside a real value and `None`, reach for a dedicated marker class from the start, not a bare
`object()` sentinel — it is free at runtime and the only form mypy's strict narrowing actually
tracks through subsequent code.
