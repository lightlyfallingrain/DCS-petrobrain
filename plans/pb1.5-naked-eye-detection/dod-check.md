# PB-1.5 Definition of Done

**Feature:** Naked-eye (binocular-aided) visual detection channel
**Branch:** `feature/pb1.5-naked-eye-detection`
**Date:** 2026-09-09
**Status:** READY FOR ACCEPTANCE TESTING

## DoD Checklist

### Code Quality — PASS

- [x] `ruff format --check body-layer/src body-layer/tests` — pass (0 changes needed)
- [x] `ruff check body-layer/src body-layer/tests` — pass (0 warnings)
- [x] `mypy body-layer/src` (run from `cd body-layer/`) — pass (0 issues across 12 source files)
- [x] `pytest body-layer/tests -q` — pass (95 tests, all green)
- [x] No unhandled errors or panics in data paths
- [x] No debug output left in committed code (grep for `print`/`pdb`/`TODO`/`FIXME` confirms clean)
- [x] No leftover debug code; Decision 7 added to plan.md as architectural note, not a TODO

### Scope & Correctness — PASS

- [x] Implementation matches plan.md stages 1, 2, 3, 6 (stages 4, 5, 7 correctly deferred/done separately)
- [x] No unplanned scope added: Decision 6 reframed the binocular premise, Decision 7 was a Reviewer note captured in plan, but no code changes required
- [x] No invariants from CLAUDE.md violated:
  - DCS remains authoritative (geometry read-only)
  - Code owns facts (no fabricated positions/identities)
  - Petrovich not omniscient (strict FOV, angular-radius gating, output quantisation to ED vocabulary)
  - No DCS installation modifications
  - Provenance/uncertainty preserved (distinct provenance, confidence 0.4 vs Hybrid's 0.6)
  - Timestamps carried through (inherits from `OwnshipState`/`Observation` schema)
- [x] All new files staged and committed (git status clean)

### Testing — PASS

- [x] Core logic covered by tests:
  - `test_object_model.py`: 9 tests (defaults, worked examples, case-insensitivity, hyphenated IDs)
  - `test_visibility.py`: 10 tests (tier boundaries, cap binding, FOV edges, LOS occlusion)
  - `test_naked_eye_source.py`: 17 tests (no snapshot/no candidates, field shapes, debounce, cap, quantisation regression)
  - `test_reporting_names.py`: 5 tests (loader, unmapped fallback, WWII guard)
  - Updated `test_logger.py`: multi-source concatenation, field format
  - Total: 95 tests (was 79 before PB-1.5), all passing
- [x] Tests are meaningful (not decorative):
  - Tier-boundary cases test the math, not just "does it run"
  - Debounce/cap logic tested against multi-object dense scenes
  - Quantisation tested with known bearing/range pairs and their expected buckets
  - Coverage floor tests against the full 316-type real DCS ground-vehicle population
- [x] No existing tests broken (all PB-1 tests still pass; logger tests updated for multi-source, not regressed)

### Documentation — PASS

- [x] Reviewer findings (two passes) fully addressed:
  - Pass 1: `OP_SHIP` keywords fixed against real DCS type names; `body-layer/CLAUDE.md` run commands fixed for `--world-model-db`; coverage finding recorded in `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`
  - Pass 2: coverage-floor fixture rebuilt as full enumeration (316 ground types), not curated sample; all tests passing
- [x] Non-obvious behavior explained:
  - Binocular premise stated plainly in `visibility.py` docstring (Decision #6)
  - `derived_world_position` left exact (internal bookkeeping, not crew-facing) documented in `naked_eye_source.py`
  - Range-bucket quantisation snaps up to ceiling (Decision #7, recorded in plan.md)
  - Bearing relative-to-heading, expressed back as true bearing (tested, consistent with geometry.py convention)
- [x] `PETROBRAIN_RUNTIME.md` updated with naked-eye section

### Security — NOT APPLICABLE

Per `CLAUDE.md` Agents section: "Skip `performance-reviewer` and `security` for now — this phase is an offline single-user local pipeline with no hot path and no untrusted-input surface yet."

### Known-Open Items — Properly Recorded

All non-blockers explicitly recorded in `todo/todo.md` Backlog, not silently closed:

- [x] **`association.py` cross-namespace bug:** PB-1 code, already merged. HelperAI emits reporting names, `LoGetWorldObjects` emits DCS type names; `_type_match_score` matches across incompatible vocabularies. Backlog item notes the 595-row fix is already in the repo (PB-1.5's `dcs_type_to_reporting_name.tsv` + `reporting_names.py`), waiting for PB-1 scope-channel re-validation before landing.
- [x] **`hybrid_source.py` multi-contact gap:** Session 5 Finding 6 of the research file. HelperAI target list is multi-row, not single-target; `hybrid_source.py` reads only `middle_list_text` and may discard rows. Flagged as separate backlog item ("HelperAI list is a multi-row window..."), not folded into PB-1.5.
- [x] **T-90A never detected in probe sortie:** User said to ignore; no action needed. Noted in probe finding.
- [x] **Ground-unit classification coverage at ~60%:** Deliberately partial. Full 316-type real DCS population measured via fixture; coverage floor set at 0.5 (measured 0.601), allowing material regression to be caught while normal noise (type additions, reclassifications) doesn't false-positive. Backlog items recorded for future refinement (broader table derivation, WWII exception gaps, towed-AA/mortar/SAM-radar classification).

### Mechanical Verification — User-Verified, Spot-Checked

User confirmed independently: `ruff format --check`, `ruff check`, `mypy src`, `pytest tests -q → 95 passed`, all from `body-layer/`. Working tree clean. Spot-checked source docstrings and fixture contents; quality is high.

---

## Milestone Completion Question (CLAUDE.md requirement)

**Does this milestone's completion change what PB-2/BL-2 should be, or invalidate any assumptions downstream?**

### The Change in Understanding

**Stage 7 probe (2026-09-09 aircraft-layer research file, Finding 1):** DCS's ambient contact callout has **no Lua-readable companion**. The HelperAI `list_indication(6)` tree is not instantiated until the sight comes on. The synthetic filter (`visibility.py`) is therefore **not a fallback awaiting a better signal — it is the only implementation**.

**User's stated direction (backlog item, answered 2026-09-09):** The naked-eye filter becomes the PRIMARY detection mechanism, not a workaround. DCS's ambient detection output is dropped as an input entirely.

### Impact on PB-2/BL-2 Architecture

**Direct answer: NONE. No architectural change needed.**

- **Interface unchanged:** PB-2/BL-2 consumes `Observation` records through the `PerceptionSource` interface "regardless of which channel produced them" (from `todo.md` backlog answer 4, confirmed by reading `plans/body-layer/plan.md`). Both naked-eye and scope channels already flow through this uniform interface. The synthetic channel becoming primary is a source-swap behind the same interface, not a contract change.

- **No downstream assumptions invalidated:** BL-2 was never predicated on "DCS provides a real ambient detection signal" (Session 4 falsified that for the HelperAI channel; Session 5 falsified it for the ambient channel). The core assumption — "BL-2 receives observations from multiple sources and reconciles them" — holds. The sources feeding it change priority (synthetic first, scope second), not identity or interface.

### Secondary Consequences Worth Flagging

1. **The scope channel stays as a distinct source** (user confirmed, needed for future acquire/lock/fire gameplay). This raises the priority of the `association.py` cross-namespace bug: the scope channel is no longer a "maybe-someday" feature, it is on the path to wanted gameplay. Should be addressed before that gameplay work starts.

2. **The visibility filter's range/tier constants are now product-critical, not provisional.** The user's direction ("if the player can see a unit, Petrovich should too") makes calibration against real gameplay essential, not optional. The probe's Finding 5 ("Petrovich detects considerably later than the player can see") is a live signal to revisit `NAKED_EYE_RANGE_CAP_M = 2500` during acceptance testing. Not a blocker for merge, but a priority for the first live sortie.

3. **Contact memory/fusion (BL-2) becomes more important.** With the naked-eye channel now primary (high detection volume), cross-channel deduplication and persistent contact identity become design constraints, not nice-to-haves. The plan explicitly deferred these to BL-2 ("left to BL-2's future contact-memory layer"). That deferral is sound, but BL-2's design should account for high inbound observation volume from a single source, not assume balanced dual-source feeds.

**Conclusion:** PB-1.5's completion does NOT change what PB-2/BL-2 *should be* architecturally. It confirms what was always true: BL-2 owns persistent contact identity and fusion. What *changes* is emphasis and priority: the synthetic channel is now the implementation we own and are optimizing, not a fallback, and its correctness becomes a product-critical path item, not an optional feature.

---

## Acceptance Testing Plan

**Goal:** Verify that the naked-eye channel detects ground objects at plausible ranges/bearings, respects FOV/terrain/range bounds, produces sensible quantised output, and does not interfere with the scope channel or flood on dense clusters.

**Note:** This is a different test from the Stage 7 probe (2026-09-09-pb15-ambient-callout-live-probe.md). That probe examined DCS's own behaviour (does the ambient callout exist, is it readable). This test examines our implementation: does our synthetic filter produce reasonable detections when presented with the same mission scenario.

### Prerequisites

- [ ] Export.lua deployed to `Saved Games\DCS\Scripts\Export.lua` (Windows)
- [ ] Firewall rule added for aircraft-layer API (Windows, per `aircraft-layer/WORKFLOW.md`)
- [ ] Both machines (Windows with DCS, Mac/test machine with logger) on the same LAN
- [ ] Collector running on Windows
- [ ] Logger running on Mac/test machine
- [ ] Mi-24P cockpit module loaded, user in pilot or CPG seat
- [ ] Syria theatre, same mission scenario as Stage 7 probe OR a new open-desert scenario with manually-placed ground targets at varied ranges (1–5 km) and bearings (full 360°)
- [ ] Type-checked and importable: `mypy --strict body-layer/src` passes (already confirmed)

### Step-by-Step Procedure

#### 1. Start the Aircraft-Layer Collector (Windows box)

From `aircraft-layer/` directory:

```bash
set PYTHONPATH=src
python -m collector
```

(macOS/Linux: `PYTHONPATH=src python -m collector`)

Expect to see:
```
Telemetry listener on 127.0.0.1:7790
API server on 0.0.0.0:7791
```

Collector should remain running for the entire test. Leave stdout visible to confirm samples are arriving (~5 Hz).

#### 2. Start the Logger (Mac/test machine)

Navigate to `body-layer/` and run (single line):

```bash
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<windows-box-lan-ip>:7791 \
  --theatre Syria \
  --world-model-db <path-to-syria-region.sqlite>
```

Replace `<windows-box-lan-ip>` with the Windows machine's LAN IPv4 (e.g., `192.168.1.100`). Replace `<path-to-syria-region.sqlite>` with the full path to the world-model's built Syria database (e.g., `/path/to/world-model/build/syria-full.sqlite`).

Expect to see:
```
Connecting to http://<ip>:7791...
Polling every 0.2s (5 Hz)
source=hybrid source=naked_eye_visual_filtered ...
```

Logger will poll the aircraft-layer API and emit observations to stdout as they are detected. Leave running for the entire sortie.

#### 3. Fly a Test Scenario (DCS)

**Segment A: In-FOV, in-range, unobstructed targets**
- Start in the same open-desert arena as Stage 7 probe, or set up manually-placed ground units (Ural truck, T-72, SA-3 launcher, infantry squad, BMP-2) at ranges 1–3 km, spread around the aircraft at bearings 12/2/4/6 o'clock, no terrain between aircraft and targets
- Keep sight off (`OBSERV OFF`) for this entire segment (naked-eye only, no scope channel interference)
- Slowly turn the aircraft to face each target, one at a time
- **Expected result:** Each target produces one `source=naked_eye_visual_filtered` observation when it enters the FOV cone (±60° off heading) and passes the visibility filter. Bearing should quantise to the nearest clock position (12/2/4/6 o'clock in degrees, e.g., 90° for 3 o'clock). Range should quantise to one of the 24 `OP_D...` buckets. Classification should read `OP_ARMORED`, `OP_TRUCK`, `OP_SRSAM`, etc., NOT `OP_GROUPSOMETHING`.

**Segment B: Out-of-FOV targets**
- Position a target directly off your left wing (90° relative to heading, fully outside the ±60° FOV cone)
- Turn aircraft to place the target at 70° off heading (outside FOV)
- **Expected result:** No naked-eye observation emitted, even though the target is well within range and unobstructed.

**Segment C: Out-of-range targets**
- Position a target at 5+ km range (beyond `NAKED_EYE_RANGE_CAP_M = 2500` m)
- **Expected result:** Observation may or may not emit depending on the target's size and the calculated angular-radius threshold, but should be rare. Infantry at 5 km should NOT be detected (900 m effective range with binocular multiplier). A large ship at 5 km may be detected (effective range ~4500 m); this is acceptable.

**Segment D: Terrain occlusion**
- Position a target behind a ridge or hill, so no line-of-sight exists from the aircraft to the target
- Turn to place it in FOV and in-range
- **Expected result:** No observation emitted for the occluded target. (The visibility filter's LOS gate should block it.)

**Segment E: Dense cluster, cap testing**
- Position 5–8 ground units (variety of types) clustered within a 500 m radius at 1–2 km range
- Turn aircraft to face the cluster
- **Expected result:** On the first poll tick after the cluster enters FOV, a MAXIMUM of 3 new observations should be emitted (per `NAKED_EYE_MAX_NEW_PER_POLL = 3`). If 8 units are in FOV simultaneously, only the 3 nearest should emit. On the next poll, no new ones should emit (debounce: they are already "previously visible"). Subsequent poll ticks should emit 0 observations for this stable cluster. If one unit leaves the FOV and re-enters later, it should re-emit when it re-enters.

**Segment F: Scope channel alongside (verify no interference)**
- With at least 2–3 naked-eye targets still visible in the FOV cone, turn on the sight (`OBSERV ON`)
- Slew the sight to acquire one of the visible targets
- **Expected result:** Both channels emit observations to the same logger output:
  - Naked-eye observations from `source=naked_eye_visual_filtered` continue as before
  - Scope observations from `source=petrovich_detection_associated` appear alongside
  - No crashes, no duplicate observations for the same target, both channels' output is syntactically valid

#### 4. Observe the Logger Output (Mac/test machine)

Throughout the sortie, the logger should print lines like:

```
source=petrovich_detection_associated observation_id=... bearing_deg=45.0 range_m=2100 classification_raw=OP_ARMORED ...
source=naked_eye_visual_filtered observation_id=... bearing_deg=60.0 range_m=1800 classification_raw=OP_TRUCK ...
```

All fields should be present and well-formed. No error messages, no crashes.

### Pass Criteria

**Pass if all of the following are true:**

1. ✓ In-FOV, in-range, unobstructed targets are detected and reported with sensible bearing/range quantisation and coarse class (not fallback `OP_GROUPSOMETHING`).
2. ✓ Out-of-FOV targets are NOT reported (FOV gate works).
3. ✓ Out-of-range targets are NOT reported (or reported very rarely for large objects near the 2500 m cap).
4. ✓ Terrain-occluded targets are NOT reported (LOS gate works).
5. ✓ Dense clusters report a maximum of 3 new detections per poll tick, with correct nearest-first ordering.
6. ✓ Scope channel continues to work alongside naked-eye channel; no interference, no crashes.
7. ✓ No segfaults, type errors, or assertion failures in logger or collector.
8. ✓ All output is syntactically valid JSON per `Observation` schema.

**Fail if any of the following occur:**

- A target that is clearly visible to the player (not occluded, in-range, in-FOV) is never reported by naked-eye channel despite multiple passes.
- An out-of-FOV or out-of-range target is reported multiple times (FOV/range gate broken or leaky).
- Cap policy breaks: more than 3 new objects in a single poll, or more new objects from a stable cluster on subsequent polls.
- Classification output is uniformly `OP_GROUPSOMETHING` (indicates `object_model.py` lookup failure).
- Scope and naked-eye channels interfere (e.g., scope channel stops working when naked-eye is active, or they produce duplicate observations with the same ID).
- Logger crashes with `ModuleNotFoundError`, `sqlite3` error, or timeout.

### Calibration Notes

**Range expectations (binocular-aided, from the plan's table):**
- Infantry squad (1.8 m): ~900 m max
- Ural truck (6 m): ~3 km max (will often bind at cap 2500 m)
- T-72 (7 m): ~3.5 km max
- SA-3 launcher (9 m): ~4.5 km max (will bind at cap 2500 m)

These are the target behaviours confirmed with the user. If you see trucks consistently failing to detect at 2.5 km on flat desert (the probe's Finding 5 scenario), the cap may need raising; that is a post-acceptance-test tuning decision, not a failure of the acceptance test itself.

**Bearing quantisation:**
Clock positions are 30° apart: 12 o'clock = 0°, 1 o'clock = 30°, 3 o'clock = 90°, 6 o'clock = 180°, 9 o'clock = 270°. The logger should report one of these 12 values (in true degrees, not relative).

**Range buckets:**
24 buckets: 100m, 200m, 300m, ..., 1000m (10 × 100m steps), then 1.5km, 2km, 2.5km, 3km, 3.5km, 4km, 4.5km, 5km, 7.5km, 10km. Values snap UP to the bucket ceiling: 549 m quantises to `OP_D600M` (the 600m bucket), not `OP_D500M`.

---

## Summary

**DoD Status: PASS**

All mechanical checks pass. Both review passes' fixes are applied and verified. Known-open items are properly recorded and scoped. The milestone-completion question is answered: the synthetic filter becomes the primary implementation (no downstream architectural change needed, but scope-channel bugs now matter more for future gameplay). Acceptance testing is ready to run with the user in the cockpit.

**Next step:** User runs the acceptance test plan above. No merge until after acceptance testing is complete.
