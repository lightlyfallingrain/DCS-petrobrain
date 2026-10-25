---
name: bl-b102-referent-memory-window-bounded
description: ReferentMemory (belief/referent.py) is pruned to REFERENT_WINDOW_S on every access, not count-bounded — accepted, same reasoning as the per-contact bounded-growth pattern but a different mechanism (time window, not contact count)
metadata:
  type: project
---

`belief/referent.py`'s `ReferentMemory` records a `Mention` per `_print` call with a non-empty
`mentions` list, and prunes to `REFERENT_WINDOW_S` (15-180s tunable, default 60s) on every
`record`/`recent`/`last` call — not count-bounded, window-bounded.

**Why accepted (BL-B102 deep analysis, 2026-10-26):** the only writer is `CrewConsole._print`,
itself rate-limited by `SPEECH_RATE_WPS`/`INTER_UTTERANCE_GAP_S` and the poll loop; the only
trigger is the pilot's own voice in a single-user LAN threat model. There is no externally-
reachable path that can make `_print` fire faster than Petrovich's own speech cadence, so the
list's peak size (mentions-per-window at that cadence) is small and not attacker-influenced.

See also [[body-layer-bounded-growth-accepted-pattern]] — same acceptance reasoning, different
mechanism (that one is sortie-lifetime/contact-count bounded; this one is a sliding time window).

**How to apply:** when a future feature adds another time-windowed ledger fed from `_print` or the
voice-command path, this reasoning transfers directly — don't re-flag as unbounded growth unless
the write rate could come from something other than the pilot's own cadence (e.g. a future
multiplayer/SRS integration, explicitly out of scope per root `CLAUDE.md`). If the mechanism is
ever reused for a less-bounded input rate (the plan's own "Second-order effect" flags a possible
BL-10/SRS conversational-memory reuse), re-check this acceptance then — it is conditioned on this
specific input path, not a blanket exemption for windowed state.
