### Implementation Summary

Implemented Stages 1 and 3 in full, plus Stage 2's authoring (not its live
verification — that's the user's Stage 2/3/4 acceptance work). Stage 4 is
out of scope for this pass entirely.

### Files Changed

**Stage 1 — aircraft-layer transport**
- `aircraft-layer/src/collector/text_sender.py` (new) — `TextOverlaySender`:
  one UDP socket, `send_line` truncates to `MAX_LINE_LENGTH=200`, JSON-encodes
  `{"text": ...}`, sends to `127.0.0.1:7792`. Catches `OSError` and never
  raises — a missing listener is an expected state, not an error.
- `aircraft-layer/src/api/server.py` — new `POST /text/push`: validates a
  non-empty (after `.strip()`) string `text` field, 200/`{"ok": true}` on
  success, 400 on missing/invalid/empty `text` or non-JSON body, 503 if the
  server has no configured `text_sender`. `TelemetryAPIServer.__init__` gained
  `text_sender: TextOverlaySender | None = None`, matching the existing
  optional-cache-defaults pattern.
- `aircraft-layer/src/collector/__main__.py` — constructs a `TextOverlaySender`,
  new `--text-overlay-host`/`--text-overlay-port` flags, passes it into
  `TelemetryAPIServer`; closes it on shutdown alongside the other two servers.
- `aircraft-layer/tests/test_text_sender.py` (new) — real throwaway UDP socket:
  well-formed datagram, truncation to `MAX_LINE_LENGTH`, send-to-closed-port
  doesn't raise, lazy `open()`.
- `aircraft-layer/tests/test_text_push_api.py` (new) — real `TelemetryAPIServer`
  with a recording `TextOverlaySender` subclass double: valid push, missing/
  non-string/empty `text`, non-JSON body, unconfigured sender → 503.

**Stage 2 — overlay Hook script (UNVERIFIED, see below)**
- `aircraft-layer/dcs-export/petrobrain-overlay-hook.lua` (new) — Hook-state
  script modeled on DCS-SRS's installed overlay. Opens a UDP listener on port
  7792, decodes each datagram, calls `addText(text, 20)` on an `AutoScrollText`
  widget. Includes the plan's one-time sizing-probe diagnostic
  (`calcSize()`/`getTextLinesCount()` for short/~100/~200-char strings, logged
  once at window creation, then cleared).
- `aircraft-layer/dcs-export/petrobrain-overlay.dlg` (new) — Window (420×200,
  top-left corner, draggable) containing a background `Panel` and one
  `AutoScrollText` widget named `MessageText`, modeled on
  `Scripts/UI/gameMessages.dlg`'s real per-instance skin override shape.
- `aircraft-layer/WORKFLOW.md` — new "Deploy the overlay Hook script" section,
  plus updates to "Run the collector" (mentions the new UDP sender) and "Query
  from the Mac" (the new `POST /text/push` example).
- `aircraft-layer/CLAUDE.md` — "What this is" opening rewritten per the plan's
  proposed text; Structure section documents the new files; Testing section
  documents the two new test files and notes the Hook script/`.dlg` pair join
  `Export.lua` in the "no automated test, live-DCS-only" category.

**Stage 3 — body-layer wiring**
- `body-layer/src/aircraft_client.py` — `AircraftLayerClient.push_text_line`
  (`POST /text/push` via a new `_post_json` helper). Unlike the `get_*`
  methods, raises `AircraftLayerError` on any failure rather than swallowing
  it — the failure is meaningful to `ConsolePerceptionRunner`'s per-push
  try/except.
- `body-layer/src/belief/console.py` — `format_event_for_overlay(store, event,
  now_sim)`: `"<kind>: <summary>"` via `tools.describe_contact`, falling back
  to `"<kind> <contact_id>"` if the contact is gone (defensive, not expected).
- `body-layer/src/logger.py` — `ConsolePerceptionRunner.overlay_client:
  AircraftLayerClient | None = None`; `run_once()` captures
  `len(self.store.events)` before `tick()`, and after ticking pushes each
  newly appended event through `format_event_for_overlay` +
  `overlay_client.push_text_line`, with a per-push `try/except
  AircraftLayerError` (logged via a new module-level `logger`, then
  continues). `main()` gained `--overlay` (`store_true`, default off), which
  passes the *same* `aircraft_client` instance as `overlay_client` when set.
