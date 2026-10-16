# brain-layer security audit — 2026-10-16

Mode 3 full-subproject audit (`[[X-B9]]`'s remaining half — per-module review, findings to a
document, document becomes a backlog item). Target `main` @ `8c30148a`. 7 source files, ~1050
lines in `src/` (`decider.py`, `job.py`, `ollama_client.py`, `prompts.py`, `server.py`,
`brain_layer/__main__.py`, `brain_layer/__init__.py`) plus two assertion-free dev tools under
`tools/`.

**Threat model, stated up front per X-B9's own scoping**: single-user, LAN-only, actively
developed. This is not a hardening audit of a public service, and the "attacker" with the most
access to this process's inputs is the pilot's own microphone — already fully trusted. The real
question this subproject raises is not "can an outsider get in" but "can the one new thing this
project does — accepting model-generated text and acting on it — leak ground truth, dispatch an
unintended action, or silently break the fire-and-forget invariant the whole design serves."

**This subproject has already had two per-feature security deep analyses** (`plans/brain-layer/
security-review.md`, Stage 1 and Stage 2, both immediately-pre-DoD passes under the current
once-per-feature cadence), both read in full before this audit and not reproduced here except
where their status has changed. That is most of what a whole-module pass would otherwise have to
discover from scratch, so this document's job is: confirm what those found still holds, check the
one thing a single-feature diff cannot see (the whole trust boundary at once, read as one piece,
plus the body-side validator this process hands its output to), and say plainly where nothing new
was found.

---

## 1. What was already found, and its current status

