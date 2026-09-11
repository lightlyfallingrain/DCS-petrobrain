### Review Summary

Implementation matches `plans/overlay-speech-callouts/plan.md` (locked at `91f00f2`) closely — no
scope drift, no unrelated refactors. Verified against the working-tree diff (plan.md itself is the
only committed change on the branch; code changes are staged/unstaged in the working tree per
`git status`):

- `overlay_client` is a genuinely separate `CrewConsole` field from `aircraft_client`, with a
  docstring explaining why (BL-6-reserved, no reader today, vs. read every `_print` call). Matches
  the plan's explicit reasoning.
- `_print` is the single funnel point. Confirmed by grep: both call sites of `_print`
  (`crew_console.py:145` in `handle_line`, `:160` in `drain_events`) are the only two, so every
  path that produces spoken text goes through it. No bypass route found.
- `"!! "` prefix is applied only at the `_print` push call, only when `bypass_gate=True`, only to
  the pushed overlay copy — `output`'s printed line is untouched (verified in code and in
  `test_urgent_call_pushes_to_overlay_with_prefix_but_prints_unprefixed`). `bypass_gate` is
  correctly scoped: `handle_line` sets it `False` explicitly for the non-`!inject-urgent` branch,
  `drain_events` always passes `False` (lifecycle `Event`s never set the flag), and
  `_handle_inject_urgent`'s new `tuple[list[str], bool]` return reads `bypass_gate` straight off
  `route_event`'s `OutgoingSpeech` rather than re-deriving it from text — no leak into an unrelated
  path. Cross-checked the "notable discovery" claim that `route_event` always sets
  `bypass_gate=True` for `UrgentCall` — confirmed at `belief/speech.py:254`.
- Failed overlay push degrades correctly: each push in `_print`'s loop is wrapped in its own
  `try/except AircraftLayerError` (log-and-continue), matching `ConsolePerceptionRunner.run_once`'s
  BL-2.5 pattern. `test_failed_overlay_push_degrades_without_raising_and_does_not_block_remaining_lines`
  exercises this with a real failure injected via `FakeOverlayClient(fail_on=...)`, not just an
  assert-no-exception — it confirms the failed line is absent from `pushed` and a later, unrelated
  push in a subsequent call still succeeds.
