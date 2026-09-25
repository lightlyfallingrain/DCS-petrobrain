## Security Deep Analysis: brain-layer BR-1 Stage 1

Branch `feature/brain-layer` @ `6e5db7b` (Reviewer: BR-1 Stage 1 review — APPROVED).

**Framing** (per the project's own scoping): single-user, LAN-only, actively developed. This is not
a hardening audit of a public service. This pass exists because Stage 1 introduces something new in
kind for this project — a **listening HTTP server** — where every other subproject so far either
binds to loopback or is a client.

### CVE Status

No new third-party dependencies. `brain-layer/pyproject.toml` declares `dependencies = []`, confirmed
by reading the file directly (not inferred from the plan). `server.py`'s own docstring records that
the implementer considered and rejected FastAPI, following the stdlib-only convention every other
subproject here uses. Nothing to check against an advisory database.

| Package | Version | Advisory | Severity | Affected in This Project |
|---|---|---|---|---|
| — | — | — | — | none added |

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `run-scripts/run-brain.sh` (`--host 0.0.0.0`) | Server bind address | **Real finding, see below.** `server.py`'s own `DEFAULT_HOST = "127.0.0.1"` is loopback, with a docstring explaining why (both brain-layer and Ollama are expected on the same Mac). The run script overrides that default to `0.0.0.0` unconditionally, with no comment justifying it. Per the project's own compute-topology note (root `CLAUDE.md` memory: Mac runs both body-layer and brain-layer; only aircraft-layer↔body-layer crosses the LAN, to Windows), nothing about this seam needs to leave loopback. | Fix — see below |
| `brain-layer/src/server.py` `_handle_escalate` | Request body parsing (malformed/oversized/non-UTF8 JSON, wrong types, missing fields) | Live-probed: malformed JSON, non-dict JSON, non-UTF8 bytes, wrong-typed `utterance_id`, empty body all return clean `400`s; a 5 MB valid payload is accepted and handled without incident; the server stayed responsive throughout and the process never crashed. No unhandled exception path found. | None |
| `brain-layer/src/server.py` (stdlib `ThreadingHTTPServer`) | Concurrency / slow-client blocking | Live-probed: a client that sends a real `Content-Length` header far larger than the bytes it actually sends, then stalls for 6s before closing, does **not** block a concurrent `GET /health` from a second client (measured 10ms). `ThreadingHTTPServer` is thread-per-connection, not single-threaded — correctly ruled out as a concern. | None |
| `brain-layer/src/server.py` `_handle_escalate` (`self.rfile.read(length)`) | Unbounded body read, no size cap | `Content-Length` is trusted with no upper bound; a caller can make the server allocate an arbitrarily large buffer in one `read()` call. On loopback with body-layer as the only real caller, not exploitable — it is trusted local code sending small JSON. **This is the one place where the `0.0.0.0` bind and this gap compound**: bound to all interfaces, any device on the LAN can point a bulk POST (or many concurrent thread-per-connection ones, each blocking on a lying `Content-Length` until its own socket timeout) at this port. Low probability (LAN-only network, no current adversary model), but it is exactly the kind of exposure that has no matching benefit today. | Covered by the `0.0.0.0` fix — see risk note below; no separate code change required for Stage 1's actual (loopback) deployment |
| `brain-layer/src/job.py` `JobSlot`/`ReplyQueue` | Thread-safety, bounded queue | `JobSlot` uses a lock around generation compare-and-check; `ReplyQueue` is a bounded `deque(maxlen=64)`, so a runaway producer cannot grow memory unboundedly. Consistent with `audio-adapter`'s established pattern. | None |
| `body-layer/src/belief/brain_client.py` `_reply_from_dict` | Reply-path structural parsing (injection-surface question) | Every field is type-checked (`isinstance`) before use; unknown `kind` values are rejected (must be one of `pick`/`ask`/`confirm`/`unable`); malformed items are skipped (`None`, not raised) rather than aborting the whole poll. `poll_replies()` further requires the top-level JSON to be a list and skips non-dict items. This is a structural parse only — no semantic validation that a `PICK`'s `contact_id` was actually among the candidates offered, or that `token` is dispatchable — **and that is correctly deferred to Stage 2's D10 validator**, not a Stage 1 gap, because the two places a reply value is actually *acted on* independently re-check it: see next row. | None for Stage 1 |
| `body-layer/src/belief/crew_console.py` `_handle_brain_pick` / `_handle_brain_confirm` | Untrusted-reply-value use | `_handle_brain_pick` re-resolves `contact_id` against the live `ContactStore` via `_find_contact` before acting — an id that doesn't exist (or no longer exists) degrades to "lost him", it is never used to index or act blindly. `_handle_brain_confirm` checks `token` against the `DISPATCHED_COMMAND_TOKENS` allowlist before setting `_pending_confirmation`, rejecting anything else as `NO_SUCH_COMMAND`. Between the structural parse and these two call sites, a malformed or adversarially-shaped reply cannot cause the poll loop to raise, grow memory unboundedly, or cause body-layer to act on an unvalidated contact id or command token — sufficient defense in depth for Stage 1, where the server on the other end is still trusted code (`StubDecider`). | None for Stage 1 — note as context for Stage 2 |
| `body-layer/src/belief/escalation.py` `_situational_header` | What crosses the wire | Independently traced: `situational_header` is exactly `{contact_counts: int, estimated_units: int, our_position?: {x, z}}`. `our_position` is ownship (ok per task framing — localhost, not a leak). No DCS object id, no raw contact/target position, and no ground-truth field anywhere in `EscalationPayload`. `partial_parse.referenced_contact_candidates[].why` traces to `belief.tools.find_contact`'s summary text (confirmed by the module's own docstring and by the `_partial_parse_to_dict` serialiser, which touches no additional fields) — consistent with the Reviewer's own check, confirmed independently for the whole payload rather than just the candidate `why` strings. | None |
| Module independence | Cross-imports between `brain-layer/` and `body-layer/` | Grepped both `src/` trees for imports across the boundary: none. The one place `belief.*` is imported from inside `brain-layer/` is `brain-layer/tools/live_cross_process_check.py`, a dev acceptance script (not part of the `brain_layer` package, not run by the server process) that is explicitly run under **body-layer's** interpreter/`PYTHONPATH` against a real HTTP server in a separate process — it is a manual proof of the HTTP seam, not an in-process import from the runtime. No violation. | None |

