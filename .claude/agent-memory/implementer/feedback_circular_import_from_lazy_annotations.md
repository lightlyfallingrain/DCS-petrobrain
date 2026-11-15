---
name: circular-import-from-lazy-annotations
description: mypy --strict can pass clean on a real runtime circular import in this codebase, because `from __future__ import annotations` makes every type hint a lazy string -- always run the test suite (which actually executes imports) after adding a cross-module import, not just mypy
metadata:
  type: feedback
---

On `BL-B111`, adding `from belief.optic_policy import LOOK_SWEEP_SIGMA` to
a new `belief/expected_area.py` (imported at runtime by `belief/contacts.py`)
passed `cd body-layer && .venv/bin/mypy src` with zero errors, but broke
every test that imports `belief.contacts` at collection time:
`belief.contacts → belief.expected_area → belief.optic_policy →
belief.enrichment → belief.contacts` (the last edge already existed:
`enrichment.py` does `from belief.contacts import Contact, ContactStore` at
module level). `ImportError: cannot import name 'Contact' from partially
initialized module`.

**Why mypy missed it**: every `.py` file in this codebase (and most Python
projects) carries `from __future__ import annotations`, which makes every
type annotation a lazy string mypy resolves structurally, without needing
the runtime import graph to actually resolve. mypy is checking *types*, not
*executing imports in order* -- a cycle that is fine for the type checker can
still deadlock the Python import machinery at runtime.

**How to apply**: whenever a new module import is added to a file that is
itself imported by something foundational (a `Contact`/`ContactStore`-style
core type module), run the actual test suite (or at minimum
`python -c "import belief.contacts"`) before trusting a clean `mypy --strict`
run. `mypy` is necessary, not sufficient, for import-cycle correctness in a
codebase using lazy annotations.

**The fix pattern already exists in this codebase and is worth copying
directly**: `belief.optic_policy.LOOK_SWEEP_SIGMA`'s own docstring already
documents *not* importing `belief.association_over_time.GATE_SIGMA_THRESHOLD`
despite sharing a value, because the two constants answer different
questions. The same "declare independently, with a comment citing the
sibling and why" move fixes an import cycle for free when the only thing you
actually need from the cyclic import is a numeric constant's *value*, not
its live-updatable binding.

**Also useful**: when a new module (`expected_area.py`) is imported by a core
module (`contacts.py`) specifically so the core module can call into it, but
the new module's own type signatures want to reference the core module's
types (`Contact`), put that import under `if TYPE_CHECKING:` in the new
module. With `from __future__ import annotations` already in force, this
costs nothing at runtime (annotations are never evaluated) and makes the
import direction strictly one-way at runtime, which is what actually matters
for avoiding the cycle.

See [[tautological-trigger-precondition]] for the other finding from the same
session.
