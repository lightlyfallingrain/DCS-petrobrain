# MI-B1 — `TriggerZone.hidden` is parsed and never consulted by the author-only filter

- [ ] **MI-B1 — `miz/tree.py` parses `TriggerZone.hidden`, and `filter/crew_available.py` never reads
  it: trigger zones pass through the author-only-knowledge filter unfiltered regardless of the flag.
  Whether that is a leak depends on what DCS means by the field, which no research note resolves.**
  #status/open Filed 2026-10-16 from the whole-subproject security survey
  (`mission-interpreter/research/2026-10-16-security-audit.md`, Finding 1).

  **Why this is filed as an open question rather than as a bug.** `Group.hidden` is author-only
  knowledge and is filtered. The zone field has the identical name, and
  `filter/crew_available.py`'s own docstring reasons explicitly about zone-level author-only
  knowledge **without ever addressing this field** — so either it was considered and dismissed
  without a note, or it was missed. The survey declined to guess, correctly: if DCS's zone `hidden`
  is purely an editor display toggle, filtering on it would **remove legitimate crew knowledge**,
  which is the opposite failure and just as bad.

  **So the first step is an `investigator` pass, not a code change** — what the zone-level flag
  means in DCS (pydcs source, Hoggit, the mission editor's own behaviour) — and only then the
  decision about `crew_available.py`. This is the standing convention for DCS-internals-uncertain
  work, and this subproject's parsers were built on exactly that kind of recon.

  Sites: `mission-interpreter/src/filter/crew_available.py:42-61`,
  `mission-interpreter/src/miz/tree.py:120-141`.

  **What makes it worth doing at all**, given the filter otherwise held up: `MI-1.5`'s boundary is
  the one thing in this subproject that protects the project's central invariant — Petrovich must
  never know what the crew could not know. The survey confirmed the coordinate-leak boundary is
  *structurally* enforced (`EnrichedThreatSignal` has no x/z field at all, so a future bug cannot
  leak one). This is the one place where the same boundary rests on a field nobody has checked.
