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

---

## Refinement pass review (2026-09-09) — commits `f8cca80`, `499811b`, `cc4599e`

Scope: exactly the refinement pass described in `session-state.md`'s "The refinement pass in
flight" — restyle to a no-chrome/transparent DCS-message-feed look, contact id on overlay lines,
and dynamic (`calcSize()`-driven) window sizing to stop clipping the last line. Everything at or
before `43872b5` was already reviewed and approved above and is not re-reviewed here, except where
this pass changed its behavior. (`ee46c10`/`eedb1d7`, also on `HEAD`, are unrelated BL-2.6
scheduling notes in `todo/todo.md` — confirmed by inspection, out of scope for this review.)

### Review Summary

Read `session-state.md`, `plan.md` (including "Output-target decision, revisited after live
acceptance"), `implementation.md`'s follow-up section, and the prior approved `review.md` above.
Reviewed the full diff `f8cca80^..cc4599e` (Python + Lua + `.dlg` + docs). Applied the reviewer's
own DCS-Lua static-review technique (agent memory
`project_dcs_lua_static_review_technique`): read the real, currently-installed
`$DCS_INSTALL_PATH/Scripts/UI/gameMessages.dlg` and `dxgui/bind/Widget.lua` in full and diffed
every restyle claim against them line-by-line, rather than trusting the implementer's own citations
at face value.

**Independently verified against the real installed files (not taken on the implementer's word):**
- `headerHeight = 0`, outer `bkg.center_center = "0x00000000"`, `draggable = true`, and the
  per-line `text` sub-skin's `bkg.center_center = "$nil$"` all appear together, exactly as claimed,
  in the real `gameMessages.dlg` read this session.
- `autoScrollTextRadio`'s real position is `(x=29, y=59)`; `petrobrain-overlay.dlg`'s new window
  position `(20, 50)` + `MessageText`'s `(10, 10)` inset lands at `(30, 60)` — within a few px, as
  claimed.
- Text style values (`0xf5f5f4ff`, `DejaVuLGCSansCondensed-Bold.ttf`, `fontSize=12`, shadow
  `0x000000ff`/`(1,1)`) match `gameMessages.dlg`'s real per-line text skin exactly (unchanged from
  the already-approved prior revision, re-confirmed here since the file was re-read anyway).
- `Widget.lua`'s real bindings (`dxgui/bind/Widget.lua`) confirm `calcSize()` returns `(width,
  height)` — matching `apply_content_size`'s `local natural_w, natural_h =
  message_text:calcSize()` destructuring order — and that `setSize`/`setBounds` are pure
  size/position setters (`gui.WidgetSetSize`/`gui.WidgetSetPosition` passthroughs) with no
  documented side effect on the other axis. This matters for the task's "does repeated resizing
  accumulate drift" question: `setSize` is idempotent for a given `(w, h)` pair and never touches
  position, so repeated `apply_content_size()` calls across many `addText()`s cannot accumulate
  positional drift — each call is a fresh absolute set, not a relative adjustment. Window `x, y`
  is set once at `createWindow()` time and never touched by `apply_content_size`.
- `apply_content_size` call-site nil-safety: it is only ever called from `log_sizing_probes()`
  (itself only called from inside `createWindow()`, after `window`/`message_text` are assigned) and
  from `listen()` (only reachable via `onSimulationFrame`, which calls `createWindow()`/
  `initListener()` first if `window` is `nil`). So `apply_content_size` can never run before
  `window`/`message_text` exist — confirmed by reading the actual call graph, not assumed.
- Both call-site error containment: `listen()` wraps `apply_content_size` in its own `pcall`;
  `log_sizing_probes()`'s direct (unwrapped) call to `apply_content_size` is still contained,
  because `log_sizing_probes` itself is only ever invoked via `pcall(log_sizing_probes)` inside
  `createWindow()`. A failure either way degrades to a logged error, never an unhandled error
  escaping a frame. (Minor wording nit below — the file's own comment says "wrapped in its own
  pcall by both call sites," which is one level looser at the probe call site than literally
  stated; functionally equivalent, not worth more than an optional note.)
- `format_event_for_overlay`'s new `"<id>: <kind>, <summary>"` format genuinely reuses the existing
  convention: `_format_contact_line` (used by the `contacts`/`find` commands) is
  `f"{facts['id']}: {result['summary']}"`, and `facts['id']` is `contact.id`
  (`belief/tools.py:92`) — the same value as `Event.contact_id`. No new id vocabulary introduced.
- Test coverage for the id change is real, not decorative: `test_console.py`'s two
  `format_event_for_overlay` tests were updated to assert the new format (including the fallback
  case, `"CONTACT_missing: CONTACT_DETECTED"`), and `test_logger.py`'s three affected assertions —
  including the load-bearing `test_console_runner_overlay_push_failure_is_isolated_per_push` — were
  correctly updated to predict `CONTACT_1`/`CONTACT_2`/`CONTACT_3` from `ContactStore`'s real
  monotonic `_new_contact_id` counter (confirmed by reading `contacts.py:238-240`), not just
  patched to make the test pass. The test's own docstring explains why prediction (not read-back)
  is necessary given `fail_on` must be configured before the id-assigning call — accurate.
- Docs: `aircraft-layer/WORKFLOW.md`'s stale "420x200px... top-left corner... draggable" +
  titled-window description is gone, replaced with an accurate description of the new look,
  including the contact-id-prefixed line example and the dynamic height. `aircraft-layer/CLAUDE.md`
  and `body-layer/CLAUDE.md` are both updated accurately and specifically (not just "see plan.md").
- Verification (re-run independently, not taken from `implementation.md`):
  - `ruff format --check` / `ruff check` — pass, both subprojects.
  - `mypy --strict` (aircraft-layer: `cd aircraft-layer && mypy src`; body-layer: `cd body-layer &&
    mypy src`, per its CWD-resolution note) — pass, both subprojects, no issues.
  - `pytest -q` — **67 aircraft-layer** (unchanged from pre-refinement; this pass touched no
    aircraft-layer Python), **210 body-layer** (unchanged count; three files' string-literal
    assertions updated, no tests added/removed) — both counts match `implementation.md`'s claims
    exactly.
  - `git status` — clean; all files from all three commits are committed, nothing outstanding.
- Scope fit: the diff touches exactly what the three-task spec called for — `console.py` +
  its tests + `body-layer/CLAUDE.md` for Task 2, the Lua/`.dlg` pair +
  `aircraft-layer/WORKFLOW.md`/`CLAUDE.md` for Tasks 1 and 3 — no drift into unrelated files, no
  aircraft-layer Python touched (correctly, since the transport itself is unchanged).

### Required Fixes

None.

### Recommended

- **The restyled window now has no user-facing dismiss/hide affordance.** Removing the title bar
  removed the close button in the same stroke (as the task's own spec asked for — "no title bar, no
  close button"), and nothing replaces it: no keybind, no conditional creation, no toggle. Once
  `petrobrain-overlay-hook.lua` is deployed, the window is created unconditionally at DCS
  application startup (`onSimulationFrame`'s first call) regardless of whether body-layer's
  `--overlay` flag is ever used, and stays until DCS is closed or the Hook script file is removed
  and DCS restarted. When empty it should be visually inert (fully transparent `bkg`, no panel), so
  this is low-impact at rest, but once a line is showing there is no way to dismiss it early — only
  wait out `DEFAULT_DURATION_S=20`. `gameMessages.dlg` (DCS's own native message window) has the
  same shape (no close button either), so this isn't a deviation from the reference design, and it
  matches what Task 1 explicitly asked for — flagging per the task's own instruction to note this
  as a usability finding, not because it's a defect against the spec. Worth the user's explicit
  awareness before the confirmation sortie, and worth a conscious decision (not a default) if this
  becomes bothersome during dev use — e.g. during screen capture, or when the box is in the way of
  something the user wants to see undistracted.

### Optional Refinements

- **The header-comment claim about `gameMessages.dlg`'s `anchorInfos` is slightly inaccurate.**
  Both `petrobrain-overlay.dlg` and `petrobrain-overlay-hook.lua`'s headers state the window is
  "anchored to the top-left corner of the screen (`layout.data.anchorInfos[1]` has `top`/`left`
  both `type="min", offset=0`)". Reading the real file: `top` and `bottom` are both `type="min"`,
  but `left` and `right` are both `type="max"` (offset 0 on all four) — not "top/left both min" as
  stated. This doesn't affect anything functional: `WINDOW_X`/`WINDOW_Y` are literal constants
  passed straight to `window:setBounds`, never parsed from this anchor data, and the actual chosen
  position `(30, 60)` vs. the real `(29, 59)` is independently correct regardless of how the anchor
  semantics are described. Given the project's stated discipline around "grounded in real files,
  not invented numbers," this is worth a one-line comment correction next time either file is
  touched — not because the wrong claim caused a wrong number, but because a slightly-misdescribed
  citation is exactly the kind of thing that erodes trust in "confirmed by reading that file" claims
  if it compounds.
- **Wording of the "wrapped in its own pcall by both call sites" claim in `apply_content_size`'s
  comment** is one level looser than literally true at the `log_sizing_probes` call site (see
  "Independently verified" above — it's contained via the caller's `pcall`, not its own). No
  behavior difference; a precise reader could get a slightly wrong mental model of the error-handling
  structure. Cosmetic.

### Verdict

APPROVED (with the one Recommended item above worth the user's conscious acknowledgment, not a
blocker — it doesn't fail any of the three task acceptance criteria, and matches the plan's
explicit spec).

### Review Confidence

Full read of the diff (`f8cca80^..cc4599e`): both Python source/test changes, both Lua/`.dlg`
files in full (not just the diff hunks — read the complete post-change file to check call-graph
nil-safety and pcall containment, which a hunk-only read can't establish), and both doc files.
Cross-checked every restyle/position/API claim against the real, currently-installed
`$DCS_INSTALL_PATH/Scripts/UI/gameMessages.dlg` and `dxgui/bind/Widget.lua` this session (env vars
`DCS_INSTALL_PATH`/`DCS_SAVED_GAMES_PATH` were both set and readable here). Independently re-ran
`ruff format --check`, `ruff check`, `mypy --strict`, and `pytest` for both subprojects (using
`body-layer/.venv`'s tooling for aircraft-layer too, since aircraft-layer has no venv of its own —
stdlib-only per its `CLAUDE.md`) rather than trusting `implementation.md`'s reported counts.

**Genuinely unverified pending the user's confirmation sortie, as expected and not a defect of this
review** (per `session-state.md`'s own framing): whether the window actually renders chrome-free
and transparent as designed; whether the position lands where computed; whether `calcSize()`-driven
resizing behaves correctly at runtime (grows/shrinks smoothly, doesn't stutter/flicker, doesn't
hit the `MAX_CONTENT_HEIGHT_PX=380` clamp under real message bursts); whether `draggable = true`
still produces a working drag hit-target now that the window has no header and a fully transparent
background (both flags are confirmed to coexist in DCS's own real `gameMessages.dlg`, which is the
strongest available evidence they're compatible, but DCS's native window-drag hit-testing is
closed-source and not independently confirmed to function this way); and whether the six-identical-
lines question resolves to distinct real contacts or an association-gate churn bug now that ids
make it diagnosable. All of these are exactly what the plan's Stage 2 boundary already marks as
user-only/live-only, not gaps in this review.
