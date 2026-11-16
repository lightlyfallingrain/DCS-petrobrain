# BL-B119 — Speak each effector sequence row's `petrovich-says`; drop the hard-coded readbacks

Small feature; the main loop wrote this plan from the pilot's own spec, without an Architect pass.

## The request, verbatim

> *"In my effectors commit 80a134c1 I added strings that Petrovich should say when the triggers
> fire and perform effector actions. Clean up code so that the hardcoded things Petrovich says on
> those trigger actions are removed. The goal is to use the effector definitions the set the string
> to say aloud. Not everything has a trigger yet, but step by step."*

Commit `80a134c1`'s own message: *"Must remove hardcoded strings that Petrovich speaks to remove
duplicate voiced lines."*

## Decisions, verbatim (2026-11-16)

Asked: (1) speak a row's line even when the switch was already in position? (2) an attack-run start
also arms via the weapons-arm sequence — speak "weapons armed" then too? (3) the line now comes
when the row runs, a poll later, not on recognition.

> *"Q1 - yes / Q2 - follow rule from Q1 / Timing change ok. It is then a confirmation that the
> action is done."*

## What is there today

- `belief/effector_sequences.py` parses `petrovich-says` into `SequenceRow.petrovich_says`, but
  **nothing reads it**: `belief/effector_engine.py`'s `advance` never speaks. The pilot's new
  strings therefore produce no speech yet.
- `belief/crew_console.py` hard-codes the readbacks: `_handle_observ_on` → `"Observ on."`,
  `_handle_observ_off` → `"Observ off."`, `_handle_weapons_armed` → `"Weapons armed."`,
  `_handle_weapons_safe` → `"Weapons safe."`. Each also sets a one-shot transition that `body.py`
  turns into `fire_effector_trigger(...)` (`OBSERV_ON`/`OBSERV_OFF`/`WEAPONS_ARM`/`WEAPONS_SAFE`);
  `advance_effectors` runs the rows each poll.
- The sequence files now carry `"observ on"`, `"observ off"`, `"weapons armed"`, `"weapons safe"`
  (quotes are part of the cell as written; strip them).

## The change

1. **The engine reports a row's line when the row completes.** A switch row *completes* when it is
   written successfully **or** found already at its target value (the R12 self-check skip) — per Q1,
   the line confirms the state is as commanded either way. A row skipped for a failed explicit
   condition, an unknown/no-readback effector, or a failed write that will retry, says nothing until
   it actually completes. Rows with an empty `petrovich-says` stay silent. The engine stays pure: it
   returns the lines (e.g. a `spoken: tuple[str, ...]` on `EffectorRunState`, or a returned value),
   it never calls speech itself; `body.py` drains them to `CrewConsole`'s normal speech path in
   order, once each.
2. **Cell text:** strip surrounding quotes and whitespace; speak it as written, sentence-cased the
   way existing readbacks are ("Observ on.") — the pilot wrote the words, the code only normalises
   punctuation/case.
3. **Remove the four hard-coded returns** in `crew_console.py` (they return `[]`). Keep everything
   else they do. Per Q2, `_handle_engage`'s arming also speaks "weapons armed" through the sequence;
   `_handle_engage`'s own readback is unchanged.
4. **Unchanged, out of scope ("step by step"):** `"Unable, guidance not ready"` (the readiness gate
   before Observ on — no trigger fires), `"Observ on, wait."`, and every other readback not tied to
   a sequence row. Say-only rows stay rejected by the parser, as today.

## Tests

- Engine: a row written → its line reported once; already-in-position → reported; empty cell →
  nothing; failed condition / unknown readback → nothing; failed write → nothing until it succeeds,
  then once; two triggers in one poll → lines in fire order.
- Parser: quotes stripped.
- Crew console: the four handlers no longer return speech, still set their transitions.
- End to end in `body.py`'s poll path with fakes: "weapons armed" spoken exactly once per command,
  never twice.

## Checks

body-layer `ruff format --check`, `ruff check`, `mypy src` (inside the subproject), and
`.claude/scripts/fast-tests.sh body-layer`. Full suite at DoD.

## Live check (card)

Say "observ on", "observ off", "weapons armed", "weapons safe": each line heard once, after the
switch moves (or at once if it was already there); start an attack run: "weapons armed" heard once.
No line heard twice.
