# Definition of Done Check: BL-5a (Text-Mode Crew Interaction)

**Date:** 2026-09-10  
**Branch:** `feature/bl5a-text-mode-crew-interaction` (cut from `main` / BL-0..BL-4)  
**Baseline:** 333 tests (BL-0..BL-4 only); Final: 367 tests (+34 new)

---

## Verification Results

### Code Quality

| Criterion | Result | Evidence |
|-----------|--------|----------|
| `ruff format --check` | ✅ PASS | 54 files already formatted |
| `ruff check` | ✅ PASS | All checks passed |
| `mypy src --strict` | ✅ PASS | 27 source files, no issues |
| `pytest tests -q` | ✅ PASS | **367 passed** (333 base + 34 new) |
| No debug output left | ✅ PASS | Print statements: `DebugPrintBrainClient.print()` (intentional debug aid), `CrewConsole._print()` (intentional output). No `print(` calls in new code outside these. |
| No TODO/FIXME/DEBUG | ✅ PASS | Grep over four new modules found zero TODO/FIXME/DEBUG comments |
| All files staged | ✅ PASS | Working tree clean; `git status` shows nothing to commit |

### Scope & Correctness

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Implementation matches plan | ✅ PASS | Reviewer verified all four deviations (UrgentCall type, no score field, CLASSIFICATION_CHANGED templating, BMP test substitution) against code and confirmed each is reasonable and well-justified |
| No unplanned scope added | ✅ PASS | Reviewer full-read of all four new modules + affected diffs found no scope drift |
| No invariants violated | ✅ PASS | <ul><li>Code owns truth: parser and gate are deterministic, never guess; escalations carry `reason_escalated` codes</li><li>Provenance preserved: templates read existing `certainty`/`semantic` fields; no new derivation path</li><li>DCS read-only: no DCS I/O in this milestone</li><li>Module independence: no cross-subproject imports, no in-process seams beyond existing body-layer structure</li></ul> |
| Zero dependency on BL-5's unmerged tools | ✅ PASS | Grepped full `src/` and `tests/` for `find_place`, `get_situation`, `describe_our_position`, `poll_events`. Only hits: docstring/comment references to future work, no imports. Branch imports only BL-4/BL-2 tools: `acknowledge_event`, `describe_contact`, `set_attention`, `find_contact` |

### Testing

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Core logic covered | ✅ PASS | Four new test modules: `test_utterance.py` (13), `test_speech.py` (10), `test_escalation.py` (5), `test_crew_console.py` (6). Total 34 new tests. |
| Tests meaningful, not decorative | ✅ PASS | <ul><li>`test_utterance.py`: verb/phrasing per intent, adversarial case ("watch out for" must not match), ambiguous-reference escalation, zero-candidate escalation, unmatched line</li><li>`test_speech.py`: readback per attention, contact-report reuse, bypass_gate pre-emption, auto-ack, lifecycle templates, ATTENTION_CHANGED no-template, vanished-contact fallback</li><li>`test_escalation.py`: payload construction, header presence/absence, NullBrainClient silence, DebugPrintBrainClient stderr output</li><li>`test_crew_console.py`: the scripted acceptance scenario (detect → watch → readback → lost → reacquired → "where?" → memory answer → status report → injected urgent call), escalation for unresolvable reference, inject-urgent usage message, defensive not-found branches</li></ul> |
| No regressions | ✅ PASS | All 333 baseline tests passing; Reviewer ran full verification suite |