- `logger.py`: mutual-exclusivity relaxed exactly as planned (`args.crew_text and args.console`
  only). `--crew-text` branch now wires `overlay_client=aircraft_client if args.overlay else None`
  into `CrewConsole(...)`. Confirmed by direct read (`logger.py:623`) that the pre-existing
  `--console` branch's `ConsolePerceptionRunner(overlay_client=aircraft_client if args.overlay else
  None)` wiring (`logger.py:654`) is untouched — same line shape, unaffected by this change. Help
  strings and module docstring updated to describe the new combination.
- Test coverage: 7 new tests (plan/implementation.md both say 7 under "Tests Added"; my review
  brief said 8 — that number came from the task prompt, not from a gap in delivered work). All 7
  assert on `FakeOverlayClient.pushed`'s actual captured content (exact text, prefix present/absent,
  no-op when unset) rather than merely "no exception raised" — meets the checklist bar.
- `belief/speech.py` and `belief/console.py` (`format_event_for_overlay`) are untouched, confirming
  the plan's "no change" list held (`git diff HEAD --stat` on both files is empty).
- `body-layer/CLAUDE.md`'s two updated sections (the `--overlay` running note and the
  `crew_console.py` Structure entry) accurately describe what was built: separate-field reasoning,
  `_print` funnel, prefix scope, and the `--crew-text`/`--overlay` combination — no drift from the
  as-implemented behavior.

Ran body-layer's own commands directly rather than trusting the Implementer's report:
- `ruff format --check src tests` — pass (62 files already formatted)
- `ruff check src tests` — pass
- `cd body-layer && mypy src` — pass, no issues in 29 source files
- `pytest tests -q` — pass, 444 passed

All match the Implementer's reported results exactly.

### Required Fixes

None.

### Optional Refinements

- No test exercises `logger.py`'s `main()` argparse mutual-exclusivity check itself (the
  `parser.error("--crew-text is mutually exclusive with --console")` path) or the `--overlay`
  wiring inside `main()` end-to-end — this is a pre-existing gap (the old mutex code had no direct
  test either, `main()`'s CLI parsing generally isn't unit-tested in this file), not something this
  change introduced or worsened. Worth closing at some point but not blocking, and out of this
  plan's stated scope. (optional)
- New files staged: `git status` shows the code changes as modified/staged (`M`/`A` markers) with
  none left as plain untracked working-tree noise except the implementer's own agent-memory file —
  fine as-is, nothing to add here, just confirming for the record.

### Verdict
APPROVED

### Review Confidence
Full read — read plan.md and implementation.md in full, read the complete diff for all four
changed files (`crew_console.py`, `logger.py`, `test_crew_console.py`, `CLAUDE.md`), grepped for
all `_print` call sites and the `--console` branch's overlay wiring to confirm no regression, cross-
checked the `route_event`/`bypass_gate` claim against `belief/speech.py` source, and ran all four
body-layer verification commands myself rather than trusting the Implementer's report.

---

## Addendum review (2026-09-11): CONTACT_DETECTED/REACQUIRED lifecycle content fix

Reviewed against the addendum section of `plan.md` locked at `6b0aba7`, and the appended
"Addendum implementation" notes in `implementation.md`. Diff scope: `body-layer/src/belief/
speech.py`, `body-layer/tests/test_speech.py`, `body-layer/tests/test_crew_console.py`,
`body-layer/CLAUDE.md` (commit `7312674`).

1. **`render_contact_report` unchanged for existing callers** — confirmed both ways: read the
   diff (it now calls `_contact_report_text(result["facts"])` and returns the same
   `OutgoingSpeech(text=..., template="contact_report")`, identical to the pre-addendum body
   modulo the extraction), and confirmed `test_render_contact_report_follows_coalition_
   unit_type_clock_range_format` and `test_render_contact_report_maps_op_class_to_display_word`
   are byte-for-byte untouched in the diff and still pass. A pure extraction, not a rewrite.
2. **`CONTACT_LOST`/`CONTACT_CLASSIFICATION_CHANGED` untouched** — confirmed in the
   `_render_lifecycle_text` diff: only the `CONTACT_DETECTED`/`CONTACT_REACQUIRED` branch changed
   (merged into one `or`-joined condition calling the shared helper); the `CONTACT_LOST` and
   `CONTACT_CLASSIFICATION_CHANGED` return lines are byte-for-byte identical to before. No
   incidental change. Confirmed further by `test_speech.py`'s diff touching only the `detected`/
   `reacquired` assertions, none for lost/classification-changed.
3. **Semantic-fragment selection mirrors `format_event_for_overlay`** — read both side by side
   (`speech.py:_contact_report_text` vs `console.py:format_event_for_overlay`, lines 595-660).
   Both guard with `isinstance(semantic, list) and semantic` and select with
   `max(semantic, key=lambda fact: fact["confidence"])`, reading `best["text"]`. Identical
   selection logic; only the join punctuation differs (`" -- "` in `console.py` vs bare `" "` in
   the new helper), which the addendum explicitly calls out as intentional (matching the user's
   own dash-free example). Not a case of "both pick a semantic fact somehow" — the selection
   expression is the same line of code, duplicated deliberately (the plan doesn't ask `console.py`
   to import from `speech.py` or vice versa, and doesn't need to for two lines).
4. **Out-of-addendum `test_crew_console.py` fix** — diff shows exactly two assertions changed,
   both string literals of the form `f"{contact_id} BMP-2."` -> `f"{contact_id}: UNKNOWN BMP-2."`
   and `f"{contact_id} reacquired."` -> `f"{contact_id}: UNKNOWN BMP-2."`, inside
   `test_scripted_crew_session_reproduces_the_first_useful_success_criterion` and
   `test_failed_overlay_push_degrades_without_raising_and_does_not_block_remaining_lines`. Both
   were pinned to the exact broken output this addendum fixes (the raw-enum lifecycle line); once
   `_render_lifecycle_text` legitimately changed shape, these two assertions had to follow or the
   suite would fail for a reason unrelated to a real regression. No assertion was loosened,
   removed, or had its checked behavior narrowed — this is a required mechanical follow-through of
   the intended change, not scope creep and not a quality regression.
5. **Id-prefix format / colon convention** — `"CONTACT_1: UNKNOWN truck, 2 o'clock, 1.5 km near a
   road (120m)."` reads as a sensible radio callout. Checked for collision against `speech.py`'s
   own existing conventions: `render_readback` (`"Watching {id}."` — id inside the sentence, not a
   prefix) and `render_contact_report`'s own no-id output (`"UNKNOWN truck, ..."`) don't use a
   leading `"id: "` shape at all, so there's nothing in this module for the new prefix to collide
   with. The `"id: "` prefix shape does already exist one module over, in
   `belief.console.format_event_for_overlay`'s `"<id>: <kind>, ..."` mirror line — the addendum's
   plan text cites that as precedent, not something reused in code, and the two functions live in
   different modules serving different consumers (spoken/pushed overlay text vs. the older
   console-mirror line), so no naming or format clash in practice. The `"!! "` urgent-call prefix
   (`crew_console.py`) is applied even further out, at the `_print` push site, prepended in front
   of whatever `OutgoingSpeech.text` already is — stacks cleanly in front of the new `"id: "`
   prefix without altering it (e.g. `"!! CONTACT_1: ..."`), no interaction bug.

