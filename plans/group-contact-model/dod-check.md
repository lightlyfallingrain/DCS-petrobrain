# Definition of Done: Group Contact Speech (feature/group-contact-speech)

**Date: 2026-09-19**

**Result: PASS — All mechanical checks pass. Acceptance testing with user required before merge.**

---

## Code Quality

- [x] **Format/Lint/Type/Test** — body-layer (only touched subproject):
  - `ruff format --check src tests tools` — 75 files already formatted
  - `ruff check src tests tools` — All checks passed
  - `mypy src` — Success: no issues found in 34 source files
  - `pytest tests -q` — **664 passed** (642 baseline + 22 new tests)

- [x] **No unhandled errors or panics** — Speech rendering uses existing exception-handling patterns; events use existing cooldown machinery

- [x] **No debug output** — No `print()`, `pdb`, or debug logging in committed code

- [x] **No leftover TODOs or debug code** — Diff clean of debug markers

---

## Scope & Correctness

- [x] **Matches plan** — Implementation follows Stage 4b design exactly:
  - Cardinality phrase ladder: `None` (singular), `"a couple of"` (2-3), `"a handful"` (4–5), `"several"` (fallback), `"many"` (16+)
  - Hedges never speak exact numbers except when watched/priority with exact interval ≤12 ✓
  - `CONTACT_CARDINALITY_CHANGED` event with existing cooldown machinery ✓
  - `_cardinality_phrase` carries its own connector (`"a handful of"`, `"a couple of"`) ✓
  - Regression guard: singular path byte-identical to pre-4b ✓

- [x] **No unplanned scope** — Five files modified (all existing):
  1. `speech.py` — cardinality phrase ladder, attention-earned precision, connectors, dead-code cleanup
  2. `events.py` — `CONTACT_CARDINALITY_CHANGED` event kind
  3. `contacts.py` — `last_emitted_cardinality` field, tick-block insertion
  4. `tools.py` — `_estimated_units_lower_bound`, `get_stats`/`get_situation` facts
  5. `tools/speak_samples.py` — new acceptance aid (dev-only, not shipping code)
  No new API surface changes beyond facts payload.

- [x] **Invariants preserved**:
  - Singular contacts produce identical speech (19 of 21 pre-existing regression tests byte-identical; 2 tests updated for unreachable level per design)
  - No omniscience violations added
  - Event log's replay determinism preserved

- [x] **All files staged** — No code changes unstaged on the feature branch

---

## Testing

- [x] **Core logic covered**:
  - `_cardinality_phrase`: 5 tests (singular, hedge boundaries, fold-derived intervals, attention-earned precision)
  - Phrase attachment points: 3 tests (CONTACT_DETECTED/REACQUIRED speak the clause, CLASSIFICATION_CHANGED does not)
  - Attention-earned exact counts: 5 tests (exact interval when attended, hedge held when inexact, cap at twelve, singular guard)
  - `_estimated_units_lower_bound`: 5 existing tools tests now assert `estimated_units` values

- [x] **Tests are meaningful, not decorative**:
  - Regression guard confirms singular case untouched
  - Boundary tests exercise exact numeric thresholds
  - Attention-earned precision tests ensure the honesty condition (inexact interval always hedges, even when watched)

- [x] **No existing tests broken** — All 664 tests pass; 22 new tests added; existing tests expanded with new assertions, no breakage

---

## Documentation

- [x] **Reviewer required fixes addressed** — One fix required in commit `950c490`: `speak_samples.py`'s docstring command is now correct (`PYTHONPATH=src:../world-model/src .venv/bin/python tools/speak_samples.py`)

- [x] **Non-obvious behavior explained**:
  - `_cardinality_phrase` reads interval magnitude directly, not `CountBucket` name — necessary for fold-derived intervals
  - Attention-earned precision rule documented in docstring and reflected in tests
  - Imperfect English ("a couple of armor", "three T-72") recorded as in-character, out of scope to polish

---

## Security

- [x] **No security plan required** — Offline pipeline, perception-layer speech rendering, no untrusted input, no new dependencies

---

## Acceptance Testing Vehicle

**`body-layer/tools/speak_samples.py`** is the acceptance aid. It:
- Renders the four cardinal speech phrases through the real `_contact_report_text` function
- Prints a table of (scenario label, rendered text) pairs for manual review
- Can POST each line to a running `srs-adapter --target local` for audio playback (optional `--speak` flag)
- Does **not** require Windows, DCS, or the aircraft layer
- Regression guard: asserts that explicit `(1,1)` cardinality and absent cardinality render identically