### SBOM

Not regenerated — no dependency changes to record (`dependencies = []` confirmed above); the existing
`sbom.json` (if present at repo root) is already current with respect to this branch.

### Verdict

**APPROVED**, with one recommended (not blocking) fix.

### Recommended Fix (not blocking DoD)

**Finding:** `run-scripts/run-brain.sh` passes `--host 0.0.0.0`, overriding `server.py`'s own
loopback default for no recorded reason. Both ends of this seam (brain-layer, body-layer) run on the
same Mac per the project's own compute topology; only the aircraft-layer↔body-layer seam genuinely
crosses the LAN to the Windows box. Binding all interfaces means any device on the user's LAN can
reach `POST /escalate` (queue jobs, force replies to be discarded/overwritten via D3 newest-wins) and
`GET /replies/poll`, and — see the unbounded-body-read row above — can hold open threads with a lying
`Content-Length`. None of this is a serious risk on a home/LAN network with no current adversary
model, but it is exposure with no offsetting benefit.

**Location:** `run-scripts/run-brain.sh`, the `--host 0.0.0.0` argument.

**Probability:** low — requires another device already on the user's LAN and deliberately probing this port.

**Impact:** low — worst case today is queuing bogus `StubDecider` jobs or tying up a few server
threads with slow/lying requests; no ground-truth or credential exposure, no code execution path.

**Recommended action:** drop `--host 0.0.0.0` from `run-scripts/run-brain.sh` and let it fall back to
`server.py`'s own `DEFAULT_HOST = "127.0.0.1"`, matching the documented deployment (both processes on
the Mac). If there's a concrete reason to keep it configurable for a future LAN topology, gate it
behind an explicit opt-in flag rather than making the wide-open bind the run script's default.

Options:
  (A) Ignore — document acceptance of risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — change one line in `run-scripts/run-brain.sh` before DoD
  (D) Stop — do not proceed until resolved

This does not block DoD on its own merits (low probability, low impact, single-user LAN framing) —
surfacing it for the user's decision per this role's standing instruction never to silently accept a
risk.

---

## Security Deep Analysis: brain-layer BR-1 Stage 2

Branch `feature/brain-layer-stage2` @ `cdb8c7f` (Reviewer: BR-1 Stage 2 fold review — APPROVED),
diffed against `6b8a86e`. This is the once-per-whole-feature pass per root `CLAUDE.md`'s "Agents"
section, run after Reviewer, immediately before DoD.

