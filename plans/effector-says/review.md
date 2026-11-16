### Review Summary

Reviewed `feature/effector-says` tip `cd293ce1` (commits `5151e837`..`28d97c3d` against base
`110067d0`; the later merge of `main`, bringing in unrelated tooling commits, confirmed to carry
no actual `BL-B119` ID collision after the merge — `main`'s own renumbering of the security
NaN-clamp item from `BL-B119` to `BL-B120` landed before this branch's commits, so both sides
converge on one `BL-B119.md`).

Plan has no `U<n>` ids (small plan, no Architect pass) — `accepted-items-ledger.sh` produced no
output, as expected for this shape; I read the "Decisions, verbatim" section by hand instead. All
three pilot decisions (Q1: speak even when already in position; Q2: an attack-run start that
triggers the weapons-arm sequence also speaks "weapons armed"; Q3: the line now arrives when the
row runs, as a confirmation) are built, not deferred.

**Mechanism.** `effector_sequences._strip_petrovich_says` strips the pilot's quoting at parse
time; `effector_engine._speak_text` sentence-cases and punctuates at speak time; `EffectorRunState.
spoken: tuple[str, ...]` is a `replace()`-only field appended to at the two completion points
(R12 self-check match, successful write) and returned wholesale each `advance()` call — the engine
stays pure, never calls speech. `crew_console.drain_effector_speech` drains it through `_print`
(no `bypass_gate`), so the normal intercom/PTT gating and callout scheduling apply — verified by
reading `_print`'s own contract, not just the call site. `body.py` calls the drain once per poll,
immediately after `advance_effectors`. The four handlers (`_handle_observ_on/off`, `_handle_
weapons_armed/safe`) now return `[]` on their accepted path; `_handle_observ_on`'s readiness
refusal and `drain_atgm_engage`'s "Observ on, wait." are untouched, as the plan required.

**Verified by mutation, not just by reading** (per this role's own standing habit): commented out
the `drain_effector_speech` call in `body.py` and re-ran
`test_weapons_armed_sequence_row_speaks_through_the_real_poll_loop` — it failed (`0 == 1`),
confirming the wiring is real and the one true end-to-end test actually exercises it, not just the
engine's own unit tests. Restored before finishing.

**Regression guard.** `test_dispatched_command_tokens_all_return_something` was correctly
identified as broken by this change (not named in the plan's own Tests section) and fixed by
adding the four tokens to `NO_RETURN_VALUE_COMMAND_TOKENS` and setting `sight_ready = True` in that
one test, exactly per this role's own memory note on that guard
(`feedback_handler_return_contract_regression_guard.md`) and the implementer's own matching memory
entry. The stale "always returns a one-line readback" comment next to `DISPATCHED_COMMAND_TOKENS`'s
four entries was corrected rather than left to rot.

**Comment pruning.** The dated user-direction quote (2026-10-21, "weapons armed/safe" vs. "weapons
on") was preserved verbatim in `_handle_weapons_armed`'s docstring, reworded only to say it now
governs the sequence file's cell text rather than a literal return value — correct handling of a
durable, dated line per the pruning rule.

**Design choice** (state field over widened return type) matches this role's own memory note and
the implementer's matching entry; confirmed the reasoning (~40 call sites in
`test_effector_engine.py`) and that `EffectorRunState.spoken` resets to `()` with every other field
via the existing `field(default_factory=EffectorRunState)` mission-reset mechanism — a dedicated
one-line test exists for it, same shape as the neighbouring `assumed_writes` test.

**No new behaviour-affecting constant** was introduced (checked the diff for bare literals/new
timing values) — the tuning-pattern checklist does not apply here.

**No voice-vocabulary change** — this feature changes what is spoken, not what is recognised, so
the `vocabulary.py`/STT-prompt check does not apply.

**Scope fit.** Touches exactly `effector_sequences.py`, `effector_engine.py`, `crew_console.py`,
`body.py`, and their tests, plus the roadmap/plan/memory bookkeeping — no drift beyond the plan's
stated change. Responsibility is in the right module: parsing cleanup in the parser, speech-line
selection and completion-reporting in the pure engine, actual speaking in the one class that owns
the speech surface.

### Required Fixes

None.

### Optional Refinements

- **Untested interaction: same-poll pending re-fire (D1) with a non-empty `petrovich-says` row.**
  The engine's own module docstring documents that a same-poll re-fire "may write once for the run
  that just finished and once more for the one that restarts" — and, per this change, a restarted
  run's row-0 self-check-skip now also speaks. `test_pending_restart_may_execute_the_same_poll`
  (pre-existing, untouched by this diff) exercises exactly this path but against `_SEQUENCES`'
  fixture rows, which all carry an empty `petrovich_says` by construction — so whether this
  combination speaks the same line twice within one poll is currently unverified by any test.
  **Not exploitable today**: all four speaking sequences (`observ-on/off`, `weapons-arm/safe`) are
  single-row with no `WaitRow`, and every one of their triggers is fired from a one-shot
  `CrewConsole` field consumed exactly once per poll in `body.py`, so a same-poll double-fire of a
  speaking trigger cannot currently happen via any real command path. Worth a one-line note on
  `EffectorRunState.spoken`'s docstring (or a dedicated test) before a future sequence — this
  project's own "step by step" plan for more triggers — gives a speaking row more than one row or a
  `WaitRow`, which is exactly the shape that would make the restart land on a *different*,
  possibly-still-non-empty row rather than collapsing silently.
- `_speak_text` has no direct unit test for the case where the pilot's cell already ends in
  terminal punctuation (the `if text[-1] not in ".!?"` branch) — covered indirectly by every
  existing case using unpunctuated cells. Low risk, pure function, `mypy --strict` clean; a single
  parametrised case would close it cheaply if this function grows more call sites later.

### Verdict
APPROVED

### Review Confidence
Full read. Read every changed file in the diff (`effector_sequences.py`, `effector_engine.py`,
`crew_console.py`, `body.py`, and all four touched test files), the full plan and implementation
log, the shipped `config/sequences/mi-24p/*.md` cell text, and traced the fire-order/drain wiring
by hand through `body.py`'s poll block. Confirmed the end-to-end wiring by mutation (disabling
`drain_effector_speech` and re-running the real-poll-loop test), not by reading alone. Ran
`ruff format --check`, `ruff check`, `mypy src` (all clean) and `fast-tests.sh body-layer`
(2237 passed, 4 xfailed) from inside `body-layer/`.