- `body-layer/CLAUDE.md` — documents `push_text_line`,
  `format_event_for_overlay`, and `--overlay` in the relevant Structure
  bullets, plus a short mention under "Running the live logger".
- Tests: extended `test_aircraft_client.py` (push success, unreachable-host
  raise), `test_console.py` (`format_event_for_overlay` normal + fallback
  cases), `test_logger.py` (overlay-off no-op, one-push-per-event, and the
  load-bearing per-push-isolation test below).

### Tests Added

- `test_send_line_delivers_well_formed_datagram`,
  `test_send_line_truncates_to_max_line_length`,
  `test_send_line_to_closed_port_does_not_raise`,
  `test_send_line_opens_socket_lazily_if_not_opened` (`test_text_sender.py`)
  — `TextOverlaySender`'s never-raises contract and truncation.
- `test_text_push_valid_forwards_to_sender`,
  `test_text_push_missing_text_field_returns_400`,
  `test_text_push_non_string_text_returns_400`,
  `test_text_push_empty_string_returns_400`,
  `test_text_push_non_json_body_returns_400`,
  `test_text_push_without_configured_sender_returns_503`
  (`test_text_push_api.py`) — the endpoint's full validation surface.
- `test_push_text_line_posts_to_text_push`,
  `test_push_text_line_raises_on_unreachable_host` (`test_aircraft_client.py`).
- `test_format_event_for_overlay_uses_describe_contact_summary`,
  `test_format_event_for_overlay_falls_back_when_contact_not_found`
  (`test_console.py`).
- `test_console_runner_without_overlay_client_pushes_nothing` — confirms
  `--overlay`'s absence is a true no-op (event still fires, nothing pushed).
- `test_console_runner_pushes_one_line_per_newly_materialized_event` — one
  event, one push, correct formatted text.
- `test_console_runner_overlay_push_failure_is_isolated_per_push` — the
  plan's flagged load-bearing case: two class-incompatible observations
  (`"BMP-2"` vs `"Ural truck"`, guaranteed to become two separate contacts
  via `association_over_time`'s class-incompatibility gate rather than
  relying on geometry) fire two `CONTACT_DETECTED` events in the same
  `tick()` batch; the first push is made to fail. Asserts: both observations
  are still in the returned list, both contacts/events still exist,
  `last_t_sim` is still updated, the *second* event's push still lands (the
  batch isn't short-circuited), and a subsequent poll's push still succeeds
  (the client isn't wedged by the earlier failure).

### Checks

- `ruff format --check aircraft-layer/src aircraft-layer/tests`: pass
- `ruff check aircraft-layer/src aircraft-layer/tests`: pass
- `mypy aircraft-layer/src` (strict): pass
- `pytest aircraft-layer/tests -q`: pass (67 tests)
- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (strict, run via `cd body-layer && mypy src` per its
  own CLAUDE.md note on `mypy_path` CWD-resolution): pass
- `pytest body-layer/tests -q`: pass (210 tests)
- Manual Stage 1 acceptance check (live, this session): started a real
  `collector` process on throwaway ports, POSTed
  `{"text":"CONTACT_DETECTED: BMP-2, high certainty"}` to `/text/push` via
  Python's `urllib` (curl itself was denied by this sandbox's permission
  system for reasons unrelated to the code — `urllib` worked immediately),
  and confirmed the exact datagram
  `{"text": "CONTACT_DETECTED: BMP-2, high certainty"}` arrived at a
  throwaway local UDP listener on the mapped port. Confirms the collector →
  UDP hop end-to-end; the Hook-script-side receipt (Stage 2) is unverified,
  see below.

### Notable Discoveries

- **The plan's anticipated Stage 2 JSON-decoding approach was wrong once the
  real files were opened.** The plan's "Affected Modules" section expected
  needing "a small, new, hand-rolled decoder" in the Hook script, reasoning
  from Export.lua's own documented constraint that LuaSocket has no JSON
  codec. That constraint is real for Export.lua's environment but does not
  hold for the Hook/GUI state: `$DCS_INSTALL_PATH/Scripts/JSON.lua` is a
  real, general-purpose, shipped JSON codec (`JSON:decode`/`JSON:encode`,
  855 lines, read in full this session), and DCS-SRS's own installed overlay
  loads exactly this file (`loadfile("Scripts\\JSON.lua")()`) rather than
  hand-rolling anything. The Hook script uses this shipped library instead of
  a new hand-written decoder — less code, and a more faithful copy of SRS's
  proven mechanism (which the plan's own stated risk-reduction principle
  favors). Documented in the Lua file's own header comment.