**Correct invocation** (from `body-layer/`):
```sh
# Print the table
PYTHONPATH=src:../world-model/src .venv/bin/python tools/speak_samples.py

# Print and speak (srs-adapter running on --target local)
PYTHONPATH=src:../world-model/src .venv/bin/python tools/speak_samples.py --speak
```

---

## Summary

All DoD criteria pass. The feature:
- Implements Stage 4b exactly
- Preserves all existing behavior for singular contacts (regression guard passes)
- Adds hedged speech for plural groups and attention-earned precision
- Introduces one new event kind (unspoken, logged, available to future consumers)
- Passes all mechanical checks (format, lint, type, test)
- Has full Reviewer sign-off (4 commits since prior approval, all re-verified)

**Ready for acceptance testing.**

---

# Acceptance Testing Plan: Group Contact Cardinality Speech (Stage 4b)

**Goal:** Verify that plural group cardinality sounds correct and attention-earned precision functions as designed — test the cardinal phrases and the honesty condition under attention.

**Prerequisites**
- [ ] Type-checked and importable (`cd body-layer && source .venv/bin/activate && mypy src` — must pass)
- [ ] `srs-adapter` running with `--target local` (optional, for audio; see `srs-adapter/CLAUDE.md`)
- [ ] `body-layer` venv active (required for `pyproj` seam)

**What to Listen For**

This stage **never speaks an exact number except when a contact is watched/priority with a precise interval**. The four cardinal phrases are:
- **Singular (no phrase):** "T-72, eleven o'clock, two kilometres" — unchanged from pre-4b
- **"a couple of"** (exactly 2–3 units, any attention): "a couple of armor, eleven o'clock, two kilometres"
- **"a handful of"** (exactly 4–5 units, any attention): "a handful of trucks, eleven o'clock, two kilometres"
- **"several"** (6–15 units, or any plural outside named buckets): "several contacts, nine o'clock, three kilometres"
- **"many"** (16+ units): "many armor, six o'clock, five kilometres"
- **Exact number** (watched/priority contact with precise interval ≤12): "three T-72s, twelve o'clock, one kilometre"
- **Exact number hedged back** (watched/priority with precise interval >12): "many contacts, ..." (hedge resumes above the spoken cap)
- **Inexact interval kept hedged** (watched/priority with fuzzy interval, e.g., `(4,5)`): "a handful of trucks, ..." (never manufactured precision)

**The regression guard is the first test:** A singular contact (`(1, 1)` cardinality) must produce zero difference from the current code. Run:
```
PYTHONPATH=src:../world-model/src .venv/bin/python tools/speak_samples.py
```
The output should show a line asserting that explicit `(1,1)` and absent cardinality render **IDENTICALLY**.

**Test Cases**

1. **Regression: Singular contact** — `(1, 1)` cardinality
   - Expected: Exact current wording, no new phrases, identical to pre-Stage-4b if recordings exist
   - Check: Both "singular, type (REGRESSION GUARD)" and "singular, no cardinality fact" render the same text

2. **Plural: "a couple of"** (2–3 units) — `(2, 2)` and `(3, 3)`
   - Expected: "a couple of [class]" with correct article flow and plural form
   - Listen for: Natural phrasing, not mechanical

3. **Plural: "a handful of"** (4–5 units) — `(4, 5)`
   - Expected: "a handful of [class]" with correct article and plural form
   - Listen for: Whether "handful" feels right for that count in a cockpit

4. **Plural: "several"** (6–15 units, or fold-derived 4–7) — `(8, 10)` and `(4, 7)`
   - Expected: "several [class]" with natural article flow
   - Listen for: Default fallback sounds right for intervals outside named buckets

5. **Plural: "many"** (16+ units) — `(16, inf)`
   - Expected: "many [class]"
   - Listen for: Appropriate for large clusters

6. **Exact count when watched** — exact intervals ≤12 with `attention="watch"`
   - Expected: "three T-72s" (for `(3,3)`, attended), "eight [class]" (for `(8,8)`, attended)
   - Listen for: Correct number, article, and plural form

7. **Exact count capped** — exact interval 13+ with `attention="watch"`
   - Expected: "many [class]" (hedge resumes; cap is 12)
   - Listen for: No leak of "thirteen" or other numbers above the cap

8. **Inexact interval stays hedged** — e.g., `(4, 5)` with `attention="watch"`
   - Expected: "a handful of [class]" (hedge held, never "four or five")
   - Listen for: Attention does not manufacture precision

