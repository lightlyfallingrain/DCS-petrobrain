# AC-B16 — False AI-wheel park signal for a few frames on pilot→operator seat swap

- [x] **AC-B16 — Hold `ai_pilot_parked_active` at its prior value for a 0.5 s settle window after a
  pilot→operator seat swap, instead of trusting arg 852 (operator stick stow) the same frame the
  camera reports the seat change — done as `fix/apw-seat-swap-settle`, DoD-PASSED 2026-11-18 (tip
  `d095d8fb`), merged to `main`.** #status/done #needs-flight Filed from live flight feedback,
  2026-11-18 (user, verbatim, `plans/apw-seat-swap-settle/debug.md`): *"The false park signal ->
  need a small delay then ... allow that inial small delay so that the control either unparks or
  remains parked, then read state ... "*.

  **The bug.** Flight 8 (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`)
  measured the camera reaching the operator seat at 17.301 s while arg 852 still read its
  pilot-seat-forced stowed value and animated down over ~0.3 s. For a few frames the seat gate saw
  "in operator seat" + "stick parked" simultaneously and raised `ai_pilot_parked_active`'s rising
  edge, with nobody's AI actually flying — a transient from DCS's own cockpit-model unstow
  animation lagging the camera-derived seat read, not a logic bug in the gate itself.

  **The fix** (`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`): a new
  `AI_PILOT_SEAT_CHANGE_SETTLE_S = 0.5` constant and a settle window armed only on a detected
  pilot→operator *transition* (never on a mission's first-ever seat read). While the window is
  open and the camera still reads "operator", `ai_pilot_parked_active` holds its prior value (which
  was always `false` while in the pilot seat) rather than reading arg 852; once the window closes,
  or the camera leaves the operator seat at all, the real reading is trusted immediately. This
  correctly resolves either of the two outcomes the user's own DCS "automatic handover" setting can
  produce: control stays unparked (normal case, settle-then-unpark) or control is genuinely parked
  by DCS's own automatic handover (settle-then-park, covered by the new
  `test_automatic_handover_parks_after_the_settle_window`). The **operator→pilot direction is
  deliberately left immediate, unchanged** — that side has no animation to absorb (852 is never
  read from the pilot seat; the seat gate already forces the park flag to unparked the instant the
  camera leaves the operator seat), and delaying it would hold a stale "parked" belief for up to
  0.5 s after the player physically has the pilot stick back, which is worse than the bug being
  fixed. Full reasoning, evidence and both-direction test list: `plans/apw-seat-swap-settle/debug.md`.

  **Review**: APPROVED, no required fixes — confirmed the asymmetry is correct (not merely
  expedient), every consumer of `ai_pilot_parked_active` reads the settled value, and mutation-
  tested the three new/updated tests by forcing the settle check to always-false and confirming
  3 of 4 failed as expected. **Security**: APPROVED, no required fixes — no new
  `performClickableAction` call site, the window always closes (every exit path verified: nil
  camera reading, 9K113 sight view, rapid seat toggling), holding a flag adds no write of its own.

  **Checks (full suite, tip `d095d8fb`, re-run at DoD):** `.claude/scripts/fast-tests.sh --full
  aircraft-layer` — 884 passed; `ruff format --check`/`ruff check` clean (81 files); `cd
  aircraft-layer && mypy src` — success, 27 files; `luac5.1 -p` clean on the touched Lua file.
  Trial merge against `main`'s tip at the time (`59192cfa`, the unrelated `fix/apw-
  status-json-quotes` merge, same `text_or_null` region but a disjoint line range in the same
  file) — `git merge-tree --write-tree` returned a clean tree, no conflict.

  **`#needs-flight`** — the Lua harness reproduces the exact flight-8 frame sequence and shows no
  edge fires with the settle window in place, but the live claim this unblocks (no false 3-frame
  park edge in a real sortie's log, settling within 0.5 s, both DCS automatic-handover settings)
  needs a real seat swap in the cockpit. Card: TBD (published in the same DoD pass, see
  `plans/apw-seat-swap-settle/dod.md`). **Branch to fly: `main`, after this merge.**

  **Milestone-completion note.** No new information for `[[BL-16]]`'s next stage (P3,
  align/launch) — this closes a transient-reading defect in mode 2's existing seat gate, and does
  not change what P3 needs or assumes.
