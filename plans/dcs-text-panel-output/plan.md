# BL-2.5 — In-cockpit text mirror (DCS overlay output channel)

> Branch: `feature/dcs-text-panel-output` (from local `main`, commit `2f7fffd`).
> Milestone source: `todo/todo.md` Backlog, "DCS radio message text panel as an SRS fallback /
> dev-visibility output channel" (raised 2026-09-09); interim-milestone status assigned by user
> decision, 2026-09-09 (see below).

### Goal

Give Petrovich's body-layer belief state a real-time, in-cockpit text display — a small scrolling
overlay window in the DCS render, fed by a new write-back channel through the aircraft layer — so
that live sortie testing (BL-2/PB-1.5 today, BL-3 next) can be observed without alt-tabbing to an
external terminal, and so the transport this milestone builds is reusable as BL-10's SRS-fallback
text channel later.

---

### Milestone identity (user decision, 2026-09-09)

**This is an interim milestone, scheduled immediately, ahead of BL-3.** Not a design question the
Architect resolves by weighing tradeoffs — the user settled it directly, the way PB-1.5 was
inserted between PB-1 and PB-2. Recorded here as a decision, not a recommendation.

**Label: BL-2.5, in the BL- (body-layer roadmap) family, not the PB- (runtime-cognition) family.**
Reasoning, since the user asked for it to be stated rather than assumed:

- PB-1.5 took the PB- label because it *was* a real cognition-capability tier — naked-eye
  perception — that maps cleanly onto `docs/concept/PETROBRAIN_RUNTIME.md`'s PB-numbered milestone
  sequence, even though its code landed inside body-layer's BL-1 timeframe. This feature has no
  such PB- slot: it doesn't perceive, remember, decide, or speak. It is dev/test instrumentation
  that happens to also lay transport groundwork BL-10 will reuse. There is no natural "PB-2.5" —
  minting one would misrepresent this as a cognition milestone.
- The roadmap it is actually scheduled into is body-layer's own (`todo/todo.md` Current Focus,
  `plans/body-layer/plan.md`'s BL-x table), sitting between BL-2 (done) and BL-3 (next before this
  decision). That makes BL- the operative family.
- **Precedent for a BL-numbered milestone containing mostly-non-body-layer work already exists**:
  BL-2's own Stage -1 was a pure aircraft-layer change (the ownship-flag fix), on its own branch,
  tracked under the BL-2 plan (`plans/pb2-contact-memory/plan.md` Stage -1) because BL-2 was the
  consumer that needed it. This milestone is the same shape, one level up: most of the new code is
  aircraft-layer (a Lua Hook script + a collector change), consumed by a small body-layer wiring
  addition — tracked as BL-2.5 because body-layer's dev-visibility need is what's driving it.

**Ordering consequence, checked per the user's request**: does landing this before BL-3 have any
effect worth recording? Two, both real — see Second-Order Effects.

**Housekeeping (do first, cheap):** update `todo/todo.md` — move the Backlog entry (line 294) into
Current Focus as "BL-2.5 (in progress)"; update `plans/body-layer/plan.md`'s milestone table to
insert a `BL-2.5 — In-cockpit text mirror` entry between the BL-2 and BL-3 bullets, one line,
cross-referencing this plan.

---

### Investigator check (architect step 2)

**Two Investigator sessions ran before this plan, both in
`aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md`** (Session 1 pre-dates this
plan; Session 2 ran during this planning pass specifically to close a gap that would otherwise have
forced a guess):

