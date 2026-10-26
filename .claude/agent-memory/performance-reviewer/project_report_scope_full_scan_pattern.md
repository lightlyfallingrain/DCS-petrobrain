---
name: report-scope-full-scan-pattern
description: body-layer's _report_scope (and now resolve_referent via restrict_to_ids) always scans every current contact, even when answering a bounded-id query -- pre-existing pattern, not a new risk, until contact counts or call frequency change.
metadata:
  type: project
---

`body-layer/src/belief/crew_console.py:_report_scope` iterates `get_contacts(self.store, now_sim,
...)` over **every current contact** to build its answer, even in its `restrict_to_ids` mode
(added by `[[BL-B102]]`, `plans/that-it-referent/plan.md`) where the caller only wants a handful
of specific ids resolved. This is `O(all contacts)` where `O(len(restrict_to_ids))` would be
structurally cheaper.

**Why:** BL-B102 deliberately reused `_report_scope`'s existing descriptor/clock/sector/relative/
band filter machinery for `resolve_referent`'s qualifier step, rather than writing a second
id-indexed filter — the plan's own stated tradeoff (code reuse over a cheaper but duplicated
path). The same full-scan shape already existed for plain `report`/`_resolve_attack_target`
before this feature; BL-B102 did not introduce the pattern, only one more caller of it.

**How to apply:** Not a credible risk at this project's current scale (single-user, LAN,
operating altitude envelope bounds contact counts to a handful–low tens per sortie) and the call
site is once-per-voice-command, never per-poll. Re-flag as NOW, not MONITOR, only if either
changes: (1) a future caller puts `_report_scope`/`resolve_referent` on a per-poll or per-frame
path, or (2) contact counts grow materially (a much larger simulated battlefield). Until then,
each new caller reusing this shape is not a fresh finding — check whether either condition above
has actually changed before re-raising it.
