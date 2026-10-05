---
name: watched-set-expansion-is-a-gated-surface
description: Expanding the watched contact set does not expand the ungated speech surface — the three watched-side paths and their gate status, checked 2026-10-06.
metadata:
  type: project
---

When a feature widens *which* contacts are watched (sortie-2026-10-05 Item 3 tagged every
`belief.groups.Group` member), the question to answer is which spoken paths watched-ness unlocks.
All three were traced on 2026-10-06 and the answer is reusable:

- `CONTACT_ATTENTION_CHANGED` — **no speech template at all**. `route_event` returns `None` and
  does not acknowledge it (`belief/speech.py` module docstring, "Which lifecycle kinds get a
  template"). Tagging N members emits N events and zero lines. This is the one most likely to be
  assumed a callout; it is not.
- `CONTACT_MOTION_CHANGED` and `CONTACT_RANGE_CROSSED` — the two watched-only *spontaneous*
  paths, both already behind `observable_or_grace` (`belief/contacts.py`, Fix A of
  `plans/sortie-2026-09-26-fixes`). So widening the watched set widens a **gated** surface.
- `optic_policy.choose_look` ordering via `logger._look_targets` — orders which look happens
  first, never whether an unwatched contact is identified. Behavioural (priority inversion on a
  big group), not a disclosure path.

**Why:** the recurring live defect on this project is a spoken clock hour the cockpit mask
declares unviewable, and the reflex is to suspect any feature that touches watching. That reflex
pointed at the wrong code here. The ungated path is the **pulled** report
(`crew_console._handle_report`, `certainty != "lost"` and nothing else), governed by a documented
decision — *"belief survives the aircraft turning away; only the absence claim is withheld"* —
not by an oversight.

**How to apply:** on any future watch/attention-scope change, check these three and the pulled
report, and do not report the pulled report as a new finding — it is a decision to re-open with
the user, documented in `crew_console.py`'s `_handle_report` docstring. Related:
[[silence-command-security-approved]], [[redundant-group-disclosure-approved]].