| Claim this plan depends on | Where it's settled |
| --- | --- |
| `Export.lua`'s environment cannot write to screen; a different Lua state is required | Session 1, Findings 1-3 (reproduced-locally, direct file read) |
| `Scripts/Hooks/*.lua` load into an unsandboxed GUI state at DCS startup, work with arbitrary missions, need no per-mission authoring | Session 1, Finding 4 (documented, `Sim_ControlAPI.md`) |
| The `net.dostring_in` → `trigger.action.outText` bridge needs an `autoexec.cfg` opt-in ED itself labels obsolete/unsafe | Session 1, Finding 4/6 — **not used by this plan**, see "Approach not taken" below |
| SRS's installed overlay is a complete, working reference implementation of exactly this pattern (Hook script + `dxgui` window + external-process-fed loopback socket) | Session 1, Finding 8 (reproduced-locally, full file read) |
| `dxgui`'s only shipped documentation is its own Lua source tree (`$DCS_INSTALL_PATH/dxgui/`), not a packed/hidden resource | Session 2, Finding 13 (reproduced-locally) |
| Plain `Static` widgets don't wrap by default (`textWrapping=false`); `AutoScrollText` — DCS's own native message-box widget — does wrap by default and has native accumulate/expire (`addText`/`clear`) | Session 2, Findings 14-17 (reproduced-locally, real shipped `.skin.lua`/`.dlg` files) |
| SRS's real, currently-installed overlay ships arbitrary-length strings to a non-wrapping `Static` with zero truncation and no known failure reports | Session 2, Finding 18 (reproduced-locally + inferred from real-world track record) |
| `Static`/`Widget` expose `calcSize()`/`getTextLinesCount()`/`getTextLines()` as real runtime self-diagnostic calls | Session 2, Finding 19 (documented, present in the shipped binding) |
| No second local `dxgui`-text addon exists to cross-check against; no further precision available from Hoggit/forums (one ED thread 403's, consistent with this project's known forum-fetch limitation) | Session 2, Findings 20-22 |

**Approach not taken, and why**: Session 1's Possible Approach 2 (`net.dostring_in` into real
`trigger.action.outText`) is not used. It requires creating `Saved Games/DCS/Config/autoexec.cfg`
with an ED-labeled "OBSOLETE and UNSAFE" opt-in — a standing config change the Hook-overlay
approach avoids entirely — and shares DCS's single global message queue with mission-author
messages, ATC text, and radio subtitles, which is the wrong long-term shape once this becomes the
real BL-10 SRS-fallback channel. Session 1's own recommendation (a Hook-state overlay, socket-fed
by the collector) stands, refined by Session 2 into a specific widget choice (below).

**No further Investigator pass is needed to start implementation.** The three items the task
flagged as unsettled are handled as follows, not deferred silently:

1. `net.dostring_in` live behavior — moot, that path isn't used.
2. `dxgui`/`Static` character-limit/wrap behavior — closed by Session 2 to the extent static recon
   can close it (see Message Model below); the one genuinely unresolvable piece (exact native
   pixel-clip behavior) is sidestepped by design (`AutoScrollText`'s own wrapping + a defensive
   server-side length cap), not left as a blocking unknown.
3. Per-frame cost of the overlay's render loop — a live-measurement question, not a desk-research
   one. Folded into Stage 4's live acceptance sortie, explicitly alongside the already-backlogged
   `LoGetWorldObjects` FPS measurement (`todo/todo.md` Backlog), per the task's own suggestion.

---

### Architect note on model depth

