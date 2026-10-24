## Security + Performance Light Pass: BL-B96 (default crew pipeline)

Light combined pass, authorised because the user waived full separate passes for this change
unless it turned out bigger than small — it did (116 files, 2411 insertions / 6722 deletions,
mostly deletions) — but the shape is a removal, not new risk surface, so a focused pass rather
than two exhaustive ones. Diff: `9ebc4149...6c63719d` (`feature/default-crew-pipeline`, tip
`6c63719d31d56bfa378cb47b709015cdda312023` — verified by `git rev-parse HEAD` after
`git checkout --detach` onto that sha; HEAD was not an ancestor/descendant of this worktree's
pre-existing tip, tree was clean, so detach was the correct path per the dispatching brief).

Reviewed: `plans/default-crew-pipeline/plan.md`, `implementation.md`, `review.md`, and the diff
itself (not taken on either report's word for the specific items below).

### Security

**F10/overlay route removal is clean — no orphaned handler, no stray listener.**

- `aircraft-layer/src/api/server.py`: `do_GET`/`do_POST` no longer dispatch
  `_F10_COMMANDS_POLL_PATH`/`_TEXT_PUSH_PATH`; `_handle_f10_commands_poll`/`_handle_text_push` are
  deleted along with the path constants and the `f10_command_queue`/`text_sender` constructor
  parameters. Confirmed by reading `do_GET`/`do_POST` and `TelemetryAPIServer.__init__` directly,
  not grep alone.
- `aircraft-layer/src/collector/__main__.py`: the `F10CommandReceiver`'s background thread (the
  one inbound loopback-UDP listener this removal takes down) and `TextOverlaySender`'s socket are
  both removed at construction, not just unwired from the API server — no dangling bound port.
  `--f10-host`/`--f10-port`/`--text-overlay-host`/`--text-overlay-port` CLI flags are gone too.
