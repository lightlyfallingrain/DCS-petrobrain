# BL-2.6 — session state / resume point

**Transient working file.** Delete at DoD; `plan.md` and `todo/todo.md` are the durable records.
Written 2026-09-09 to survive a context clear, at the user's request to stop after the Architect.

Branch: `feature/classification-refinement`, branched from local `main` at `a7733f5` (the BL-2.5
merge). Plan committed as `5cf8969`. **No implementation code written yet.**

## Where this stands

| Stage of the role sequence | State |
| --- | --- |
| Architect | **Done** (`5cf8969`) — `plan.md`, 468 lines, 10 implementation stages |
| Investigator (invoked by Architect) | **Done** — Session 6 addendum appended to `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` |
| Implementer | **Not started — deliberately stopped here by the user** |
| Reviewer / DoD | Not started |

**The user stopped the Auto-Advance chain after the Architect.** Do not start implementing on
resume without checking in — and in particular, **four decisions are escalated and unanswered**
(below). Decision 1 changes what the milestone's headline behaviour looks like, and Stage 2
onwards depends on it.

## The four escalated decisions — UNANSWERED as of 2026-09-09

Full text in `plan.md`, "Decisions Requiring User Input". In short:

1. **Cap the naked-eye channel at coarse class, or let it reach a specific type at close range?**
   Plan of record caps it — the investigator established ED's own ambient vocabulary has *no*
   per-model fragments, so coarse class is ED's answer to "what can a crew member see without the
   sight." Under the cap, `something → tank → T-72` still lands in full, but `T-72` arrives from
   the **scope**, not from closure. **This is the load-bearing one** — it decides what the user
   actually sees in the cockpit. Architect recommends: cap.
2. **Move the naked-eye gating tier `medres` → `lowres` (Stage 7)?** A *separate axis* from
   grading. Grading alone cannot produce a `something` stage — that needs the detection gate
   extended outward, so Petrovich also notices **more**, further away. That is the opposite
   direction from "make him worse," which is why it needs an explicit yes. Architect recommends:
   yes.
3. **`NAKED_EYE_RANGE_CAP_M = 5000`** — accept that it binds the presence tier and flattens the
   size curve for everything truck-sized and up, or raise it (to what)? Already open from PB-1.5;
   BL-2.6 is where it starts to matter.
4. **Should classification *level* ever decay, not just confidence?** Plan says no — confidence
   decays, level is sticky. The user's own framing ("Petrovich forgetting that he identified
   something is arguably correct") points the other way. One-constant change; cheaply revisitable
   after Stage 8 rather than blocking Stage 1.

Also flagged: Stage 7 will **rewrite rather than extend** the tier-threshold assertions in
`test_visibility.py` / `test_naked_eye_source.py`, since those constants are the thing being
changed. That trips an AGENTS.md escalation rule ("existing tests must be rewritten rather than
extended") and is called out in the plan rather than done silently.

## Design, in one paragraph

Four totally-ordered *levels* (`unknown` → `presence` → `class` → `type`) with a shallow tree over
*values*, in a new `body-layer/src/belief/classification.py` which also re-homes `_op_class_of` /
`class_compatibility` out of `association_over_time.py`. Specificity is driven by the same
angular-radius quantity that already gates detection, so there is one calibration surface, not two
that can disagree. `Contact.classification` is **folded, not overwritten** — higher refines, equal
reinforces, **lower holds**, incompatible-at-equal-or-higher collapses to the common ancestor. That
fold is the fix for the last-writer-wins oscillation that would otherwise spam refine/de-refine
events. `last_class_raw` keeps its exact current meaning and stays the association gate's input —
feeding the gate the monotone best-claim would make it progressively stricter and start rejecting
genuine re-observations. Confidence decays on `IDENTITY_HALF_LIFE_S` (declared in `decay.py` since
BL-2, never consumed until now). Monotonicity makes threshold-edge hysteresis structurally
unnecessary.

## Stages

1 re-home class resolution (pure move) · 2 lattice + fusion, mechanism only · 3 the event ·
4 surfacing (tools/console/overlay) · **5 LIVE ACCEPTANCE #1 (recommended)** · 6 tier-derived
confidence in the naked-eye channel, gate unchanged · 7 calibration: gate `medres`→`lowres`, own
commit · **8 LIVE ACCEPTANCE #2 (required)** · 9 tuning pass, constants only · 10 docs.

Mechanism and calibration never share a commit — the BL-2.5 lossy-revert lesson applied directly.

## Offline execution

**Stages 1–4, 6, 7, 10 are fully offline.** The user asked (2026-09-09) that work be able to
continue with **no access to the DCS install or Saved Games**, and the plan's "Offline execution"
section inventories every DCS-derived fact against where it is committed: tier constants, the full
`OP_*` vocabulary, the 595-row reporting-name TSV, per-type sizes, and six *real* scope indication
strings (`Ural truck`, `Slava cruiser`, `Tarantul III corvette`, `SA-3 launcher`, `SA-3 Low Blow
radar`, `Civilian bus`) that Stage 2 lifts into a fixture with provenance. **No samples were
invented.** Note `win-mac-sync/from-windows/` is gitignored and will not exist offline — cite the
committed research docs, never that path.

**Needs a live DCS:** Stages 5, 8 (acceptance sorties) and 9 (tuning values are a function of
Stage 8's observations).

## Next steps, in order

1. **Get the user's answers to the four escalated decisions** — at minimum #1 and #2 before
   Stage 2. #3 and #4 can be deferred until after Stage 8 if the user prefers.
2. Implementer on Stages 1–4, then Reviewer per AGENTS.md Auto-Advance.
3. Live acceptance #1 (Stage 5) — needs the user.
4. Stages 6–7, then live acceptance #2 (Stage 8, required), then 9–10, Reviewer, DoD.
5. Merge on user approval.

## Carry-over from BL-2.5 (merged `a7733f5`)

One open defect in the Backlog: **the overlay window clips its last line** at 420x200. The fix
existed (`apply_content_size()`) and was reverted with the rejected restyle by the user's explicit
choice. Re-implementing it independent of cosmetics is the obvious candidate. Not part of BL-2.6.

## Verification

```sh
V=body-layer/.venv/bin   # NOTE: there is no aircraft-layer/.venv; tools live in body-layer's
$V/ruff format --check <sub>/src <sub>/tests && $V/ruff check <sub>/src <sub>/tests
cd <sub> && ../$V/mypy src && ../$V/pytest tests -q
# baseline at branch point: 67 aircraft-layer, 210 body-layer
```

Commit messages end with:

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PyBUHKWzZDmkLugmR4HRtw
```
