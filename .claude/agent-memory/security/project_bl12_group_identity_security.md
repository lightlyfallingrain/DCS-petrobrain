---
name: project_bl12_group_identity_security
description: BL-12 group-identity security deep analysis — group_trace_log.py matches the accepted speech_log/detection_trace_writer posture; BL-B59 eviction is visible in --group-trace but only partially bounded by non-group-dependent disclosure channels.
metadata:
  type: project
---

BL-12 ("Group-level contact identity and continuity") passed security deep analysis at
`33da5b4` (feature/bl12-group-contact-identity), APPROVED, no required fixes.

**`group_trace_log.py` / `--group-trace PATH`** is the fourth sortie-path file writer
(alongside `speech_log.py`, `detection_trace_writer.py`, `belief_truth_log.py`). It is
byte-for-byte the same posture as `speech_log.py`: unbuffered, `OSError`-only catch,
`_disabled=True` after first failure, path resolved via `logger.py`'s
`_resolve_group_trace_log_path` (expanduser, per-run stamp, `mkdir(parents=True,
exist_ok=True)`, degrades to `None` on `_RESOLVE_FAILURES` rather than crashing). Any future
sortie-log writer should be diffed against this family rather than re-derived from scratch —
the pattern is now applied four times identically.

**Arithmetic in `belief/groups.py` and `belief/position_belief.py`** (circular-mean heading,
centroid RMS uncertainty, covariance inverse/floor) is all guarded against division-by-zero
either by a minimum-sample-count early return, a `min_members` floor before any `fmean` call,
or an explicit degenerate-case branch. None of it needed a fix. `Contact.fold_displacement_m`
looks like an unbounded accumulator but resets on every unambiguous resolution and, even in
the pathological case of permanent ambiguity, only ever makes the admission gate *more*
conservative — never a crash, never a forced merge.

**`BL-B59`** (the fold-drift eviction defect, deferred by user decision, prioritised next):
independently confirmed two things worth remembering for any future pass on this area —
(1) `belief/callouts.py`'s observability gate filters `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
out of the push pool for grouped contacts, but explicitly does **not** filter
`CONTACT_CLASSIFICATION_CHANGED` the same way (it "still competes... grouped contact or not"),
and `CONTACT_ENGAGEMENT_CHANGED` is keyed on the contact's own `is_watched` state, not group
membership — so an evicted air-defence contact whose classification or engagement warning
already fired individually is not silenced by the eviction. (2) `--group-trace`'s phase
records (`overlap`/`property`/`found`/`expired`) carry each tick's *current*
`member_contact_ids`/`air_defence_composition`, so a consecutive-tick eviction is directly
visible as a shrinking roster for the same `group_id` — the roadmap's claim that the trace
makes this observable is accurate, verified against the actual `reconcile` code, not just
taken on the roadmap's word. The gap that is *not* bounded: a contact absorbed and evicted
again before its own individual disclosure ever fires, and never explicitly watched, has only
the group's own aggregate line as a channel — exactly what the defect breaks. This is why the
defect is correctly characterised as "suppresses a report" rather than "silent and
undetectable" — it is detectable, just not prevented.
