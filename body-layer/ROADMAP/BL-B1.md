# BL-B1 — Threat-database follow-on extraction

- [ ] **BL-B1 — Threat-database follow-on extraction: search/track radar + acquire time — raised
  `plans/watch-reporting/plan.md` Decision 4f-iii, 2026-09-24.** #status/open The Hoggit source page (saved
  beside `body-layer/data/threat_envelopes.json` for exactly this) carries `Track RADAR`/`Search
  RADAR` columns with HARM codes and an acquire-time column; none of it is in the extracted
  payload. Both are worth a *later* pass, not the one that just landed:
  - **Search/track radar is detection range, a different and longer claim than weapon range** —
    being tracked at 12 NM by a gun that reaches 2 NM is information, not a threat. Natural home of
    a future "he's looking at us" warning (a slewed dish is *observable*, not an omniscience
    problem) — needs a behaviour-change channel that does not exist yet, so the data would sit
    unused if extracted now.
  - **Acquire time** would decide whether a fast crossing pass actually gets engaged — needs a
    time-in-envelope model nothing in this codebase has.
  Re-extract from the already-saved HTML; no re-fetch needed.
