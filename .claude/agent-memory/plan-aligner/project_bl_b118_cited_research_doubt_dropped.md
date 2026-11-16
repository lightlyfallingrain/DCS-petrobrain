---
name: project_bl_b118_cited_research_doubt_dropped
description: BL-B118 QNH-vs-QFE plan check -- a plan can summarize its own cited research selectively, carrying forward every finding except the one that doubts the goal parameter itself.
metadata:
  type: project
---

BL-B118 (`plans/bl16-qnh-mission-start/plan.md`, checked 2026-11-16): the plan's "Why, and what is
already known" and "Risks & Unknowns" sections summarize
`aircraft-layer/research/2026-11-16-mi24p-operator-altimeter-recon.md` thoroughly -- the knob's
gain, the no-response risk, the dynamic-weather caveat -- but silently drop that same note's
section E, which found the operator altimeter's in-cockpit checklist/hint text calls it a "QFE"
knob and states outright "the pilot chose QNH before this was found." If the AI reads the gauge as
height-above-field rather than height-above-sea-level, QFE (not QNH) is the value that actually
fixes the bug this feature exists for.

**Why this is worth a general lesson:** a plan that accurately summarizes most of its cited
research can still be picking and choosing -- the parts that got dropped are exactly the parts
most likely to matter, because they're the parts that complicate the already-chosen path. Grepping
the plan for a topic ("QFE") and finding nothing is not the same as the topic being absent from
the investigation it's built on; check the cited research document itself, not just the plan's own
account of it.

**How it was caught:** read the full research note (not just the plan's summary of it) end to end,
independently of the plan's own "what is already known" section, and compared headings/sections
against what the plan chose to carry forward.

**How to apply:** when a plan cites a research/recon note as its evidentiary basis, read that note
in full rather than trusting the plan's digest of it -- especially any section of the note that
reads as "raised for the pilot" or similarly flagged-but-unresolved, since that is precisely the
kind of content a plan under schedule pressure drops first. See also
[[project_bl16_vocabulary_grep_stopped_one_layer_short]] for the sibling lesson about grep stopping
one layer short of where the real answer lives.
