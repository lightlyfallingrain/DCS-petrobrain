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
