# BL-B8 — F10 command vocabulary and ownship-relative sectors

- [x] **BL-B8 — F10 command vocabulary and ownship-relative sectors — command half done, merged
  2026-09-16, merge `1a9189c` (`feature/f10-command-vocabulary`,
  `plans/f10-command-vocabulary/plan.md`).** #status/done Addresses "F10
  command refinement and specification" below for the command half of `docs/concept/
  state-transitions.jpg`'s spec — the vocabulary/geometry/wiring half, not the autonomous-behaviour
  half (deliberately out of scope, see that plan's Scope section). Widens the F10 menu from three
  flat items to 15 tokens (D4): **Scan** → Ahead/Left/Right/Full (ownship-relative) + eight compass
  **Bearing** items (absolute), **Watch** → Nearest/Nearest Air Defence, **Cancel Task**;
  `scan_forward` was *replaced* by `scan_ahead`, not kept as a synonym. **Watch → Nearest Air
  Defence** (D6) filters on the *believed* classification -- `class`/`type` level resolving into
  the air-defence `OP_*` buckets (four of them at this merge — `OP_LRSAM` was missing and was
  folded in 2026-09-24, see the entry below) -- so a `presence`-level contact is never matched even when
  the object really is a SAM; it will honestly report nothing rather than name an unidentified
  blob as air defence. New ownship-relative `AttentionArea` kind
  (`belief/attention.py`'s `RelativeSector`/`wedge_deg`/`project_relative_area`) that re-projects
  onto ownship's current heading every telemetry tick (`ContactStore.reproject_relative_areas`,
  called from `logger.py`'s `run_once` before `ingest`/`tick`) — a standing "watch left" now tracks
  the nose through a turn instead of freezing to the heading held when the button was pressed (D1-D3).
  **D5 fixes the hollowness this backlog item's live test found**: every `scan_*` token now
  registers a real `belief.tasks.PendingIntent` via `belief.tools.scan_area` *before* firing the live
  effector, wrapped so a failed trigger still leaves the task registered — `cancel_task` (previously
  always "no pending task" in `--crew-text` sessions) is no longer dead. What this milestone did
  **not** do: the spec's `Observ`/`Track` verbs (still blocked — the 9K113 OBSERV OFF control is
  still not identified, [[BL-6]] recorded only 3001/3015; an Investigator pass is needed before that's
  plannable) and the spec's autonomous-behaviour half (weapon filtering, classification-upgrade
  reports, engagement-envelope danger/safe calls, auto-watch-on-engaged, group-as-single-threat,
  mission-lifecycle reset/debriefing — deferred to design against real sortie feedback, same
  reasoning that gates [[BL-8]] on real flights). No live-DCS acceptance in this milestone's own DoD —
  the whole point is to enable the next sortie; that sortie is the acceptance test and feeds the
  autonomous half. Next-milestone impact: none on the BL-x sequence.
