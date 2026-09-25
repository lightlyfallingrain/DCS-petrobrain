### Debug Report

### Observed Issue
Live sortie report, `main` @ `b7ad1a5`: with `scan right` commanded (confirmed by the eyesight
view showing the gaze cone on the right), Petrovich spoke "ground 10 o'clock, 2 km" — a bearing on
the *opposite* side from where he was actively looking.

### Hypothesis
Not a gaze/perception defect. `CONTACT_RANGE_CROSSED` — one of `plans/watch-reporting/plan.md`'s
three "watched-only" callout kinds — renders through `belief.speech._contact_report_text` with
**no lead or event_clause at all** (Decision 3: *"no affixes at all — the range is already in the
body. This is the user's example verbatim."*), producing exactly the reported shape:
`"<unit type>, <clock> o'clock, <range> km."`. This event is emitted from `ContactStore.tick`'s
sixth block purely from **current ownship position vs. the watched contact's last *believed*
position** — it requires no detection this poll and is gated on attention (`watch`/`priority`) and
on the belief still being "fresh" (`certainty_of(...) in ("observed", "tracked")`, i.e. seen within
`POSITION_HALF_LIFE_S` = 30 s), never on current gaze. So a contact watched a few seconds to tens of
seconds ago, while Petrovich was looking elsewhere or has since redirected his scan, is reported
exactly as if freshly spotted — because the wording carries no signal that it is a memory-based
tracking update rather than a live sighting.

### Evidence
1. **The two upstream gaze-gating hypotheses are ruled out by reading the gate code, not
   assumption:**
   - `perception/visibility.py`'s Gate 0 (`within_gaze`) runs first and unconditionally for the
     naked-eye channel; `perception/gaze.py`'s `gaze_at`/`ScanPlan` resolves a **narrow
     `FOCUS_CONE_HALF_WIDTH_DEG = 15.0`** wedge that, under a commanded `right` scan, only ever
     cycles through `1, 2, 3` o'clock (`_SECTOR_LEGS["right"]`) — never anywhere near 10 o'clock.
     `gaze_for`'s peripheral bypass is confirmed inert (`peripheral_stimulus_ids` is always an
     empty `frozenset` — the attention-capture channel doesn't exist yet). So the naked-eye
     channel structurally cannot admit a 10 o'clock candidate while `scan right` is active.
   - `perception/hybrid_source.py` (HelperAI/`LoGetWorldObjects` channel) has zero gaze awareness
     (confirmed by grep — no reference to `gaze`/`scan_plan`), but it always emits
     `classification_level=3` (type-specific text like `"Ural truck"`) — it can never be the
     source of a `"ground"` (presence-level) callout for a contact whose folded classification
     hasn't since been refined.
2. **`CONTACT_RANGE_CROSSED`'s render path matches the reported text exactly.**
   `belief/speech.py::_render_lifecycle_text`, the `CONTACT_RANGE_CROSSED` branch:
   ```python
   if event.kind == CONTACT_RANGE_CROSSED:
       return _contact_report_text(result["facts"])
   ```
   No `lead`, no `event_clause` — unlike `CONTACT_MOTION_CHANGED` (`event_clause="moving"/
   "stopped"`) and `CONTACT_ENGAGEMENT_CHANGED` (`lead="Danger, "`/`"Safe from "`), which both
   carry a distinguishing marker. `CONTACT_RANGE_CROSSED` is the one watched-only kind with none.
3. **The emission condition, `belief/contacts.py::ContactStore.tick` sixth block**, is
   gate-on-attention and gate-on-belief-freshness only:
   ```python
   is_watched = current_attention in ("watch", "priority")
   ...
   range_m_value = range_m(observer, contact.last_position)   # ownship NOW vs. believed position
   ...
   fresh = certainty_of(contact, now_sim) in ("observed", "tracked")
   if past_deadband and fresh: ...
   ```
   `contact.last_position` is the contact's last *believed* position, not a fresh detection —
   `certainty_of` allows this up to `POSITION_HALF_LIFE_S` (30 s, `belief/decay.py`) after the
   contact was last actually seen by either channel, independent of current gaze. This is
   confirmed, deliberate design, not an oversight: `plans/watch-reporting/plan.md`'s Decision 3
   explicitly states the omission of affixes and cites the user's own example verbatim, and
   `tests/test_speech.py::test_route_event_contact_range_crossed_speaks_with_no_affixes` pins the
   exact behaviour with a docstring citing that decision.
4. **A `"ground"` label is consistent with this contact being naked-eye-only.** `_unit_type_display`
   renders a `classification_level == PRESENCE` contact as `"ground"` — exactly what a contact
   only ever picked up by the naked-eye channel's `lowres` tier (never refined by a HelperAI
   detection) would fold to and hold.

### Fix Applied
**None.** This is not a gate defect — gating `CONTACT_RANGE_CROSSED` on current gaze would be
wrong: it would suppress a legitimate "closing on something you told me to watch" report the moment
the player looks away, which is exactly the behaviour `plans/watch-reporting/plan.md` was built to
provide, and the debug task's own brief warns against exactly this failure mode ("getting this wrong
in the restrictive direction would make commanded scans hide real threats").

The real defect is a **wording ambiguity**: `CONTACT_RANGE_CROSSED`'s render is indistinguishable
from a live `CONTACT_DETECTED`/`CONTACT_REACQUIRED` sighting, even though it can legitimately
describe a contact up to 30 s stale and at any bearing regardless of where Petrovich is currently
looking. Fixing that means reversing `plans/watch-reporting/plan.md`'s Decision 3 — a deliberate,
user-specified format ("this is the user's example verbatim") that is pinned by an existing,
explicitly-worded regression test (`test_route_event_contact_range_crossed_speaks_with_no_affixes`).
Per the project's own Escalation Rules ("existing tests must be rewritten rather than extended" —
`AGENTS.md`), that is not a call for Debugger to make unilaterally: it is a product-wording decision
that needs the user's sign-off, not a code defect with one correct fix.

**Recommendation for the user:** give `CONTACT_RANGE_CROSSED` its own distinguishing lead (the same
pattern `CONTACT_ENGAGEMENT_CHANGED`/`CONTACT_MOTION_CHANGED` already use), e.g. a "Still tracking, "
or "Last seen, " prefix, so a memory-based watch update never reads as a fresh sighting outside the
current gaze. This is a one-line change in `_render_lifecycle_text` plus updating the one pinned
test — small, but it reopens a decision the user made explicitly, so it should be their call.

### Verification
No code changed. Confirmed by reading (not modifying) the gate chain, the render path, the emission
condition, and the existing pinned test, cross-checked against `plans/watch-reporting/plan.md`'s
Decision 3. `body-layer` baseline (`main` @ `b7ad1a5`) is unaffected — no files under `src/` or
`tests/` were touched.
