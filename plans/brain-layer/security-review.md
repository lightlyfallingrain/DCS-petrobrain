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
