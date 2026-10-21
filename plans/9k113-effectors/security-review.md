## Security Deep Analysis: 9k113-effectors (BL-B66), Stages 1-4 + 4b (one batch)

Reviewed at tip `da1812f62de4a28ed016d52f1b37bbd5fe11cda7` (fast-forwarded cleanly from `b2583b84`,
the pre-review `main`). Scope is computer/network security only, per this role's revised remit
(root `CLAUDE.md`'s "Agents" section, `.claude/agents/security.md`'s "Scope" section, merged
2026-10-21): code execution, machine access, what a LAN port scanner reaches, LLM prompt injection,
dependency/framework risk. Player-experience correctness (switch sequencing, slew behaviour,
calibration accuracy) is the Reviewer's, already covered in `plans/9k113-effectors/review.md`.

### Dependency Status

No dependency change. `git diff main...HEAD -- '*/pyproject.toml'` is empty. Matches
`security-plan-review.md`'s own finding (DCS-BIOS evaluated and kept reference-only, never a
runtime import).

### The one real new surface: `cockpit_switch`, and the user override that governs it

This entry adds the aircraft layer's first **unvalidated-value** write path — `POST
/command/cockpit_switch` → `collector.command_sender.send_cockpit_switch` → loopback UDP →
`Export.lua`'s `handle_cockpit_switch_command` → `GetDevice(device):performClickableAction(cmd,
value)`. The plan review (Mode 1, `security-plan-review.md`) correctly flagged this as a departure
from the subproject's standing "no general-purpose remote-exec surface" invariant and rejected the
plan pending an allow-list. **The user explicitly declined that fix** (`aircraft-layer/CLAUDE.md`,
"What this is": *"Allow any cockpit switch. That gives us much more freedom later and even now
with experimenting. This is LAN only and switch behaviour is limited to DCS."*) — this is a
recorded user decision, not a finding this pass can re-raise, per this role's own memory
(`.claude/agent-memory/security/project_cockpit_write_vocabulary_invariant.md`).

What this pass verified, rather than re-litigating the allow-list:

1. **This is a cockpit-control write, not code execution.** `handle_cockpit_switch_command`
   (`Export.lua` L946-967) only ever reaches `GetDevice(device):performClickableAction(cmd,
   value)` — a DCS clickable-cockpit-action call, the same primitive every other write path in
   this subproject already uses. No `eval`/`loadstring`/`dostring`/`net.dostring_in` is reachable
   from this input; `grep -n "eval(\|exec(\|loadstring\|dostring\|net\.dostring_in"` over
   `Export.lua` and the whole feature diff turns up nothing new. `device`/`cmd` are both forced
   through `math.floor` equality checks (integers only) and `value` is checked for
   non-finiteness (`NaN`/`±inf` rejected) before the call — type-shape validated, as the plan
   review required; only the *value vocabulary* (which device/cmd pairs) is intentionally
   unchecked. A caller can flip any clickable switch in the cockpit; it cannot run code, open a
   file, or reach outside the DCS process. `handle_cockpit_switch_command`'s own call is wrapped in
   `safe_call` (the file's existing `pcall` wrapper), so even an out-of-range `device` id fails
   safely rather than killing the per-frame export loop — the "crash that kills a poll loop" case
   this role's scope specifically names is covered.
2. **The command socket is still loopback-only.** `COMMAND_HOST = "127.0.0.1"`, `COMMAND_PORT =
   7793` (`Export.lua` L174-175), unchanged by this feature — confirmed by `git diff` showing no
   edit to those two lines. Only a process on the same box (the collector) can reach the UDP
   listener `cockpit_switch` ultimately lands on. This matches `security-plan-review.md` finding 5
   and is re-confirmed here at the code, not just read in the review document.
3. **The HTTP endpoint cannot be used for more than a cockpit-control write.**
   `_handle_command_cockpit_switch` (`aircraft-layer/src/api/server.py` L607-665) parses JSON,
   validates `device`/`cmd` as non-bool `int` and `value` as a finite number (checked with
   `math.isfinite`, same non-finite rejection as the Lua side), 400s on anything else, 503s when
   `command_sender` is unconfigured, and forwards exactly `{device, cmd, value}` — no other field
   is read from the request body, and nothing in the handler can be coerced into a different op
   (`op` is not even accepted from the HTTP body; it is hardcoded at the `send_cockpit_switch`
   call site). A caller reaching this port can write any clickable cockpit action and nothing
   else — no file write, no shell command, no arbitrary code path.
4. **Request bodies are read without an upper bound**, same as every other `POST` handler on this
   server (`_handle_text_push`, `_handle_audio_play`, `_handle_command_petrovich_search`,
   `_handle_command_look_direction` all share the identical `length = int(Content-Length); raw_body
   = self.rfile.read(length)` shape with no cap). This is a genuine, if low-severity, instance of
   the "what a LAN port scanner reaches" class this role watches for — a large `Content-Length`
   from a misbehaving/infected LAN box ties up a handler thread/memory before the body is even
   parsed. **Not new to this feature** (`git diff` shows `_handle_command_cockpit_switch` copying
   the existing four handlers' shape verbatim, introducing no new risk beyond extending the count
   from four instances to five) and not blocking on that basis, but worth having a tracked item
   rather than only a prose note — filed as **`AC-B11`**.

### Stage 4b: per-frame slew trace (`Export.lua`) and `--slew-trace` (body-layer)

- `Export.lua`'s `push_slew_trace`/`slew_log_flush` write to a fixed, hardcoded path
  (`lfs.writedir() .. "Logs\\aircraft_layer_slew_trace.log"`) — no externally-influenced path
  component, gated behind its own file-presence flag
  (`Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag`), which only the person with
  filesystem access to that box can create. The logged fields (`t`, `az`, `elev`, `observe`,
  `slew_cmd_az`/`slew_cmd_el`, the latter two always `null` in this entry) are all DCS-internal
  numeric readbacks, never a string sourced from network input or another player — no injection
  surface, LLM or otherwise. A failed `io.open` drops the buffer rather than growing it
  unboundedly (`slew_log_flush`, L329-332) and the buffer itself flushes every 25 lines — bounded
  memory, consistent with the project's existing `detection_trace_writer` shape.
- `body-layer`'s `--slew-trace PATH` (`src/sight_trace_writer.py`) is a CLI argument the operator
  supplies at process launch — not data received over the network — so there is no path-injection
  concern (the "file paths built from received data" item in this role's scope does not apply:
  the path originates from the same trusted operator who starts the process, identically to every
  other `--*-trace`/`--*-log` flag this subproject already has). `SightTraceWriter` disables itself
  after the first write error rather than raising repeatedly (`_fail`), the same fail-quiet-not-
  fail-loud posture `DetectionTraceWriter` already uses — no unbounded retry loop, no crash path.
  Logged row contents (`_row`) are exclusively numeric belief/readback fields — no free text, no
  LLM-reachable content.

### LLM prompt injection

No new text surface reaches a model in this diff. The audio-adapter vocabulary additions
(`audio-adapter/src/vocabulary.py`: "weapons armed"/"weapons on"/"tanks" etc.) are fixed command
tokens matched by `command_matcher.py`'s existing ratio-based matcher against a closed vocabulary,
not free text forwarded to an LLM. `crew_console.py`'s new OBSERV/weapons-safety write-through
speaks fixed template strings (readbacks of DCS switch state), not a model-generated or externally
supplied string. Nothing in this feature adds a new channel for untrusted text to reach a model's
context.

### Verification performed

- Read the full feature diff (`git diff main...HEAD`, 45 files) with focus on
  `Export.lua`, `aircraft-layer/src/api/server.py`, `aircraft-layer/src/collector/command_sender.py`,
  `aircraft-layer/src/schema/cockpit_switch.py`, `body-layer/src/sight_trace_writer.py`.
- `grep` for `eval|exec(|loadstring|dostring|subprocess|os.system|pickle|yaml.load|__import__`
  across every changed `.py`/`.lua` file — no hits.
- Confirmed `COMMAND_HOST`/`COMMAND_PORT` unchanged (loopback) by direct read, not by trusting the
  plan review's account of it.
- Confirmed `handle_cockpit_switch_command`'s shape checks (integer device/cmd, finite value) and
  that `safe_call` wraps the actual `GetDevice` call, so a bad `device` id cannot crash the export
  loop.
- Confirmed no new entry in any `pyproject.toml`.
- Checked `schema/cockpit_switch.py`'s `from_dict` does real `isinstance` type-checking on every
  field rather than trusting the wire — same posture as every other schema in this subproject.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py` L623-624 (and 4 sibling handlers) | Unbounded `Content-Length`-driven `rfile.read` | Pre-existing shape, extended (not newly invented) by this feature's handler; low/low on LAN-only threat model | Filed as `AC-B11`, not blocking |
| `aircraft-layer/dcs-export/Export.lua` L946-967 (`handle_cockpit_switch_command`) | Unvalidated `(device, cmd)` vocabulary — any clickable cockpit action writable | User-overridden standing invariant, recorded decision (`aircraft-layer/CLAUDE.md`) | None — not re-raised per that decision |
| `Export.lua` L303-338 (`SLEW_DEBUG`/`slew_log_flush`) | Local file write, fixed path, flag-gated, bounded buffer | Clean | None |
| `body-layer/src/sight_trace_writer.py` | Operator-supplied CLI path, bounded buffer, disable-on-error | Clean | None |

### Passed to Reviewer

Nothing — `plans/9k113-effectors/review.md` already covers player-facing correctness
(switch-sequencing idempotence, takeoff-edge detection, "Guidance unit ready" spoken-once
behaviour, the review-fix integration tests) and is approved.

### Verdict

APPROVED

No required fixes. The one design departure from this subproject's write-path invariant
(`cockpit_switch`'s missing allow-list) is a recorded, explicit user decision overriding the plan
review's rejection, not an outstanding security gap this pass can reopen. One low/low finding
(`AC-B11`, unbounded request-body read, pre-existing and now on five endpoints instead of four) is
filed to the backlog rather than left in prose, per this role's own closing-step rule.