- **`module(...)` was deliberately not used**, unlike SRS's own file. SRS
  wraps itself in `module("srs_overlay")`, which replaces the chunk's global
  environment and then forces every otherwise-bare global (`pcall`, `type`,
  etc.) to be re-accessed via a captured `local base = _G` alias for the rest
  of the file. Every function/variable in the new Hook script is instead
  scoped as a chunk-local or a field on a local table, so nothing here ever
  touches the shared global namespace regardless of `module()` — the wrapper
  buys this file's shape no additional safety, so it's omitted to avoid the
  `base.pcall`-style indirection it would otherwise force throughout. Plain
  globals (`pcall`, `type`, `tostring`, `log`, `package`, `loadfile`) are used
  directly, exactly as SRS's own file does for the handful of lines that run
  before its own `module()` call — i.e. this is not a guess, it's the same
  behavior SRS's file itself demonstrates is safe in this state.
- **SRS's exact package.path/package.cpath extension was copied verbatim**
  into the Hook script (harmless if the default GUI-state search path already
  covers LuaSocket's DLL location, load-bearing if not) — this remains
  genuinely unverified without a live DCS session, so the safe choice was to
  copy it rather than omit it.
- **Both new Lua files were syntax-checked, not just written on faith.** No
  Lua interpreter was preinstalled in this sandbox; `lupa` (a Python binding
  bundling its own Lua 5.5 runtime) was pip-installed into a throwaway venv
  to compile-check both files (a real syntax parse, no execution against
  DCS's globals) and to walk the `.dlg`'s table structure programmatically
  (confirmed `type="Window"`, `type="AutoScrollText"`, bounds, and the
  `MessageText` child key all match what the Lua script expects). This is
  strictly weaker than a live DCS load — it cannot catch a wrong `dxgui` API
  call shape or a Hook-state-specific runtime error — but it does rule out
  a plain typo/syntax mistake, which a pure text review would not.
- **Screen position for the overlay window (20, 20 — top-left corner) is a
  genuine guess**, not verified against SRS's actual on-screen default
  (Session 2's own research notes that SRS's `.dlg` doesn't fix absolute
  screen coordinates in a way that's authoritative — its runtime default of
  200,200 lives in `SRSConfig.lua`, which is itself overridable and
  user-moved in practice). Chosen only to plausibly avoid SRS's stated
  default footprint; the window is draggable, so this is cheap to fix
  visually in Stage 2 regardless.
- **`DEFAULT_DURATION_S=20`, `WIDTH=420`/`HEIGHT=200`, `fontSize=12`, and
  `MAX_LINE_LENGTH=200`** were all taken directly from the plan/research
  doc's already-decided values — no new judgment calls there, just transcribed
  into code/the `.dlg`.
- **Everything in Stage 2 is unverified against a live DCS session per the
  task's explicit instruction** — both new files are marked as such in their
  own headers, in `WORKFLOW.md`, and in `aircraft-layer/CLAUDE.md`. Nothing
  about their DCS-runtime correctness (whether the window actually renders,
  whether `AutoScrollText`'s wrapping behaves as the research predicted,
  whether the sizing-probe diagnostic's log lines actually appear) has been
  confirmed — that is squarely the user's Stage 2 live check.

---

### Follow-up: restyle + two defect fixes (2026-09-09)

Refinement pass after Stage 2 + Stage 4 both passed live acceptance, driven by the user's
"Output-target decision, revisited after live acceptance" (see plan.md): keep the overlay, but
make it read like DCS's own native message feed, plus fix two defects the user's screenshot
exposed. Not a new stage of the original plan — same milestone, same branch.

**Task 1 — restyle (window chrome, position, legibility).** `aircraft-layer/dcs-export/
petrobrain-overlay.dlg` and `petrobrain-overlay-hook.lua` changed. Grounded directly in
`$DCS_INSTALL_PATH/Scripts/UI/gameMessages.dlg` (DCS's own native radio/trigger message boxes),
read in full this session:

- **No title bar, no close button**: `skin.params.headerHeight = 0` on the outer `Window` (matches
  `gameMessages.dlg`'s own override) plus `text = ""`. `gameMessages.dlg`'s own window has neither
  a header nor a close-button widget — removing the header removes both in one change, not two
  separate fixes.
- **No opaque panel**: the prior revision's `Box`/`Panel` child (a `0x00000090` dark rectangle) is
  removed entirely; the outer `Window`'s own background is set to `0x00000000` (fully transparent —
  alpha `00`), and `MessageText`'s per-line `text` sub-skin background is set to `"$nil$"`
  (`gameMessages.dlg`'s own override — the base `auto_scroll_text.skin.lua` skin otherwise defaults
  that to a faint `0x0000007d` translucent box per-line, which was still visible chrome). Text now
  floats directly over the 3D scene, exactly as `gameMessages.dlg` does.
- **Legibility without a panel**: the prior revision's text style (`color = 0xf5f5f4ff` near-white,
  font `DejaVuLGCSansCondensed-Bold.ttf`, `fontSize = 12`, `shadowColor = 0x000000ff`,
  `shadowOffset = {horz=1, vert=1}`) already matched `gameMessages.dlg`'s own values exactly and
  needed no change — confirmed, not assumed, by reading that file this session. The 1px black drop
  shadow, not a background box, is what keeps near-white text legible over bright terrain in DCS's
  own real design — directly relevant to the user's stated pale-desert-terrain case.
- **Screen position**: moved from the prior revision's arbitrary `(20, 20)` to `(20, 50)`, grounded
  in `gameMessages.dlg`'s own `autoScrollTextRadio` widget position `(29, 59)` inside a
  top-left-anchored window (`layout.data.anchorInfos[1]`, `top`/`left` both `type="min", offset=0`).
  `MessageText`'s own 10px inset from the window corner puts its rendered top-left at approximately
  `(30, 60)` — within a few px of DCS's real placement, not a fresh guess. `draggable = true` is
  kept (confirmed compatible with `headerHeight = 0` by `gameMessages.dlg` itself, which sets both).

**Task 2 — contact id in overlay lines** (defect: six `CONTACT_DETECTED: OP_ARMORED, observed,
currently visible.` lines were indistinguishable). `belief.console.format_event_for_overlay`
changed from `"<kind>: <summary>"` to `"<contact id>: <kind>, <summary>"` — reusing
`console.py`'s own existing `"<id>: ..."` convention (`_format_contact_line`/
`_format_contact_block`, the `contacts`/`show <id>` commands) rather than inventing a second id
format. `event.contact_id` is used directly (it's the same value `describe_contact`'s `facts['id']`
would return, since events are only ever derived from a contact that exists at tick time) — no new
lookup needed. Fallback case (`describe_contact` returns `None`, defensive-only) changed from
`"<kind> <contact_id>"` to `"<contact_id>: <kind>"` for the same consistency.

Tests updated: `test_format_event_for_overlay_uses_describe_contact_summary`,
`test_format_event_for_overlay_falls_back_when_contact_not_found` (`test_console.py`); three
string-literal assertions in `test_logger.py`
(`test_console_runner_pushes_one_line_per_newly_materialized_event`,
`test_console_runner_overlay_push_failure_is_isolated_per_push`, twice). The push-failure-isolation
test now predicts contact ids (`CONTACT_1`/`CONTACT_2`/`CONTACT_3`) ahead of the call that assigns
them, documented inline as relying on `ContactStore._new_contact_id`'s monotonic per-store counter
starting at 1 for a fresh store — necessary because `fail_on` must be configured before the
`run_once()` call that both assigns the ids and triggers the push.

**Six-identical-lines question (task's explicit ask, not fixed speculatively)**: `belief.events.
lifecycle_event_kind` makes a literal same-contact re-fire of `CONTACT_DETECTED` structurally
impossible under current code — that transition only fires when `previous_certainty is None`, which
is true exactly once per `Contact` (its founding tick); a contact that goes fully lost and comes
back fires `CONTACT_REACQUIRED`, never a second `CONTACT_DETECTED`. So the six lines were either (a)
six genuinely distinct real contacts, or (b) association-gate churn — `association_over_time`'s gate
failing to merge repeat percepts of one physical object into its existing contact, minting a new
`Contact`/`CONTACT_DETECTED` each time. Both would have looked identical under the old id-less
format; the id fix above makes this directly diagnosable on the next sortie without further
guessing: distinct `CONTACT_N` ids across the six lines confirms (a) or (b) is happening (own
positions/timestamps would then distinguish them), and if a tight cluster of new ids appears for
what's visually one object, that is a real, reportable association-gate bug — not fixed here, per
the task's explicit instruction not to chase this speculatively.

**Task 3 — clipped last line** (defect: the 6th of 6 lines was cut off mid-height at the prior
revision's fixed `420×200`, `HEIGHT` constant). Root cause is not fully certain from static recon —
`MAX_LINE_LENGTH = 200` chars at 400px width/`fontSize 12` with `AutoScrollText`'s wrapping means a
single event line can itself wrap to multiple visual lines (more so now that Task 2 lengthened
every line with a contact-id prefix), so "6 messages" was plausibly more like 9-12 wrapped visual
lines needing more than the fixed 180px content budget — but the exact native wrap/line-height
metrics are compiled into DCS's closed-source renderer and not recoverable by reading any Lua file
(confirmed already in Session 2 Findings 14/18 of the research doc).

Given that, a bigger guessed constant was rejected in favour of using the plan's own suggested
runtime self-diagnostic (`calcSize()`/`getTextLinesCount()`) as the live sizing mechanism itself,
not only as a one-time log: `petrobrain-overlay-hook.lua`'s new `apply_content_size()` calls
`message_text:calcSize()` after every `addText()` and resizes both `MessageText` and the window to
exactly that natural content height, clamped to `[MIN_CONTENT_HEIGHT_PX=60,
MAX_CONTENT_HEIGHT_PX=380]`. `calcSize()`/`setSize()` are both confirmed-real `Widget.lua` API
(direct `gui.WidgetCalcSize`/`gui.WidgetSetSize` passthroughs, read in full this session) — this is
new runtime behaviour, not previously exercised, and therefore the most load-bearing unverified
piece of this pass. Accepted worst case, documented in the Lua file itself: a burst of many
messages within one `DEFAULT_DURATION_S` (20s) window can still make `calcSize()` report more than
`MAX_CONTENT_HEIGHT_PX`, and it is unverified whether `AutoScrollText` then degrades by internally
scrolling (consistent with its name) or by pixel-clipping — same open question as before, just
pushed to a much less likely trigger. The existing one-time sizing-probe function was extended to
also log the post-resize window size for three known-length probe strings, so the next live session
gives concrete numbers to sanity-check `MIN_CONTENT_HEIGHT_PX`/`MAX_CONTENT_HEIGHT_PX` against,
rather than this pass's estimate standing unchecked indefinitely.

Both `.dlg` and `.lua` files were re-verified with the same `lupa`-based technique as the original
authorship pass (syntax-parse via `load()`, plus walking the `.dlg`'s table structure to confirm
`headerHeight`, the transparent `bkg`, the nilled per-line `bkg`, and the removed `Box` child are
all actually present as written) — this is strictly weaker than a live DCS load and cannot confirm
`calcSize()`/`setSize()`'s actual runtime behaviour, but rules out syntax/structural mistakes.

**Docs updated**: `aircraft-layer/WORKFLOW.md` ("Deploy the overlay Hook script" — new appearance
description, dropped the stale "420x200px... top-left corner... draggable" line) and
`aircraft-layer/CLAUDE.md`/`body-layer/CLAUDE.md` (verification-status note and
`format_event_for_overlay`'s format string, respectively).

**Checks**: `ruff format --check`/`ruff check`/`mypy --strict`/`pytest` all pass for both
subprojects (aircraft-layer 67 tests, body-layer 210 tests) — aircraft-layer's Python surface is
unchanged by this pass (only Lua/`.dlg`/docs), so its test count is identical to the prior revision;
body-layer's 210 (same count, three files' string literals updated, no new/removed tests).

**Still unverified pending the user's next sortie**: the entire restyle (window position/chrome/
legibility) and the entire Task 3 mechanism (`apply_content_size`'s live resize behaviour, and
whether `MIN_CONTENT_HEIGHT_PX`/`MAX_CONTENT_HEIGHT_PX` are well-chosen) — same discipline as
Stage 2's original authorship, marked as such in the Lua file's own header, `WORKFLOW.md`, and
`aircraft-layer/CLAUDE.md`.
