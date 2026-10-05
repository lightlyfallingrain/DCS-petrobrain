### Debug Report

**Date:** 2026-10-06 · **Branch:** `worktree-agent-a46d5a8b04e2de408` → `fix/callout-observability-gate`
**Base:** `main` @ `dce2534`

---

### Observed Issue

Petrovich speaks about clock hours his own cockpit mask declares unviewable, with a
classification attached — a direct no-omniscience violation
(`body-layer/CLAUDE.md`, "No omniscience is structural, not a convention").

From the 2026-10-05 sortie speech log (`~/dcs-belief-truth.jsonl`, `kind == "speech"`),
**20 of 357 spoken lines** were about masked hours — of which **17 are this defect** and 3 are a
documented pull-path decision (see "Size of the defect: 17, not 20" below):

| hour | lines | body azimuth | `_CO_PILOT_MASK.rear_cutoff_deg = 130.0` says |
|---|---|---|---|
| 4 | 6 | 120° | visible |
| **5** | **5** | 150° | **masked** |
| **6** | **4** | 180° | **masked** |
| **7** | **11** | 150° | **masked** |
| 8 | 11 | 120° | visible |

Real examples, with the gaze label from the same row:

- `unit 7 o'clock, very close is Tigr armored vehicle.` — gaze `11_oclock`
- `unit 6 o'clock, very close is infantry.` — gaze `12_oclock`
- `A couple of contacts, 5 o'clock, 2.5 kilometres.` — gaze `12_oclock`
- `Group, 5 o'clock, 4 kilometres.` — gaze `12_oclock`

The pilot reported this as lateness (*"unit 7 o'clock, which is late by definition because
Petrovich can't even see 7 o'clock"*). It is not latency; it is a correctness defect.
Context: `plans/post-review-fixes/explore-notes.md` §6 and decision 11.

---

### Size of the defect: 17, not 20 — and there is a *third* site, which is correct as it stands

The 20 masked-hour lines were correlated against the sortie's own `acted_token` history
(`~/dcs-speech.jsonl`, by `now_sim`); there were only seven report-family commands in the whole
sortie. Recorded as §9 of `plans/post-review-fixes/explore-notes.md` (`main` @ `5a656ad`), with a
security pass reaching the same conclusion independently.

| | lines |
|---|---|
| **no report-family command within 30 s — unprompted, the push path, this defect** | **17** |
| spoken 0.0–4.4 s after a report command — a pull-path answer | 3 |

The three pull-path lines are at `t_sim` 1601.0, 1734.3 and 2966.2.

**So `CrewConsole._handle_report` (`crew_console.py:1639`) is a third site that produces 5/6/7
o'clock output, and it is a deliberate decision rather than an oversight** — its own docstring:
*"belief survives the aircraft turning away; only the absence claim is withheld."* Its behaviour is
**left exactly as it was**, and its 3 lines are not part of this defect's count.

This fix cannot have touched it, by construction rather than by care: `_handle_report` calls
`render_group_full_disclosure`/`group_facts` directly and never reaches `scheduler.tick` or
`callout_observable`. Its own inline comment already says so — *"A report is pull-based, so it
always speaks fresh ... that exists only to throttle the push (`CalloutScheduler`) path."*

**Use 17, not 20**, wherever this defect's size is quoted (`BL-11` Stage 0 and `BL-B30`'s entry
both carry 20 and are being corrected from this report).

---

### Hypothesis

The hypothesis handed to this pass was that the observability gate introduced on 2026-09-27
(`plans/sortie-2026-09-26-fixes/plan.md` Stage 1, Fix A) is **correct but under-applied** —
that classification and group-disclosure callouts were never wired to it.

**Confirmed, and the reason is structural rather than an oversight: the gate was placed at
event *emission*, and group disclosure emits no event at all.**

`belief.contacts._callout_may_speak` is called from exactly two places, both inside
`ContactStore.tick`'s per-contact loop, and it governs exactly two event kinds —
`CONTACT_MOTION_CHANGED` (fifth block) and `CONTACT_RANGE_CROSSED` (sixth block). Every other
spoken path bypasses it.

---

### Evidence

**1. The real path for each of the four example lines, traced to its render branch.**

