# AC-8 — DCS-driven line of sight, Stages 1-3

**OPEN** — this entry's own *"not yet merged, not yet flown"* disagrees with [[WM-W2]], which
records the same work as *"FLOWN 2026-10-05"* and reads 101,091 live verdicts off
`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`. Both claims are carried
verbatim and neither was edited. The merge half is settled mechanically rather than by judgement:
`aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` is present on `main`, and `main`'s
history carries the branch's whole review/DoD trail (`3b904fc`, *"DoD: X-B29 DCS-driven LOS Stages
1-3 — PASSED"*). So this entry's text is the stale half. Flagged rather than fixed in place, per
`docs/DOC_CONVENTIONS.md`: the next reader should be able to see that the two records disagreed,
and `#needs-flight` is deliberately withheld while the marker stands, since tagging it would pick
a side.

- [ ] **DCS-driven line of sight, Stages 1-3 — DoD PASSED on fixtures 2026-10-05, not yet merged, not
  yet flown** #status/open (`feature/dcs-driven-los`, [[X-B29]]/[[X-B30]] in `todo/backlog.md`). New Hook script
  (`dcs-export/petrobrain-line-of-sight-hook.lua`) computes both terrain and building line of sight
  for every unit inside Petrovich's gaze cone in one batched `world.searchObjects`/`SEGMENT` call per
  poll, replacing body-layer's SRTM-approximated terrain-only answer for any unit the live feed
  covers. **First channel where the cone itself (not just the bubble) scopes the query set** — a
  unit outside the gaze wedge is not uncovered, its LOS is irrelevant (the plan's own governing
  principle). Needed a second inbound command channel the other way: `POST /command/look_direction`
  (own port 7797, range-validated `hour: 0..11`/`fov_half_deg: 5..180`) tells the Hook script where to
  scope its cone, since `land.*`/`world.*` are reachable only from the mission-scripting state that
  `Export.lua` does not run in — a genuinely different bridge from the F10/velocity Hook scripts'
  `dostring_in("scripting", ...)` pattern, not a copy of it. `GET /line_of_sight/latest` serves the
  result. Both Security plan-review required fixes (NaN/Inf-guarded numeric clamp on the two spliced
  `%d` values; the inbound listener coalesces a frame's queued datagrams to exactly one
  `dostring_in` call) landed in the first pass. Checks: 252 passed (baseline 210 + 42 new). **Not
  attempted here, needs a live DCS flight**: the `atan2` heading/bearing convention inside the Hook's
  `LOS_CODE` string, `tonumber("nan")`/`tonumber("inf")` behaviour on DCS's bundled Lua/CRT, whether a
  building actually occludes in the running game, per-frame look-direction socket-poll cost. See
  `world-model/ROADMAP.md`'s "Live acceptance debt" list and
  `docs/acceptance/2026-10-05-dcs-driven-los-sortie.md`. Full record: `plans/dcs-driven-los/`.
