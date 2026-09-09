### Review Summary

Reviewed BL-2.5 (in-cockpit text mirror / DCS overlay output channel), commits
`7a336f0..d0a0988` on `feature/dcs-text-panel-output`, against
`plans/dcs-text-panel-output/plan.md`, `implementation.md`, root `CLAUDE.md`/`AGENTS.md`, and
`aircraft-layer/CLAUDE.md`/`body-layer/CLAUDE.md`.

Stage 1 (aircraft-layer transport) and Stage 3 (body-layer wiring) are complete, correctly scoped,
and well tested. Stage 2's artifacts (Hook script + `.dlg`) were reviewed as carefully as static
analysis allows, cross-checked line-by-line against the real, currently-installed DCS-SRS overlay
(`DCS-SRS-OverlayGameGUI.lua`/`DCS-SRS-Overlay.dlg`) and DCS's own shipped `gameMessages.dlg` /
`auto_scroll_text.skin.lua` / `Scripts/JSON.lua` under `$DCS_INSTALL_PATH` (read-only). Every
claim made about those reference files in the plan, implementation.md, and the Lua file's own
header checked out exactly as stated.

**Verified independently, not just taken on the implementer's word:**
- `ruff format --check`, `ruff check`, `mypy --strict`, `pytest` all pass for both
  `aircraft-layer/` (67 tests) and `body-layer/` (210 tests) — matches implementation.md's reported
  counts exactly.
- Working tree is clean; all new files are committed (nothing to additionally stage).
- The plan's specifically-flagged load-bearing test
  (`test_console_runner_overlay_push_failure_is_isolated_per_push`,
  `body-layer/tests/test_logger.py`) genuinely exercises what it claims: two class-incompatible
  observations forced into two separate contacts/events in one `tick()` batch, first push made to
  fail via a real `AircraftLayerError`-raising double, asserting the returned `Observation` list,
  `store.contacts`/`store.events` count, and `last_t_sim` are all unaffected, the *second* event's
  push still lands in the same batch, and a subsequent poll's push still succeeds. Not vacuous.
- `TextOverlaySender.send_line` never raises: only catches `OSError` around `sendto`, which is the
  correct and complete exception surface for a UDP send — `json.dumps`/`.encode("utf-8")` on a
  `str` cannot raise for this input shape, and truncation (`text[:MAX_LINE_LENGTH]`) is a plain
  string slice (character-based, not byte-based), so no encoding edge case at the truncation
  boundary either.
- `--overlay` defaults off (`store_true`, default `False`) and is a true no-op when absent:
  `overlay_client` stays `None`, `run_once()`'s overlay branch is skipped entirely, verified both
  by reading `logger.py` and by `test_console_runner_without_overlay_client_pushes_nothing`.
- `POST /text/push` validation (`server.py`): non-dict body, non-string `text`, empty/whitespace-only
  `text` (via `.strip()`), non-JSON body, and `text_sender=None` → 503 are all handled and tested
  (`test_text_push_api.py`, six cases, each asserting the sender was *not* called on the reject
  paths).
- The JSON-decoding deviation (loading DCS's shipped `Scripts/JSON.lua` instead of hand-rolling a
  decoder) is honestly documented in three places (plan deviation was implementer's own finding,
  `implementation.md`, and the Lua file's own header) and is correct: `Scripts/JSON.lua` exists,
  is exactly the file SRS's own overlay loads the same way
  (`loadfile("Scripts\\JSON.lua")()`, confirmed byte-for-byte identical line in
  `DCS-SRS-OverlayGameGUI.lua`), and returns an object exposing `:decode`/`:encode` (confirmed via
  `return OBJDEF:new()` at end of file) — the `JSON:decode(received)` call shape matches.
- `AutoScrollText` widget API usage (`addText(text, duration)`, `calcSize()`,
  `getTextLinesCount()`, `clear()`) all confirmed as real, currently-used calls in DCS's own
  shipped `Scripts/UI/gameMessages.lua`/`FoldableView.lua`/others — not invented API surface.
- The `.dlg`'s `skin.skins.text.skinData` override shape (color/font/fontSize/shadowColor/
  shadowOffset only, no `textWrapping` re-declaration) matches `gameMessages.dlg`'s own real
  per-instance override pattern exactly, and correctly relies on
  `auto_scroll_text.skin.lua`'s own `skins.text.skinData.params.textWrapping = true` default
  (confirmed by reading that file) rather than re-stating it — exactly as the plan/research doc
  claimed.
