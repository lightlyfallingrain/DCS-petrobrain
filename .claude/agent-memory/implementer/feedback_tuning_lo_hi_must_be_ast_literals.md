---
name: tuning-lo-hi-must-be-ast-literals
description: body-layer tuning.real/whole/table lo=/hi= kwargs must be literal numbers, not names referencing another module constant -- generate_defaults.py's AST scan can't resolve them, and module-level execution order can independently break a forward reference anyway.
metadata:
  type: feedback
---

In `body-layer/src/perception/visibility.py` (and any other module using `tuning.real`/
`tuning.whole`/`tuning.table`), the `lo=`/`hi=` keyword arguments are read by
`body-layer/tools/generate_defaults.py` via `ast.parse` + a `_literal()` helper that only
understands `ast.Constant`, `ast.Tuple`/`ast.List`, `ast.Dict`, and `ast.UnaryOp(USub)` nodes.
Passing `lo=SOME_OTHER_CONSTANT` (an `ast.Name` node) raises
`ValueError: unsupported literal node` in the generator -- it never even gets to import the
module, since it scans source text/AST specifically to avoid importing every tunable module.

Separately, even without the generator, a forward name reference inside the same module would
raise `NameError` at import if the referenced constant is defined later in the file (Python
executes module-level assignments top to bottom; `Final` annotations do not defer evaluation).

**So when a tuning bound needs to match another constant's value** (e.g. a floor that must track
a fixed calibration constant defined elsewhere in the same file), write the bound as a literal
with a comment naming the source constant on both sides -- the constant that is the "source of
truth" should itself gain a comment saying copies of its value exist elsewhere and must be kept in
sync if it ever changes. Do not try to fix this by reordering the module so the referenced
constant comes first; reordering only solves the `NameError` half, not the AST-literal half, so it
buys nothing and costs a larger diff through any docstring prose that says "above"/"below".

This came up fixing `plans/configurable-constants/security.md`'s Recommended finding: `LOWRES`/
`MEDRES_ANGULAR_RADIUS_RAD`'s `lo` bounds needed to floor at `RESOLUTION_ANGULAR_RADIUS_RAD`
(0.00128), defined later in the same file. Used `lo=0.00128` with a comment naming
`RESOLUTION_ANGULAR_RADIUS_RAD` as the source, in both directions.

See also [[feedback_agent_memory_path]] for where this file itself must live.