This plan adds the aircraft layer's **first inbound/write path** — until now the pipeline is
one-way out of DCS (`aircraft-layer/CLAUDE.md`: "read-only telemetry pipeline"). That is a real
architectural shift and is called out explicitly below (Affected Modules, Risks). I judged it does
**not** meet this role's bar for an opus re-invocation (coordinate systems, spatial schema,
cross-theatre generalization): the write surface is narrow (one string field, fire-and-forget UDP,
no delivery confirmation, no code execution, no aircraft state mutation), the transport pattern is
a direct copy of a proven, currently-installed reference implementation (SRS's own overlay), and
every design choice below is local and reversible. This is explicitly **not** the same class of
decision as BL-7's future real command channel (`scan_area`, aircraft-layer command issuance),
which `plans/aircraft-layer/plan.md`'s own "Architect note on model depth" already flagged as
needing its own Security plan review when it arrives — that flag stands unchanged and is not
satisfied or discharged by this plan.

---

### Output-target decision, revisited after live acceptance (user decision, 2026-09-09)

The backlog item this milestone came from asked for **DCS's native in-game radio message text
panel**. This plan instead specified a custom `dxgui` overlay window (see "Approach not taken"
above). After Stage 2 and Stage 4 both passed live, the user saw the working overlay and raised
exactly that divergence — the result imitates the radio feed rather than being it.

**Decision: keep the overlay; restyle it to read like the native message feed.** Not a switch to
`net.dostring_in` → `trigger.action.outText`. The tradeoff as put to the user:

- The native feed costs a `Saved Games/DCS/Config/autoexec.cfg` enabling an API ED itself labels
  "OBSOLETE and UNSAFE" — a standing config change on the user's machine, not a repo change.
- It shares DCS's single global on-screen message queue with mission-author text, ATC, and radio
  subtitles. That matters more, not less, once this becomes BL-10's real SRS fallback: Petrovich's
  speech interleaved with ATC is the wrong long-term shape.
- The overlay path was already working live, and the gap was cosmetic — chrome (title bar, close
  button, opaque panel) copied wholesale from SRS, not anything structural.

So the divergence is closed by making the overlay *look* right rather than by changing channel.
The `net.dostring_in` path stays rejected and documented above; DCS-gRPC's production use of it
(Session 1 Finding 10) means it remains a real option if this decision is ever revisited.

**Follow-up work under this decision** (refinement pass, post-acceptance): strip the title bar,
close button and opaque background; position and style per DCS's own `Scripts/UI/gameMessages.dlg`
and `dxgui` skins; plus two defects the user's screenshot exposed — overlay lines carried no contact
id (six distinct contacts and one contact re-firing six times rendered identically), and the window
clipped its last line at 420×200.

---

### Message model (Session 2 findings applied)

**Widget: `AutoScrollText`, not a manual `Static`-per-line stack.** Refining Session 1's
recommendation with Session 2's evidence: DCS's own native message system (`Scripts/UI/
gameMessages.dlg`) already *is* "a small scrolling log of short text lines" — this project's exact
shape — built on `AutoScrollText`, whose default skin wraps text and which manages its own
accumulate/expire list natively (`addText(text, duration)`, `clear()`). Building on it means
getting wrapping and line-stacking for free from a widget ED ships and maintains, instead of
reimplementing SRS's manual `Static` array + Y-offset bookkeeping. SRS's pattern remains a fully
valid fallback if `AutoScrollText`'s timed-expiry model proves awkward in practice (see Stage 2).

**Window construction: a `.dlg` file loaded via `DialogLoader.spawnDialogFromFile`, mirroring
SRS's exact, proven file pair** (`DCS-SRS-OverlayGameGUI.lua` + `DCS-SRS-Overlay.dlg`) rather than
constructing widgets by hand in Lua — this is the one part of the DCS-side implementation with no
independent confirmation beyond "SRS does it this way," so copying the mechanism as closely as
possible is the risk-reduction move, not a stylistic preference.

**Sizing (starting values, tunable at Stage 2/4, not hard-locked)**:
- Window footprint: 420×200px, matching SRS's proven real-world size.
- Text sub-skin: `textWrapping = true` (explicit — the default is `false`; DCS's own
  `auto_scroll_text.skin.lua` sets this explicitly on its inner text skin, not on the outer one),
  `fontSize = 12` (the `dxgui` default across every skin read this session).
- Screen position: a corner not overlapping SRS's own overlay (SRS's on-screen position wasn't
  determined this session — SRS's `.dlg` doesn't fix absolute screen coordinates in a way Session 2
  read as authoritative). **Confirm/adjust visually in Stage 2** — a cheap, local, reversible check,
  not a design decision to lock now.

**Expiry model: fixed-duration `addText(text, DEFAULT_DURATION_S)`, `DEFAULT_DURATION_S = 20`.**
This makes the overlay a *recent-activity feed*, not a persistent scrollback — body-layer's own
console/log remains the durable record; the overlay only needs to be readable for the few seconds
after an event fires. `DEFAULT_DURATION_S` is a Lua constant in the Hook script, not part of the
wire schema (keeps the wire format minimal; revisit only if a real need for per-message duration
control appears).

**Defensive length cap, regardless of widget choice**: the collector truncates `text` to
`MAX_LINE_LENGTH = 200` characters before sending, server-side (Python, not Lua) — Session 2
Finding 18's "overflow, not crash" conclusion is inferred from SRS's track record, not proven by
reading the native renderer, so a cheap truncation removes the one edge case that inference doesn't
fully cover. `AutoScrollText`'s own wrapping is expected to handle everything under that cap
without further truncation.