| Prior finding | Where | Status now |
|---|---|---|
| `run-brain.sh --host 0.0.0.0` with no justification | Stage 1 review | **Fixed.** `run-scripts/run-brain.sh` passes no `--host`; `server.py`'s `DEFAULT_HOST = "127.0.0.1"` stands, with a dated comment explaining why. Confirmed by reading the live script, not the review's account of it. |
| `_validate_confirm` checked `CONFIRM <token>` against body's *entire* ~30-token dispatchable set rather than the 7-token set the classify prompt actually offers | Stage 2 review, Finding 1 | **Fixed.** `body-layer/src/belief/brain_reply.py`'s `_validate_confirm` now checks membership in **both** `OFFERED_CONFIRM_VOCABULARY` (a hand-synced mirror of `brain-layer/src/prompts.py`'s `CLASSIFY_COMMAND_VOCABULARY`) **and** `dispatched_command_tokens`. A cross-process test (`brain-layer/tests/test_prompts.py::test_offered_confirm_vocabulary_matches_body_layers_mirror`) enforces the two lists stay in sync by reading body-layer's source as text. |
| No byte cap on `response.read()` in `ollama_client.OllamaClient.generate`/`warm_up`, and (pre-existing) `body-layer`'s `brain_client._poll_once` | Stage 2 review, Finding 2 | **Still open.** Confirmed at `brain-layer/src/ollama_client.py:81` — `raw = response.read()`, no size argument. Never filed as a backlog item (checked `todo/backlog/` and `body-layer/ROADMAP/` — no hit). See §3 below; carried forward as a candidate item rather than re-argued, since the Stage 2 review's probability/impact reasoning (operator-trusted local Ollama, no crash path found) still holds and I found nothing to revise in it. |

Both fixed items were confirmed by reading the current code, not by trusting the review's
narrative of them — in keeping with this project's own "verify state, not the account of it" rule.

## 2. What a whole-module read adds that the two feature passes could not

Read as one piece rather than as a diff, the trust boundary is: `body-layer` serialises its own
belief-derived data onto the wire (`belief.brain_client._payload_to_dict`) → `brain-layer` builds a
prompt from it and calls Ollama (`decider.py`, `prompts.py`, `ollama_client.py`) → the model's raw
text is parsed structurally, never raising, never inventing a value outside the regex's capture
groups (`_parse_discriminate_reply`/`_parse_classify_reply`) → the structured reply crosses back
over the wire → `body-layer`'s D10 validator (`belief/brain_reply.py`) re-checks every field
against data `body-layer` itself owns, before anything is dispatched or spoken.

Traced the two invariants root `CLAUDE.md` and `brain-layer/CLAUDE.md` state explicitly:

- **"The model never writes what Petrovich says."** Confirmed structurally, not just by
  docstring claim: `reply.because` (the one field that could carry a quoted fragment of the
  model's own composition, via `PICK <id> BECAUSE <words>`) is read in exactly one place in the
  entire `body-layer` tree — `belief/brain_reply.py`'s own `_validate_pick`, for the
  verbatim-substring check — and nowhere else. `grep -rn "\.because\b" body-layer/src/` outside
  tests returns that one hit. It never reaches `belief.speech`, the overlay feed, the audio
  adapter, or any log line that something downstream parses. `_handle_brain_pick` dispatches by
  `contact_id` alone, through the ordinary `_act`/readback path that already existed before BR-1 —
  the model's wording is used to *validate* a pick, never to *phrase* one.
- **Evidence must appear verbatim in the candidate it picked.** `_validate_pick`
  (`body-layer/src/belief/brain_reply.py:173-200`) does exactly the three substring checks D10
  specifies — in the transcript, in the chosen candidate's own `why`, not in any other candidate's
  `why` — over plain Python strings, nothing templated into a query or a path. `decider._unquote`
  (the one piece of string surgery between the model's raw output and this check) was independently
  re-reviewed for a smuggling bypass at Stage 2 and found to only ever *remove* characters already
  present verbatim in the model's own output, never introduce new content — re-read here and found
  unchanged.
- **The validator's own closed sets are genuinely closed, not just type-closed.** `BrainReply.kind`
  is a `Literal["pick", "ask", "confirm", "unable"]`, enforced at the structural-parse stage
  (`brain_client._reply_from_dict`) before a `BrainReply` can even be constructed with any other
  value — so `validate_brain_reply`'s four-way dispatch has nothing left to reject at its own
  level, by construction rather than by diligence. `VALID_UNABLE_REASONS` is exactly D11's
  three-token set; `OFFERED_CONFIRM_VOCABULARY` is exactly `prompts.py`'s 7-token classify
  vocabulary, kept in sync by a real test rather than a comment (§1 above).

No gap found in either invariant, across the whole module rather than one feature's diff.

## 3. New findings this pass

### 3.1 — `server.py`'s `Content-Length` header is trusted without being validated itself. LOW.

`brain-layer/src/server.py:173-174`:

```python
length = int(self.headers.get("Content-Length", "0") or "0")
raw_body = self.rfile.read(length) if length > 0 else b""
```

A **negative** header value is already harmless here — `if length > 0 else b""` means a negative
`int()` result takes the `b""` branch, never reaching `rfile.read` with a negative count (the
infinite-block failure mode `audio-adapter/src/server.py:137-164`'s own docstring describes and
guards against explicitly). So the one failure mode that sibling fix cares most about does not
apply here.

What *is* missing: a **non-numeric** `Content-Length` (`"abc"`, or any value `int()` rejects)
raises an uncaught `ValueError` straight out of `do_POST`. `ThreadingHTTPServer` isolates this to
the one connection's own thread — it prints a traceback and drops that connection, but does not
crash the process or affect any other in-flight request — so this is a robustness gap, not a
server-down vulnerability: a malformed request gets a stack trace instead of a clean `400`, the
exact distinction `audio-adapter/src/server.py`'s own `_read_body` docstring calls out as the
reason for its own guard ("a malformed request should get a clean `400`, not a traceback").
`brain-layer/tests/test_server.py` has no test for a malformed `Content-Length` header (confirmed
by grep), unlike the coverage that exists on the sibling.

There is also still no upper bound on `length` itself — a caller can request an arbitrarily large
`rfile.read(length)` in one call. Under this project's threat model (loopback by default; the only
realistic caller is `body-layer`'s own `BrainLayerClient`, trusted local code sending small JSON)
this is not exploitable today, and it is the same shape the Stage 1 security review already
weighed and judged not worth a Stage-1-blocking fix once the `0.0.0.0` bind was removed.

**Recommended action:** adopt `audio-adapter/src/server.py`'s `_read_body` pattern verbatim (guard
the header, answer `400` on non-numeric/negative rather than raising, read `rfile` only once the
value is known-safe). Small, local, and brings this server's `Content-Length` handling to parity
with its one HTTP-serving sibling that has already paid for this fix once.

**Probability:** low — requires a malformed request, which today only a misbehaving or
deliberately-adversarial local caller would send; `body-layer`'s real client always sends a correct
header.

**Impact:** low — one dropped connection and a logged traceback, never a process-wide crash
(`ThreadingHTTPServer` isolates per-connection) and never a hang (the `length > 0` guard already
rules out the negative-length block).

Options:
  (A) Ignore — document acceptance of risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — port `audio-adapter`'s guarded `_read_body` into `brain-layer/src/server.py`
  (D) Stop — do not proceed until resolved

### 3.2 — No byte cap on `OllamaClient.generate`'s `response.read()`. LOW. (Carried forward, not new.)

Re-confirmed at `brain-layer/src/ollama_client.py:81`. This is the Stage 2 security review's own
Finding 2, still unaddressed and never filed as a backlog item — it exists only as prose inside
`plans/brain-layer/security-review.md`. Carrying it forward here because this is the mechanism
X-B9 names for exactly this situation ("findings to a document, document becomes a backlog item")
— nothing about the finding itself has changed, and the previous review's probability/impact
reasoning (operator-trusted local Ollama; no crash path found; `num_predict` already bounds the
model's own output to ~40 tokens, so the only way this grows is a wrong-service-on-the-port
misconfiguration, not an attack) still reads correctly on a second look.

Options as previously stated: (A) ignore, (B) backlog, (C) fix now (cap via `Content-Length` or a
bounded `read(max_bytes)`), (D) stop. No new argument for escalating past the original LOW/LOW
rating.

## 4. Explicitly not a problem, checked and ruled out

- **No third-party dependency.** `brain-layer/pyproject.toml` declares `dependencies = []`,
  confirmed by reading the file. Nothing to check against an advisory database; this held at both
  prior passes and still holds.
- **No `eval`/`exec`/`pickle.loads`/`yaml.load`, no `subprocess`, no filesystem writes anywhere in
  `brain-layer/src/`** — confirmed by `/security-grep`'s category hits, scoped to this subproject:
  zero results in "dynamic code execution," "external command / process execution," and "file
  writes / paths" for `brain-layer/src`. Matches the stdlib-only, no-local-persistence design the
  module docstrings describe.
- **No hardcoded credentials** — zero hits for brain-layer in that category; there is nothing in
  this subproject that would hold one (no auth anywhere on this LAN-only seam, by design, matching
  every sibling HTTP surface in this repo).
- **Prompt construction cannot be used to escape the template.** `str.format(transcript=...,
  candidates=...)` substitutes already-built values into the template string; it does not
  re-parse the substituted text for further `{}` placeholders. A transcript or candidate `why`
  string containing literal braces cannot inject additional template fields.
- **Prompt-injection-shaped attacks from the transcript are not a reachable vulnerability under
  this project's threat model.** The pilot's own voice is the only source of `transcript`, and the
  pilot is already fully trusted (single-player, no other party's input reaches this field). Even
  a transcript deliberately worded to manipulate the model can only steer it toward one of
  `PICK`/`ASK`/`CONFIRM`/`UNABLE`, which D10 independently re-validates against body-owned
  candidate/token data before anything is dispatched — this was the Stage 2 review's own
  conclusion and nothing in a whole-module read changes it.
- **`JobSlot`/`ReplyQueue` thread-safety and bounds** — `JobSlot.is_current` is lock-guarded;
  `ReplyQueue` is a bounded `deque(maxlen=64)`. Re-read whole; no race or unbounded-growth path
  found.
- **`_run_job`'s decider-agnostic timeout wrapper** — re-read against `server.py`'s own docstring
  claims; the `ThreadPoolExecutor(max_workers=1)` + `shutdown(wait=False)` pattern does what it
  says (bounds the daemon worker's own wait, cannot forcibly kill a genuinely-hung network call —
  already documented as an accepted, Python-imposed limit, not a gap this pass found new).
- **Module independence holds.** No import crosses the `brain-layer/`↔`body-layer/` boundary in
  either direction in `src/`; the one place `belief.*` is imported from inside `brain-layer/` is
  `tools/live_cross_process_check.py`, a dev script explicitly run under body-layer's own
  interpreter against a real server in a separate process, not an in-process import from the
  runtime. (Confirmed independently here, same conclusion as the Stage 1 review.)
- **The two `tools/` scripts** (`live_cross_process_check.py`, `live_stage2_decider_check.py`) are
  assertion-free dev aids that print numbers for a human to judge, carry no secrets, and make no
  calls beyond the already-reviewed `BrainLayerClient`/HTTP paths.

## 5. Candidate backlog items

- **Guard `brain-layer/src/server.py`'s `Content-Length` parsing** the way
  `audio-adapter/src/server.py`'s `_read_body` already does (§3.1). LOW/LOW; not blocking.
- **Cap `response.read()` in `brain-layer/src/ollama_client.py`'s `OllamaClient.generate`**, and
  while filing it, note the same pattern pre-exists in `body-layer/src/belief/brain_client.py`'s
  `_poll_once` (§3.2, carrying forward the Stage 2 review's own unfiled Finding 2). LOW/LOW; not
  blocking.

## 6. Verdict

**No exploitable vulnerability found.** Both design invariants this subproject exists to protect
— the model never writes what Petrovich says, and a `PICK`'s evidence must appear verbatim in the
candidate it picked — hold structurally across the whole module, not just the paths the two prior
per-feature passes exercised. The two items above are genuine but low-probability/low-impact
robustness gaps, both already weighed once before at the per-feature level and neither changed by
a wider read; they are carried forward as filing candidates per X-B9's own instruction, not as
blockers.
