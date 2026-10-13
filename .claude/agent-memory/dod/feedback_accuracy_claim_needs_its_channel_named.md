---
name: accuracy-claim-needs-its-channel-named
description: A position-accuracy number belongs to one perception channel; stating it as a blanket per-weapon verdict (good for guns, bad for ATGM) is wrong when the other weapon's guidance uses a different channel entirely that the number says nothing about.
metadata:
  type: feedback
---

On `bounded-fold-displacement` (`BL-B58`/`BL-B59`), I initially drafted the acceptance split as
*"40 m clears the bar for guns and rockets and does not clear it for 9K113 ATGM guidance"* — an
accuracy split, implying the naked-eye-derived position was simply not good enough for the
missile case and some future improvement to it might fix that.

**User correction**: ATGM guidance is served by the 9K113 sight only, and there is no naked-eye
channel for ATGM guidance at all. So 40 m is not a shortfall against the ATGM requirement — it is
the wrong instrument for that question entirely. No amount of improving the naked-eye position
would be relevant, because guidance reads a different channel this project has not even built
(`perception/optics.py` declares only `UNAIDED_OPTIC`/`BINOCULAR_OPTIC` — the 9K113 is deferred
entirely, stated in several places in the code).

**Why: not just a wording nit.** Framing it as an accuracy shortfall implies the fix is "make the
number smaller" — which is false and would send a future planner looking for position-precision
work that cannot possibly close this gap. Framing it as a channel split correctly implies the fix
is "build the missing channel," a different and much larger piece of work with its own
prerequisite (the 9K113 optic does not exist).

**How to apply.** Before writing a per-weapon or per-use-case accuracy verdict, check whether each
use case actually reads the same measured channel/mechanism, or a different one entirely. If a
weapon or consumer's accuracy need is served by a perception path that was never measured (or
does not exist), say that plainly as a channel/prerequisite gap, not as "this number isn't good
enough yet" — the two read very differently to whoever plans the next milestone from your report.