**Edge Cases to Probe**
- **Singular at presence level:** "contact, one o'clock, ..." — no "a contact" (singular noun survives)
- **Plural at presence level:** "several contacts, ..." — plural form correct
- **Type-level classification:** "a couple of T-72" (plural form of the type name)

**Pass Criteria**
1. **Regression:** Singular renders identically (word-for-word match vs. pre-4b)
2. **Phrases:** All cardinal phrases present and grammatically correct
3. **Honesty:** No manufactured precision — inexact intervals always hedge, exact counts capped at 12
4. **Flow:** Phrase + class + clock + range flow as a coherent sentence

**Cannot be Verified Without DCS (live-acceptance debt list)**
- Whether hedged cardinality (never exact) actually feels useful in a real cockpit during a sortie
- Whether "a handful" genuinely sounds better than "several" at 4–5 units over rotor noise
- Whether the absence of exact numbers is the right default, or whether users would prefer exact counts in some tactical scenarios (deferred to Stage 5 composition + user feedback)

---

## Milestone Completion Question: Stage 5 (Composition)

**Context:** The group contact model's headline motivation was twelve real units collapsing into five contacts that never separated. The angular model (Stage 3b-i, rev.2) now resolves that case exactly — twelve perpendicular units at 9 km become twelve contacts; the same layout along the line of sight stays one contact with cardinality reporting "a group of several." The acuity floor that originally justified a Stage 3b-ii sortie was found to be non-binding; the optic multiplier cancels out.

**What this means for Stage 5:** Does composition (mixing of types within a group) add value now that cardinality alone resolves the twelve-unit case?

**What to listen for on the next sortie that argues for or against building composition:**

1. **For building composition:** Do you hear callouts where *kind separation* matters more than *count*? Examples: "several armor and support vehicles" instead of "several vehicles" would add tactical context; "two tanks and three BTR personnel carriers" tells you something a group count alone does not. If contacts mixing types sound vague or unactionable, that's the signal that composition buys clarity.

2. **Against building composition:** Do hedged cardinality callouts ("several armor", "a handful of trucks") already give you what you need to act? If you find yourself thinking "I know it's several vehicles; I don't care whether it's two tanks and three trucks," that suggests composition's marginal value is low. Cardinality + class already gives you enough to decide tactics.

3. **The honest check:** Under time pressure or high workload, is an exact count ever actually better than a hedge? ("Three T-72s" vs. "a handful of tanks"? Or does "a handful" free up your attention for something else?) This informs whether Stage 5's composition tool (which still never reports exact per-type counts, just relative composition) is worth the complexity.

The user's own instruction (2026-09-18) was to "re-judge this after flying." The sortie that exercises the F10 vocabulary (Stage 4b's next sortie) is the one to re-judge on.

---

## Summary

- **DoD: PASS** — All mechanical checks pass, no blockers to merge
- **Acceptance testing:** Ready, via `body-layer/tools/speak_samples.py` (no DCS required)
- **Reviewer:** Full approval with required fixes applied (commit `950c490`)
- **Roadmap:** Updates required (see below)
- **Knowledge harvest:** One candidate (unit test isolation vs. integrated output)

---

## Roadmap Updates Required

**`body-layer/ROADMAP.md`**: Group contact entry needs three changes:

1. Mark **Stage 4b ✅** as done
2. Record the new rule: **Attention earns precision** — a watched/priority contact with an exact interval speaks the real count (capped at twelve); an inexact interval keeps the hedge regardless of attention (no manufactured precision)
3. Update the remaining stages note: Stage 3b-ii's scope is now questionable (acuity calibration sortie's main purpose removed by rev.2's finding), Stage 5's decision deferred to next sortie feedback, Stage 6 still pending

**Root `ROADMAP.md`**: Body Layer row already notes "first five stages merged 2026-09-18"; update the status table to reflect 4b done and the cardinality-plus-speech fact.

---

## Knowledge Harvest Candidate

**Finding:** Unit tests asserting a component in isolation passed, while the integrated output was wrong, and only rendering the full speech phrase exposed it.

**Context:** Stage 4b introduced connectors ("a handful of", "a couple of") as part of the phrase itself, not as separate composition logic. A test asserting `_cardinality_phrase` returned the right phrase could pass ("a handful of" correct) while `_contact_report_text` produced grammatically wrong output if the composition step lost the connector or duplicated it. Early draftwork had exactly this error: the phrase carried "of", then composition added another "of", producing "a handful of of trucks". The full-sentence render (via `speak_samples.py`) caught it immediately; a unit test of the phrase alone would not.

**Implication:** For perception-layer logic that composes text, integration tests (full callout render) are not optional validation; they catch grammar errors no component test can.