| spoken line | kind | render site | gate passed through |
|---|---|---|---|
| `unit 7 o'clock, very close is Tigr armored vehicle.` | `CONTACT_CLASSIFICATION_CHANGED` | `speech._render_lifecycle_text`, the `f"{lead} {clock} o'clock, {range} is {unit_type}."` branch | **none** |
| `unit 6 o'clock, very close is infantry.` | `CONTACT_CLASSIFICATION_CHANGED` | same branch (`_identification_lead` → `"unit"` for a type whose `op_class` is the object model's default) | **none** |
| `A couple of contacts, 5 o'clock, 2.5 kilometres.` | group disclosure | `speech.render_group_disclosure` → `_undifferentiated_phrase` | **none** |
| `Group, 5 o'clock, 4 kilometres.` | group disclosure | `speech.render_group_disclosure`, bare-word branch | **none** |

**2. `CalloutScheduler.tick` had no visibility check of any kind.** It is the single
speech-time choke point (`CrewConsole.drain_events` → `scheduler.tick` is its only caller) and
it gated candidates on `_TEMPLATED_KINDS`, `_consumed`, group membership,
`_WATCHED_ONLY_KINDS` + attention, `WATCH_REPORT_MIN_GAP_S`, `CALLOUT_MAX_AGE_S` and
`_last_spoken_signature` — and on nothing geometric. Confirmed by reading the whole function
and by grepping every `COCKPIT_MASKS`/`is_visible` call site in `src/`: `contacts.py`,
`visibility.py`, `logger.py`, `crew_console.py` (both of the latter two for the eyesight view
only), and nothing in `callouts.py`.

**3. Group disclosure could never have been reached by an emission-site gate.**
`tick` reads `store.groups` directly as a second candidate source and mints no `Event` for a
group's own trigger (`plans/group-reporting/plan.md` Stage 4's explicit design). There is no
emission site to gate.

**4. The founding path is *not* the leak, which is why the measured violations are only these
two kinds.** Both perception channels already respect the mask when a contact is founded:
`naked_eye_source` calls `check_visibility`, whose Gate 0/1 chain includes
`cockpit_mask.is_visible` (`visibility.py:750-760`); `hybrid_source` never checks the mask but
is confined by `association.FORWARD_HEMISPHERE_HALF_WIDTH_DEG = 90.0`, which is *narrower* than
the 130° rear cutoff. So `CONTACT_DETECTED`/`CONTACT_REACQUIRED` cannot found a contact dead
astern, and the sortie's violating lines are accordingly all post-founding kinds.

**5. The prior pass on this mechanism was read first** (`plans/callout-outside-gaze/debug.md`,
2026-09-26) and is **not** superseded by this one. It diagnosed the *wording* of
`CONTACT_RANGE_CROSSED` — a memory-based watch update reading as a fresh sighting — and applied
no code fix; its recommendation was later taken as the `"Getting closer, "`/`"Moving away, "`
leads now in `_render_lifecycle_text`. Different defect, same family. Its ruling-out of the
naked-eye gaze gate still holds and was re-confirmed by reading `visibility.py`.

**6. Probe confirming the geometry used by the new tests.** A contact at `(1000, 0, alt 500)`
with ownship at the origin at the same altitude: `last_observable_sim` is stamped at heading 0
(dead ahead, depression ~0 against 22° of clearance) and stays `None` at heading 180 (dead
astern, past the rear cutoff at any elevation).

---

### Fix Applied

**One gate, at the speech choke point, covering every spontaneous candidate.**

`body-layer/src/belief/contacts.py`
- `ContactStore._observability_tracked: bool`, set `True` the first time `tick` runs with an
  `ownship`.
- `ContactStore.callout_observable(contact, now_sim)` — a **read** of the bookkeeping
  `_callout_may_speak` already maintains, not a second mask computation. `ContactStore.tick`
  loops *every* contact with no early `continue` and runs immediately before
  `drain_events` in the poll loop (`logger.Runner.run_once`), so the answer is already current
  for this `now_sim`. Returns `True` when the bookkeeping has never run — which is what keeps
  every `tick()` caller that omits `ownship` a true no-op, and is why `None` can safely mean
  "confirmed never observable" everywhere else.

`body-layer/src/belief/callouts.py`
- `tick`'s event loop: skip a candidate whose contact is not observable-or-in-grace.
  **Placed after the `CALLOUT_MAX_AGE_S` check and skipped without consuming** — deferred, not
  lost. There is nothing stale about an identification Petrovich cannot see *yet*; the same
  line is correct the moment the bearing returns, and the age check is what bounds the wait.
  Ahead of that check, a permanently-astern contact's event would never be retired at all.
- `tick`'s group loop: skip a group **no** member of which is observable-or-in-grace. *Any one
  member is enough* — a group straddling the cutoff is a group he can genuinely see, and the
  disclosure line renders its position from the nearest member rather than per-member.

**Why the gate is total rather than a per-kind list.** The defect's whole shape is a per-kind
list that a new kind silently fails to join. `CONTACT_DETECTED`/`CONTACT_REACQUIRED` are now
gated too, which is close to a no-op in practice (see Evidence 4, and
`CALLOUT_OBSERVABILITY_GRACE_S == CALLOUT_MAX_AGE_S == 10.0`) but closes the overflight case
where a contact founded ahead is spoken about several seconds later from astern.

**The task's caveat is honoured by construction.** The gate is on *observability*, never on the
rendered hour: `CALLOUT_OBSERVABILITY_GRACE_S` (10 s, measured from the last *confirmed*
sighting) is exactly what absorbs a believed bearing that has drifted a few degrees past the
cutoff while the contact is genuinely observable. Pinned by
`test_classification_change_speaks_inside_the_observability_grace_window`.