- Doc accuracy: `aircraft-layer/CLAUDE.md`'s rewritten opening line accurately describes the new
  write path; no other doc in the repo still asserts the pipeline is unconditionally read-only
  (`aircraft-layer/WORKFLOW.md`'s "everything else on this API is read-only" is a correctly scoped
  residual claim, not a stale one; `docs/concept/PETROBRAIN_RUNTIME.md`'s "read-only-DCS-access
  invariant" reference is about a different, unrelated concern — reverse-engineering DCS's compiled
  detection engine — and is untouched by this milestone). `plans/aircraft-layer/plan.md`'s original
  "read-only" line is a dated historical plan record, correctly left unedited.
- `todo/todo.md` and `plans/body-layer/plan.md` updates match the plan's required housekeeping
  exactly (Backlog entry promoted, BL-2.5 row inserted between BL-2/BL-3, BL-3's forward note about
  `format_event_for_overlay` recorded).
- Port bookkeeping is consistent end-to-end: Export.lua/collector 7790, LAN API 7791, overlay UDP
  7792 — no collisions, matches WORKFLOW.md's claims.

### Required Fixes

None.

### Optional Refinements

- **Unguarded `loadfile("Scripts\\JSON.lua")()` at Hook-script chunk-load time** (optional/
  observation, not a defect) — `petrobrain-overlay-hook.lua` line ~92. If `Scripts/JSON.lua` were
  ever missing (e.g. a corrupted/non-standard install), `loadfile` returns `nil` and `nil()` raises
  a plain Lua error with no `pcall` around it at that point in the file. This is a faithful,
  line-for-line copy of SRS's own currently-installed, proven file (which has the exact same
  unguarded call), so it isn't a new risk introduced here, and `Scripts/JSON.lua` is a core,
  general-purpose file other DCS-adjacent mods (SRS) already depend on existing — its absence would
  already break more than this feature. Worth a one-line mental note for Stage 2's live check (if
  the Hook script silently fails to load, check `dcs.log` for this specific failure mode first)
  but not worth guarding defensively given it mirrors the reference implementation exactly.
- **`int(self.headers.get("Content-Length", "0") or "0")` in `server.py`'s `_handle_text_push`**
  has no guard against a malformed (non-integer) `Content-Length` header — would raise
  `ValueError` uncaught by the handler, likely surfacing as a generic 500 from
  `BaseHTTPRequestHandler` rather than the endpoint's own `400`. Extremely low-risk (this is a
  loopback-adjacent LAN endpoint with no untrusted-input surface per the project's current
  security-review exemption, and every other endpoint on this server already trusts
  `Content-Length` the same way where bodies exist), not worth blocking on, but a one-line
  `try/except ValueError` would make the failure mode consistent with the rest of the endpoint's
  400-on-bad-input posture if anyone revisits this file later.
- **Screen position (20, 20) is an untested guess**, honestly flagged as such in both
  `implementation.md` and the Lua file's own header — not a defect, just a reminder this is exactly
  what Stage 2's live visual check exists to settle, and the window is draggable so cheap to
  correct in place.

### Verdict

APPROVED

### Review Confidence

Full read — plan, implementation.md, both CLAUDE.md files, the full diff (all 5 commits), all
new/changed Python source and tests, and the two Stage 2 Lua/`.dlg` artifacts. Cross-checked
against real, currently-installed DCS reference files (DCS-SRS's overlay script/`.dlg`, DCS's own
`gameMessages.dlg`/`gameMessages.lua`/`auto_scroll_text.skin.lua`/`Scripts/JSON.lua`) under
`$DCS_INSTALL_PATH`/`$DCS_SAVED_GAMES_PATH`, read-only. Independently re-ran
`ruff format --check`, `ruff check`, `mypy --strict`, and `pytest` for both subprojects rather than
trusting `implementation.md`'s reported results. Stage 2's live-DCS render/behavior is, as the plan
states, genuinely unverifiable without a running DCS session — that portion is unverified by
design (the plan's own Stage 2 boundary), not under-reviewed by this pass.
