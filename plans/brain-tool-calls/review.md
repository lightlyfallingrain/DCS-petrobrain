# BR-2 brain tool calls — review (Stages 0–3 batch)

Reviewed on branch `feature/brain-tool-calls`, HEAD `0f9ecbcaa7eb36163ddbfd921464aeb4163e05d6`
(fast-forwarded from `415fa135`, which was a strict ancestor; tree was clean). Diff reviewed:
`9a6e5983..0f9ecbca` across `audio-adapter/`, `body-layer/`, `brain-layer/`.

Inputs read in full: `plans/brain-tool-calls/plan.md`, `alignment.md`, `explore-notes.md`,
`implementation.md` (Stage 0–3 logs), `brain-layer/research/2026-11-12-tool-call-form.md`,
`plans/brain-layer/plan.md` (D10 boundary).

### Review Summary

This is careful, well-documented work. The D3/D10 trust boundary is implemented correctly almost
everywhere I traced it: the model can never supply a coordinate, `now_sim`, or an unoffered ref;
`handle_command` dispatch is gated by an explicit `BRAIN_COMMANDS` allowlist with slot-shape
checks; `because` evidence is a verbatim-substring check against the turn's own immutable
transcript, inherited correctly from the BR-1 mechanism. D6 (threat callouts never touch Ollama,
at most one tool execution per poll) holds by construction and by the real `body.py` poll order,
which I read directly rather than trusting the plan's line numbers. The R1 fix is correctly
narrowed and I confirmed it against the real dispatch table rather than the plan's prose. All
three subprojects' format/lint/type/test commands pass, including the full body-layer suite
(3263 passed, 4 xfailed).

One genuine trust-boundary gap, below, needs a fix before this batch should be considered closed
on the D3/D10 checklist. Everything else is either already correctly scoped, already documented
by the Implementer as a deliberate, flagged choice, or cosmetic.

### Required Fixes

- **D3's ambiguity-evidence rule does not cover header-seeded multi-candidate sets, and this is a
  real gap, not just a difference of degree from BL-B102's pronoun trust.**
  `body-layer/src/belief/crew_console.py::_start_brain_turn` (`turn.offered.update(cid for cid, _
  in header_refs)`) offers every recently-mentioned contact (up to `BRAIN_TOOL_LIST_CAP` = 5) but
  deliberately does **not** push them into `turn.candidate_sets`
  (`_start_brain_turn`'s own comment: "not pushed into `candidate_sets`... gets the same
  no-evidence trust a bare `it`/`that` pronoun already gets"). `belief/brain_reply.py`'s
  `_candidate_set_for_ref` only searches `turn.candidate_sets`, so when a final names a header-
  seeded ref, `_validate_turn_answer`/`_validate_turn_command` never run the evidence check at
  all — not "runs it and it's lenient," genuinely skipped.

  The analogy to BL-B102 does not hold once the header offers **two or more** contacts.
  `belief.referent.resolve_referent` for a bare pronoun never makes a choice among several
  candidates — it deterministically returns the single most recent mention, so there is no
  "which one did the model pick" question to ask evidence of. The header, by contrast, can and
  does offer multiple genuine candidates with equal, unconditional trust: the plan's own
  acceptance case **`A4_which_ones_the_bmp`** is exactly this shape — two header-offered contacts
  (`CONTACT_8`: T-72, `CONTACT_9`: BMP), `expected.final` names `CONTACT_9` with **no `because`
  field at all** (confirmed by reading `brain-layer/tools/stage0_cases.json` directly). As
  implemented, the validator would accept `CONTACT_8` (the wrong answer) exactly as readily as
  `CONTACT_9`, with zero code-side check that the pick was grounded in anything the model said or
  any tool told it — purely model competence, not the deterministic safety net D10's own module
  docstring says is the point: *"a small model that silently picks on a genuinely ambiguous
  reference is exactly the failure D10 is built to catch."* `test_header_refs_offered_without_a_
  tool_call` only exercises a **single**-candidate header, so this gap is not demonstrated red by
  any existing test — it has to be read to be seen, which is presumably why it passed three
  Stage-3 checks already.

  **Fix:** extend the ambiguity-evidence rule to a header-seeded candidate set once it has ≥2
  members — treat `turn.header_refs` as a `candidate_sets`-like entry for
  `_candidate_set_for_ref`'s purposes (or push it into `candidate_sets` at turn start when
  `len(header_refs) >= 2`), so a final naming one of several header-offered contacts needs the
  same verbatim `because` evidence a tool-returned multi-candidate pick already needs. This should
  not break `A4_which_ones_the_bmp`'s intended pass — `describe_contact`'s own summary text
  ("BMP"/"T-72") already discriminates the two, so a model naming `CONTACT_9 BECAUSE "BMP"` would
  still validate; only an ungrounded or wrong pick would now correctly degrade to "which one?".
  This is a body-layer-only change (`crew_console.py`/`brain_reply.py`); no wire-shape change
  needed.

### Optional Refinements

- **The E3 differential test covers 2 of 30 `BRAIN_COMMANDS` tokens** (`mark_target`,
  `cancel_task`) rather than every allowlisted token. I don't think this needs to block — every
  token dispatches through the identical `_handle_brain_command` → `handle_command` call with only
  two possible slot shapes (`takes_target` or none), and the two chosen tests cover both shapes —
  but a reader skimming the plan's "Stage 3 adds an explicit differential test" sentence could
  reasonably expect a sweep over all 30. Worth a one-line note in the plan or the test file saying
  why two representative tokens are sufficient, so a future reader doesn't "fix" this by adding 28
  more near-duplicate tests. (Optional.)
- **R1's fix changes behaviour for a case the plan never named**: a *pure-voice* "where is it"
  followed by a different voice command in the *same* poll (both dispatched inside one
  `_poll_transcripts` loop iteration) was silently dropping the first request before this fix —
  `handle_command`'s old unconditional reset would wipe `where_is_it_requested` before the next
  poll's `drain_where_is_it` ever consumed it, regardless of whether the second dispatch came from
  the brain or from another voice command. This is a genuine bug fix, not a regression, but it's
  worth telling the user explicitly: a mission where two voice commands landed in one poll used to
  silently eat the first "where is it," and no longer does. (Informational — no action needed, but
  it should be called out rather than only discovered by reading the diff.)
- `body-layer/src/belief/tool_api.py:426,590` carry `# type: ignore[arg-type]` against
  `tools.get_contacts`/`mission_memory_tools.recall_memory`'s own `Literal`-typed parameters,
  because the adapters pass a plain `str | None` through from already-`ParamSpec`-validated
  model args. Harmless (mypy strict passes), but if either underlying function's signature is ever
  loosened to accept `str | None` directly, these two suppressions become removable. Not worth
  doing now.

### Verdict

NEEDS REVISION — one required fix (the header-ref ambiguity-evidence gap). Everything else in
this batch — D1/D2 transport and calling convention, D4 wake routing, D5 tool/command surface, D6
poll-thread safety and callout priority, D7 answer forms, D9 budget/stand-by, the Co-moving Fields
table (including the documented, deliberately-unimplemented `cancel_nevermind` dispatch path), and
the R1/R6 risk resolutions — is implemented as planned, tested, and matches the real code rather
than the plan's illustrative prose where the two diverge (the Implementer caught and fixed two
such divergences itself: the clock/bearing token families, and the `final_to_dict` `target`
duplication).

