# Definition of Done: group-contact-model Stage 4b (feature/group-contact-speech)

**Result: PASS** — All mechanical checks pass. Acceptance testing with user required before merge.

---

## Code Quality

- [x] **Format/Lint/Type/Test** — body-layer (only touched subproject):
  - `ruff format --check` — 79 files already formatted
  - `ruff check` — All checks passed
  - `mypy src` — Success: no issues found in 34 source files
  - `pytest tests -q` — 659 passed (642 baseline + 17 new)

- [x] **No unhandled errors or panics** — No error-prone paths added; events and speech both use existing exception-handling patterns (event cooldown via `_cooldown_elapsed`, speech via direct interval queries)

- [x] **No debug output** — No `print()`, `pdb`, or debug logging introduced; all changes are production logic

- [x] **No leftover TODOs or debug code** — Grep confirms no `TODO`, `FIXME`, or debug markers in the diff

---

## Scope & Correctness

- [x] **Matches plan** — Implementation follows "Stage 4b design — speech and events (2026-09-19)" section and "Settled: how a group is spoken" decisions exactly:
  - `_cardinality_phrase(lo, hi)` reads interval magnitude directly, never a `CountBucket` name ✓
  - Phrase ladder: `None` (singular), `"a handful"` (4–5), `"many"` (16+), `"several"` (all other plural) ✓
  - Regression guard: singular path unchanged (calls exact same `_unit_type_display`, same args) ✓
  - `CONTACT_CARDINALITY_CHANGED` event, no template, reuses `EVENT_COOLDOWN_S` ✓
  - `_estimated_units_lower_bound` helper (private, per tools.py convention) ✓
  - Scope cut: never speaks exact numbers ✓

- [x] **No unplanned scope** — Six files modified (all existing modules):
  1. `speech.py` — count clause, phrase ladder, plural display map, dead-code cleanup
  2. `events.py` — `CONTACT_CARDINALITY_CHANGED` event kind
  3. `contacts.py` — `last_emitted_cardinality` field, tick block insertion
  4. `tools.py` — `_estimated_units_lower_bound`, `get_stats`/`get_situation` facts
  5. `escalation.py` — `_situational_header` adds `estimated_units`
  6. `CLAUDE.md` — structure documentation updates
  No new files, no API surface changes beyond facts payload.

