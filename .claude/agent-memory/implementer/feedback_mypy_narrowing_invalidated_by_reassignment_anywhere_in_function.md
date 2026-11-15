---
name: mypy-narrowing-invalidated-by-reassignment-anywhere-in-function
description: reassigning a local variable inside one branch can invalidate mypy's attribute narrowing of that same-named variable in an unrelated, earlier-returning branch of the same function
type: feedback
---

`mypy --strict`'s narrowing of `x.attr` (from an earlier `if x.attr is None: return ...` guard)
is invalidated by *any* reassignment `x = ...` that appears later in the function body textually —
even when that reassignment sits inside an `if` branch that always `return`s, and even when the
code reading the narrowed attribute is in a completely different, sibling branch that the
reassigning branch can never reach. mypy does not prove the two branches are mutually exclusive
before invalidating; it treats the reassignment as poisoning the variable's narrowed type for the
rest of the function.

**Found in `belief/optic_policy.py`'s `_decide_without_guidance`** (`plans/
expected-area-check/plan.md` Stage 1, look-follow): the top of the function has
`if state.phase_started_sim is None: return ...`, narrowing `state.phase_started_sim` to `float`
for everything after. Adding `state = replace(state, search_pattern_steps=..., ...)` inside the
`GLASSING` branch (itself gated behind `if state.phase is OpticPhase.GLASSING:`, always returning
before falling through) made mypy report `Unsupported operand types for - ("float" and "None")`
at **three unrelated sites in the `SCANNING`-at-home branch further down** — a branch the
`GLASSING` reassignment can never reach, and which never itself reassigns `state`.

**Fix**: bind the reassignment to a differently-named local (`glassing_state = state`, then
`glassing_state = replace(glassing_state, ...)`) instead of reusing the parameter name. This
contains the narrowing loss to the one branch that actually needs the new value, and the
unrelated branch keeps its original top-of-function narrowing intact.

**How to apply**: before reassigning a function parameter or an already-narrowed local inside one
branch of a long multi-branch dispatch function, check whether *other* branches of the same
function read a narrowed attribute of that same name. If so, bind the branch-local mutation to a
new name rather than the original — cheaper than re-asserting the narrowing at every downstream
read site, and the new name also documents that this branch's value diverges from the function's
own contract.
