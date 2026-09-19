### Definition of Done Check — feature/contact-report-wording

**Reviewed against:** `body-layer/ROADMAP.md` "Contact report fine tuning" entry (four cheap items) and `plans/contact-report-wording/implementation.md` / `review.md`.

**Feature status:** Reviewer APPROVED (no required fixes, optional bookkeeping done).

---

## Checklist

### Code Quality

- [x] **Format/lint/type/test all pass** (body-layer only subproject touched)
  ```
  ruff format --check src tests        → pass (74 files already formatted)
  ruff check src tests                 → pass (all checks passed)
  mypy src --strict                    → pass (no issues in 34 source files)
  pytest tests -q                      → pass (677 passed, up from 664 on main; +13 new)
  ```
- [x] **No unhandled errors or panics** — All new code is tested; tests exercise boundary conditions and error paths.
- [x] **No debug output left in committed code** — Reviewed all changes; no print/logging statements left behind.
- [x] **No leftover debug code or TODO comments** — Implementation log confirms clean scope; no TODOs introduced.

### Scope & Correctness

- [x] **Implementation matches plan** — All four "cheap" roadmap items shipped:
  1. Spell units out: "kilometres"/"metres" in ranges and enrichment fragments ✅
  2. Acronym respelling: "Mi-8" → "M I 8"; SAM is exception (class-level, out of reach) ✅
  3. "very close" under 0.5 km replaces bare range ✅
  4. On/next-to feature proximity wording at 0-10m and 10-100m bands ✅
- [x] **No unplanned scope added** — Out-of-scope items explicitly deferred (bearing-from-feature wording, range uncertainty, airborne classification). Range uncertainty moved to detection-cones milestone; airborne classification deferred by user.
- [x] **No invariants violated** — `body-layer/CLAUDE.md` module independence maintained; world-model seam untouched; no new dependencies.
- [x] **All new/modified files staged** — Confirmed via `git status`.

### Testing

- [x] **Core logic covered** — 14 new tests added, 4 pre-existing updated:
  - TTS respelling: 4 new tests (known designation, case-insensitivity, unlisted tokens, SAM exception)
  - Wiring into rendering path: 2 new tests (type/plural level)
  - "very close" threshold: 1 new test (boundary at 500m)
  - Proximity bands: 5 new tests (on/next-to/near transitions, integration via `semantic_facts_for`)
  - Updated: `test_speech.py` x4, `test_crew_console.py` x1 (exact-text wording only)
- [x] **Tests are meaningful** — Not decorative; boundary conditions verified, integration tested, regression guard (singular cardinality) confirmed.
- [x] **No existing tests broken** — All 677 pass; net +13 new.

### Documentation

- [x] **Reviewer findings addressed** — No required fixes. Optional bookkeeping (marking four sub-bullets "done" in roadmap) was applied.
- [x] **Behavior explained** — `implementation.md` is thorough; `review.md` verified every change independently; roadmap updated with shipped status and user corrections noted.

### Security

- [x] **N/A for this feature** — Pure presentation/wording changes; no trust boundary, no data handling, no new external inputs. Project exempts security review for this phase per `CLAUDE.md`.

---

## Acceptance Testing Prerequisites

- [x] Type-checked and importable: `mypy --strict` passes; `speak_samples.py` imports the real `_contact_report_text` function and produces correct output.
- [x] All four roadmap items exercisable via `tools/speak_samples.py`'s `WORDING_SAMPLES` section (hand-built `facts` dicts rendered through the real functions).

---

## Verification Output

**Wording samples (exact output from `speak_samples.py`):**
```
range spelled out                                     |  armor, 3 o'clock, 3 kilometres.
very close (under 0.5 km)                             |  truck, 12 o'clock, very close.
known designation respelled (Mi-8)                    |  M I 8.
SAM is NOT respelled (the roadmap's named exception)  |  SAM.
semantic fragment distance rounded and spelled        |  armor near a road (~400 metres).
on the road (zero distance)                           |  armor on a road.
next to the road (~10-100 m)                          |  armor next to a road.
```

---

## Acceptance Boundary

What can and cannot be verified structurally:

**Can verify (fixture-testable):**
- Units are spelled out ("kilometres", "metres") ✅
- "very close" appears for ranges < 500m ✅
- Acronym table respells "Mi-8" correctly and leaves "SAM" untouched ✅
- On/next-to/near band logic executes in the right distance ranges ✅
- Regression guard: explicit (1,1) cardinality and absent cardinality render identically ✅

**Cannot verify without TTS voice (deferred to live sortie):**
- Whether "M I 8" actually sounds correct when spoken aloud (TTS voice quality/timing issue, not a code issue)
- Whether "very close" reads naturally as a register mid-flight vs. "over half a kilometre" (pilot judgment, not code correctness)
- Whether "on a road" is more useful than "near a road (~4 metres)" in live callouts (practical utility, requires hearing in context)

The actual TTS pronunciation is verifiable only by ear through a running `srs-adapter --target local` session. The fixture layer cannot reach this.

---

## Debt List Note

**This is the fourth item now waiting on a single sortie for live TTS voice acceptance.** Prior debt:

1. BL-4's attention/events tools (`set_attention`, `watch_area`, etc.) — deferred from BL-5 plan.
2. F10 vocabulary remainder (relative-vs-bearing sector rotation through 0/360 wraparound, `F10_SCAN_RADIUS_M` calibration) — merged 2026-09-16, first flight 2026-09-16/17, still unexercised.
3. Stage 4b speech (cardinality phrasing) — merged in a later milestone, not yet live-tested.
4. Contact report wording (TTS voice acceptance) — this feature, today.

This is worth surfacing explicitly: a single flight is accumulating significant value, and that density is either a scheduling efficiency (batch-test everything in one sortie) or a risk signal (too many unknowns landing simultaneously). Track the next sortie's capacity.

---

## Roadmap Updates

`body-layer/ROADMAP.md` already has:
- Four cheap sub-bullets marked "✅ All shipped 2026-09-19 (`9035317`)".
- Parent checkbox correctly stays `[ ]` open (bearing-from-feature is blocked on world-model work, so the item cannot close until that lands).
- User correction notes applied (0m threshold clarified to 10m, airborne deferred).

Root `ROADMAP.md` does not need updates; no Body Layer overall status changed.

---

## Milestone Completion Question

**Does completion of this feature change what the next milestone should be?**

No. The "Contact report fine tuning" item remains open (one expensive sub-item — bearing-from-feature — blocked on world-model coordinate changes). The body-layer speech surface is essentially complete until either:

1. World-model delivers bearing-from-feature data (then the bearing wording lands), or
2. A real sortie produces new observations (then the running-list grows).

Body-layer's next milestone (BL-9 onwards per `ROADMAP.md`) is independent of this item's completion.

---

## Result

**DoD: PASSED**

All criteria met. Ready for acceptance testing.
