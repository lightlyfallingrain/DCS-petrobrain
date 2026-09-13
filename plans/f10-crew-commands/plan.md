### Goal

Let the player issue a small, fixed set of Petrovich commands (watch nearest contact, scan
forward, cancel task) from DCS's native F10 radio-comms menu, using the Hook→mission-scripting
bridge (`net.dostring_in("scripting", ...)`) that `aircraft-layer/research/
2026-09-13-f10-radio-menu-command-input.md` (Findings 7–11) live-confirmed on DCS 2.9.29.27278,
and route selections into body-layer's existing `--crew-text` command handling.

**Mechanism check (per user instruction to flag substitutions up front): this plan builds exactly
Approach B from the research doc** — a Hook script registers F10 → Other items via the
`dostring_in("scripting", "missionCommands.addCommand(...)")` bridge at `onSimulationStart` and
drains selections back out by polling the same bridge — no per-mission `.miz` authoring (Approach
A) and no keybind fallback (Approach D). This is the same mechanism AI wingman commands use, per
the user's explicit preference.

### Affected Modules / Files

**aircraft-layer** (new Hook→collector inbound direction — the reverse of BL-2.5's
collector→Hook UDP, and a new channel distinct from BL-6's collector→Export.lua command port):

- `aircraft-layer/src/schema/f10_command.py` *(new)* — `F10CommandEvent` dataclass
  (`command: str`, `received_wall_clock_s: float`), `to_dict`/`from_dict`, mirroring every other
  schema module's shape. No DCS model-time field — the Hook cannot cheaply attach one (see
  "Decisions" §1) — so provenance here is wall-clock-at-receipt only, stated explicitly rather
  than fabricating a model-time value.
- `aircraft-layer/src/collector/cache.py` — new `F10CommandQueue` class: a bounded FIFO
  (`collections.deque(maxlen=...)`), `push`/`drain_all` (not `push`/`latest` — this is the first
  *event-queue* cache in this module, not a *latest-value* cache; see "Decisions" §1 for why a
  single-slot cache is wrong here).
- `aircraft-layer/src/collector/f10_command_receiver.py` *(new)* — `F10CommandReceiver`, a
  loopback UDP **listener** (mirrors `TextOverlaySender`'s socket lifecycle, reversed direction: a
  `recvfrom` loop on a background thread instead of `sendto`). Validates each datagram against a
  fixed allowed-token constant (`ALLOWED_COMMANDS = ("watch_nearest", "scan_forward",
  "cancel_task")`) before enqueueing — malformed/unrecognized payloads are dropped and logged at
  debug level, never enqueued, so this socket cannot become a general remote-exec surface even
  though it's loopback-only.
- `aircraft-layer/src/api/server.py` — new `GET /f10_commands/poll`: drains `F10CommandQueue` and
  returns a JSON list of `{"command": ..., "received_wall_clock_s": ...}`, oldest first, empty
  list if none pending. **Documented exception to every other endpoint's idempotent-read
  contract** — this one mutates collector-local queue state on every call, so it assumes exactly
  one poller (body-layer); a second concurrent poller would silently steal commands from the
  first. Worth a docstring callout at this endpoint, same as `/text/push`'s "only inbound/write
  path" callouts elsewhere.
- `aircraft-layer/src/collector/__main__.py` — wire `F10CommandQueue` + `F10CommandReceiver` in
  alongside the existing caches/senders; new `--f10-host`/`--f10-port` CLI flags (default
  `127.0.0.1:7794` — **not** 7793, which BL-6's `command_sender.py`/`Export.lua`'s
  `COMMAND_PORT` already own; this is a fourth distinct loopback port).
- `aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua` *(new file, not an extension of
  `petrobrain-overlay-hook.lua`* — see "Decisions" §2) — registers the three F10 items under a
  `missionCommands.addSubMenu("Petrovich", nil)` submenu at `onSimulationStart` via
  `net.dostring_in("scripting", ...)`, each callback appending a fixed literal token to a
  mission-scripting-state queue table; polls and drains that queue once a second via the same
  bridge, only between `onSimulationStart`/`onSimulationStop`; sends one UDP datagram per drained
  token to the collector's new port. The injected `dostring_in` snippet is a single fixed,
  version-controlled string literal (labels/tokens baked in) — no string built from network input,
  per the user's "no general-purpose remote-exec surface" constraint.
