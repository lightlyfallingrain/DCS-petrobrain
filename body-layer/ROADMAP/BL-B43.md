# BL-B43 — Drop `PLAYER_BUBBLE` rows from the detection trace

- [ ] **BL-B43 — Drop `PLAYER_BUBBLE` rows from the detection trace's JSONL writer (not the
  collector).** #status/open User direction 2026-10-08, answering `Q7`: *"drop them, if it does not disable the
  ASCII graph view."*

  60–80 % of a trace is `PLAYER_BUBBLE` rows — one per candidate further than the 10 km bubble, each
  carrying one bit ("further than 10 km") that any other row's `true_range_m` already implies. At
  ~25 MB/min post-[[BL-11]]-Stage-5 that is most of the file.

  **The condition is satisfiable, and where the drop happens decides it.** Checked rather than
  assumed, because the obvious reading is wrong:

  - Markers beyond the view radius are **clamped to the rim, not dropped** — `eyesight_view.py:448`
    (`clipped_rng = min(rng, radius_m)`), and the module docstring states it: *"a contact beyond
    `radius_m` is never silently dropped."* So out-of-bubble objects **do** render in the ASCII view.
  - But the live `--eyesight-view` takes its ground truth from the **in-memory
    `DetectionTraceCollector` snapshot**, not the JSONL file (`logger.py`'s `_eyesight_frame`
    docstring).

  **So: writer-level drop, flag-gated. Never collector-level.** A writer drop costs the graph
  nothing; a collector drop would strip exactly the rim markers the user asked to keep. Two changes
  that look alike and are not — if this is ever "simplified" into one, the ASCII view loses contacts
  silently.