**What changed since the Stage 1 pass above, and why it matters here:** Stage 1 shipped
`StubDecider` — canned replies, no model. Stage 2 adds `OllamaDecider` (`brain-layer/src/decider.py`),
a real local model behind the same wire, called over HTTP by `brain-layer/src/ollama_client.py`,
using two prompts built from live belief state (`brain-layer/src/prompts.py`) and validated on the
body side by a new trust boundary, `body-layer/src/belief/brain_reply.py` (D10). This is the first
place in the whole project where **model-generated text crosses a process boundary and is acted
upon** — the focus of this pass.

### CVE Status

No new third-party dependency. `brain-layer/pyproject.toml` still declares `dependencies = []`,
confirmed by reading the file directly. Ollama itself is external infrastructure (a local daemon
the operator runs, not a package this project vendors or pins a version of) — same posture as
`world-model`'s/`aircraft-layer`'s treatment of DCS itself, not an entry for this table.

| Package | Version | Advisory | Severity | Affected in This Project |
|---|---|---|---|---|
| — | — | — | — | none added |

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/brain_reply.py` `_validate_pick` | D10 trust boundary — `PICK` validation | Attacked directly as untrusted input. `contact_id` must be a key of `candidate_why`, built from `parse.referenced_contact_candidates` — **the original body-side `PartialParse` object held in `_pending_escalations`, never anything deserialised off the wire** — so a model cannot invent a `contact_id` outside what body itself offered. The `BECAUSE` check requires the (lowercased, stripped) words to appear in the transcript **and** the chosen candidate's own `why` **and not** in any other candidate's `why`; all three are plain Python substring tests over body-owned strings, nothing derived from the reply is interpolated into a query, path, or shell command anywhere. Traced `_handle_brain_pick` (`crew_console.py:879`): even after D10 passes a `PICK`, `contact_id` is **re-resolved against the live `ContactStore`** via `_find_contact` before acting — an id for a contact that has since decayed/vanished degrades to "Lost him," never used to index or act blindly. Two independent gates (D10, then a live-store re-check) stand between model output and action. | None |
| `brain-layer/src/decider.py:151` `_unquote` | Quote-stripping added this stage, specifically flagged for smuggling risk | Reviewed for a bypass: strips **exactly one matched pair** of quote characters, and only when the *whole* trimmed string both starts and ends with the same pair — a partial/unbalanced quote (`"T-72" near Gemerek`, missing the closing mark) is left untouched, including its literal quote character, which then fails D10's verbatim-transcript check (the transcript never contains a literal `"` there) and correctly degrades to `ASK`. An empty-after-unquote result (`""`  or `'""'`) is caught upstream by `_validate_pick`'s `not because.strip()` guard. No sequence of quote characters lets `because` end up containing anything not already present, character-for-character, in the model's own raw output — this is a strip, never a rewrite or an injection point. Confirms the fix does what its docstring claims and introduces no new bypass. | None |
| `body-layer/src/belief/brain_reply.py` `_validate_confirm` | D10 trust boundary — `CONFIRM` validation, checked against the **full** `DISPATCHED_COMMAND_TOKENS` rather than the narrower set the model was actually offered | `brain-layer/src/prompts.py`'s `CLASSIFY_COMMAND_VOCABULARY` (7 no-slot tokens) is what `OllamaDecider`'s classify prompt shows the model; `_validate_confirm` instead checks membership in body's *entire* dispatchable set (`crew_console.DISPATCHED_COMMAND_TOKENS`, ~30 tokens including slot-taking ones like `scan_bearing_deg`/`report_bearing_deg`/`follow`, none of which appear in the prompt). A model could therefore hallucinate `CONFIRM scan_bearing_deg` and have it validate, even though that token was never offered. Traced the consequence: `_handle_brain_confirm` calls `_describe_token_for_confirm(token)` with **no slots** (`crew_console.py:873`, single-arg call site) — for a slot-taking token this degrades to the bare literal (e.g. `"scan bearing deg"`, an odd but harmless confirm prompt) rather than raising; if the pilot then affirms, `handle_command(token, now_sim, slots=None)` is documented (`crew_console.py:518-520`) to gracefully degrade any of these slot-taking tokens to a "say again" line rather than misdispatching. **Fails safe** — worst case is a confusing confirm question, never an unintended action — and a human affirmation is still required before anything dispatches. Real gap in defense-in-depth, not exploitable to reach unintended dispatch today. | Recommended, not required — see below |
| `brain-layer/src/decider.py`/`brain_reply.py` — `BECAUSE` evidence has no minimum length | Degenerate-evidence risk | D10's verbatim/discrimination checks are pure substring tests with no length floor; a one- or two-character quoted "evidence" could pass by lexical accident (e.g. a rare letter that happens to appear in only one candidate's `why`) without being genuinely discriminating. Checked where `because` is actually used: grepped all of `body-layer/src/` — it is read **only** inside `brain_reply.py`'s own validation, never passed to `belief.speech` or spoken to the pilot. Worst case is committing to the wrong (but real, currently-tracked) contact among genuinely ambiguous candidates, silently and without the spoken justification ever being exposed — an accuracy/UX risk bounded by the same live-store re-resolution noted above, not a data-exposure or omniscience issue. | Recommended, not required |
| `brain-layer/src/prompts.py`, `brain-layer/src/decider.py` `_discriminate`/`_classify` | Prompt construction from live belief state | Traced every value that reaches a prompt template: `render_discriminate_prompt` takes `transcript` and `[(id, why)]` from `payload["partial_parse"]["referenced_contact_candidates"]`; `render_classify_prompt` takes only `transcript`. Neither prompt, nor anything else `OllamaDecider.decide()` reads from `payload`, touches `situational_header` (`contact_counts`/`estimated_units`/`our_position`) — that field crosses the wire (per Stage 1's own trace) but Stage 2 never reads it. `why` traces to `belief.tools.find_contact`'s summary text (Stage 1's own finding, unchanged this stage) — never a raw DCS object id or ground-truth position. Under this project's stated threat model (single-player, no untrusted network input — the only "attacker" able to shape `transcript` is the pilot's own voice/typed input, already trusted), there is no realistic injection path; and even a hostile transcript can only ever steer the model toward `PICK`/`ASK`/`CONFIRM`/`UNABLE` text that D10 independently re-validates against body-owned data before anything is acted on. | None — reachability is theoretical under this project's own threat model |
| `brain-layer/src/ollama_client.py` `OllamaClient.generate`/`warm_up` | New HTTP client surface — URL handling, timeouts, response parsing, size limits | `base_url` is an operator-set CLI flag (`--ollama-url`, `__main__.py`), not attacker/network-reachable input. Defaults to `127.0.0.1:11434` (loopback), unchanged from Ollama's own default. Response handling: `json.loads` wrapped in `try/except JSONDecodeError`, a `dict`-and-`str`-typed-`"response"` check before use — malformed/wrong-shaped JSON is caught and raised as `OllamaRequestError`, never lets a `KeyError`/`TypeError` propagate. `urlopen(..., timeout=self.timeout_s)` (5.0s) bounds *inactivity* per socket operation, not wall-clock total — a peer that trickles bytes just under the timeout on each `recv` could in principle extend one call past 5.0s (and, compounding, past `server.py`'s own 12.0s outer bound), leaking the one daemon thread `_run_job`'s `ThreadPoolExecutor` can't forcibly kill (documented, accepted tradeoff, `server.py`'s own docstring — this is the "silent daemon-thread death" class of risk this task asked to check for). Reaching this requires either a malicious Ollama (outside this project's threat model — Ollama is trusted local software the operator installed) or a *different* process squatting on the configured port (operator misconfiguration, not attacker-controlled). `response.read()` (both here and in `body-layer/brain_client.py`'s `/replies/poll`, unchanged from Stage 1) has no byte cap — theoretical amplification from the same wrong-service-on-the-port scenario. | Recommended, not required |
| `brain-layer/run-scripts/run-brain.sh`, `brain-layer/src/brain_layer/__main__.py` | Stage 1's loopback fix — still in place after Stage 2's new flags? | Confirmed: `server.py`'s `DEFAULT_HOST` is still `"127.0.0.1"`; `run-brain.sh` still passes no `--host`, and its own comment (dated 2026-09-25, this review) explains why. New flags `--decider`, `--brain-model`, `--ollama-url`, `--decide-timeout-s` add no host/bind surface — `--ollama-url` defaults to loopback and is the *outbound* connection target, not a listener. No regression. | None |
| `brain-layer/src/server.py` `_run_job` | Thread/resource safety under failure — daemon-thread leak on a hung `decide()` | This is the same risk class as the watch-reporting precedent this task named (a silent thread death costing a sortie with no cockpit symptom), but here it is the *opposite* shape: not a silent death, a **silent leak**. Already identified and accepted as a documented tradeoff pre-Stage-2 (`plans/brain-layer/performance-review.md`'s prerequisite 2): `ThreadPoolExecutor(max_workers=1)` per job, `shutdown(wait=False)` on timeout — Python cannot preempt a blocked thread, so a genuinely-hung `decide()` leaks its worker thread permanently. Bounded in practice by `OllamaClient`'s own 5.0s socket timeout (the real fix per that module's docstring), with the caveat immediately above (inactivity-based timeout, not wall-clock). Under repeated pathological hangs (not malicious, just a wedged/misbehaving local Ollama) over a long multi-hour sortie, threads could accumulate — no cockpit-visible symptom, same failure shape as the watch-reporting precedent. Not new to Stage 2's design (the wrapper was added specifically to bound this before Stage 2 shipped `OllamaDecider`), and the underlying constraint (Python can't kill a blocked thread) has no cheap fix beyond what's already there. | Noted — already mitigated as far as practical without a process boundary per decide() call |
| No-omniscience invariant (root `CLAUDE.md`) | Ground truth reaching belief via the model, prompts, candidate summaries, or validator bypass | Traced end to end for this stage's new path: prompts carry only `transcript` + candidate `why` text (body-owned, belief-derived, traced above — never a DCS id/position); the model's structured reply can only select among body-offered ids (`PICK`) or body-owned tokens (`CONFIRM`, modulo the narrower-vocabulary gap noted above, which still can't introduce a *value* body didn't already define); D10 and the live-`ContactStore` re-check both run before anything is acted on or spoken. No path found by which a model's output — however malformed, however "creative" — can cause Petrovich to act on or say something ground-truth-only. Invariant holds for Stage 2. | None |

### SBOM

Not regenerated — no dependency changes to record (`dependencies = []` confirmed above for both
`brain-layer` and unchanged for `body-layer`); the existing `sbom.json` (if present at repo root)
remains current with respect to this branch.

### Verdict

**APPROVED.**

### Recommended Fixes (not blocking DoD)

**Finding 1:** `body-layer/src/belief/brain_reply.py`'s `_validate_confirm` checks a `CONFIRM
<token>` reply against the full `DISPATCHED_COMMAND_TOKENS` set rather than
`brain-layer/src/prompts.py`'s narrower `CLASSIFY_COMMAND_VOCABULARY` — the vocabulary the model
was actually shown. A hallucinated `CONFIRM` naming a slot-taking token outside that vocabulary
(`scan_bearing_deg`, `report_bearing_deg`, `follow`) currently fails safe (an odd confirm prompt,
then a "say again" degrade if affirmed, per `crew_console.py`'s own documented behaviour) rather
than misdispatching, so this is not a required fix — but tightening `_validate_confirm` to check
the offered vocabulary (or explicitly excluding slot-taking tokens) would close the gap between
"what D10 calls legal" and "what the model was actually asked to choose from," which is the same
principle already applied to `PICK`'s candidate-membership check.

**Location:** `body-layer/src/belief/brain_reply.py:126` (`_validate_confirm`).

**Probability:** low — requires the model to hallucinate a token it was never shown, a failure
mode Measurement 4/D6's own findings suggest real 3-4B models do occasionally produce.

**Impact:** low — bounded to a confusing confirm prompt or a "say again" line; no path to
misdispatch found.

Options:
  (A) Ignore — document acceptance of risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — narrow `_validate_confirm`'s membership check to the offered vocabulary
  (D) Stop — do not proceed until resolved

**Finding 2:** No byte cap on `response.read()` in `brain-layer/src/ollama_client.py`'s
`OllamaClient.generate` (new this stage) or `body-layer/src/belief/brain_client.py`'s
`_poll_once` (pre-existing, same pattern). Under this project's threat model — loopback, single
operator, Ollama is trusted local software — this requires a misconfigured `--ollama-url` pointing
at the wrong service to matter at all.

**Location:** `brain-layer/src/ollama_client.py:80` (and, pre-existing,
`body-layer/src/belief/brain_client.py`'s `_poll_once`).

**Probability:** low — requires operator misconfiguration or a compromised local daemon, neither
in scope for this project's stated threat model.

**Impact:** low — memory growth on this one process, no crash path found, no data exposure.

Options:
  (A) Ignore — document acceptance of risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — cap the read (e.g. `Content-Length`-bounded or `read(max_bytes)`)
  (D) Stop — do not proceed until resolved

Neither finding blocks DoD on its own merits (both low probability, low impact, and both fail
safe under this project's actual deployment) — surfacing both for the user's decision per this
role's standing instruction never to silently accept a risk.
