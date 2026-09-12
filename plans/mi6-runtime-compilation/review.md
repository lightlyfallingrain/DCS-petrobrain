### Review Summary

MI-6 implements the compact `RuntimeMissionUnderstanding` mapping exactly per the locked plan
(`plans/mi6-runtime-compilation/plan.md`, `48a2f5c`): `src/runtime/compact.py`/`compile.py`, the
`--emit-compact` CLI flag, and matching tests. Verified independently (not from the Implementer's
report): `ruff format --check`, `ruff check`, `mypy --strict src`, and `pytest -q` all pass
(111 tests), the change is scoped to `mission-interpreter/` plus the two `ROADMAP.md` files with no
stray edits, and no new files are left unstaged (working tree only has unrelated agent-memory
files, already committed history matches `git diff --stat` above).

Traced the four `player_intent` reconciliation paths (`ownship`, `purpose`/`task`,
`threat_{index}`) against MI-5's actual `questions.py`/`console.py` — the `Question.id` patterns,
`PlayerAnswer.question_kind`/`parsed` typing, and the index-stability assumption for
`threat_{index}` all genuinely match what MI-5 produces, not a guess at its shape. The confirmed
"epistemic status survives confirmation, only confidence is raised" invariant is real: traced
through `_reconcile_purpose_or_task`'s `answer.parsed is True` branch, `epistemic_status` is
carried through unchanged from `source.epistemic_status`, only `confidence`/`basis` change; the
named test (`test_task_confirmed_raises_confidence_without_upgrading_epistemic_status`) exercises
exactly that branch, not a shallow pass-through. `current_phase` is genuinely absent;
`phases`/`route`/`key_locations`/`priorities`/`intended_plan` all match the plan's resolved
decisions, verified against `compact.py`'s dataclass fields and an explicit test
(`test_priorities_and_intended_plan_and_role_keying_are_absent`) rather than trusting the
docstring. `compile.py`'s imports contain no `OllamaClient`/`WorldModelClient` reference — this is
genuinely a pure mapping. `write_compact` in `main.py` is a real, separately-testable unit (calls
`compile_current_mission`, not a stub), and `main()`'s untested live-network portion is the same
class of gap MI-5's own `main()` already carries, not a new one introduced here.

One real issue found, in the flagged judgment call (see below).

### Required Fixes

- **Purpose/task rejection collapses "never asked" and "asked-and-rejected" into the same `None`,
  losing real information a future BL-7 consumer would want.** `compile.py`'s
  `_reconcile_purpose_or_task` returns bare `None` both when MI-4 never populated the field and
  player_intent has no matching answer (`compile.py:124`), and when MI-4 guessed, the player was
  asked, and explicitly rejected the guess (`compile.py:140`). These are not the same fact: "the
  model never had a guess" vs. "the model guessed, and the player told it that guess is wrong" are
  different pieces of provenance, and only the second carries an active correction a dialogue layer
  might want to treat differently (e.g. never resurface that specific debunked value, or note the
  player actively corrected something). The plan's own prose anticipated a distinction ("clears...
  to `None` with `epistemic_status` `UNKNOWN`" — i.e., a `Tagged` wrapper carrying `UNKNOWN`, not a
  bare `None`), but the plan's field-type listing in the same document declared `Tagged[str] |
  None`, which cannot express that. The Implementer noticed and flagged the conflict rather than
  silently picking one reading — correct to surface it, but the chosen reading throws away the
  distinguishing information rather than preserving it. Recommended fix: retype `purpose`/`task` to
  `Tagged[str | None]` (always a `Tagged` wrapper, matching every other field on this dataclass) so:
    - never-populated-and-never-asked → `Tagged(value=None, epistemic_status="UNKNOWN", basis=())`
    - asked-and-rejected → `Tagged(value=None, epistemic_status=source.epistemic_status (or "FACT" for the player's act itself — pick one and document it), basis=(*source.basis, "player:rejected"))`
    — distinguishable from the first case by non-empty `basis` alone, without inventing a new
    epistemic vocabulary. This is the one-line/one-function change the plan's own Risks section
    already anticipated as cheap to revisit; not a structural rework. `test_purpose_rejected_clears_to_none`
    and the "stays none when never asked" test both need updating to assert on `.value` instead of
    identity-with-`None`.

### Optional Refinements

- `_reconcile_ownship`'s `passthrough` case formats `Ownship` as `f"{aircraft} ({flight})"`, and the
  `UNKNOWN` case falls back to an empty string display value rather than `None` — defensible (keeps
  the field a plain `Tagged[str]` instead of `Tagged[str | None]`), but a reader skimming JSON
  output could mistake `""` for a real (empty) callsign rather than "unknown." Worth a one-line
  comment at the `display = ... else ""` branch, or reusing the same `Tagged[str | None]` pattern
  proposed above for consistency, if that type is touched anyway. Optional — the `epistemic_status`
  field already disambiguates this for any consumer that checks it, which is the documented
  convention this whole module relies on.
- `_first_place_name` reaches into `name_matches[0]` as "best-effort," silently ignoring any
  ranking/relevance info a future world-model `PlaceMatch` might carry beyond ordinal position — the
  plan explicitly scoped this as good-enough for now, no action needed, just noting it as the
  obvious next knob if BL-7 finds the wrong place name is being surfaced.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — `compact.py`, `compile.py`, `questions.py`, `console.py`, `main.py`,
`test_runtime_compile.py`, `test_runtime_compact.py` (via its round-trip assertions surfaced
through `test_player_intent_main.py`), `test_player_intent_main.py`, both `ROADMAP.md` updates, and
`CLAUDE.md`'s new Structure bullet all read directly, not summarized from the Implementer's report.
Format/lint/mypy --strict/pytest re-run independently from `mission-interpreter/` (111 passed,
matching the reported count).
