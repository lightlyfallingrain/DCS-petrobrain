# Security Review: aircraft-layer (full subproject, static)

Date: 2026-09-26. Reviewed at `main` tip `ace280e` (worktree confirmed fresh
against `main` before starting). User-requested full-subproject review, not a
feature diff — no plan/PR to gate.

**Threat model used throughout:** single-player, single-user, LAN-only,
under active development. No untrusted network, no multi-tenant surface, no
adversary with an account. The findings below are about self-inflicted
damage (to the user's own machine, DCS install, or an in-progress sortie),
not about defending against an attacker — most classic web-vuln categories
(auth, injection from an untrusted party, XSS, CSRF) simply don't apply here
and are not reported as if they did.

**Sandbox honesty note:** this is a static read only. No DCS session and no
Windows box is reachable from here. Anywhere a conclusion needs a live run
to confirm, it's marked as such below rather than asserted.

## 1. The write path into DCS / `net.dostring_in`

**NOTED — no finding, but this is the highest-consequence path and it holds
up.** Read `Export.lua`'s inbound command listener (`COMMAND_PORT` 7793,
`handle_petrovich_search_command`), `petrobrain-f10-commands-hook.lua`, and
`petrobrain-mission-telemetry-hook.lua` in full — these are the only three
places `net.dostring_in` or code otherwise reaches DCS's scripting sandbox
from outside.

- Both Hook scripts' `dostring_in` payloads (`REGISTRATION_CODE`/`POLL_CODE`
  in the F10 script, `VELOCITY_CODE` in the telemetry script) are fixed
  string literals baked in at authoring time, and the file headers say so
  explicitly and correctly — grep confirms no `..` concatenation of any
  runtime value into either script's `dostring_in` argument. This is exactly
  the shape to hunt for (per the task brief) and it isn't present.
- `Export.lua`'s inbound UDP command channel (collector → Export.lua,
  loopback 7793) does not use `dostring_in` at all — it's parsed by
  `extract_json_string_field`, a regex-based field extractor
  (`"field":"([%w_]+)"` — alphanumeric/underscore only) and the result
  (`mode`) is compared against two literal strings (`"forward"`/
  `"boresight"`) before doing anything; an unrecognized value is logged and
  dropped (`handle_petrovich_search_command`, `Export.lua:511-536`). No
  string is ever passed to `loadstring`/`dostring_in`/`os.execute` here.
- The F10 command vocabulary (`ALLOWED_COMMANDS` in
  `f10_command_receiver.py`) is a closed, hand-maintained tuple checked
  before enqueueing (`_handle_datagram`, line 168) — an out-of-vocabulary
  token is dropped, never forwarded to `CrewConsole`.
- The one place free text does reach a DCS-loaded script is
  `petrobrain-overlay-hook.lua`'s `listen()` — but it only calls
  `message_text:addText(decoded.text, ...)`, a display call, never
  `dostring`/`load`/`os.execute`. Text is displayed, not executed.

Conclusion: the "code from the LAN crossing into a Lua interpreter" shape
the brief asked me to hunt for does not exist in this codebase. Every
`dostring_in` call site carries a compile-time-fixed string; every
runtime-derived value that reaches DCS is either a validated enum token or
inert display text.

## 2. The HTTP listener itself

**NOTED — LAN bind is deliberate and documented, not a leftover default.**
`api/server.py`'s `DEFAULT_HOST = "0.0.0.0"` is commented at the point of
definition as "LAN-facing by design, unlike `collector.server.DEFAULT_HOST`"
— this is the opposite of the brain-layer precedent (`run-brain.sh`
defaulting wide when both ends were same-box). Here the LAN bind is the
entire point: this is the hop the Mac/body-layer process polls over the
actual network, per `WORKFLOW.md`. `collector.server.CollectorServer` (the
Export.lua ingest hop) is correctly loopback-only (`127.0.0.1:7790`), and
every other loopback channel (7792 overlay, 7793 command, 7794 F10, 7795
unit-velocity) binds `127.0.0.1` explicitly, both on the Python side and in
each Hook script's `setsockname`. Confirmed by grep across `dcs-export/*.lua`
and `src/collector/*.py` — no channel other than 7791 binds wider than
loopback.

