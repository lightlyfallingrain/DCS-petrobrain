# MI-6 — Runtime compilation

- [x] **MI-6 — Runtime compilation.** #status/done Completed 2026-09-12
  (`plans/mi6-runtime-compilation/plan.md`, locked commit `48a2f5c`). **Delivered:** new
  `src/runtime/` package -- `compact.py`'s `RuntimeMissionUnderstanding` (`schema_version`,
  `theatre`, `ownship`, `purpose`, `task`, `phases`, `route`, `key_locations`,
  `expected_threats`, all still `Tagged[T]`-wrapped -- no epistemic metadata stripped) with two
  new small dataclasses (`CompactRoutePoint`, `CompactLocation`) dropping `WorldRef`'s heavy raw
  JSON down to `x`/`y`/`place_name`; `compile.py`'s `compile_current_mission`, a pure deterministic
  mapping (no model, no world-model call) that also folds MI-5's `player_intent` answers back into
  the fields they answered -- the actual substantive work of this stage, since nothing upstream
  ever did that reconciliation. Two documented corrections to
  `docs/concept/MISSION_INTERPRETER.md`'s `current_mission` example, both per the locked plan:
  **no `current_phase` field** (that needs a live aircraft-position state engine that doesn't exist
  yet -- MI-6 emits ordered `phases` boundaries for that future engine to walk instead) and **no
  `priorities`/`intended_plan` fields** (no data source anywhere in the pipeline -- declared gap,
  not fabricated). `key_locations` keyed by `ImportantLocation.id`, not a semantic role (no role
  classifier exists). `player_intent/main.py` gained an additive `--emit-compact PATH` flag.
  18 new unit tests covering all three reconciliation rules (ownship free-text fill, purpose/task
  confirm-raises-confidence-without-upgrading-status vs. reject-clears-to-`None` vs.
  fill-from-free-text vs. untouched-when-no-answer, threat confirm-keeps/reject-drops-from-compact-
  only), route/key-location place-name extraction, the absence of `priorities`/`intended_plan`/
  role-keying, and `asdict()`→`json.dumps` round-tripping. **Does not change what comes after** --
  no BL-7 consumer exists yet; wiring this artifact into body-layer is BL-7's own design decision,
  explicitly out of this plan's scope. This is the last planned Mission Interpreter stage per the
  parent plan's original stage list.
