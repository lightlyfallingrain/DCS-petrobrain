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

### Re-review of `3a54b55b`

Fast-forwarded cleanly from `415fa135` (strict ancestor, tree clean) to `3a54b55b`. Both
`plans/brain-tool-calls/review.md` (this file, pre-fix) and `implementation.md`'s new "Review fix"
section were present and read in full before this re-review.

**The fix lands exactly where the review asked.** `crew_console.py::_start_brain_turn` now does

```python
turn.offered.update(cid for cid, _ in header_refs)
if len(header_refs) >= 2:
    turn.candidate_sets.append(header_refs)
```

— the review's suggested shape verbatim ("push it into `candidate_sets` at turn start when
`len(header_refs) >= 2`"). `_candidate_set_for_ref`/`_validate_turn_answer`/
`_validate_turn_command` are unchanged and did not need to be: they already walk
`turn.candidate_sets` generically, so a header-seeded entry now gets the identical verbatim-
`because` evidence check a tool-returned multi-candidate set already got. A single header contact
(`len == 1`) is not pushed and keeps the no-evidence pronoun trust — correctly unaffected, and the
pre-existing `test_header_refs_offered_without_a_tool_call` (single-contact shape) still passes
unchanged, confirming that.

**Verified the new tests are genuinely red without the fix, not taken on the implementer's word.**
Reverted the two added lines above by hand in this worktree, ran
`pytest tests/test_brain_tool_loop.py -k "test_header_ref_ambiguity"`:
`test_header_ref_ambiguity_without_because_becomes_which_one` failed (`'BMP.'` was spoken directly
instead of degrading to `"Which one -- "`); `test_header_ref_ambiguity_with_because_dispatches`
passed either way, as expected (it's the positive-evidence case, not the one the fix changes).
Restored the fix (`git checkout -- src/belief/crew_console.py`) and confirmed both pass green.
This is exactly the shape the implementer's own log claims ("verified red without the fix...
confirmed green") — reproduced independently rather than trusted.

**`A4_which_ones_the_bmp` outcome matches the review's own prediction.** The review said the fix
"should not break `A4_which_ones_the_bmp`'s intended pass... a model naming `CONTACT_9 BECAUSE
"BMP"` would still validate." The fixture was given exactly that (`"because": "BMP"` added to
`expected.final`) rather than the fix being shaped to dodge touching it — the right choice: the
fixture was asserting an ungrounded pick as correct, which is precisely the gap being closed, so
updating the fixture's evidence rather than carving an exemption for header-seeded picks is
faithful to D10's intent, not a workaround. `test_stage2_acceptance_bench.py`'s
`_EXPECTED_COMMAND_NEEDS_EVIDENCE_GAP`/`_EXPECTED_NO_HEADER_REFS_GAP` bookkeeping sets were
re-checked: both stay empty, correctly — `A4` now validates through the evidence path rather than
around it, and `A1_where_two_shilkas_discriminated` (the one genuine, already-documented gap) is a
tool-returned candidate set, unaffected by this fix, and was already gated by the evidence check
before it.

**The bench's `_turn_from_case` mirroring is faithful to the real fix, but the mirror itself is a
standing, pre-existing risk this fix makes slightly more concrete, not a new one.** `_turn_from_case`
reconstructs `_start_brain_turn`'s seeding logic by hand (`if len(header_contacts) >= 2:
turn.candidate_sets.append(...)`) rather than calling the real function — this pattern predates the
fix (the original Stage 3 addition already hand-seeded `offered` the same way, and the original
review did not flag it) and the fix correctly extended the existing mirror rather than introducing
a second one. It is a real, if modest, drift risk: the mirror had to be touched by hand in lockstep
with the real change, and nothing would fail loudly if a future edit to `_start_brain_turn`'s
seeding logic were not mirrored here — the bench would keep passing against its own
(now-stale) reimplementation. This is not a reason to hold up this fix (the mirror is correct today,
the bench's job is to validate `validate_turn_final` against canned turns, and calling the real
`_start_brain_turn` would require a full `CrewConsole`/store/transcript setup the bench deliberately
avoids), but it is worth a non-blocking note for whoever next touches header-ref seeding: check
`_turn_from_case` when you do, since nothing currently enforces that this stays in sync.
(Optional, not required — matches the shape of the review's own prior "Optional Refinements.")

**Nothing else regressed.** No other file in the diff touches D1–D9 or D10's other mechanisms; the
E3 comment addition is documentation-only (confirmed by re-reading both differential tests —
`mark_target`/`cancel_task` — unchanged in behaviour, only a docstring addition answering the
original review's own non-blocking note).

**Checks (independently re-run in this worktree, not taken from the implementer's log):**

- `body-layer`: `ruff format --check src tests` — pass. `ruff check src tests` — pass. `mypy src`
  (strict, 82 files) — pass. `pytest -q` — **3265 passed, 4 xfailed** (matches the implementer's
  claimed count exactly).
- `brain-layer`: `ruff check src tests tools` — pass. `mypy src` (strict, 9 files) — pass.
  `pytest -q` — **89 passed** (matches).

### Verdict (re-review)

**APPROVED.** The one required fix from the original review is correctly and narrowly implemented,
verified red-then-green independently (not taken on the implementer's claim), the acceptance
fixture update matches the review's own prediction rather than working around it, and all three
subprojects' checks pass with counts matching the implementer's log. One non-blocking note left for
a future touch of header-ref seeding (the bench's hand-mirrored `_turn_from_case`), consistent with
"Optional Refinements" above and not a reason to withhold approval.

### Review of the security and performance fixes (a31be8c2..1b13975f)

Reviewed on branch `feature/brain-tool-calls`, fast-forwarded this worktree from `415fa135` (strict
ancestor of `1b13975f`, tree clean) to `1b13975f`. This is the change-request re-entry required by
root `CLAUDE.md`: Security's two option-C findings and Performance Reviewer's one required
mitigation, reviewed as ordinary new code per that rule. Diff reviewed: five commits,
`a31be8c2..1b13975f` (`5011349f`, `023b1fed`, `4d021768`, `9d3e944c`, `1b13975f`).

Inputs read in full: `plans/brain-tool-calls/security-review.md` (findings 1 and 2, both option C),
`plans/brain-tool-calls/performance-review.md` (the required enrich-before-cap mitigation),
`implementation.md`'s "Security fixes" and "Performance fix" sections, this file's own prior review
and re-review above.

**Security fix 1 (BR-B2/BR-B3).** `brain-layer/src/server.py`'s new `_read_body` is the same shape
as `audio-adapter/src/server.py`'s own — read side by side, both reject a non-numeric or negative
`Content-Length` with a clean `400` before `rfile.read` is ever touched, and brain-layer's version
adds only the declared-length cap `audio-adapter`'s single-utterance bodies don't need. A ported
guard, not a third variant. `test_escalate_non_numeric_content_length_returns_400_without_raising`/
`test_escalate_negative_content_length_returns_400`/`test_escalate_oversized_content_length_
returns_400` exercise this over a real HTTP round trip (`running_server` fixture) — a 400 with a
JSON body, not an uncaught exception, and `test_escalate_valid_content_length_still_succeeds`
confirms the legitimate path (202) is unaffected. `ollama_client.OllamaClient._post_json` is the
one method `generate()`, `generate_with_usage()`, and `chat()` all route through (read the class:
`generate()` calls `generate_with_usage()`, which calls `_post_json`; `chat()` calls `_post_json`
directly) — the byte cap at `response.read(MAX_OLLAMA_RESPONSE_BYTES + 1)` plus the
over-cap-raises check covers all three, confirmed by dedicated tests for `generate()` and `chat()`
plus an under-cap success case. Both constants (`MAX_ESCALATE_BODY_BYTES`,
`MAX_OLLAMA_RESPONSE_BYTES`) carry a `#:` comment explicitly noting they are behaviour-affecting
and would want the tuning mechanism, with the stated reason (`brain-layer` has no loader yet) —
correct per the Implementer's standing instruction for this case. **Nothing left unbounded on this
path**: `rfile.read(length)` is bounded by the now-capped `length`; `json.loads(raw)` on the
Ollama side parses at most `MAX_OLLAMA_RESPONSE_BYTES + 1` bytes (1 MiB), cheap. The pruned
`ollama_client.py` docstring paragraph is a correct prune — it stated a now-false claim
("`chat()` reproduces `generate()`'s own unbounded `response.read()`"), and the replacement
correctly describes the shared, now-fixed path; nothing durable was lost (no date, no verbatim
user quote, no measurement).

**Security fix 2 (uncaught-exception gap).** The `except Exception` in `_handle_brain_tool_call`
wraps exactly the single `self.run_brain_tool(...)` call — not validation (`validate_tool_call`
runs outside the `try`), not the round-cap degrade path, not `turn.offered`/`turn.candidate_sets`/
`turn.steps` bookkeeping, all of which stay outside the guard and still fail loudly if something
there is wrong. The turn is popped (`self._brain_turns.pop(reply.utterance_id, None)`) before
speaking the degrade, so a later utterance gets a fresh turn rather than colliding with a dead one.
`test_run_brain_tool_raising_ends_the_turn_and_logs_rather_than_propagating` genuinely asserts the
logged exception (`caplog` at `ERROR`, checks the message or `exc_info is not None`) and drives a
second, unrelated utterance afterward to completion — not just that the first call returned
cleanly. `logger.exception` is the same call shape `body.py`'s own poll-loop guards use
(`"live LOS coverage summary failed (ignoring)"`, `"crew-text poll cycle failed; continuing"`) —
consistent, not a new logging convention.

**Performance fix.** Read `belief.tools.get_contacts`/`find_contact`: `limit=None` is the default
and the only new code path is `if limit is not None: contacts = contacts[:limit]` / `matches =
matches[:limit]`, placed after the existing sort and strictly before the enrichment comprehension
— for `limit=None` this is a no-op, so every existing caller (`report_all`, the phrasebook
`report`/`watch` loops) is byte-for-byte unaffected; confirmed by reading the diff rather than
assuming it. The two adapters (`_find_contact_adapter`/`_list_contacts_adapter`) compute `total`
from an unenriched call (`enrichment` omitted) and `shown` from the enriched, capped call;
`_contact_result`'s own `enrichment` parameter gates `_add_enrichment_facts` entirely (confirmed in
`tools.py`), so the unenriched count call never touches the world-model connection — genuinely
cheap, not just asserted to be. Both calls share the same deterministic filter/sort logic (only
`enrichment`/`limit` differ between them), so `total >= len(shown)` always holds and `extra =
max(0, total - len(shown))` is never actually clamping a negative value in practice — the `max(0,
...)` is defensive, not masking a real miscount. Ordering is preserved because the cap is applied
after the pre-existing `sorted(..., key=lambda c: c.last_seen_sim, reverse=True)` — exactly as
claimed, and `test_get_contacts_limit_preserves_most_recently_seen_first_ordering`/the `find_contact`
twin verify this directly against the unlimited call's own first-N, not by assumption. The call-count
tests genuinely count `describe_position` invocations via a monkeypatch counter (`test_tools.py`'s
`_counting_enrichment_context`), not something that would pass trivially: `limit=5` on a 50-contact
store asserts exactly 5 calls, `limit=None` asserts exactly 50 — both directions checked, and the
`test_brain_tool_loop.py` pair exercises this through the real registered `BrainTool`s
(`BRAIN_TOOLS_BY_NAME`), not `belief.tools` directly, with the same assertion plus the "and N more"
summary text.