Once the header-ref fix lands, re-run `test_stage2_acceptance_bench.py` (it should still pass,
with `A4_which_ones_the_bmp` now exercising the evidence path rather than skipping it) and the new
`_EXPECTED_COMMAND_NEEDS_EVIDENCE_GAP`/`_EXPECTED_NO_HEADER_REFS_GAP` bookkeeping should be
rechecked for whether `A4` needs to move between those sets depending on how the fix is shaped.

### Checks run (all passed)

- `audio-adapter`: `ruff format --check`, `ruff check`, `mypy src` (16 files), `pytest -q` — 391
  passed, 2 skipped.
- `body-layer`: `ruff format --check`, `ruff check`, `mypy src` (82 files), `pytest -q` — 3263
  passed, 4 xfailed.
- `brain-layer`: `ruff format --check`, `ruff check`, `mypy src` (9 files), `pytest -q` — 89
  passed. (`ruff format` reformats the untouched `tools/live_cross_process_check.py`; confirmed via
  `git diff` that this file is not part of this branch's diff — pre-existing debt, not this
  batch's.)

### Review Confidence

Full read — plan, alignment, explore-notes, all four implementation-log stages, the research note,
and the complete diffs of `tool_api.py`, `brain_reply.py`, `escalation.py`, `final_reply.py`,
`tool_loop_prompts.py`, `ollama_client.py`'s new methods, and the relevant sections of
`crew_console.py` (turn lifecycle, `_handle_brain_reply`/`_handle_brain_tool_call`/`_handle_brain_
turn_final`/`_handle_brain_command`, `_start_brain_turn`/`_post_tool_continuation`,
`handle_command`'s reset block) and `body.py` (the real poll order, `_poll_transcripts`). The
Stage 0 probe/fixture (`brain-layer/tools/stage0_tool_call_probe.py`,
`brain-layer/tools/stage0_cases.json`) was read lightly, per the dispatch instruction — enough to
confirm the acceptance-set fixtures the Stage 2/3 bench reuses, not a full line-by-line read of the
probe CLI itself.
