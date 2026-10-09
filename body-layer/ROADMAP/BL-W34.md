# BL-W34 — Voice command completeness — Stages 1 through 5

- [x] **Voice command completeness — Stages 1 through 5. DONE** #status/done
  (`feature/voice-command-completeness`; plan: `plans/voice-command-completeness/plan.md`). 20 of
  41 recognised voice tokens (`report_all`, the nine `report_clock_*`, the eight
  `report_bearing_<compass>`, `report_bearing_deg`, `scan_bearing_deg`) reached `CrewConsole.
  handle_command` (renamed from `handle_f10_command`, Stage 1 — the F10 radio menu is the transport
  being retired, not the concept the rest of this codebase still needs) and fell through its
  defensive `else` doing nothing — recognition succeeded, the dispatcher said "act", and the act was
  a silent no-op, indistinguishable from not having been heard at all.

  **Stage 2 — the report families.** `report` is a read of current belief and nothing else, never a
  look (*"report is always about current belief. Scan tells to go look"* — user, 2026-09-23): no
  `AttentionArea`, no task, no gaze change. Drops `certainty == "lost"` contacts (never pruned, so a
  report would otherwise grow across a sortie) and anything with no `relative_now`, filters by the
  requested family, groups via a new `belief.callouts.group_facts` (the bucket+chain rule extracted
  out of `group_candidates` so the report and callout paths share one aggregation rule), and speaks
  **one utterance**, capped at `REPORT_MAX_GROUPS` (3, uncalibrated) with a trailing `"And more."`
  when truncated — never one line per group, the same discipline `plans/callout-scheduling/`
  established. An empty result says `"Clear."`/`"<direction>, clear."` — **except** a compass/
  numeric-bearing direction past the cockpit mask's rear cutoff relative to current heading, which
  says `"Can't see <direction>."` instead: `"clear"` there would claim a look that is physically
  impossible, the no-omniscience invariant's mirror image. A contact actually believed to sit there
  is still reported normally; only the absence claim is withheld.

  **Stage 3 — the numeric bearing slot.** `scan_bearing_deg`/`report_bearing_deg` quantise onto the
  nearest of the eight compass sectors (`_nearest_sector`, 45° buckets — *"o'clock direction is
  enough, no need for x degrees granularity now"*, user 2026-09-23) and then behave exactly like
  their compass-word sibling tokens, readback and confirm prompt included (naming the sector, never
  the raw number). Required an `audio-adapter` wire fix: `MatchResult.bearing_degrees` was computed
  by `command_matcher.match_transcript` and then dropped at the wire — `TranscriptEvent` carried
  seven fields, not eight. Now eight; `PendingConfirmation.bearing_degrees` carries the parsed value
  across a confirm round trip so an "affirm" commit does not lose the heading.

  **Stage 4 — prose** (`body-layer/CLAUDE.md`, `docs/concept/STATE_TRANSITIONS.md`, this entry).

  **`DISPATCHED_COMMAND_TOKENS`** (module-level, `crew_console.py`) is now the canonical
  "what has real behaviour" set, asserted against by test; an unrecognised token logs a warning
  instead of vanishing silently. `CrewConsole._print`'s non-urgent path now also calls
  `CalloutScheduler.note_reply`, closing a separate latent defect the reports made audible: every
  command readback has been unbudgeted since readbacks existed, so a routine callout could queue
  immediately behind one rather than waiting for it to finish.

  **Stage 5 -- ownship-relative o'clock scans, and compass scans that finally steer the naked eye**
  (both land together, per Decision 5, since they are two partial fixes to the same seam).
  `scan_clock_1..12` (nine forward hours, mirroring the report family's own clock tokens) give the
  ownship-relative frame the fine granularity it lacked: `left` alone spans three o'clock hours (a
  90-degree wedge), and there was no way to say "just there" relative to the nose (user, 2026-09-23:
  *"'scan 1 o'clock' directs scan at a narrow sector that is own ship relative. That is needed."*).
  `perception.gaze.ScanPlan` gained a `commanded_legs: tuple[int, ...] | None` field carrying legs
  directly -- the architect's own generalisation, rather than widening `RelativeSector` with twelve
  more literals -- so a single o'clock hour is a one-leg plan exactly as `ahead` already is.
  `logger._active_gaze` now also resolves a compass-only `AttentionArea.sector` task (previously
  silently skipped, the measured pre-existing defect: `scan north` registered an area and spoke a
  readback while Petrovich kept free-scanning), converting it to relative legs every poll via the
  new `perception.gaze.legs_within_wedge`, using that poll's own ownship heading -- so `scan north`
  finally moves his eyes, and stays correct as the aircraft turns. `belief.attention.AttentionArea`
  gained a third, sibling directional field, `relative_clock_hour: int | None`, pairwise mutually
  exclusive with `sector`/`relative_sector`; `project_relative_area` projects it the same way. The
  binocular search sweep (`logger._search_sweep`) stays gated on `commanded_sector` alone --
  deliberately not extended to the new commanded-legs cases, out of this stage's scope. Nine new,
  **unbenched** tokens (no recordings in this corpus), the same cost class as `cancel_scan`/
  `cancel_watch` before 2026-09-23 -- next corpus recording's job. **Unflown as of merge.**


**Closed by [[BL-W7]]'s sortie, 2026-09-25** — this entry's own "Unflown as of merge" sentence above predates that closure and is left unedited (see [[BL-W7]] for why), but live acceptance is no longer outstanding.