Ran body-layer's commands myself rather than trusting the Implementer's report:
- `ruff format --check src tests` — pass (62 files already formatted)
- `ruff check src tests` — pass
- `cd body-layer && mypy src` — pass, no issues in 29 source files
- `pytest tests -q` — pass, 446 passed

Matches the Implementer's reported 446-passed exactly. `body-layer/CLAUDE.md`'s updated
`speech.py` Structure entry (diff read in full) accurately describes the shared helper, the new
detected/reacquired format, and leaves the lost/classification-changed description correctly
unextended.

### Addendum: Required Fixes
None.

### Addendum: Optional Refinements
None identified beyond what the addendum's own "Risks & Unknowns" already documents (enrichment-
fragment wording as a placeholder, silent no-fragment when no `EnrichmentContext` is wired,
coalition staying `"UNKNOWN"`) — all pre-existing, already-tracked, out of this addendum's scope.

### Addendum: Verdict
APPROVED

### Addendum: Review Confidence
Full read — read the addendum section of `plan.md` and the "Addendum implementation" notes in
`implementation.md` in full, read the complete `speech.py` diff, read `format_event_for_overlay`
in `console.py` side by side with the new `_contact_report_text` to verify the mirrored selection
logic, read the full `test_speech.py` and `test_crew_console.py` diffs (not just the new tests) to
confirm scope of what changed vs. what didn't, and ran all four body-layer verification commands
myself.

---

## Addendum 2 review (2026-09-11): terser crew-text vocabulary