**Runtime self-diagnostic, one-time (Stage 2), not shipped logic**: log `calcSize()` and
`getTextLinesCount()` after `addText()` for 2-3 known-length test strings, per Session 2's Possible
Approach 2 — sidesteps needing an exact glyph-width number, and informs whether
`MAX_LINE_LENGTH`/window size need adjusting before Stage 4's live acceptance. This is diagnostic
output written once during the spike, not a mechanism the shipped script depends on at runtime —
keeps the Hook script as "deliberately dumb" as `Export.lua` already is.

**Wire schema (collector → Hook script, UDP, one JSON object per datagram — no newline needed,
datagram framing already provides it, unlike the existing TCP stream)**:

```
{"text": "<line, already truncated to MAX_LINE_LENGTH>"}
```

Deliberately minimal and content-only — no contact id, no event kind, no belief-specific field —
so BL-10 can reuse this exact channel later by POSTing `OutgoingSpeech` text instead of a belief
event line, with zero changes to the transport. A `level`/color field (mapping to SRS's own
white/yellow/red skin pattern) is a natural, cheap future extension for severity-differentiated
color — **not built now**, noted so it isn't rediscovered as a surprise later.

---

### Affected Modules / Files

**New — aircraft-layer:**

- `aircraft-layer/src/collector/text_sender.py` — `TextOverlaySender`: opens one UDP socket,
  `send_line(text: str) -> None` truncates to `MAX_LINE_LENGTH`, JSON-encodes
  `{"text": ...}`, `sendto()`s it to `(DEFAULT_HOST="127.0.0.1", DEFAULT_PORT=7792)`. Catches and
  logs `OSError` (loopback UDP can raise `ECONNRESET`-class errors on Windows after a prior ICMP
  port-unreachable, e.g. when DCS/the Hook script isn't loaded) — must never raise out of
  `send_line`, since a missing listener is an expected, non-error state (DCS not running, or
  running without the overlay Hook script), mirroring the "`null` is not an error" posture already
  used for the empty-cache `/latest` endpoints.
- `aircraft-layer/dcs-export/petrobrain-overlay-hook.lua` — canonical Hook-state script, deployed
  to `Saved Games\DCS\Scripts\Hooks\petrobrain-overlay.lua`. Opens a UDP listener on
  `TEXT_OVERLAY_PORT` (7792, loopback), decodes one JSON object per received datagram (a small,
  new, hand-rolled *decoder* — `Export.lua` only ever encodes JSON today, this is the project's
  first Lua-side JSON *decode*, needed because LuaSocket has no JSON codec, same constraint
  `Export.lua`'s header already documents), calls `addText(text, DEFAULT_DURATION_S)` on the
  `AutoScrollText` widget.
- `aircraft-layer/dcs-export/petrobrain-overlay.dlg` — the widget/skin definition (window, `Box`,
  `AutoScrollText`, text sub-skin with `textWrapping=true`), deployed alongside the `.lua` to
  `Saved Games\DCS\Scripts\Hooks\petrobrain-overlay.dlg`, loaded via
  `lfs.writedir() .. "Scripts\\Hooks\\petrobrain-overlay.dlg"` (mirrors `Export.lua`'s own
  `lfs.writedir()`-relative path convention for its debug flag/log).
- `aircraft-layer/tests/test_text_sender.py` — fake UDP receiver socket, confirms well-formed
  datagram content and confirms a send to a closed/unreachable port doesn't raise.

**Modified — aircraft-layer:**

- `aircraft-layer/src/api/server.py` — new `POST /text/push` on the existing LAN-facing
  `TelemetryAPIServer` (port 7791, unchanged). Body `{"text": "<string>"}`; validates `text` is a
  non-empty (after `.strip()`) string, calls `TextOverlaySender.send_line`, responds `200
  {"ok": true}`. `400 {"error": ...}` on a missing/invalid/empty `text` field or non-JSON body.
  `TelemetryAPIServer.__init__` gains `text_sender: TextOverlaySender | None = None` (defaults to
  `None`, matching the existing "keep every existing call site working unchanged" pattern used for
  `world_objects_cache`/`petrovich_indication_cache`) — when `None`, `/text/push` responds `503
  {"error": "text push not configured"}` rather than crashing.
- `aircraft-layer/src/collector/__main__.py` — constructs a `TextOverlaySender`, new
  `--text-overlay-host`/`--text-overlay-port` CLI flags (mirroring the existing `--host`/`--port`
  pattern), passes the sender into `TelemetryAPIServer`.
- `aircraft-layer/WORKFLOW.md` — new "Deploy the overlay Hook script" section (copy both new files
  to `Saved Games\DCS\Scripts\Hooks\`, same discipline as the existing `Export.lua` deploy section:
  canonical copy in the repo, never edit the deployed copy in place; optional sync-folder copy
  follows the same user-managed convention as `Export.lua`'s `win-mac-sync/to-windows/` mention —
  no repo change needed there, `win-mac-sync/` is entirely gitignored and gets nothing added by
  this plan).
- **`aircraft-layer/CLAUDE.md`'s "What this is" opening line** — must change. Current text: "Live,
  LAN-reachable, **read-only** telemetry pipeline." This is no longer accurate once `/text/push`
  exists. Proposed replacement:

  > Live, LAN-reachable telemetry pipeline (read path: DCS → `Export.lua` → collector → LAN API)
  > plus one narrow write-back channel for in-cockpit text display (`POST /text/push` → collector →
  > loopback UDP → a DCS Hook-state overlay). Kinematic state, world objects, and Petrovich's
  > indication text remain read-only; text display is the only inbound direction, and it carries
  > opaque display strings only — no aircraft state, no commands, no code. Switches, contacts, and
  > aircraft commanding remain out of scope, deferred to follow-on milestones.

  Also update the "Structure" section's `src/api/` bullet to list `POST /text/push` alongside the
  three existing `GET` endpoints, and the "Testing" bullet list to mention `test_text_sender.py`.

**New — body-layer:**

- `body-layer/tests/test_aircraft_client_text_push.py` (or extend the existing aircraft-client
  test file) — spins up a real `TelemetryAPIServer` with a fake `TextOverlaySender` double, POSTs
  through the real `AircraftLayerClient.push_text_line`, asserts the fake sender received the text.

**Modified — body-layer:**

- `body-layer/src/aircraft_client.py` — `AircraftLayerClient.push_text_line(text: str) -> None`:
  `POST /text/push`, raises `AircraftLayerError` on failure (network error, non-200, invalid JSON),
  mirroring the existing `_get_json`/`get_*` method style (a new `_post_json` private helper
  alongside `_get_json`).
- `body-layer/src/belief/console.py` — new `format_event_for_overlay(store: ContactStore, event:
  Event, now_sim: float) -> str`: looks up the event's contact via `tools.describe_contact` and
  returns `f"{event.kind}: {result['summary']}"`, or `f"{event.kind} {event.contact_id}"` if the
  contact is no longer found (should not normally happen — events are only ever derived from a
  contact that exists at tick time — kept as a defensive fallback, not a expected path). Reuses
  `describe_contact`'s existing `summary` field rather than inventing new belief-reading logic,
  consistent with `console.py`'s "owns no belief logic" invariant.
- `body-layer/src/logger.py` — `ConsolePerceptionRunner` gains `overlay_client:
  AircraftLayerClient | None = None` (mirroring the existing `output: TextIO | None` optional-sink
  pattern exactly). In `run_once()`: capture `len(self.store.events)` before calling
  `self.store.tick(...)`; after, if `overlay_client is not None`, format and push each newly
  appended event via `format_event_for_overlay` + `overlay_client.push_text_line`, catching
  `AircraftLayerError` per push (log and continue — one failed push must never stop the poll loop,
  drop the observations already collected this poll, or skip pushing subsequent events in the same
  batch). `main()` gains `--overlay` (`store_true`, default off — an explicit opt-in, matching
  `--debug`/`--console`'s existing explicit-opt-in convention rather than defaulting a new network
  write path on); when set, passes the *same* `aircraft_client` instance as `overlay_client` (no
  new URL/CLI argument needed — the push endpoint lives on the exact aircraft-layer instance
  `--aircraft-layer-url` already points at).
- `body-layer/CLAUDE.md` — document `push_text_line`, `format_event_for_overlay`, and `--overlay`
  in the `aircraft_client.py`/`logger.py`/`belief/` Structure bullets.

**Deliberately not modified / considered and deferred:**

- `PerceptionLogger` (the plain, non-`--console` logger path) does **not** get overlay wiring in
  this milestone. Its per-`Observation` stream runs at up to source-poll rate (5-10 Hz-class under
  `every_poll`), which would produce line-churn on the cockpit display rather than the
  contact-event-rate signal that's actually useful in-cockpit. If a future need for raw-observation
  in-cockpit visibility appears, wire it the same way (an optional `overlay_client` field), don't
  invent a second mechanism.
- No `level`/color wire field (see Message Model).
- No persistence of pushed lines anywhere — the overlay is a live mirror, not a log; body-layer's
  own observation/event log remains the durable, replayable record.

---

### Implementation Plan

**Stage 1 — Aircraft-layer collector-side transport (no DCS needed).**
`text_sender.py`, `api/server.py`'s `POST /text/push`, `collector/__main__.py` wiring, unit tests
(fake UDP receiver for the sender; extended API tests for `/text/push` — valid, missing/invalid
`text`, `text_sender=None` case).
*Acceptance:* `ruff format`/`ruff check`/`mypy --strict`/`pytest` all clean under
`aircraft-layer/`, no live DCS needed. Manually confirm with `curl -X POST
http://localhost:7791/text/push -d '{"text":"test"}'` against a running collector (no DCS
required) that a UDP datagram appears on `127.0.0.1:7792` (e.g. via `nc -ul 7792` or a throwaway
Python listener) before moving to Stage 2.

**Stage 2 — Overlay Hook script (USER-ONLY, needs DCS running — cheap/quick, not the full
acceptance sortie).**
Build `petrobrain-overlay-hook.lua` + `petrobrain-overlay.dlg` per the Message Model section above,
modeled directly on `DCS-SRS-OverlayGameGUI.lua`/`DCS-SRS-Overlay.dlg`. Deploy per the new
WORKFLOW.md section. Load DCS (mission or main menu, whichever the Hook-state load timing turns
out to support — confirm which, this is exactly the kind of detail Session 1/2's static recon
couldn't settle), confirm the window renders, then re-run Stage 1's `curl` test and confirm the
line appears on screen. Push 5+ lines in quick succession, confirm scrolling/expiry behavior looks
reasonable at `DEFAULT_DURATION_S=20`. Log `calcSize()`/`getTextLinesCount()` for a short, a
~100-char, and a ~200-char (`MAX_LINE_LENGTH`) test string; adjust window size/`fontSize` if the
log shows real wrapping/clipping problems — a local, reversible tuning step.
*Acceptance (USER-ONLY):* overlay visibly renders and updates from a manual `curl` push; no DCS
crash or Lua error in `dcs.log`.

**Stage 3 — Body-layer producer wiring (no DCS needed for unit tests).**
`AircraftLayerClient.push_text_line`, `belief.console.format_event_for_overlay`,
`ConsolePerceptionRunner.overlay_client` + `run_once()`'s new-event-forwarding logic, `main()`'s
`--overlay` flag.
*Acceptance (fixture):* a scripted `ConsolePerceptionRunner.run_once()` sequence (fake aircraft
client producing observations that trigger `CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`,
fake overlay-client double recording calls) asserts exactly one push per newly materialized event,
correct formatted text, and that a fake `AircraftLayerError` on one push doesn't affect
`store`/`last_t_sim`/the returned `Observation` list or block the next poll's pushes.

**Stage 4 — Live integration acceptance (USER-ONLY, requires flying DCS).**
Run the full pipeline: Stage 1's collector + Stage 2's deployed Hook script + `python -m logger
--console --overlay --aircraft-layer-url ... --theatre ... --world-model-db ...` against a live
mission with placed targets (reuse BL-2 Stage 6's target setup). Protocol:
(a) fly a naked-eye detection pass, confirm `CONTACT_DETECTED: <summary>` appears in-cockpit within
one poll interval of it appearing in the console's own state;
(b) fly away, confirm `CONTACT_LOST` appears;
(c) return, confirm `CONTACT_REACQUIRED` appears;
(d) qualitatively assess whether `DEFAULT_DURATION_S=20` feels right at real sortie pace — adjust
the Lua constant if not (local, reversible, no plan update needed for a tuning-constant change);
(e) **fold in the already-backlogged `LoGetWorldObjects` FPS measurement** (`todo/todo.md` Backlog,
"measure `LoGetWorldObjects` FPS cost live before tuning its poll rate") into this same sortie —
toggle the overlay Hook script present/absent (or just note frame-time with it actively rendering
vs. not) alongside that item's existing 5/2/1 Hz `LoGetWorldObjects` toggle protocol, per the
task's own suggestion that these two measurements share one sortie rather than costing two.
*Acceptance (USER-ONLY):* all three lifecycle events observed in-cockpit with plausible timing;
`--overlay` off (default) reproduces BL-2 Stage 6's existing behavior unchanged, confirming the
opt-in flag is a true no-op when absent.

---

### Risks & Unknowns

- **First inbound/write path on the aircraft-layer LAN API.** Called out in "Architect note on
  model depth" above — not blocking, but worth the user's explicit awareness since it changes a
  documented invariant statement (`aircraft-layer/CLAUDE.md`'s "read-only" framing) for the first
  time. The write surface is narrow (one opaque display string, fire-and-forget, no delivery
  confirmation, no aircraft-state mutation) and does not, on its own, trigger the project's current
  security-review exemption for this phase (root `CLAUDE.md`: skip Security/Performance-Reviewer
  "this phase is an offline single-user local pipeline with no hot path and **no untrusted-input
  surface yet**") — but this endpoint *is* a new LAN-reachable write surface, even if a low-risk
  one, and if the user wants a Security plan-review pass despite the current exemption, that's a
  one-line ask, not a plan change.
- **No delivery confirmation, by design.** UDP collector→Hook-script send is fire-and-forget; a
  successful `POST /text/push` (200) means only "the collector attempted the UDP send," not "the
  line appeared on screen" (e.g. DCS not running, or running without the overlay Hook script
  loaded). Body-layer's `--overlay` mode has no way to detect this and will silently produce no
  visible effect — acceptable for a dev-visibility mirror, would need reconsidering if BL-10 ever
  wants a stronger delivery guarantee for the real SRS-fallback case.
- **Exact native overflow/clip behavior for an over-length string remains genuinely unverified**
  (Session 2's own "Unresolved" — this is a closed-source native-renderer question no further desk
  recon can answer). Mitigated, not eliminated, by `AutoScrollText`'s wrapping plus the
  `MAX_LINE_LENGTH` server-side cap; Stage 2's live spike is the first real look.
- **Hook-state load timing (main menu vs. mission) is unconfirmed** — Session 1/2 established
  scripts load once at DCS *application* startup, not per-mission, but neither session ran DCS to
  confirm whether the window is visible/rendering before a mission is loaded. Stage 2 settles this
  directly; if the window only renders in-mission, that's still sufficient for both this
  milestone's use case and BL-10's later one.
- **`DEFAULT_DURATION_S=20` and the 420×200/fontSize-12 sizing are placeholders**, chosen from
  SRS's real-world proven values and this project's own judgment of what reads well during a
  sortie, not measured against this project's actual line-arrival rate. Tune at Stage 4; no plan
  update needed for a constant change.
- **Scope-boundary risk**: `--overlay`'s per-push `AircraftLayerError` handling must genuinely be
  per-push, not per-poll — a single unreachable collector (DCS not running, network hiccup) must
  degrade to "no overlay lines this poll," never to "the whole `--console` poll loop stops working."
  Reviewer should check this specifically, since it's the one place a defensive try/except is load
  bearing rather than cosmetic.

---

### Second-Order Effects

- **Landing this before BL-3 plausibly makes BL-3's own live acceptance easier, which is an
  argument the user's ordering is correct, not just convenient.** BL-3 (world enrichment) adds
  semantic/terrain-derived facts to `Contact` that are exactly the kind of thing worth eyeballing
  against what's actually visible out the window during a live sortie — the same benefit BL-2/PB-1.5
  already got from an external log, now available in-cockpit for BL-3 too, for free, once this
  lands.
- **Conversely, BL-3 landing first would have changed this milestone's event-line content, not its
  transport.** `format_event_for_overlay` can only surface what BL-2 already produces
  (classification + certainty via `describe_contact`'s `summary`) — no semantic/general-area
  reference, no clock-bearing, since those are BL-3 fields that don't exist yet. **Known,
  deliberately accepted follow-up**: when BL-3 lands, its own plan should touch
  `format_event_for_overlay` to enrich the mirrored line with the new semantic fields, rather than
  leaving the overlay's text stuck at BL-2's vocabulary. Recording this now so BL-3's plan doesn't
  have to rediscover it.
- **Unblocks BL-10 partially, not fully.** The collector↔Hook-script transport (UDP, `/text/push`,
  `AutoScrollText`) is designed to be content-agnostic and directly reusable for BL-10's SRS-fallback
  text channel (Message Model's "reuse" note). What BL-10 still owns entirely and this milestone
  does not touch: the actual SRS client/plugin interface (unverified per `plans/body-layer/plan.md`
  §7, needs its own Investigator pass), and swapping the producer from body-layer's belief-event
  mirror to BL-5a/BL-10's real `OutgoingSpeech` records.
- **Narrows `aircraft-layer/CLAUDE.md`'s "read-only" framing permanently** — any future aircraft-layer
  capability now joins a precedent of "read-mostly, with narrow, explicitly-scoped write channels,"
  rather than an absolute read-only rule. BL-7's future command channel is a much larger instance of
  the same shape and still needs its own Security review when it arrives (unchanged from
  `plans/aircraft-layer/plan.md`'s existing flag).
- **No effect on world-model, Mission Interpreter, or coordinate/spatial invariants** — this
  milestone touches only the aircraft-layer transport and body-layer's belief-consumption edge; no
  new coordinate transform, no new persisted schema, no DCS-authority question.

---

### Invariant Check

- **DCS authoritative / never modified**: the new Hook script + `.dlg` are written to `Saved
  Games\DCS\Scripts\Hooks\`, not the DCS installation — same sanctioned category as `Export.lua`'s
  existing deployment. No install-tree file is touched, no `autoexec.cfg` is created (that path was
  explicitly rejected — see "Approach not taken").
- **Code owns facts, models interpret**: unaffected — no model is involved anywhere in this
  milestone. The overlay displays facts `belief.tools`/`belief.events` already derived
  deterministically; it adds no new derivation.
- **Petrovich never omniscient**: unaffected — the overlay mirrors `Contact`/`Event` state that
  already passed through the `Percept` boundary (BL-2's invariant); it introduces no new read of
  DCS ground truth.
- **Provenance / uncertainty / timestamps**: the overlay is a **display surface, not a record** —
  it carries no independent provenance obligation of its own. The durable, provenance-carrying
  record remains body-layer's append-only observation/event log; a line disappearing from the
  cockpit overlay after `DEFAULT_DURATION_S` is not a loss of any fact, only of a transient display.
  Worth stating explicitly so this isn't later mistaken for a second data store that also needs
  provenance fields.
- **`world-model/data/` gitignore boundary**: unaffected — no world-model code or data touched.
- **Module independence (root `CLAUDE.md`)**: body-layer ↔ aircraft-layer stays HTTP/JSON
  throughout (a new endpoint on the existing client/server pair, not a new transport kind or a new
  in-process import). No exception to the body-layer↔world-model-only in-process-import rule is
  introduced or needed.

---

### Decisions made without escalation (local, reversible, recorded per AGENTS.md)

- `AutoScrollText` over a manual `Static`-per-line stack (Message Model).
- Window sizing (420×200, fontSize 12), position-TBD-at-Stage-2, `DEFAULT_DURATION_S=20`,
  `MAX_LINE_LENGTH=200` — all tunable constants, not locked contracts.
- Scope: mirror only belief lifecycle events (via `--overlay`'s `ConsolePerceptionRunner` hook),
  not `PerceptionLogger`'s raw per-`Observation` stream — line-noise vs. signal tradeoff, reversible
  by adding the same optional-field pattern to `PerceptionLogger` later if ever needed.
  `format_event_for_overlay` reusing `tools.describe_contact`'s `summary` rather than inventing new
  belief-reading logic.
- `--overlay` as an explicit opt-in flag defaulting off, reusing the existing `aircraft_client`
  instance rather than adding a second client type or a new URL argument.
- No `level`/color wire field in this milestone (Message Model).

No item in this plan met AGENTS.md's escalation bar (two reasonable approaches with `CLAUDE.md`
silent, a new dependency, a materially larger/smaller scope than expected, a need to rewrite
existing tests, or a conflict with a stated invariant) strongly enough to stop and ask — the one
genuinely notable architectural fact (the first write path on the LAN API) is surfaced above as a
Risk for the user's awareness, not as a blocking question, since only one workable design exists
for it and it doesn't conflict with any stated invariant.