- The four deleted Lua Hook scripts (`petrobrain-f10-commands-hook.lua`,
  `petrobrain-f10-probe-hook.lua`, `petrobrain-overlay-hook.lua`, `petrobrain-overlay.dlg`) have no
  remaining caller: grepped every surviving `.lua` file in `aircraft-layer/dcs-export/` for
  `f10`/`overlay` — every hit is prose (a comment citing the pattern as precedent, e.g.
  `petrobrain-mission-telemetry-hook.lua`'s "same posture as `petrobrain-f10-commands-hook.lua`"),
  never a `dofile`/`require`/`net.dostring_in` reference to the deleted files. `Export.lua` itself
  only mentions "overlay" in a port-numbering comment.
- The one hard constraint the plan named — the `autoexec.cfg` `net.allow_dostring_in` opt-in
  paragraph must survive the F10 Hook's deploy section being deleted — is satisfied:
  `aircraft-layer/WORKFLOW.md` still carries it (lines ~49-60), now under the mission-start Hook's
  own section, not lost with the F10 section.
- `body-layer/src/connection_reporter.py` and `belief/audio_client.py`: log lines are bounded —
  `"%s disconnected (%s)", label, exc` where `exc` is `AudioAdapterError(f"request to {url} failed:
  {exc}")`; `url` is the operator-supplied `--audio-adapter-url` (a LAN address, not a secret) and
  the wrapped exception is `urllib.error.URLError`/`OSError`'s own `str()`, not remote response
  body content — `push_speech`/`get_transcripts` never log the HTTP response body on failure, only
  on a JSON-decode failure do they quote `exc` (a `JSONDecodeError`, not the payload itself). No
  unbounded remote-content logging, no secret leakage found in the touched files.
- `--audio-adapter-url` is a plain required flag with no hardcoded default/credential; the
  `--print-tuning` escape hatch correctly exempts it (checked after the tuning-only early return,
  same posture as `--aircraft-layer-url`).

No security blocker. No finding requires a backlog ID — nothing here is a deferred risk, it is a
removal confirmed complete.

### Performance

**No new hot-path cost from making speech unconditional, with one caveat worth noting but not
blocking.**

- `_poll_transcripts` (speech-input) and `CrewConsole._print`'s `push_speech` call (speech-output)
  both run on the *same* background poll thread that already drives aircraft-layer polling,
  belief `tick()`, and mission-memory — confirmed by reading `_run_crew_text_poll_loop`'s body
  (`_poll_transcripts` is called inline at line ~3567, inside the same `try` block as
  `drain_events`/`drain_brain`/`_mission_memory_step`). This was already true when
  `--speech-input`/`--speech-audio` were opt-in; BL-B96 did not move it to a separate thread, it
  only made the flag-gate (`speech_input_enabled`) always `True` at the one call site in `main()`.
  So the *mechanism* is unchanged — only who hits it by default changed.
- `AudioAdapterClient`'s per-call timeout is `_DEFAULT_TIMEOUT_S = 5.0`s, unchanged by this plan
  and not overridden at the `main()` construction site (`AudioAdapterClient(base_url=args.
  audio_adapter_url)`). Poll cadence defaults to `_DEFAULT_POLL_INTERVAL_S = 1.0`s
  (`_wait_for_next_tick` clamps to "next tick immediately" rather than negative sleep when a poll
  overruns, so a stalled call does not compound into a growing backlog, but it does mean the
  *effective* poll rate degrades to roughly one poll per failed-connect duration while the adapter
  is unreachable, not 1 Hz).
- **Caveat, not a blocker given this project's actual topology:** a true 5s stall per poll only
  materializes against a silently-dropped connection (host unreachable / firewalled with no RST) —
  an `ECONNREFUSED` on a closed port (the realistic "audio-adapter not started yet" case, and
  especially the common same-box `127.0.0.1` case per `audio-adapter/CLAUDE.md`'s `--target local`
  default) returns near-instantly, not after the timeout. The plan's own words call "a developer
  running `body.py` before `audio-adapter`" the new common case — that is exactly the fast-fail
  case, not the slow one. The slow case needs a LAN-reachable-but-non-responding host (process
  running but hung, or a firewall drop rather than a refusal), which is possible on this project's
  Mac/Windows split but not the default dev workflow.
- `ConnectionReporter` itself is O(1) per call (one boolean compare, one log call on transition
  only) — no new cost there, and it correctly fixes the real problem it was built for (log flood),
  not the connect-timeout question, which is a separate axis the plan's Risks section did not
  claim to have addressed.

**Finding, not filed as a blocker — presented per the risk format:**

**Finding:** the audio-adapter poll/push calls share the main perception/belief poll thread with no
per-call timeout shorter than the full 5s default, now exercised unconditionally every poll instead
of only when a user opted in.
**Location:** `body-layer/src/body.py` `_run_crew_text_poll_loop` (`_poll_transcripts` call site,
~line 3567); `body-layer/src/belief/crew_console.py` `CrewConsole._print`'s `push_speech` call
(~line 4442); `AudioAdapterClient._DEFAULT_TIMEOUT_S` in `belief/audio_client.py`.
**Probability:** low in this project's actual topology (same-box `127.0.0.1` target, closed-port
fast-fail) — medium if the audio adapter is ever run cross-machine with a firewall that drops
rather than refuses.
**Impact:** low-medium — a degraded perception/belief tick rate (down from 1 Hz to roughly
once-per-timeout) for as long as the condition holds, self-recovering once the adapter answers or
refuses; never a crash, never silent (the `ConnectionReporter` announces the transition).
**Recommended action:** if this is ever observed in a real sortie (the plan's own "Risks &
Unknowns" already flags this mechanism as unexercised in a live sortie for the aircraft-layer-
reporter reuse), shorten the timeout for this specific always-on path (e.g. 1-2s) or move the
audio-adapter calls off the shared poll thread onto their own — either is a small follow-up, not
a reason to hold this merge.

Options:
  (A) Ignore — accept as documented, re-measure if a sortie shows a stall
  (B) Add to todo.md — a future tuning/threading follow-up
  (C) Fix now — shrink the timeout before merge
  (D) Stop — do not proceed until resolved

Given the light-pass authorisation and that this mechanism (same thread, same 5s timeout) already
existed for the opt-in case and is now just reached by default, this does not block APPROVED — it
is handed to the user as (A)/(B)/(C)/(D) rather than decided unilaterally.

### Verdict

**APPROVED**

No required security or performance fixes. One non-blocking finding above, left to the user's
choice per the Risk Communication Format rather than filed as a backlog item on my own authority —
if the user picks (B), mint a `BL-B` id for it at that point; it is not filed now because the
finding is a "watch for this" rather than a confirmed defect, and the plan's own Risks section
already names the adjacent unexercised-in-sortie concern it would extend.
