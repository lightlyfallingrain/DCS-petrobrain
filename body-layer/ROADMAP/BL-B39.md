# BL-B39 — A log that disabled itself reads as one that stopped

- [ ] **BL-B39 — A log that disabled itself mid-sortie reads as a log that simply stopped.** #status/open Found by
  the [[BL-11]] security pass, 2026-10-06 (`plans/bl11-tick-cost/security-review.md` finding 4), and
  filed rather than fixed because it is a *reading*-side gap, not a defect in the mechanism.

  Stage 5's degrade is correct and was traced: a write failure reports once on stderr, stops trying,
  and the collector is still drained (`logger.py:1231`'s `else: records.clear()` covers the
  degraded-to-`None` case, and all six writer call sites are `is not None`-guarded). **But the file
  it leaves behind has no in-band marker.** The disk fills at `t_sim 1200`, the trace just ends, and
  a later triage reads "nothing admitted after 1200" and diagnoses a perception defect that does not
  exist.

  **That matters more here than it would elsewhere**, because post-flight log archaeology *is* this
  project's primary diagnostic method — the 2026-10-05 sortie analysis is four research notes built
  entirely on these files, and `.claude/skills/sortie-log-triage` exists to automate it. `RUN.md`
  documents the stderr line for a human; the skill has been taught the stamping/glob half but not
  this one.

  **Cheap fix**: inside the existing `contextlib.suppress`, attempt one
  `{"event": "<writer>_disabled", "t_sim": ...}` row. It fails silently on a genuinely full disk —
  which is fine, that case has the stderr line — and succeeds on the path-gone-bad case, which is
  the one that produces a plausible-looking truncation. Teach the triage skill to look for it, and to
  treat a trace with neither the marker nor a clean ending as suspect.