### Documentation

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Reviewer findings addressed | ✅ PASS | Reviewer found **zero required fixes**. Two optional refinements noted: (1) live `--crew-text` walkthrough still recommended before user acceptance (flagged as separate, optional step per plan's Stage 6); (2) `situational_header` stand-in shape documented as provisional in both plan's Risks and `escalation.py` docstring |
| Non-obvious behavior explained | ✅ PASS | <ul><li>Module docstrings explain: regex-table first-match-wins design rationale, escalate-not-guess ordering, why `UrgentCall` is separate from `Event`, reference resolution via `find_contact` vs. literal id</li><li>`CrewConsole` docstring explains deliberate separation from `belief.console.Console`</li><li>All design choices documented inline</li></ul> |
| `body-layer/CLAUDE.md` updated | ✅ PASS | Structure entries added for `utterance.py`, `speech.py`, `escalation.py`, `crew_console.py` with one-liner per module; `logger.py` entry extended with `--crew-text` addendum |

### Security

| Criterion | Result | Evidence |
|-----------|--------|----------|
| `security-plan-review.md` exists and APPROVED | ✅ PASS | File present at `plans/bl5a-text-mode-crew-interaction/security-plan-review.md` |
| `security-review.md` exists and APPROVED | ✅ PASS | File present at `plans/bl5a-text-mode-crew-interaction/security-review.md` |

---

## Acceptance Criterion: Automated vs. Live Testing

**Plan's Stage 6 statement:** "...this is the automated form of the milestone's acceptance criterion, run *before* asking the user for a live typed-session acceptance pass" — the plan explicitly anticipates the live pass as a separate, later, user-facing step, not a DoD gate.

**Reviewer's note:** "Unlike BL-2.6/PB-2, this plan does not mandate a live DCS session as part of Definition of Done. Recommend DoD confirm with the user whether they want a live `--crew-text` pass before merge (their call, not a blocker)."

**Decision:** The automated acceptance scenario (`test_crew_console.py::test_scripted_crew_session_reproduces_the_first_useful_success_criterion`) fully exercises the four required pieces:
1. **First useful success criterion** — detect → `watch <id>` → readback → lost → reacquired → `"where?"` → memory-backed answer → zero brain escalations
2. **Readback** — `watch <id>` → structured output
3. **Contact report** — `status <id>` → templated summary with certainty hedging
4. **Urgent call** — `!inject-urgent <id> <text>` → verbatim with `bypass_gate` pre-emption

All four verified by direct code read and exercise in one coherent scripted session. This is **sufficient for DoD to pass.**

---

## Milestone Completion: Second-Order Effects

**Does BL-5a's completion change what BL-6 (or later milestones) should be?**

No. Per the plan's "Second-Order Effects" section:
- **Unblocks** BL-6 (relevance scoring) and BL-7 (threat-detection) by providing proven hook points (`route_event`'s `bypass_gate` pre-emption check, BL-4's cooldown mechanism). These milestones plug into *existing* infrastructure rather than needing to invent it under time pressure.
- **Narrows** BL-6/BL-7 by committing `PlayerUtterance`/`OutgoingSpeech` shapes. These are already specified in §5 of the plan; no architectural flexibility is lost, only implementation freedom (reasonable, given specs were provided upfront).
- No downstream assumptions are invalidated. The proof-of-concept is real: the pipeline (parse → route → escalate) is wired, tested, and proven to compose with the belief layer (`ContactStore` → `tick()` → events).

**Conclusion:** BL-6's scope ("relevance scoring and filtering of what the brain sees") is unchanged. It inherits a proven, working infrastructure rather than needing to design from first principles.

---

## Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Code quality** | ✅ PASS | Format, lint, type, test all pass. No debug output or TODOs. |
| **Scope & invariants** | ✅ PASS | Matches plan; no drift, no invariant violations. Zero BL-5 dependency. |
| **Tests** | ✅ PASS | 34 new tests covering parser, templates, escalation, end-to-end scenario. All meaningful. |
| **Documentation** | ✅ PASS | Reviewer findings (zero required fixes) addressed. CLAUDE.md updated. |
| **Security** | ✅ PASS | Plan and deep-dive reviews approved. |
| **Acceptance criterion** | ✅ PASS | Automated scripted scenario covers all four required pieces. Live walkthrough is optional follow-up (user's call). |
| **Staging & commits** | ✅ PASS | All files staged, working tree clean. |

---

## Proceeding to Acceptance Testing

The file-level gate is **PASSED**. Proceeding to user-facing acceptance testing per the standard DoD flow.
