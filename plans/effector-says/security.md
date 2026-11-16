## Security Deep Analysis: effector-says (BL-B119)

### Dependency Status
No dependency change. `*pyproject.toml`/`*requirements*.txt` untouched in this diff — confirmed by
diffing the full commit range.

### Scope
Code commits `5151e837`..`28d97c3d` against `110067d0`, on `feature/effector-says`, fast-forwarded
in this worktree to tip `621baf0d`. Reviewer approved (`plans/effector-says/review.md`, APPROVED,
no required fixes).

### What can reach the spoken text
Traced `petrovich-says` cell text end to end:

- **Single read site**: `body.py:3812`, `load_sequences(sequences_dir, registries_only)` — called
  once, at process startup, against `config/sequences/<aircraft-dir>/*.md`. No other call site in
  `src/` or `tests/`. No network handler, no `GET`/`POST` endpoint, no brain-layer reply, and no
  recognised-voice-transcript path writes or re-reads this field — confirmed by grep across `src/`
  for `petrovich_says`/`EffectorRunState.spoken`: the only readers are
  `effector_sequences.py` (parses it), `effector_engine.py` (formats/reports it),
  `crew_console.py`/`body.py` (the two doc-comment mentions tracing the drain, plus the one actual
  `drain_effector_speech` call), nothing in `tool_api.py`, `brain_client.py`, `brain_reply.py`,
  `escalation.py`, or `mission_memory/`.
- **No LLM-prompt-injection feedback loop.** Since the brain-layer (`tool_api.py`'s `BRAIN_TOOLS`)
  never reads `petrovich_says`/`EffectorRunState.spoken` back as model input (confirmed by the same
  grep), a line that originated in a local config file cannot re-enter the brain's own context as
  if it were new information. This matters because the project *is* building an addressed
  tool-calling brain (BR-2) — the chain simply does not touch this field, so BL-B119 adds no new
  prompt-injection surface, in or out of scope.
- **Conclusion**: only the four local `config/sequences/mi-24p/*.md` files the pilot edits can feed
  `petrovich-says`. Matches the plan's own stated scope exactly.

### Parser's handling of odd cells (`effector_sequences._strip_petrovich_says`)
Read the function and `_parse_tables`'s line-splitting and worked every edge case by hand (not
just by reading — traced the control flow for each):

| input | result | notes |
|---|---|---|
| `"observ on"` | `observ on` | the documented case |
| `` (empty) | `` (empty) | engine's `if row.petrovich_says:` guard treats falsy as silent — no crash |
| whitespace only | `` (empty) | same as above |
| single `"` | `"` (unchanged) | `len(text) >= 2` guard fails, no strip attempted — no `IndexError` |
| `"` then text with no closing quote | first char kept literal | `text[0] == text[-1]` fails, no strip — the stray quote is just spoken |
| very long cell (no cap) | passed through unbounded | see "Low-risk, not filed" below |
| non-ASCII / Unicode | passed through | `str.upper()`/indexing on a Python `str` does not crash on multi-byte/combining characters |
| embedded `\|` | breaks column count, not quoting | `_parse_tables` splits on `|` per physical line — a stray `|` shifts the row to the wrong arity, which the existing 5-cell check already rejects (pre-existing parser behavior, not changed by this diff) |

**No embedded newlines are possible in a cell at all**: `_parse_tables` (`effector_sequences.py:278`)
splits the file with `text.splitlines()` and requires each table row to be one line starting and
ending with `|`. A `petrovich-says` cell therefore cannot smuggle a second "row" or a log-line
break into the speech/log pipeline — ruled out by construction, not by convention.

`effector_engine._speak_text` (the only other function touching this text) is itself guarded:
`if not text: return text` comes before any `text[0]`/`text[-1]` indexing, so every empty-string
path (the only way to reach a zero-length string here, since `_strip_petrovich_says` already
normalises whitespace-only cells to `""`) is handled before any indexing — confirmed no
`IndexError` is reachable, and the single-character case (`text[0].upper() + text[1:]`, then
`text[-1] not in ".!?"`) was traced by hand and does not double-index out of bounds either.

