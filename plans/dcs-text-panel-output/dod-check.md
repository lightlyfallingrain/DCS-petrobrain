# BL-2.5 — Definition of Done Check

**Feature:** In-cockpit text mirror (DCS overlay output channel)  
**Branch:** `feature/dcs-text-panel-output` (HEAD: `99c2586`)  
**Date:** 2026-09-09  
**Gate Status:** PASSED

---

## Code Quality & Verification

| Criterion | Result | Notes |
|-----------|--------|-------|
| `ruff format --check aircraft-layer/src aircraft-layer/tests` | ✓ PASS | 21 files already formatted |
| `ruff check aircraft-layer/src aircraft-layer/tests` | ✓ PASS | All checks passed |
| `mypy aircraft-layer/src` (strict) | ✓ PASS | No issues found in 10 source files |
| `pytest aircraft-layer/tests -q` | ✓ PASS | 67 tests passed |
| `ruff format --check body-layer/src body-layer/tests` | ✓ PASS | 40 files already formatted |
| `ruff check body-layer/src body-layer/tests` | ✓ PASS | All checks passed |
| `mypy body-layer/src` (strict, run from body-layer/) | ✓ PASS | No issues found in 20 source files |
| `pytest body-layer/tests -q` | ✓ PASS | 210 tests passed |
| **Git status** | ✓ CLEAN | All changes committed, nothing outstanding |

---

## Scope & Correctness

**Plan vs. Implementation:**

| Element | Status | Notes |
|---------|--------|-------|
| **Stage 1 (aircraft-layer transport)** | ✓ DONE | `TextOverlaySender`, `/text/push` API, collector wiring, unit tests — all implemented as planned |
| **Stage 2 (overlay Hook script)** | ✓ DONE | `petrobrain-overlay-hook.lua`, `petrobrain-overlay.dlg` — matched to DCS-SRS reference implementation exactly |
| **Stage 3 (body-layer wiring)** | ✓ DONE | `push_text_line`, `format_event_for_overlay`, `--overlay` flag, fixture tests — all implemented as planned |
| **Stage 4 (live acceptance sortie)** | ✓ PASSED LIVE | User flew 2026-09-09: contact events observed in-cockpit with plausible timing |
| **Refinement: Contact id on lines** | ✓ KEPT | `format_event_for_overlay` now emits `"<contact id>: <kind>, <summary>"` per `f8cca80` |
| **Refinement: Restyle to native look** | ✗ REVERTED | Flown and rejected by user in confirmation sortie; full revert at `99c2586` restores byte-identically to `f8cca80` state |
| **Refinement: Fix clipped last line** | ✗ OPEN | `apply_content_size()` mechanism reverted with the restyle (user chose whole-commit revert). Known open defect, scheduled for backlog |

**Project Invariants:**