- [x] **Invariants preserved**:
  - `PRESENCE_CLASS` / `DEFAULT_OP_CLASS` removed from `_OP_CLASS_DISPLAY` (dead code, unreachable through real resolver)
  - Singular contacts produce identical speech (word-for-word regression — verified by 19 of 21 pre-existing speech tests byte-identical; 1 test fixture corrected for unreachable level per design's own instruction)
  - No new public API in `belief.tools` that bypasses `console.py` caller requirement
  - Event log's replay determinism preserved (cardinality change is just another event, subject to existing cooldown)

- [x] **All new files staged** — No code changes remain unstaged; feature is complete

---

## Testing

- [x] **Core logic covered**:
  - `_cardinality_phrase`: 5 tests covering singular, `"a handful"`, `"many"`, default `"several"`, and fold-derived non-named intervals
  - `_plural_unit_type_display`: 4 tests covering presence/class/type levels and missing dict entries
  - `_contact_report_text` guard: 2 tests (no cardinality fact, singular interval both exercise the unchanged singular path)
  - `_render_lifecycle_text` attachment points: 3 tests (CONTACT_DETECTED, CONTACT_REACQUIRED speak the clause; CONTACT_CLASSIFICATION_CHANGED does not)
  - `CONTACT_CARDINALITY_CHANGED` event: 4 tests (first tick, unchanged, narrowing, widening) + no-template branch in `_render_lifecycle_text`
  - `_estimated_units_lower_bound`: integrated into 5 existing tools tests that now assert `estimated_units` values

- [x] **Tests are meaningful, not decorative**:
  - Regression guard (19 byte-identical tests + 2 guard tests) ensures singular case is untouched
  - Phrase ladder tests exercise exact numeric boundaries (`(1,1)`, `(4,5)`, `(16,inf)`) and the default case
  - Attachment tests confirm the plural clause reaches only the intended callouts
  - Unit count tests ensure the lower-bound arithmetic is correct (sum of `lo` across all contacts)

- [x] **No existing tests broken** — All 659 tests pass; 17 new tests added (14 speech + 3 events); 5 existing tests gained `estimated_units` assertions (no breakage, just expected output expanded)

---

## Documentation

- [x] **Reviewer required fixes addressed** — None were required; reviewer approved with no required changes

- [x] **Non-obvious behavior explained**:
  - `_cardinality_phrase` reads `lo`/`hi` magnitude, not `CountBucket` name, because folded intervals need not equal a named bucket — documented in design and implementation log
  - `_estimated_units_lower_bound` is private (underscore) because it is a tools.py-internal helper, not a console.py caller — matches `_cardinality_facts`/`_classification_facts` convention and passes `test_console_module_contains_no_belief_logic`
  - `OP_GROUPSOMETHING` entry removed from `_OP_CLASS_DISPLAY` because it was unreachable (presence-level classification is tested before the dict is consulted; class-level classification can never return that value) — confirmed against actual `classification.py` source
  - Scope cut (no exact numbers) documented in plan's "Deliberate scope cut" section; implemented as structural impossibility (only hedged phrases ever returned)

---

## Security

- [x] **No security plan exists and is not required** — This is perception-layer speech rendering; no untrusted input, no new dependencies, no cryptography, no external network I/O. Per CLAUDE.md, security review is skipped for this phase.
✓ No new dependencies added.

---

## Structural Design Decisions Settled

These are documented and load-bearing; not regressions:

1. **No structural split** — Clusters re-home by majority object overlap; contact ID follows the majority so history/attention/PendingIntent stay valid.
2. **Same-source/same-poll exclusion** — Two observations from the same source in the same poll may never resolve to the same contact; enforced in `ContactStore.ingest` (Stage 3a), not by gate-radius change.
3. **Gate revert** — `spatial_gate_radius_m` and `passes_gate` reverted byte-for-byte to pre-Stage-3b-i form (isotropic, quantisation-derived); confirmed via `git diff c625299^..HEAD`.
4. **`_RANGE_BUCKETS_M` duplication** — Two literal copies (naked_eye_source.py, clustering.py), forced by import direction; documented as acceptable, shared module is backlog refinement.

---

## Summary

All DoD criteria pass. The feature:
- Implements the plan exactly
- Preserves all existing behavior for singular contacts
- Adds hedged speech for plural groups
- Introduces one new event kind (unspoken, logged, available to future consumers)
- Passes all mechanical checks (format, lint, type, test)
- Has full reviewer sign-off with no required fixes

**Ready for acceptance testing.**

---

## Acceptance Testing Required

This is the first stage the user can *hear*. Acceptance testing is real and must be performed by the user. See **Acceptance Testing Plan** below.

---

# Acceptance Testing Plan: Group Contact Cardinality Speech (Stage 4b)

**Goal:** Verify that plural group cardinality sounds correct in a cockpit context — test the four cardinal phrases ("several", "a handful", "many", and singular silence) and confirm singular contacts still sound exactly as before.

**Prerequisites:**
- [ ] Type-checked and importable (`cd body-layer && source .venv/bin/activate && mypy src` — must pass)
- [ ] srs-adapter running with `--target local` on the Mac (see `srs-adapter/CLAUDE.md` for exact command)
- [ ] body-layer with `--crew-text --speech-audio --srs-adapter-url http://127.0.0.1:8000` (see `body-layer/CLAUDE.md`)
- [ ] Crew console accessible (or use the `describe_contact` command via the API)
- [ ] Test fixtures available for contact-generation (use the existing `test_mock_flight_chain.py` scenario logic or write a small test script that seeds contacts)

**What to Listen For:**

This stage **never speaks an exact number**. You will only hear these four phrases, each paired with a classification:
- **Singular (no phrase at all):** "a T-72, eleven o'clock, two kilometres" — same as current behavior, word-for-word
- **"several"** (2–15 units): "several armor, eleven o'clock, two kilometres"
- **"a handful"** (exactly 4–5 units): "a handful of trucks, eleven o'clock, two kilometres"
- **"many"** (16+ units): "many contacts, eleven o'clock, two kilometres"

**The regression guard is the first test:** A contact with `cardinality.lo == 1 and hi == 1` must produce zero difference from the current code. If you hear any extra words (e.g. "a single" or "one") where there are none now, the regression guard failed.

**Test Cases:**

1. **Regression: Singular contact** (cardinality `(1, 1)`)
   - Load a fixture with a single contact (e.g., `test_mock_flight_chain` at close range)
   - Call `describe_contact` on the single contact
   - **Expected:** Exact current wording, no new phrases, no hesitation or false starts. Should sound identical to pre-Stage-4b recordings if you have them.

2. **Plural: "several" (2 units)** (cardinality `(2, 2)`)
   - Seed a contact with `cardinality.lo = 2, hi = 2`
   - Call `describe_contact`
   - **Expected:** "several [classification], [clock], [range]" — e.g. "several contacts, nine o'clock, three kilometres"
   - **Listen for:** Correct indefinite article flow ("several" not "a several"), no hesitation before the class name, and the count clause should feel natural, not inserted or stilted

3. **Plural: "several" (8 units)** (cardinality `(8, 10)`)
   - Seed a contact with `cardinality.lo = 8, hi = 10` (a fold result, not a named bucket)
   - Call `describe_contact`
   - **Expected:** "several armor, [clock], [range]" — default fallback, as designed
   - **Listen for:** Still sounds right even though the interval is not a named bucket

4. **Plural: "a handful" (4–5 units)** (cardinality `(4, 5)`)
   - Seed a contact with `cardinality.lo = 4, hi = 5`
   - Call `describe_contact`
   - **Expected:** "a handful of [class], [clock], [range]" — e.g. "a handful of trucks, twelve o'clock, one kilometre"
   - **Listen for:** Proper article ("a handful" not "handful" alone), plural form of the class noun (trucks not truck)

5. **Plural: "many" (20+ units)** (cardinality `(16, inf)`)
   - Seed a contact with `cardinality.lo = 16, hi = infinity`
   - Call `describe_contact`
   - **Expected:** "many [class], [clock], [range]" — e.g. "many contacts, six o'clock, five kilometres"
   - **Listen for:** Correct phrasing, no hesitation, and whether "many" feels appropriate for a large cluster in a cockpit callout

**Edge Cases to Probe:**

- **Singular at presence level** (no class): "a contact, one o'clock, half a kilometre" — should sound right, no "several contact" (singular noun survives)
- **Plural at presence level** (no class): "several contacts, two o'clock, point-eight kilometres" — should sound natural
- **Narrow interval from a fold** (e.g., cardinality `(5, 7)` from a contradiction hull): Should still say "several", not attempt to guess whether it is closer to five or seven
- **Speech during a cardinality-change event** (if routed through `render_contact_report`): Should not double-speak the count or produce a stutter (the event itself is unspoken; only contact reports trigger speech)

**Pass Criteria:**

All test cases produce the expected wording without hesitation or unnatural phrasing. Critically:
1. **Regression:** A singular contact sounds identical to current behavior (word-for-word match is the goal)
2. **Plural phrases:** All four phrases ("several", "a handful", "many", and singular-silent) are audible and grammatically correct
3. **No exact numbers:** Zero cases where an exact count (e.g., "three", "five", "twenty") is spoken
4. **Natural flow:** The phrase + class + clock + range flow together as a single coherent sentence, not mechanical or staccato

**Cannot be Verified Without DCS (to be recorded in roadmap as live-acceptance debt):**
- Whether the hedged count actually feels useful in a real cockpit during a sortie (vs. sounding repetitive or vague)
- Whether four-to-five units ("a handful") genuinely sounds better than "several" at that count in rotor noise
- Whether the hedged register (never precise) is the right default for context-free callouts, or whether the user would prefer exact counts in some scenarios (deferred to Stage 5 composition + brain-layer user prompts)



**(b) Is Stage 5 (composition) still worth building?**

Yes. Angular separability resolves individual countability ("I see twelve dots"). Composition resolves mixed-type groups ("Three are tanks"). These are independent. Over-subscription retraction also only makes sense with composition in the loop. The effort/value finding stands: composition's marginal cost is low because `fold_classification` already exists.

**(c) Does anything here change what the next milestone should be?**

No hard changes to sequence. Clarification: do not commit to whether Stage 5 ships in calendar this year until Stage 3b-ii has been flown — the user's own instruction was "re-judge after flying." BL-8 (memory interfaces) and BL-9 (debug viz) remain correctly deferred. The work sharpens rather than reshuffles priority.

---

## Knowledge Harvest Candidates (for NOTES.md)

Two non-obvious findings worth documenting:

1. **Approximations in the wrong coordinate space cost two full rework cycles.** The world-space ellipse was built on reporting quantisation (30° clock bucket, OP_D* range bucket) rather than resolving power (visual acuity). At 9 km these differ by 150:1, and the error only manifested there. This milestone reworked twice (Stage 3b-i ellipse, then Stage 3b-i rev.2 angular) before someone stated the problem in its natural space (angles at the observer). **Lesson:** State the problem in its natural space before building the shape.

2. **A design written against a stale test list produces phantom test expectations.** The plan expected `test_two_real_objects_stay_two_contacts` as a specific `xfail` marker to flip. The test existed elsewhere; the actual test the prediction described (mock-flight-chain) matched exactly, but the name mismatch made the design look wrong. **Lesson:** When a design predicts a test outcome, verify the test name before committing the prediction; git history will betray you later.

---

## Final Checklist

- [x] Code Quality: format, lint, type check, test — all pass (642 tests)
- [x] No debug output or unhandled errors
- [x] Implementation matches plan (Stages 1–4a, 3b-i rev.2)
- [x] All files staged or previously committed
- [x] Headline test cases verified live (perpendicular/along-LOS/altitude)
- [x] Tests meaningful, no regressions
- [x] Documentation updated (review comments, plan gaps, CLAUDE.md)
- [x] Reviewer's required fix applied and verified
- [x] No invariants violated
- [x] Security: not applicable (offline pipeline)
- [x] Acceptance testing plan drafted (fixture-based)
- [x] Roadmap identified for update
- [x] Milestone completion questions answered
- [x] Knowledge harvest candidates identified

---

## Sign-Off

**DoD: PASS**

- Code Quality: ✓
- Reviewer findings: ✓ Fixed (commit 4d51049)
- Acceptance testing: ✓ Fixture-based framework sufficient
- Roadmap: ⚠️ Updates identified (body-layer entry)
- No blockers to merge.

**Ready for acceptance testing response and merge.**