- `aircraft-layer/WORKFLOW.md` — new "Deploy the F10 commands Hook script" section (deploy step,
  port table entry for 7794, the `autoexec.cfg` opt-in as a stated deploy prerequisite — already
  user-accepted per the research doc), plus the minimal-opt-in verification sub-step (see
  "Decisions" §1 and "Risks").
- `aircraft-layer/tests/` — `test_f10_command_receiver.py` (real loopback UDP socket, mirroring
  `test_text_sender.py`'s pattern: well-formed datagram enqueues, malformed/unknown-token datagram
  is dropped, queue bound is respected), `test_api.py` additions for `/f10_commands/poll`
  (drain-then-empty, correct ordering). `petrobrain-f10-commands-hook.lua` gets a `luac5.1 -p`
  syntax check like every other Lua file — no automated behavioral test (same posture as
  `petrobrain-overlay-hook.lua`).

**body-layer** (consumes the new endpoint, dispatches through the existing `--crew-text` handler):

- `body-layer/src/aircraft_client.py` — new `get_f10_commands(self) -> list[dict[str, Any]]`
  (`GET /f10_commands/poll`), following the existing `get_*` convention: raises
  `AircraftLayerError` on network/parse failure (via `_get_json`, same as every other `get_*`),
  returns `[]` on an empty response rather than `None` (the response is always a list, never
  `null`, unlike the `/latest` endpoints).
- `body-layer/src/belief/crew_console.py` — `CrewConsole` gains:
  - a new optional field `tasks: TaskStore | None = None` (mirrors `aircraft_client`'s
    reserved-field pattern — `None` unless wired), needed for `cancel_task` (see "Decisions" §4
    and the Risks note on this field currently having no producer in `--crew-text` mode).
  - `handle_f10_command(self, token: str, now_sim: float) -> list[str]` — a small fixed dispatch
    table (`watch_nearest` / `scan_forward` / `cancel_task` → three private handlers), each
    ending in the same `self._print(...)` call `handle_line`/`drain_events` already use, so F10
    output reaches `output` and `overlay_client` through the one existing funnel point (Decision 4
    — no parallel print/push path). An unrecognized token (should not happen, aircraft-layer
    already filters, but defensive) returns `[]`.
  - `_nearest_contact_id(self, now_sim)` helper — new, small glue logic (not a rediscovery of
    existing selection logic; checked `tools.py`/`belief.attention` and found no "nearest by
    range" helper exists today, only `_highest_attention_contact`'s attention-tier-then-phase
    selection). Calls `get_contacts(self.store, enrichment=self.enrichment)`, reads each result's
    `facts["relative_now"]["range_m"]` (requires `self.enrichment` — see the guard below), and
    returns the minimum-range contact id, or `None` if `enrichment` is unset or no contacts have a
    resolvable range.
- `body-layer/src/logger.py` — new `--f10-commands` flag (default off), **only meaningful combined
  with `--crew-text`** (mirrors `--overlay`'s "additive to an existing mode" posture, not a
  standalone flag): `_run_crew_text_poll_loop` gains a call to
  `aircraft_client.get_f10_commands()` after each `run_once()`/`drain_events()` pass (same hook
  point `--overlay`'s event mirror and `--crew-text`'s own event drain already use), dispatching
  each returned token through `CrewConsole.handle_f10_command`. Wrapped in its own
  `try/except AircraftLayerError` (log-and-continue) — the same per-call isolation shape
  `run_once`'s BL-2.5 overlay-push loop already uses, so one failed poll never stops the loop.
- `body-layer/tests/` — `test_crew_console.py` additions: `handle_f10_command` for all three
  tokens against a fixed `ContactStore`/`TaskStore` fixture (including the no-`enrichment`/
  no-contacts/no-`tasks` guard-clause cases), `test_aircraft_client.py` addition for
  `get_f10_commands` against a real loopback server double.