**RECOMMENDED — no request body size cap on the four `POST` handlers.**
`_handle_text_push`/`_handle_command_petrovich_search`/`_handle_audio_play`
all do `length = int(self.headers.get("Content-Length", "0") or "0")` then
`self.rfile.read(length)` unconditionally — a client that sends an
enormous `Content-Length` (or a slow-trickling body of that length) is read
in full before any validation runs, and `_handle_audio_play` additionally
base64-decodes and writes the whole thing to a temp file with no cap.
Under this threat model there's no adversary sending this — the only caller
is body-layer's own client, same LAN, same user — so this is not
exploitable today. It's still worth a cap (e.g. reject `Content-Length`
above a few MB before reading) as cheap insurance against a future
bug on the caller side turning into disk fill (temp WAV files) or a wedged
handler, since `ThreadingHTTPServer` gives each request its own thread but a
single very large read still blocks that thread's turnaround. Not required
given the current caller is trusted and single-purpose.

**NOTED — malformed request handling is fine.** Non-JSON bodies, wrong
types, missing fields, and invalid base64 all get explicit `400`s
(`_handle_text_push`, `_handle_command_petrovich_search`, `_handle_audio_play`
all checked). `ThreadingHTTPServer`/`BaseHTTPRequestHandler` isolate a
malformed request to its own handler thread; no single bad request can take
down the listener.

## 3. Read-only access to the DCS installation

**NOTED — the rule holds.** Grepped every `lfs.writedir()`/`io.open` call
across `dcs-export/*.lua` and every file-path reference in `src/`: all
writes go to `Saved Games\DCS\{Scripts,Logs}\...` (debug flags/logs, the
deployed Hook `.dlg`), never into the DCS install tree (`Program Files`/
wherever DCS is installed). `Saved Games` is user-profile config space, not
the install this project's read-only rule protects — no violation found.
`WORKFLOW.md`'s deploy steps are explicit about exactly what they touch
(`Saved Games\DCS\Scripts\Export.lua`, `...\Scripts\Hooks\*.lua/.dlg`,
`...\Config\autoexec.cfg`) and repeatedly warn against editing the deployed
copy in place or restoring from a stale `.backup` — both are hygiene
properties, not security ones, but they prevent exactly the "partial/failed
deploy leaves DCS in a broken state" failure mode the brief asks about,
since every deploy step is a whole-file copy, not an in-place patch.

## 4. Resource and liveness failures with sortie-scale consequence

**RECOMMENDED — none of the four background daemon threads
(`collector_thread`, `api_thread`, `f10_command_receiver_thread`,
`unit_velocity_receiver_thread` in `collector/__main__.py`) are supervised
or restarted.** This is the precedent named in the task brief (the
watch-reporting review's silent daemon-thread death) and the shape recurs
here structurally, even though I did not find a live bug that currently
triggers it:

- `CollectorServer.serve_forever()` (`collector/server.py:158-172`) wraps
  `_handle_connection` in `try/except OSError`, but the `self._socket.accept()`
  call itself is *not* wrapped. If `accept()` ever raises for a reason other
  than an intentional `close()` (e.g. a transient Windows socket/resource
  error), the whole Export.lua ingest thread dies silently — the process
  keeps running, the `--dump-interval` loop keeps printing "(no sample
  received yet)" or a frozen last sample forever, and there is no
  cockpit-visible symptom and no restart. This is exactly the failure shape
  named in the brief: a dead thread with no in-game symptom, costing the
  rest of a sortie.
- `F10CommandReceiver.serve_forever()` and `UnitVelocityReceiver.
  serve_forever()` both catch `OSError` around `recvfrom()` and treat it as
  a shutdown signal (`return`) — deliberate, since that's how `close()`
  unblocks a pending `recvfrom`. But it means *any* `OSError` from
  `recvfrom()`, not just the intended-shutdown one, silently ends that
  channel for the rest of the process's life with only a log line (no
  `logger.warning`/`error` even — the loop just returns). I did not find a
  live trigger for this beyond `close()` itself (schema parsing is well
  contained — see below), so this is a latent structural gap rather than a
  demonstrated bug.