Reviewed the third round against Addendum 2 of `plan.md` (locked, `c06c30b`) and the "Addendum 2
implementation" section of `implementation.md`. Read the full `speech.py`/`test_speech.py` diff
(`git show 0b280f9`), the `test_crew_console.py` diff (`dacd642`), confirmed `console.py` and
`crew_console.py` are untouched this round (`git diff main -- src/belief/console.py` empty;
`crew_console.py`'s last touch predates this round), and read the updated `speech.py` Structure
entry in `CLAUDE.md` in full.

1. **`CONTACT_LOST` / unspoken-event acknowledgement.** `_render_lifecycle_text`'s `CONTACT_LOST`
   branch is now `return None`. `route_event` (speech.py:328-352) computes `text =
   _render_lifecycle_text(...)`, returns `None` immediately if `text is None`, and only calls
   `acknowledge_event` after that check — so a `CONTACT_LOST` event is left in
   `store.unacknowledged_events`, exactly mirroring `CONTACT_ATTENTION_CHANGED`'s existing
   behaviour. Confirmed directly in `route_event`'s source and in
   `test_route_event_contact_lost_has_no_template_and_is_not_acknowledged`, which asserts
   `lost in store.unacknowledged_events` both before and after the `route_event` call. Correct —
   no accidental acknowledge-and-discard.
2. **No id leak in `CONTACT_DETECTED`/`CONTACT_REACQUIRED`.** Grepped `contact_id` usage across
   `speech.py`: the only remaining uses are `render_readback`'s existing `"Watching {id}."`
   template and `describe_contact` call sites (`event.contact_id`, an internal store lookup key,
   never rendered into text). `_render_lifecycle_text`'s detected/reacquired branches call
   `_contact_report_text(result["facts"])` with no id concatenation anywhere. Test assertions
   (`test_route_event_contact_detected_renders_classification_with_no_id`, the reacquired
   equivalent) pin the exact id-less string. Confirmed.
3. **`CONTACT_CLASSIFICATION_CHANGED` wiring.** New branch reads `result["facts"]["classification"]`
   through `_unit_type_display` (not `event.classification`) and `result["facts"].get
   ("relative_now")` for clock/range, building `"unit at {clock} o'clock, {range} km is {type}."`
   when enriched, degrading to `"unit is {type}."` when `relative_now` is absent — no malformed
   trailing comma or dangling clause in either branch. Both paths are exercised by
   `test_route_event_classification_changed_speaks_position_and_new_type` (enriched) and
   `..._omits_range_when_not_enriched` (unenriched), both passing. Confirmed correct and matches
   the addendum's spec exactly.
4. **`_COALITION_PLACEHOLDER` removal.** Grepped `src/` and `tests/` for `_COALITION_PLACEHOLDER`
   and a bare `"UNKNOWN"` token — zero hits outside an unrelated docstring reference and an
   unrelated `classification.py` enum member. `_contact_report_text` now starts `text =
   _unit_type_display(...)` directly (was `text = f"{_COALITION_PLACEHOLDER} {unit_type}"`) — no
   leading space, no empty-string prefix artifact; confirmed by
   `test_render_contact_report_follows_unit_type_clock_range_format`'s `"BMP-2."` (not `" BMP-2."`)
   and `test_render_contact_report_maps_op_class_to_display_word`'s `"truck."`. Clean removal.
5. **Rounding helpers.** `_format_range_km` and `_round_enrichment_fragment` are called only from
   `_contact_report_text` (grepped — no other call sites), which `console.py`/
   `format_event_for_overlay` never invokes; confirmed `console.py` has a fully empty diff against
   `main` this round, so the `--console` debug path is untouched as required.
   `_ENRICHMENT_DISTANCE_RE = re.compile(r"\((\d+)m\)$")` is `$`-anchored to the end of the string,
   so it only matches a genuine trailing `"(NNNm)"` parenthetical and correctly passes through
   distance-free fact text (`"inside Anapa"`) unchanged, per
   `test_round_enrichment_fragment_passes_through_text_without_distance`. On the round-half-to-even
   characterization: `_format_range_km`'s `round(range_m / 500.0) * 0.5` and
   `_round_enrichment_fragment`'s `round(int(...) / 100.0) * 100` both call Python's builtin
   `round()`, whose ties-to-even behaviour on exact `.5` boundaries (`round(2.5) == 2`,
   `round(3.5) == 4`) is standard library behaviour, not something the wrapping arithmetic
   introduces or could reasonably special-case away without adding real complexity for an edge case
   (an exact 1250m/1750m/450m reading) that is rare in practice. The implementer's characterization
   as "inherent to `round()`, not a bug in the wrapping logic" is fair; boundary tests pin the actual
   computed values rather than asserting a wished-for symmetry, which is the right call for
   documenting a known, low-severity quirk rather than hiding it.
6. **Casing.** `_unit_type_display`'s presence/fallback words are now `"ground"`/`"contact"`
   (lowercase); `_OP_CLASS_DISPLAY`'s existing entries are unchanged (lowercase words, `"SAM"`/
   `"AAA"` acronyms intact). Grepped for `"GROUND"`/leftover caps literals in `src/`/`tests/` — none
   found. Consistent.
