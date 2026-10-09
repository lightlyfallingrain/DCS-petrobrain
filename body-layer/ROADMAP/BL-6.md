# BL-6 — Commands and inspect-and-adapt

- [x] **BL-6 — Commands and inspect-and-adapt (done, merged 2026-09-11, `feature/bl6-commands-
  inspect-adapt`, merge commit — see `git log --oneline -1 main` after this push).** #status/done `PendingIntent`
  lifecycle (`body-layer/src/belief/tasks.py`), `scan_area`/`get_task_status`/`cancel_task`; this
  was the tool-set freeze point (moved from BL-7, see that entry above). A day of live-DCS probing
  plus a real-manual cross-check (RU Mi-24P QuickStart, `docs/concept/mi-24_info/`) resolved the
  plan's original two blocking premises — see `aircraft-layer/research/2026-09-11-SUMMARY-
  petrovich-control.md` and the revised `plans/bl6-commands-inspect-adapt/plan.md`: Petrovich has
  real search verbs (`SRCH FWD`/`BRST` triggerable; every *directed*-aim route — `SRCH 9K113 LOS`,
  `DesignateAttackPoint`, puppeting the pilot's view — closed, the last confirmed by the manual to
  have no real-hardware analog at all) and a real, directly-readable outcome signal
  (`list_indication(6)`/`(10)`), so `scan_area` triggers a real search and verifies a real outcome
  rather than inferring success from belief-state timeout. `cancel_task` removes its
  `AttentionArea` (user decision). Aircraft-layer effector: `POST /command/petrovich_search` +
  `GET /petrovich_wheel/latest`, wired into body-layer's `Console` via an optional
  `aircraft_client` field — no separate Security plan review was run (this project's current
  phase exempts Security/Performance Reviewer per root `CLAUDE.md`'s "Agents" section; the
  original "needs its own Security plan review" language above predates that exemption and is
  superseded). 437 body-layer + 90 aircraft-layer tests green; live-DCS acceptance of the new
  effector (does `POST /command/petrovich_search` actually fire `SRCH FWD` in a running mission)
  is deliberately deferred to the user's own follow-up, not this milestone's DoD gate — add to the
  "Live acceptance debt" list above if it isn't exercised soon. **Downstream consequence for BL-7/
  BL-8:** every future "have Petrovich actually do X" idea inherits the same closed-directed-aim
  ceiling this investigation found — no design assumes we can point his attention at a bearing we
  choose, only trigger-and-verify. **Next queued item (user priority, `todo/todo.md`):** route
  `belief.speech`'s spoken contact callouts to the in-game overlay (currently only reaches
  `--crew-text`'s stdout, not `--overlay`'s cockpit text panel) — not part of BL-6's own scope, a
  separate follow-on.