- Nothing joins or health-checks these threads from the main loop. A future
  bug introduced into `_handle_datagram`/`_handle_line`/`_handle_connection`
  that raises something other than the types currently caught would kill
  that channel's thread permanently and invisibly. Today's handlers are
  well-guarded (see below), so this is defense-in-depth rather than a live
  vulnerability, but it's the same gap that cost a sortie once already on
  this project.

Recommended fix (not urgent, not blocking): wrap each `serve_forever` call
in `__main__.py` with a small supervisor (e.g. log at `ERROR` and note the
channel as dead if the target function returns/raises unexpectedly), or at
minimum log a distinguishing `ERROR`-level line when a receiver loop exits
for any reason other than the process shutting down, so a dead channel
shows up in the collector's own log even if not in the cockpit.

**NOTED — the code these threads run is itself well-guarded against
malformed input**, which is why the above is a structural/latent finding,
not a live one:
- `UnitVelocitySnapshot.from_wire`/`_parse_entry` (`schema/unit_velocity.py`)
  only ever raise `UnitVelocityParseError` (a `ValueError` subclass) for bad
  input — every `int()`/`float()` conversion is wrapped, `rsplit` with a
  fixed count guards against extra colons in a unit name. No unguarded
  exception path found.
- `F10CommandEvent.from_dict`/`_handle_datagram` similarly only raise the
  declared `F10CommandParseError`, and non-JSON/non-dict payloads are
  checked before that.
- `F10CommandQueue` is a bounded `deque(maxlen=64)` — a flood of F10
  selections (malicious or just a stuck Hook script) cannot grow memory
  unboundedly, it silently drops the oldest under load. Reasonable given the
  realistic F10 selection rate (hand-operated, three-click menu).
- `TelemetryCache`/`WorldObjectsCache`/etc. are single-slot "latest" caches
  with no unbounded growth possible.

## 5. Deploys into Saved Games

**NOTED — no finding.** Every Hook script deploy in `WORKFLOW.md` is a
whole-file copy (`Export.lua`, `petrobrain-overlay-hook.lua` +
`.dlg`, `petrobrain-f10-commands-hook.lua`,
`petrobrain-mission-telemetry-hook.lua`) with an explicit warning against
in-place edits of the deployed copy and against restoring from a stale
`.backup`. The `EXPECTED_EXPORT_VERSION`/`EXPORT_SCRIPT_VERSION` mismatch
check (`collector/server.py`) makes a stale deploy loud (a `WARNING` log
line) rather than silently wrong — this is a correctness safeguard that
also limits the blast radius of a partial/forgotten redeploy: DCS still
loads and runs (Hook scripts are independent files, loaded once at DCS
startup, sorted by filename — one stale/missing file doesn't break another).
The `autoexec.cfg` opt-in (`net.allow_dostring_in = { "scripting" }`) is
documented as user-machine-wide and ED-labeled "OBSOLETE and UNSAFE!!!" in
its own docs — `WORKFLOW.md` states this plainly rather than hiding it, and
confines the opt-in to exactly the one state (`"scripting"`) actually
needed, not the broader `allow_unsafe_api` superset an earlier probe run
tried. No credentials, API keys, or auth tokens exist anywhere in this
subproject (matches the "no credentials expected in this phase" framing) —
confirmed by grep for common key/token/secret patterns across `src/` and
`dcs-export/`, nothing found.

## Summary

| # | Finding | Class | Reachable under this threat model? |
|---|---|---|---|
| 1 | `dostring_in` payloads are fixed literals only; no injection path found | — | N/A — confirms the design holds |
| 2 | LAN API bind (`0.0.0.0:7791`) is deliberate, documented, and is the intended cross-machine hop | NOTED | Yes, by design — not a finding |
| 3 | No request-body size cap on `/text/push`, `/command/petrovich_search`, `/audio/play` | RECOMMENDED | Only via the trusted body-layer caller today — no adversary path |
| 4 | No supervision/restart/loud-failure for the 4 background daemon threads | RECOMMENDED | Latent — no live trigger found, but structurally identical to a prior real incident (watch-reporting) |
| 5 | Read-only-install rule and deploy hygiene both hold | NOTED | N/A |

No REQUIRED FIX. Nothing here blocks continued work; the two RECOMMENDED
items are cheap, low-urgency hardening appropriate to "deeper security
effort comes once brain/memory are complete" (root `CLAUDE.md`), not
sortie-blocking defects.