### Does a cell break the speech pipeline, the logs, or the brain's escalation payload?
- **Speech pipeline (`CrewConsole._print`)**: takes a `list[str]`, loops, `print()`s and (if
  configured) pushes to `AudioAdapterClient`/`SpeechWorker` over HTTP — ordinary string payload,
  JSON-encoded by the client (standard-library `json`, which escapes control characters rather than
  choking on them). No new failure mode versus every other line this funnel already carries
  (contact callouts, readbacks already contain pilot/mission-author-influenced text).
- **Logs**: `speech_log_sink` (pre-existing, unmodified by this diff) also JSON-serialises; same
  reasoning.
- **Brain's escalation payload**: confirmed this is not reachable at all — see "What can reach the
  spoken text" above. `escalation.py`'s payload concerns the *player's* utterance being escalated,
  not Petrovich's own effector-confirmation speech; the two never cross.

### The stripping logic
`_strip_petrovich_says` (`effector_sequences.py:200-210`) strips whitespace, then strips exactly one
matching pair of quote characters (`"` or `'`) if the first and last characters match and the
string is at least 2 characters long, then strips whitespace again. No regex (so no catastrophic-
backtracking surface), no recursion, bounded to two passes regardless of input length — O(n) in
cell length. No way to make it loop or blow the stack.

### Gates unchanged
Read `_print`'s own contract and `drain_effector_speech`'s call to it directly, not just the call
site: `drain_effector_speech(now_sim, spoken)` calls `self._print(list(spoken), now_sim)` with no
`bypass_gate` argument (defaults `False`), the same funnel every other command-readback line
already went through before this change (handler return values flow to `_print` the same way).
`self.silenced` still gates whether anything is actually pushed to the audio pipeline; nothing in
this diff touches that gate, `drain_guidance_unit_ready`'s lamp-edge logic, or `_handle_observ_on`'s
synchronous `"Unable, guidance unit not ready."` refusal (confirmed unchanged in the diff — that
branch still returns before `observ_transition` is ever set, never reaching the sequence/engine at
all). No intercom-specific gate (the kind `drain_config_error` has for the SPU-8 banner) applied to
the old hard-coded readbacks either, so none is missing now — confirmed by reading pre-change
`crew_console.py` history for these four handlers, which called `_print`'s normal path
unconditionally on their accepted branch, same as today.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `effector_sequences.py:200` `_strip_petrovich_says` | new string-handling function on parsed config | Bounded, crash-free on every edge case traced above; input is local-file-only | None |
| `effector_engine.py:170` `_speak_text` | string formatting with indexing | Empty-string guard precedes all indexing; traced single-char case | None |
| `crew_console.py` `drain_effector_speech` | new speech-drain call | Goes through the same `_print` funnel/gates as every pre-existing speech line; no bypass | None |
| `body.py` `drain_effector_speech(...)` call | new call site | Unconditional per-poll call, same posture as `drain_config_error`; no new input source | None |

### Verdict
APPROVED

### Required Fixes (if any)
None.

### Low-risk, not filed (intentionally)
**No cap on `petrovich-says` cell length.** A pathologically long cell (tens of thousands of
characters) would pass through unbounded to the TTS push and to logs. Probability: very low — the
only path to this text is the pilot's own four local markdown files, which they write themselves;
there is no remote or LAN-reachable way to alter them within this project's stated threat model
(malicious dependency code, or an infected LAN host port-scanning). Impact if it did happen: a slow
or garbled spoken line and a large log row — no code execution, no path traversal, no crash traced
(see table above). Not filing a backlog ID: fixing it would be effort spent against a threat this
project's own threat model (single-user, LAN-only, config files the user edits) does not include: the
"attacker" would need pre-existing write access to the user's own filesystem, which is already a
total compromise unrelated to this feature.

No other finding from this pass needed a risk-matrix presentation or a backlog ID.