**The coordinator's cross-plan constraint is satisfied without a design choice having to be
made**, because the two paths do not share a chokepoint. `scheduler.tick` has exactly one
caller, `CrewConsole.drain_events` (the push path). A pilot-initiated `report` goes
`handle_line` → `_handle_report` → `belief.speech` and touches the scheduler only via
`note_reply`, which is occupancy bookkeeping and gates nothing. `callout_observable` has no
call site outside `callouts.py`. Recorded in `callouts.py`'s module docstring so a later pass
does not "complete" the gate by wiring it to the pull path.

`body-layer/src/perception/motion.py` — **comment only; this was not a defect.** See below.

---

### The second scope item (`BL-B34`'s correctness half): not a live defect

`perception/motion.py:91` asserts *"objects arrive at 5 Hz, velocity at 1 Hz, so worst-case
skew is ~1 s plus transport"*, the basis of `MOTION_VELOCITY_MAX_SKEW_S = 2.0`. The concern was
that it reasons from a sample interval five times shorter than reality, since
`logger._DEFAULT_POLL_INTERVAL_S` has always been 1.0 s.

**Both rates are the aircraft-layer *producers*, and both are correct as written** — verified
against the installed Lua rather than against the plan that quotes them:

- `aircraft-layer/dcs-export/Export.lua:143` — `EXPORT_INTERVAL_S = 0.2` (5 Hz), gating the
  `LoGetWorldObjects` send at `:881`.
- `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua:91` —
  `POLL_INTERVAL_S = 1.0` (1 Hz), gating the velocity send.

**body-layer's poll rate cannot affect this bound.** The compared quantity
(`naked_eye_source._resolve_velocity_by_object_id`) is
`|world_objects_t_sim − unit_velocity["dcs_model_time_s"]|` — a difference between two
*producer* sim stamps. How often body-layer reads the two `/latest` endpoints does not enter
it. No threshold or integration anywhere depends on the consumer rate.

So: **no code change, and not a stale comment either.** The comment now names where each rate
comes from and says explicitly that the poll interval is irrelevant to the bound — because
`BL-B30` and `BL-B34` have each already read it as a claim about the poll loop and flagged it as
a mis-calibration, and a third re-derivation costs more than four lines of provenance.
(Roadmap/backlog files deliberately untouched, per the task's constraint.)

---

### Verification

All four `body-layer` checks, run from `body-layer/` with its own venv:

| check | result |
|---|---|
| `ruff format --check src tests` | 115 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy src` (CWD-only discovery, run from `body-layer/`) | Success: no issues found in 53 source files |
| `pytest -q` | **1473 passed, 4 xfailed** (baseline on `dce2534`: 1466 passed, 4 xfailed) |

**Seven new tests in `body-layer/tests/test_callouts.py`, and the three that cover the fixed
paths were confirmed to fail before the fix** (gate temporarily neutralised to a bare
`return True`, then reverted):

| test | pre-fix |
|---|---|
| `test_classification_change_is_silent_about_a_cockpit_masked_bearing` | **FAIL** |
| `test_group_disclosure_is_silent_when_every_member_is_masked` | **FAIL** (`['Group.'] != []`) |
| `test_classification_change_masked_past_the_grace_window_is_deferred_not_lost` | **FAIL** |
| `test_classification_change_still_speaks_about_an_observable_bearing` | pass (guard: not over-suppressed) |
| `test_classification_change_speaks_inside_the_observability_grace_window` | pass (guard: the caveat) |
| `test_group_disclosure_speaks_when_any_one_member_is_observable` | pass (guard) |
| `test_observability_gate_is_a_no_op_for_a_store_never_ticked_with_ownship` | pass (guard) |

That split is the intended shape: the three defect tests fail without the gate, the four guards
pass either way because they assert behaviour the fix must *not* change.

No debug instrumentation remains (`grep TEMP-PREFIX-PROBE src` is empty; the probe was a
reversible edit, reverted).

---

### For the user — queued, nothing blocking

1. **The one judgement call worth your eye: `CONTACT_DETECTED`/`CONTACT_REACQUIRED` are now
   gated too**, not just the two kinds that actually misfired. In practice this is near-nil
   (both channels respect the mask at founding, and the grace window equals the candidate max
   age), but it does mean a contact founded ahead and spoken about several seconds later from
   astern now goes quiet instead. That is the invariant applied consistently; if you would
   rather hear it late than not at all, say so and it narrows to two kinds in one line.
2. **This silences, it does not re-time.** The 17 unprompted masked-hour lines are now unspoken rather
   than spoken correctly — the contacts are still believed, still in the debug view, still
   answerable by a `report`. Whether some of them *should* reach you another way (an "I lost
   sight of it" marker, say) is a product question this pass deliberately did not decide.
3. **`CALLOUT_OBSERVABILITY_GRACE_S = 10.0` is still an untuned starting value**, by its own
   docstring, and this fix now makes it load-bearing for three more paths than it was. A sortie
   can measure it; nothing here changed the number.
