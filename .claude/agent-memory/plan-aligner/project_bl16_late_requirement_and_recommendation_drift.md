---
name: project-bl16-late-requirement-and-recommendation-drift
description: BL-16 plan check caught a late-arriving verbatim user requirement the plan text never absorbed (grep found nothing), and an Architect recommendation that would re-open an already-settled decision.
metadata:
  type: project
---

BL-16 (flight-control) plan check, 2026-10-31. Two generalizable shapes, not specific to this
feature:

**1. A binding user requirement arrived mid-check, after Architect wrote the plan, committed to the
branch as explore-notes only.** The coordinator flagged it explicitly ("every flight-axis write
needs the invisible wobble... trace it as an expectation") rather than leaving it for the aligner to
notice on its own. `grep -i wobble plan.md` confirmed: zero hits. The plan's own Decision 6 said the
opposite shape — wobble as a fallback tried only if a plain write fails — which the user's new
"regardless of how writing is done" wording directly supersedes. **Lesson: when a coordinator names
a specific later commit and a specific absence to verify, verify it mechanically (grep) before
writing the finding, and check whether an existing Decision contradicts the new requirement, not
just whether the requirement is present.** A missing requirement is a weaker finding than a missing
requirement plus a Decision asserting its opposite.

**2. An Architect's own "Decisions Requiring User Input" recommendation (D-e: auto-take controls on
park, no spoken trigger) would, if accepted as written, contradict a decision the user had already
settled three sessions earlier ("Handover is spoken only," 2026-10-25) and which was carried into
the roadmap entry and the goal check's E1/E6.** The recommendation was correctly flagged as not yet
decided, so nothing in the plan *acted* on it — but the recommendation itself reads as if it forgot
the earlier settled point. **Lesson: when a plan has an open "Decisions Requiring User Input" list
with Architect recommendations attached, check each recommendation against the feature's own earlier
settled/Decision list, not just against the goal check's expectations — the Architect can
contradict itself across sessions the same way a stage can contradict the why.** This is a case
general enough for `docs/BEHAVIOUR_ALIGNMENT.md`'s calibration table if it recurs.

See [[project_bl_b104_clean_trace]] for the contrasting case (explore-notes pre-answering every
open assumption) — this feature's explore-notes did the same for the original E1–E10/F1–F8, which
is why the trace was otherwise clean; the two gaps found here both arrived *after* that point, not
from a weak explore pass.