- `body-layer/ROADMAP.md` / `todo/todo.md` — not touched by this plan; update at merge time per
  the root `CLAUDE.md` "Milestone Completion" note (this is a body-layer backlog item, not
  currently numbered `BL-x` — leave numbering to whoever closes it out, since it rides on both
  subprojects and isn't a `PB-x` runtime milestone).

### Implementation Plan

1. **Collector-side inbound channel (aircraft-layer, fully unit-testable, no DCS needed).**
   `schema/f10_command.py`, `cache.F10CommandQueue`, `collector/f10_command_receiver.py`,
   `api/server.py`'s `GET /f10_commands/poll`, `collector/__main__.py` wiring, `--f10-host`/
   `--f10-port` flags. Tests: receiver (loopback UDP, allowed-token filter, queue bound), API
   endpoint (drain-then-empty). This alone is a runnable, testable increment with nothing to send
   to it yet.

2. **Body-layer consumption (fully unit-testable against fixtures).**
   `aircraft_client.get_f10_commands`, `CrewConsole.tasks` field + `handle_f10_command` + the
   three private handlers + `_nearest_contact_id`, `logger.py`'s `--f10-commands` wiring. Tests
   against a fixed `ContactStore`/`TaskStore`/fake aircraft-layer server — no live DCS. At the end
   of this stage, a developer can `curl -X POST .../f10_commands` (a throwaway manual POST, or a
   tiny debug script) against the running collector and watch `--crew-text --f10-commands` react,
   without DCS in the loop at all — the cheapest possible correctness check before touching Lua.

3. **The Hook script (aircraft-layer, Lua-only, live-DCS-dependent from here on).**
   `petrobrain-f10-commands-hook.lua`: registration snippet (fixed string, three
   `missionCommands.addCommand` calls under one `addSubMenu("Petrovich", nil)`), the drain-and-
   poll loop (1 Hz, gated to run only between `onSimulationStart`/`onSimulationStop` per the
   research doc's explicit fix-forward note), the UDP send to the collector's new port. `luac5.1
   -p` syntax check. `WORKFLOW.md` deploy section + port table entry.

4. **Live acceptance (user-run, per aircraft-layer's established "no automated test for the live
   Hook path" posture).** Deploy the Hook script, restart DCS, fly a mission with the
   `autoexec.cfg` opt-in already in place:
   - Confirm all three F10 → Other → Petrovich items appear and fire (log lines + `--crew-text`
     output/overlay for each).
   - **Paused-mission check** (per aircraft-layer/CLAUDE.md's explicit convention — both the
     export-rate bug and the dropped delta endpoint were caught only by pausing): pause, select
     an F10 item, confirm it either queues correctly and fires on resume, or is cleanly dropped —
     not a crash or a stuck poll.
   - **Mission-restart check**: fly one mission, select each item once, end the mission, start a
     second mission, confirm the menu re-registers and all three still fire (this is exactly what
     the research doc's run 2 already demonstrated for `dostring_in`/`addCommand` in isolation —
     this step confirms the full Hook file, including the drain loop's `onSimulationStart`/
     `onSimulationStop` gating, does the same).
   - **Minimal opt-in check**: try `Config/autoexec.cfg` with only
     `net.allow_dostring_in = { "scripting" }` (no `net.allow_unsafe_api` entries at all) first —
     the research doc's run 2 enabled a superset (`allow_unsafe_api = {"userhooks","gui"}` plus six
     `allow_dostring_in` states) without isolating which entries were load-bearing. If the reduced
     opt-in works, that becomes `WORKFLOW.md`'s documented minimum; if not, fall back to the known-
     working run-2 superset and document that the reduction failed (don't re-attempt narrowing
     indefinitely — one reduced/one full attempt is enough).
   - Confirm `missionCommands.addSubMenu` itself works via the bridge — only `addCommand` was
     live-confirmed by the research doc (Finding 11); this plan is the first thing to call
     `addSubMenu` over `dostring_in`. If it fails, fall back to three flat F10 → Other entries
     (no submenu) — a purely cosmetic, local, reversible change, not a redesign.

### Decisions Made (with reasoning)

1. **Transport: a new dedicated loopback UDP inbound channel (collector listens, Hook sends),
   drain-on-GET, at-most-once.** Not a reuse of Export.lua's TCP line-protocol (that channel is
   tightly bound to the telemetry wire format; repurposing it for a wholly different one-off event
   type adds coupling for no benefit) and not a poll-from-collector-into-Hook scheme (Hook exposes
   no server DCS-side to poll). UDP mirrors the direction and reliability posture this project
   already accepts for `TextOverlaySender` (collector→Hook), just reversed. **Cache shape is a
   bounded FIFO queue, not a single-slot "latest" cache** (unlike every existing aircraft-layer
   cache) — a "latest" slot would let two F10 selections inside one body-layer poll interval
   silently collapse into one, which is a real behavioral loss for discrete commands like "cancel
   task" in a way it isn't for continuously-refreshed telemetry. **Drain-on-GET is at-most-once**:
   if body-layer's HTTP response never arrives after the collector has already cleared its queue,
   those commands are lost, not retried. Accepted as consistent with this project's existing
   fire-and-forget precedent for this class of feature (`/text/push`), and because loopback HTTP
   failure between two local processes is rare; worst case the player re-selects the F10 item. No
   DCS model-time timestamp is attached (the Hook would need extra, unverified mission-scripting
   API access — e.g. `timer.getTime()` — to stamp one; not worth adding an unverified dependency
   for a display-only timestamp), so provenance here is wall-clock-at-receipt only, stated
   explicitly per the project's provenance invariant rather than fabricated.

2. **A new, separate Hook file (`petrobrain-f10-commands-hook.lua`), not an extension of
   `petrobrain-overlay-hook.lua`.** The two files have opposite data directions (overlay:
   collector→Hook UDP receive; F10: Hook→collector UDP send) and different lifecycle triggers
   (overlay: per-frame socket drain only; F10: `onSimulationStart` registration +
   `onSimulationFrame`-gated 1 Hz poll). Multiple Hook files each calling
   `DCS.setUserCallbacks(...)` already coexist in this project without conflict (Export.lua +
   overlay hook + the throwaway probe hook all ran simultaneously during the research session), so
   a second file carries no new risk and keeps each file single-concern, matching the existing
   Export.lua/overlay-hook split.

3. **Command set and menu layout: three fixed tokens under one `addSubMenu("Petrovich", ...)`.**
   Flat entries directly under F10 → Other were considered and rejected — grouping under one
   named submenu is the more DCS-native pattern (matches how AI wingman/mission-add-on commands
   are typically grouped) and costs one extra, well-understood call in the same `missionCommands`
   table already confirmed reachable via the bridge. `addSubMenu` itself is unverified live (see
   Stage 4) — a flat-entry fallback is cheap if it fails. Scoped to exactly the three verbs the
   roadmap backlog item names (watch nearest, scan forward, cancel task) — "etc." in that item is
   read as "the design should make adding a fourth token cheap" (it is: one more literal in the
   Lua registration snippet, one more line in the Python allowed-token constant, one more case in
   `handle_f10_command`'s dispatch table), not as license to invent additional commands now.
   - **"Scan Forward" maps to the raw AI-Wheel trigger (`aircraft_client.trigger_petrovich_search
     ("forward")`), not `tools.scan_area`.** `scan_area`'s full form takes `bearing_deg`/
     `range_m`/`radius_m`/`reason` — real geometry and a real justification an F10 button (no
     argument entry) cannot supply. Fabricating placeholder values for those fields to force a
     `PendingIntent` into existence would be exactly the kind of invented-not-derived body
     behavior the user's brief warns against. The bare trigger is the literal existing capability
     (BL-6's console `scan-area` command already fires this same call as a side effect) with no
     invented parameters.
   - **"Cancel Task" cancels the most recently-created pending `PendingIntent` in the shared
     `TaskStore`**, regardless of source. Because "Scan Forward" (above) deliberately does *not*
     create a `PendingIntent`, and `--crew-text` mode has no other command path that creates one
     either (`scan-area` is `--console`-only), **this item will currently always report "no
     pending task" in `--crew-text --f10-commands` sessions** — flagged in Risks, not hidden. Kept
     in this initial set anyway (rather than dropped) because it's forward-compatible at zero
     cost: it becomes real the moment any future command path creates a `PendingIntent` while
     running in `--crew-text` mode, and the roadmap explicitly names it as a wanted verb.

4. **F10 dispatch reuses `CrewConsole`, not a parallel handler.** `handle_f10_command` is a new
   entry point alongside `handle_line`/`drain_events` on the same `CrewConsole` instance, sharing
   `store`/`enrichment`/`aircraft_client`/`overlay_client`/the new `tasks` field and — critically —
   the same `_print` funnel, so F10 output reaches stdout and the cockpit overlay exactly like
   typed/spoken output does, with no second push/print path to keep in sync. This directly
   satisfies the brief's "reuse the `--crew-text` command path so both inputs share one handler."

### Risks & Unknowns

- **`missionCommands.addSubMenu` over the `dostring_in` bridge is unverified** — only `addCommand`
  was live-confirmed (research Finding 11). Stage 4 must confirm it or fall back to flat entries.
- **Minimal `autoexec.cfg` opt-in is unresolved** (research doc's own "Unresolved" list) — Stage 4
  tests a reduced opt-in once; if it fails, the full run-2 superset is the documented fallback, not
  a search space to keep narrowing.
- **Drain-on-GET is at-most-once** — a command can be silently lost if the HTTP response between
  collector and body-layer fails after the collector has already cleared its queue. Consistent
  with this project's existing tolerance for this class of loss (`/text/push`), but this is the
  first *inbound* channel with that failure shape — BL-6's `/command/petrovich_search` (the other
  inbound-write path) instead raises on failure because the send itself is what can fail, not a
  post-hoc drain race. Worth re-examining if F10 commands ever need to be higher-stakes than they
  are today.
- **"Cancel Task" has no current producer of pending tasks in `--crew-text` mode** (see Decision
  3) — not a bug, but worth being upfront that this menu item does nothing observable until some
  other command path creates a `PendingIntent` while `--crew-text` is running.
- **Token-vocabulary parity between the Lua literal list and the Python `ALLOWED_COMMANDS`
  constant is maintained by hand, not derived from one shared source** — a future edit to one side
  without the other silently drops the new command (Python rejects unknown tokens) rather than
  failing loudly. Low risk at three fixed tokens; worth a code comment pointing each side at the
  other.
- **Re-registration idempotency**: whether calling `missionCommands.addCommand` twice for the same
  label within one mission-scripting-state lifetime duplicates the menu entry or errors is
  untested. Research indicates mission-scripting state resets per mission (re-registration on a
  second mission worked cleanly), so this should only matter if `onSimulationStart` somehow fires
  twice without an intervening mission unload — considered unlikely, but the registration snippet
  should guard with a `PB_F10_REGISTERED` check regardless, cheap insurance.
- **This is now the third consumer of `net.dostring_in`**, a mechanism ED's own docs label
  "OBSOLETE and UNSAFE!!!" (already accepted for BL-2.5 and BL-6). No new risk category, but worth
  restating: if this mechanism is ever removed/changed by ED, all three features break together,
  not just this one.

### Second-Order Effect

This is the first Hook→collector inbound direction in the project (previously every Hook
interaction was collector→Hook display push, or body→aircraft-layer→Export.lua command push); the
queue-drain pattern built here (bounded FIFO cache + drain-on-GET endpoint + allowed-token
validation) is reusable for any future DCS-side player-input signal, not just F10. It also gives
`CrewConsole` a second, non-text input surface alongside typed lines — worth keeping in mind for
BL-10 (real SRS transport): once SRS/PTT input exists, `CrewConsole` will have three entry points
(typed line, SRS transcript, F10 token), which is exactly why this plan adds `handle_f10_command`
as a sibling to `handle_line` rather than special-casing F10 inside it — `_print`/the store/the
overlay wiring stay input-source-agnostic.