**Backlog bookkeeping.** `BR-B2`/`BR-B3` are marked `[x]`/`#status/done` in
`brain-layer/ROADMAP/BR-B2.md`/`BR-B3.md` with a resolution line naming this branch. The dispatch
named `todo/backlog/BR-B2.md`/`BR-B3.md`, which do not exist — the implementer correctly found and
fixed the real location instead of creating a duplicate pair, and said so in `implementation.md`.
`brain-layer/ROADMAP/brain-layer-roadmap.md` (the index) correctly carries no status marker next to
either entry — that file's own "Keeping this current" section states status lives only on the
entry file, never the index, so no index edit was owed here.

**Checks (independently re-run in this worktree, fresh, not taken from any log):**

- `body-layer`: `ruff format --check src tests` — pass. `ruff check src tests` — pass. `mypy src`
  (strict, 82 files) — pass. `pytest -q` — **3274 passed, 4 xfailed** (matches the implementer's
  claimed count exactly).
- `brain-layer`: `ruff format --check src tests` — pass (the one reformat `ruff format --check`
  reports, `tools/live_cross_process_check.py`, is pre-existing and untouched by this diff —
  confirmed via `git diff` — per the dispatch's own note, ignored). `ruff check src tests tools` —
  pass. `mypy src` (strict, 9 files) — pass. `pytest -q` — **96 passed** (matches the implementer's
  figure once the four new security tests plus three others from the batch are accounted for —
  consistent with growth from 89 at the prior review to 96 here).
- `audio-adapter`: `ruff format --check src tests` — pass. `ruff check src tests` — pass.
  `mypy src` (strict, 16 files) — pass. `pytest -q` — **391 passed, 2 skipped** (the two skips are
  the pre-existing env-var-gated live-binary/live-Piper classes, unrelated to this diff).

### Verdict (security/performance fix re-review)

**APPROVED.** Security fix 1 ports the existing guard shape rather than inventing a third variant,
covers `generate`/`generate_with_usage`/`chat` uniformly, and leaves nothing unbounded downstream
of the cap; the two new constants are correctly flagged for the tuning mechanism that doesn't yet
exist in this subproject. Security fix 2's guard is scoped to exactly the one call that needed it,
pops the turn so the console stays usable, and is proven by a test that drives a second utterance
through afterward rather than just asserting no crash. The performance fix's `limit=None` path is a
genuine no-op confirmed by reading the diff, the unenriched count call is cheap by construction (no
world-model touch), the count is correct because both calls share one deterministic filter, and
ordering/call-count are each verified by a dedicated test rather than assumed. Backlog bookkeeping
correctly located and fixed the real files instead of the ones the dispatch named. All three
subprojects' format/lint/type/test commands pass, fresh in this worktree.

No required fixes. No optional refinements beyond what the earlier review already logged.

### Review Confidence (security/performance fix re-review)

Full read — all five commits' diffs read in full, every named test read and evaluated for whether
it could pass trivially (none can), and all three subprojects' checks re-run fresh rather than
taken from any prior log.