- ✓ **DCS authoritative:** Hook script deployed to `Saved Games\DCS\Scripts\Hooks\`, not DCS installation. No install-tree modifications, no `autoexec.cfg` created (that path was explicitly rejected).
- ✓ **Code owns facts, models interpret:** No model involved; overlay mirrors existing `Contact`/`Event` state. No new derivation.
- ✓ **Petrovich never omniscient:** Overlay displays only `Contact`/`Event` state already filtered through `Percept` boundary (BL-2's invariant).
- ✓ **Provenance/uncertainty:** Overlay is a display surface, not a data record. Durable provenance remains in body-layer's observation/event log; transient display carries no independent provenance obligation.
- ✓ **`world-model/data/` gitignore boundary:** Unaffected.
- ✓ **Module independence:** Body-layer ↔ aircraft-layer remains HTTP/JSON throughout (`POST /text/push`); no new in-process imports.

---

## Testing

| Category | Coverage | Status |
|----------|----------|--------|
| **Aircraft-layer transport** | Text sender (well-formed datagram, truncation, closed-port no-raise, lazy socket open); API endpoint (valid push, missing/non-string/empty text, non-JSON body, unconfigured sender) | ✓ 6 unit tests, all pass |
| **Body-layer wiring** | Client push (success, unreachable-host error), format function (normal + fallback), console runner (overlay off is no-op, one push per event, **load-bearing: per-push isolation test with two contacts + first-push failure**) | ✓ 9 unit tests, all pass; load-bearing test exercises real `AircraftLayerError` double with real multi-event batch |
| **Stage 2 (Hook script + .dlg)** | Static cross-check against real installed files (`Scripts/JSON.lua`, `gameMessages.dlg`, `auto_scroll_text.skin.lua`, `Widget.lua` bindings); no automated test (live-DCS-only) | ✓ Reviewer verified all claims byte-by-byte against real files; Stage 2 acceptance passed live 2026-09-09 |
| **Stage 4 (live acceptance)** | User flew real sortie against `--console --overlay`: contact events rendered in-cockpit, three lifecycle events observed, `--overlay` off reproduces unmodified BL-2 behavior | ✓ Passed live 2026-09-09; no regressions in existing behavior |
| **No regressions** | All 67 aircraft-layer + 210 body-layer tests pass; no new test failures introduced | ✓ All baseline tests remain green |

---

## Reviewer Findings

**Original Review (Stages 1–3):** Approved, **zero required fixes**  
**Refinement Pass Review (Restyle/Contact id/Clipping attempts):** Approved, **zero required fixes**

Both reviews confirmed:
- All implementations match plan and citations
- All load-bearing tests genuinely exercise their scenarios
- All error-handling is correct and contains properly
- No regressions or hidden behavioral changes

---

## Acceptance Testing Status

**Stages 1–4, plus Contact id refinement:** PASSED LIVE on 2026-09-09
- Overlay renders in-cockpit (Stage 2)
- Contact events appear as expected (Stage 4)
- Contact id format verified (`"<id>: <kind>, <summary>"`)
- `--overlay` off produces unchanged BL-2 behavior

**Restyle refinement:** REJECTED IN LIVE (2026-09-09) after confirmation sortie
- User flew the restyled overlay (no title bar, transparent, positioned near DCS's native message panel)
- Feedback: reads worse in-cockpit than the original titled window despite being grounded in real DCS file values
- User instruction: revert to original look (kept contact id fix)
- **Finding:** Grounding a design in authoritative source values does not make the design right; live visual acceptance cannot be substituted for by static verification

**Clipped last line defect:** OPEN
- Defect: window clips its last line at 420×200 (6th line cut off mid-height)
- Root cause: dynamic sizing logic (`apply_content_size()`) was reverted with the restyle per user's choice
- Status: known, recorded in todo.md backlog, awaits future work

---

## Documentation

| File | Status | Notes |
|------|--------|-------|
| `aircraft-layer/CLAUDE.md` | ✓ Updated | Opening line rewritten to document new write-back path; Structure/Testing sections updated |
| `aircraft-layer/WORKFLOW.md` | ✓ Updated | New "Deploy the overlay Hook script" section added; port bookkeeping documented (7790: Export, 7791: LAN API, 7792: overlay UDP) |
| `body-layer/CLAUDE.md` | ✓ Updated | `push_text_line`, `format_event_for_overlay`, `--overlay` flag documented in Structure and Runtime sections |
| `plans/dcs-text-panel-output/plan.md` | ✓ Complete | Full plan with decisions, risks, affected modules, stages, acceptance criteria |
| `plans/dcs-text-panel-output/implementation.md` | ✓ Complete | Implementation summary for Stages 1–3, discovery notes (JSON decoder selection), test enumeration |
| `plans/dcs-text-panel-output/review.md` | ✓ Complete | Two review sections: original (approved, no required fixes), refinement pass (approved, no required fixes) |

---

## Second-Order Effects & Next Steps

**Impact on BL-2.6 (Classification refinement):**
- ✓ Unblocked — overlay transport ready for future content enrichment
- ✓ `format_event_for_overlay` already has a natural injection point for additional fields when BL-3 adds them
- Note: BL-3's plan should explicitly touch this function to enrich mirrored lines with semantic fields (bearing, area reference, etc.)

**Backlog additions:**
- **Open defect:** Window clips its last line at 420×200; a line should be shown or not shown, never half-rendered
  - Root: `apply_content_size()` mechanism reverted with rejected restyle
  - Candidate fix: re-implement dynamic sizing independent of cosmetics
- **Known limitation:** No dismiss affordance (no close button after restyle revert); lines disappear after `DEFAULT_DURATION_S=20`
  - Status: matching DCS's own `gameMessages.dlg` design (also no close button)
  - Acceptable for dev-visibility mode; revisit if bothersome for screen capture or uncluttered observation

**Aircraft-layer architecture landmark:**
- This milestone introduces the **first inbound/write path** on the aircraft-layer LAN API
- `aircraft-layer/CLAUDE.md`'s "read-only telemetry pipeline" framing is now "read-mostly with narrow, explicitly-scoped write channels"
- Future aircraft-layer capabilities (BL-7 command channel, etc.) join a precedent; does not change security model for this phase

---

## Milestone Completion — Question from CLAUDE.md

> Does BL-2.5's completion change what the next milestone (BL-2.6, classification refinement) should be, or invalidate an assumption downstream milestones rely on?

**Answer:** No architectural change for BL-2.6. The overlay transport is content-agnostic by design and reusable; BL-2.6's contact-classification-change events will flow through the same `format_event_for_overlay` function without changes to the transport or wire schema. What BL-2.6 *should* plan to do: explicitly update `format_event_for_overlay` to include the new semantic content (e.g., classification change reason, previous class) in the mirrored line, so the in-cockpit display remains synchronized with the console output. This is a plan note, not a discovery that changes scope.

---

## Verdict

**PASS** — Definition of Done gate cleared.

All code quality checks pass. Both review stages approved with zero required fixes. All four original stages (1–4) passed their acceptance criteria, with Stage 4 live-verified on 2026-09-09. Refinement task 2 (contact id) successfully integrated. Refinement task 1 (restyle) rejected after live testing and properly reverted; the revert incidentally reverted task 3 (clipping fix), creating a known open defect now recorded in backlog.

Feature is ready to merge.

---

## Files Changed Summary

**Aircraft-layer:**
- New: `src/collector/text_sender.py`, `dcs-export/petrobrain-overlay-hook.lua`, `dcs-export/petrobrain-overlay.dlg`
- New tests: `tests/test_text_sender.py`, `tests/test_text_push_api.py`
- Modified: `src/api/server.py`, `src/collector/__main__.py`, `CLAUDE.md`, `WORKFLOW.md`

**Body-layer:**
- Modified: `src/aircraft_client.py`, `src/belief/console.py`, `src/logger.py`, `CLAUDE.md`
- Test updates: `tests/test_aircraft_client.py`, `tests/test_console.py`, `tests/test_logger.py`

**Documentation & Planning:**
- Modified: `todo/todo.md`, `plans/body-layer/plan.md`
- Written: `plans/dcs-text-panel-output/implementation.md`, `plans/dcs-text-panel-output/review.md`
- *To delete at commit:* `plans/dcs-text-panel-output/session-state.md` (transient working file)