7. **`render_contact_report` shares the terser format.** `render_contact_report` remains a thin
   wrapper calling `_contact_report_text` (unchanged from Addendum 1's extraction) — the same
   function that dropped the coalition token and gained rounding, so both the `status`/`watch`
   player-command-response path and the lifecycle paths picked up the terser format identically.
   Confirmed by `test_render_contact_report_follows_unit_type_clock_range_format` and
   `test_render_contact_report_maps_op_class_to_display_word`, both updated to the id-less,
   coalition-less, unrounded-input-but-correctly-formatted output. Matches the addendum's Design
   point 8 resolution (apply to both call sites, not fork a second formatter).
8. **`console.py` untouched.** `git diff main -- body-layer/src/belief/console.py` is empty.
   `crew_console.py` was not touched this round either (last commit touching it is `f2e2302`, the
   round-1 reviewer-approval commit, predating this round's `0b280f9`/`dacd642`). The `--console`
   debug path's independence from `speech.py`'s three rounds of changes holds.

**Scope.** Diff is `speech.py` (implementation + docstring), `test_speech.py`, two mechanically-
required `test_crew_console.py` assertion updates (string literals only, no behaviour-check
narrowed), and the `CLAUDE.md` Structure entry — matches the addendum's own Affected Modules list
exactly, no drift.

**`body-layer/CLAUDE.md`.** Updated `speech.py` entry (lines 322-363) read in full — accurately
describes the id-less/coalition-less format, `CONTACT_LOST`'s no-template status, the new
`CONTACT_CLASSIFICATION_CHANGED` line, and both rounding helpers, including their scoping to the
`--crew-text` path only. No stale claims found.

Ran body-layer's commands myself:
- `.venv/bin/ruff format --check src tests` — pass (62 files already formatted)
- `.venv/bin/ruff check src tests` — pass
- `cd body-layer && .venv/bin/mypy src` — pass, no issues in 29 source files
- `.venv/bin/pytest tests -q` — pass, 453 passed

Matches the Implementer's reported 453-passed exactly. No leftover debug code, `print()` calls, or
`TODO`/`FIXME` comments found in `speech.py`. Working tree is otherwise clean except two
`.claude/agent-memory/implementer/` bookkeeping files (out of this review's code scope).

### Addendum 2: Required Fixes
None.

### Addendum 2: Optional Refinements
- The tie-boundary rounding asymmetry (1250m/1750m round to different halves of a km) is already
  flagged by the implementer as a live-acceptance caveat and confirmed fair above — worth a look
  only if live testing surfaces it as actually confusing to a listener; not worth pre-emptively
  switching to round-half-up for a case this rare (optional).
- `_round_enrichment_fragment`'s coupling to `semantic_facts_for`'s current trailing-`"(NNNm)"`
  phrasing (documented as a known risk in the plan itself) means a future rewording of that text
  degrades silently to unrounded output rather than erroring — acceptable for now per the plan's
  own risk note; a `SemanticFact.distance_m` field would remove the coupling if `enrichment.py`'s
  phrasing churns later (optional, not blocking, already tracked as a risk in the plan).

### Addendum 2: Verdict
APPROVED

### Addendum 2: Review Confidence
Full read — read Addendum 2 of `plan.md` and its "Addendum 2 implementation" notes in full, read
the complete `speech.py` diff (`0b280f9`) including the full rewritten module docstring, read the
full `test_speech.py` diff (all new and changed assertions, not just names), read the
`test_crew_console.py` diff (`dacd642`), confirmed `console.py`'s diff against `main` is empty and
`crew_console.py` was not touched this round via `git log`, read the updated `CLAUDE.md`
`speech.py` Structure entry in full, and ran all four body-layer verification commands myself
rather than trusting the reported 453-passed figure.
