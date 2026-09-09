---
name: pb2-stage4-tools-console
description: PB-2 Stage 4 (belief.tools/console) implementation notes -- extra tool functions, mypy narrowing gotcha, grep-based structural test trap.
metadata:
  type: project
---

Stage 4 of `plans/pb2-contact-memory/plan.md` built `body-layer/src/belief/tools.py` and
`console.py`. Notable, non-obvious things for future BL-x work touching this layer:

- The task listed exactly four `tools.py` functions (`get_contacts`/`describe_contact`/
  `get_contact_history`/`find_contact`, mirroring §3.3), but also required `console.py`'s
  `watch`/`unwatch`/`stats` commands to have zero belief logic of their own. Resolved by adding
  `watch_contact`/`unwatch_contact`/`get_stats` to `tools.py` too, even though their real §3.3
  equivalents (`set_attention`, `get_attention_state`) are BL-4/BL-5 work. If a future stage's
  instructions name a fixed tool list but also imply a console/API command with no home, check
  whether the same "no logic outside tools.py" constraint applies before improvising.
- Stage 1's structural test (`test_belief_source_never_references_derived_world_position`)
  greps every `belief/*.py` file's raw source **text** (docstrings included) for the literal
  substring `"derived_world_position"`, except `percept.py`. Explaining the identity invariant
  in a new module's docstring by naming that field directly will trip this test. Describe the
  field instead (e.g. "`Observation`'s DCS ground-truth position field").
- mypy narrows *repeated* attribute-access expressions (e.g. `store.contacts[0].attention`) as
  if they were a stable binding: asserting `== "watch"` then later asserting `== "normal"` on the
  same unbound expression produces a `comparison-overlap` error, even though the underlying
  object legitimately changed in between (e.g. via a mutating call). Bind to a local variable at
  each point instead of re-evaluating the same expression twice in one test.
- `Contact` gained `attention`/`attention_source` fields with defaults (`"normal"`/`None`) --
  safe to add fields with defaults to a dataclass all existing tests construct via keyword args
  or `Contact.from_percept`; no Stage 0-3 test needed touching.
- `logger.py`'s `--console` REPL wiring (background poll thread + foreground stdin loop reading
  `ConsolePerceptionRunner.last_t_sim`) was left untested, consistent with the project's existing
  "`main()`'s CLI wiring is untested by design" posture -- only the new `last_t_sim` field
  (real logic on the tested `ConsolePerceptionRunner` class) got a test.
