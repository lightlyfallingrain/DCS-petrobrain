---
name: pb2-stage0-scope-channel-repair
description: PB-2 Stage 0 fixed a 0-score association bug and a single-Observation-per-poll bug in the HelperAI scope channel; real before/after numbers and a subtle debounce-preservation gotcha.
metadata:
  type: project
---

Stage 0 of `plans/pb2-contact-memory/plan.md` fixed two independent scope-channel bugs, both
fixture-validated (no live sortie required, per the plan's scope-emphasis note):

(a) `association._type_match_score` scored HelperAI's *reporting* name (e.g. `"Slava cruiser"`)
against `LoGetWorldObjects`'s raw *type* (`MOSCOW`) and got 0 for anything but a Ural-truck
coincidence. Fixed by resolving `object_type` through `reporting_names.reporting_name_for` and
scoring against both raw type and resolved name, max of the two. Real before/after: Slava
cruiser/MOSCOW 0->2, Tarantul III corvette/MOLNIYA 0->3, SA-3 launcher/5p73 s-125 ln 0->3, SA-3
Low Blow radar/snr s-125 tr 0->5 (see `plans/pb2-contact-memory/implementation.md`).

(b) `hybrid_source.py` only ever read `middle_list_text`, but the five `*_list_text` leaves are a
window into a multi-row list holding several *simultaneous distinct contacts* (confirmed from a
real spike log, not inferred — `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-
ambient-detection.md` Finding 6). Fixed by reading all five leaves, de-duping by text, associating
each distinct text in order against a candidate pool with already-claimed candidates removed.

**Debounce-preservation gotcha**: the old single-leaf code only advanced its debounce state
(`_last_emitted_classification`) on a *successful* association — a detection that failed to
associate was retried every poll, not silently debounced away. Naively updating the new
multi-leaf debounce state (`_last_emitted_texts`) unconditionally at the end of `poll()` would
have silently broken this (stopped retrying a briefly-unassociable detection until its text
changed), and **no existing test would have caught it** — had to reason about it from first
principles and add an explicit `if observations:` guard. Worth checking for this shape of bug
(a debounce/cache write that fires on *every* exit path vs. only the success path) whenever
generalizing a single-item guard to a multi-item one.

See [[feedback_verify_mission_probe_pattern_claims]] and [[project_pb1_5_naked_eye]] for related
scope-channel/naked-eye channel history.
