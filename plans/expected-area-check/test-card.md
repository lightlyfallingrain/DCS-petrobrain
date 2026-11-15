### Acceptance Testing Plan: Expected-area check — Stage 0a/0/1 (BL-B110)

**Card (published artifact):** https://claude.ai/artifact/GHLrELVKDaBDs1FDosbxfd — this file is
the source the card was generated from; read/update there if the test changes.

**Branch to fly: `main`, after merge.** This DoD pass merges automatically on PASSED
(root `CLAUDE.md`, "Workflow"); nothing below has been flown yet, so the roadmap entry carries
`#needs-flight` until a sortie clears it.

**Goal:** confirm Petrovich's new per-sector scan/binocular rhythm (sweep ahead, then alternating
flanks, 12 s of binoculars per cycle) behaves as designed in the cockpit, and specifically watch
the two items this stage's own measurements flagged as close to the edge of what it guarantees.

**Prerequisites**
- [ ] Type-checked and importable: `cd body-layer && .venv/bin/mypy src` — run, PASS (0 errors, 79
  source files).
- [ ] `body-layer/tests -q` full suite — run, PASS (3044 passed, 4 xfailed).
- [ ] Launch `body.py` against a mission with at least 2–3 ground groups spread across more than
  one o'clock sector (left/ahead/right), per `body-layer/CLAUDE.md`'s "Running the live logger"
  command. Normal operating envelope (`project_operating_altitude_envelope` memory): 50–800 m AGL,
  straight or circling approach at ~100 km/h.

**Test Cases**
1. Fly straight and level toward a group dead ahead — Petrovich should sweep ahead (12 o'clock)
   first, before the flanks, and raise binoculars on it within the first scan cycle if it is worth
   a look (expect this to feel the same as before this change for a contact already ahead).
2. Fly past two groups on opposite flanks (one left, one right) — Petrovich should alternate
   between the two flank sectors rather than finishing one side before starting the other, and
   should not binocular-glass continuously on one flank at the expense of the other (12 s rolling
   budget per cycle, gates a look's *start* only).
3. Watch a single flank contact across a full scan cycle with nothing else competing for
   attention — confirm it gets at least one naked-eye mention and, if worth a look, a binocular
   mention within roughly 30 s, not noticeably longer.
4. Command "watch" on a contact, then ask Petrovich to report on it — confirm he raises binoculars
   for an exact-location fix only after classification is already settled, not before (Priority 4,
   after Priority 3).

**Edge Cases to Probe**
- **Circling/sidestep sector-edge watch item (user's own cautious-approach profile):** while
  flying the ~100 km/h sidestep/orbit approach the plan calls out specifically, watch a contact
  that is near a sector boundary as it crosses from one sector to the next. The plan's own
  measurement says this can go **~30–40 s with no mention at all** in the worst case (28 s nominal
  quiet-sweep aliasing, growing toward ~40 s with a full glass budget in play) — this is a
  pre-existing eye-aliasing gap, not newly introduced, and is *not* fixed by this stage. Expected
  correct behaviour: the contact is not dropped or mis-identified, just quieter than usual for
  up to that long. Flag it if the silence feels longer than ~40 s, or if the contact is ever
  dropped/re-founded rather than just quiet.
- **`GLASS_STALL_COOLDOWN_S` (3 min) re-look watch item:** glass a contact that then sits still
  with nothing new to learn (e.g. already classified, not moving) — Petrovich should not retry a
  binocular look at it for about 3 minutes (180 s) unless you've closed enough range to make a
  retry worthwhile (`RETRY_RANGE_FRACTION`). Confirm he does eventually look again once that
  cooldown elapses or range has closed, rather than ignoring the contact forever.

**Pass Criteria**
The feature passes if the sector-order and budget behaviour in Test Cases 1–4 match the
description above, the two edge cases produce only the *expected* quiet periods (not a dropped
contact, not a wrong verdict), and no regression is visible in ordinary scan/binocular behaviour
relative to before this change.

**Known, disclosed, out of scope for this card:**
- Stage 2 (never folding an ambiguous memory-only match) is **not built and will not be** (BL-B110
  Decision 13 (a), 2026-11-10). A second group seen on a remembered group's bearing is often **not
  called out** (13–86% depending on optics and order) — known, measured, and carried by `[[BL-B111]]`
  and `[[BL-B114]]`. Note it if you notice it, but it is not a regression of this card.
- The same group re-sighted past ~2 min may be called twice (~10% by eye, `[[BL-B113]]`, deferred).
