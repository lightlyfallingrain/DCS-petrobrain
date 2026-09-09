## Review: BL-2.6 Stages 1-4 (classification-refinement)

Commits reviewed: `381e745` (Stage 1), `8a3c343` (Stage 2), `06b3ea8` (Stage 3), `0e305ea` (Stage 4).
Scope: mechanism only (lattice, fusion, event, surfacing) — no calibration (Stages 6/7/9 out of
scope for this pass, confirmed not touched).

### Review Summary

This is a clean, well-scoped implementation. Each commit does exactly what its stage promises,
docstrings are precise about *why* (not just what), and the plan's explicit decisions (naked-eye
reaching type at Stage 6, not this pass; `last_class_raw` staying the gate's input; events minted
in `tick` not `ingest`) are all honored correctly in code, not just in prose.

Verified directly against the code (not just the implementer's log):

- **Fold table matches plan §3 exactly.** Traced `fold_classification`/`_fold_higher`/
  `_fold_same_level`/`_collapse` by hand against refine/reinforce/hold/contradict, including the
  edge cases: unresolvable-parent always refines (never contradicts), same-class-different-type
  collapses to class, different-class collapses to presence, lower incoming level is a pure hold
  (held survives untouched, no confidence/established_sim mutation).
- **`last_class_raw` untouched in meaning** — still set unconditionally in `record()`/
  `from_percept()` from the raw percept string, still the sole input to
  `association_over_time`'s gate. `Contact.classification` is the new, separate folded field.
  `tools.py`/`console.py` read `classification`, never `last_class_raw`, per plan.
- **`classification_level` defaults preserve every existing construction site.**
  `Observation.classification_level: int = 2` and `Percept.classification_level: int = 2` both
  default to `SpecificityLevel.CLASS`'s value; `mypy --strict` and the full suite confirm nothing
  broke.
- **No `perception/` → `belief/` import introduced.** Grepped `src/perception/` for `from belief`/
  `import belief` — zero hits. `classification_level` is a bare `int` on `Observation`/`Percept`,
  exactly as the plan requires; the enum only appears once the value crosses into `belief/`.
- **Event minted in `tick()`, not `ingest()`, after the lifecycle event** — read `ContactStore.tick`
  directly: lifecycle event appended and `last_emitted_certainty` updated first, *then*
  `classification_event()` compared and appended, per contact. Matches plan §4's ordering
  requirement.
- **`Event` fields default to `None`** — `previous_classification`, `classification`, `direction`
  are all `X | None = None` on the frozen dataclass; every pre-existing `Event(...)` construction
  site in the three lifecycle-event tests still compiles unchanged.
- **`format_event_for_overlay` only branches on the new kind** — the `if event.kind ==
  CONTACT_CLASSIFICATION_CHANGED:` branch is additive; the fallthrough line for every other kind is
  byte-for-byte what it was before this branch, confirmed by reading the diff (no lines touched
  outside the new `if`).
- **Stage 6 boundary respected.** `naked_eye_source.py` declares `classification_level=2`
  unconditionally (one call site, no tier branching); `perception/visibility.py`,
  `tests/test_visibility.py`, and `tests/test_naked_eye_source.py` all show a zero-line diff across
  the whole Stage 1-4 range (`git diff --stat 1dd2d54..0e305ea` on those three paths is empty).
  Tier thresholds are genuinely untouched, as the plan's "mechanism and calibration never share a
  commit" rule requires.
- **Test coverage matches the plan's Affected Modules list** — `test_classification.py` (new,
  19 tests: lattice ordering, `parent_class_of`, fold table including lockout),
  `test_contacts.py`, `test_events.py`, `test_tools.py`, `test_console.py`,
  `test_cross_channel_fusion.py`, `test_decay.py` all extended as listed; nothing extra, nothing
  missing from that list.

### Verification commands (run directly, body-layer venv)

- `ruff format --check src tests` — pass (42 files already formatted)
- `ruff check src tests` — pass, no findings
- `mypy src --strict` — pass, no issues in 21 source files
- `pytest tests -q` — **238 passed**, matching the implementer's reported count exactly
- `git status --short` — clean; all Stage 1-4 files are committed, nothing left unstaged
- No debug prints or TODO/FIXME/XXX markers introduced in the changed files (one pre-existing
  legitimate `print()` in `console.py`'s own output-writing path, unrelated to this change)

### Required Fixes

None.

### Optional Refinements

- `implementation.md`'s "Notable Discoveries" note that `FoldOutcome.contradicted` is used only for
  the lockout timestamp, and `classification_event` re-derives direction independently from
  before/after level+value. This is a reasonable simplification (confirmed correct by hand-tracing
  `_collapse`'s guarantee that a genuine same-level disagreement always produces a strictly lower
  level), but it does mean two different code paths encode "was this a contradiction" using two
  different definitions that happen to agree by construction rather than by shared logic. Worth a
  one-line comment cross-referencing the other, if a future stage ever changes `_collapse`'s
  collapse target — not blocking now, since both are separately tested.
- `_classification_facts` in `tools.py` renders `level` via `classification.level.name.lower()`
  (`"unknown"`/`"presence"`/`"class"`/`"type"`). Fine as-is; just flagging that this string is now
  part of the brought-forward-toward-§3.4 tool surface, so a future rename of `SpecificityLevel`'s
  members would be a silent API break for any brain-facing consumer — not this pass's concern, but
  worth a note when BL-5 freezes the surface.

### Verdict

**APPROVED**

Ready to proceed to Stage 5 (live acceptance) — this needs the user in the cockpit, not another
Implementer pass. No required fixes; the two optional notes above are forward-looking and do not
block.

### Review Confidence

Full read. Read the plan and implementation log in full; read every Stage 1-4 diff hunk directly
(not just the implementer's summary); hand-traced the fold table's edge cases against the code;
independently ran and confirmed all four verification commands and the "Stage 6 boundary" claim via
`git diff --stat`.
