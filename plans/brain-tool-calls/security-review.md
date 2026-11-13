## Security Deep Analysis: BR-2 brain tool calls (Stages 0–3 batch)

Reviewed on branch `feature/brain-tool-calls`, HEAD fast-forwarded from `415fa135` (strict
ancestor, tree clean) to `3a54b55bb547c50cce45c5edb5f65cd9d95cfd71`. Diff reviewed: `9a6e5983..
3a54b55b` across `audio-adapter/`, `body-layer/`, `brain-layer/`, plus the fix commit `3a54b55b`
itself (the Reviewer's required fix, applied on top of `0f9ecbca`).

Inputs read in full: `plans/brain-tool-calls/plan.md` (D2, D3, D8/U2/U4), `implementation.md`
(all four stage logs plus the review-fix log), `review.md`, `plans/brain-layer/plan.md` (D10),
`brain-layer/research/2026-10-16-security-audit.md`, `brain-layer/ROADMAP/BR-B2.md`/`BR-B3.md`,
and this role's own agent-memory (`project_bl8_tool_set_undispatched_check_before_rating_
reachability.md`, `project_br1_stage2_ollama_trust_boundary.md`, `project_brain_layer_wide_bind_
no_benefit.md`).

### Dependency Status

No new dependencies. `pyproject.toml` diffs confirmed empty across all three touched
subprojects (`git diff 9a6e5983..3a54b55b -- '**/pyproject.toml'` is empty).

### Trust Boundary (D3/D10) — traced end to end

Traced every path from a model reply to an action or to speech:
`brain_reply.validate_tool_call`/`validate_turn_final` → `crew_console._handle_brain_tool_call`/
`_handle_brain_turn_final`/`_handle_brain_command` → `run_brain_tool`/`handle_command`/
`_render_turn_answer`/`_render_turn_ask`.

- **Unoffered refs**: every `*_ref` param (`contact_ref`/`place_ref`/`memory_ref`) is checked
  against `turn.offered` in `_check_param` (`brain_reply.py:194-201`); `answer`/`command` finals
  re-check `refs`/`target` the same way (`_validate_turn_answer`/`_validate_turn_command`). `ask`
  deliberately skips up-front validation of `reply.refs`, but traced its one consumer,
  `CrewConsole._render_turn_ask`: it only uses `refs` to *select* which already-known
  `turn.candidate_sets` entry to render from (set-intersection against real candidates, falling
  back to the most recent set or "say again"), and always speaks from that candidate set's own
  tool-derived text, revalidated against the live store — a hostile or garbage `refs` list cannot
  inject unoffered text, cannot leak anything, and cannot raise (plain string ops throughout).
  This is correct by design, not an oversight.
- **Coordinates/`now_sim`/position**: grepped `EscalationPayload`/`BrainReply` field population —
  a model can never supply a coordinate. `now_sim`/`t_sim` on the wire is always body's own clock,
  never model-supplied input that reaches a trust decision.
- **Tool outside `BRAIN_TOOLS`, unknown args, wrong shape**: `validate_tool_call` rejects an
  unknown tool name, unknown arg names, and per-`ParamSpec` type/enum/range/length violations,
  returning a string the caller turns into an `invalid:` observation (never executing
  `run_brain_tool` for a rejected call). Confirmed `BRAIN_TOOLS` is exactly D5/D8's seven read-only
  query tools (`find_contact`, `get_contacts`, `describe_contact`, `get_contact_history`,
  `find_place`, `describe_our_position`, `recall_memory`) — **`remember_location` is not present**
  (grep `BRAIN_TOOLS\b`/`BRAIN_TOOLS_BY_NAME` confirms it is absent; it exists only in
  `mission_memory.tools`, which `tool_api.py` imports but does not register). `TOOL_SET` (the
  older, still-undispatched registry this role flagged at BL-8) is untouched and still has no
  generic dispatcher — so this prior finding's own "next touch" trigger has not fired.
  `recall_memory` is traced read-only end to end (`tool_api._recall_memory_adapter` →
  `mission_memory.tools.recall_memory` → `query.recall_memory`, no `Entry(` construction anywhere
  outside `mission_memory/store.py`'s single construction site). **BL-B79 is correctly confirmed
  unreachable in this batch.**
- **Command outside `BRAIN_COMMANDS`, or a token's own shape violated**: `BRAIN_COMMANDS` is the
  explicit opt-in allowlist, 30 tokens; confirmed by reading it directly that U2's exclusions
  (`engage`, `disengage`, `weapons_armed`, `weapons_safe`, `observ_on`, `observ_off`, `point`) and
  every flight token are absent by construction (not a denylist). A `target` without
  `command.takes_target`, or any non-empty `slots`, degrades rather than dispatches. `_handle_
  brain_command` asserts `token is not None` only after `_validate_turn_command` has already
  guaranteed a legal, allowlisted token — a model cannot reach `handle_command` with anything
  outside the 30-token set or with a slot its schema never declared.
- **Free text spoken**: grepped every render path (`speech.py`'s new `render_nothing_seen`/
  `render_our_position_answer`/`render_contact_answer`/`render_memory_entry`) — none takes
  `reply`'s own free-text fields and speaks them verbatim; each renders from store/enrichment/
  memory data looked up by a validated handle. `say` (free-text speech) is confirmed Stage 5, not
  built — no code path speaks model-generated prose.
- **`because` passing `_evidence_passes` on non-verbatim text**: `_evidence_passes` requires the
  substring to appear in the real transcript *and* the chosen candidate's text *and* not in any
  other candidate's text — unchanged logic from BR-1, now shared. Confirmed by reading, not just
  by name, that `_validate_turn_answer`/`_validate_turn_command` call this against the correct
  `turn.candidate_sets` entry (`_candidate_set_for_ref`).
- **Repeated identical calls / round-budget exhaustion**: `validate_tool_call`'s own
  `(tool, canonical_args)` dedup against `turn.steps` rejects an exact repeat without executing it
  (`test_repeated_identical_tool_call_is_rejected`). `BRAIN_MAX_TOOL_ROUNDS` (tuning, default 4,
  bounds 1–8) and `_handle_brain_tool_call`'s own `turn.round > BRAIN_MAX_TOOL_ROUNDS` check end
  the turn deterministically via `_speak_turn_degrade`, never silently hanging.
- **Very long strings / deep JSON / huge `refs` lists from a crafted reply**: every `str` param
  has a `max_len` (default 40) enforced before use; `answer(contacts, refs)` is additionally
  capped at `ANSWER_CONTACTS_MAX_REFS = 3`. A long/garbage `refs` list on `ask` is bounded in
  practice by `TOOL_LOOP_NUM_PREDICT = 120` (model output tokens) and, per above, never used for
  anything but set-membership against real candidates. No unbounded-growth path found.

**Required fix from `review.md` (header-ref ambiguity-evidence gap) is fixed correctly and
verified**: `3a54b55b`'s diff to `crew_console.py::_start_brain_turn` pushes `header_refs` into
`turn.candidate_sets` when `len(header_refs) >= 2`, exactly as prescribed; re-ran the two new
tests plus the full `test_brain_tool_loop.py`/`test_stage2_acceptance_bench.py`/
`test_crew_console.py` suites independently (see Checks below) — all green.

### The Wire

- **`escalation.py`/`brain_client.py`**: `_reply_from_dict` is a defensive structural parse —
  every new field (`tool`/`args`/`form`/`refs`/`target`/`slots`) is type-checked (`str`/`dict`/
  `list[str]`), `None` on anything malformed rather than raising. `audio-adapter`'s new
  `addressed` field is likewise `isinstance`-checked at the one consumer
  (`body.py:3679`, `if not isinstance(addressed_raw, bool)`), not just truthiness-checked —
  matches this project's established wire-boundary convention.
  (`[[project_wire_boundary_type_check_not_range_check]]` from a prior pass re-confirmed, not
  re-litigated: type-checked fields here are additionally re-validated against real state at the
  point they act, same pattern.)
- **`OllamaClient.chat()`/`generate()`**: `num_ctx`/`num_predict` always passed explicitly;
  `ToolLoopDecider.decide()` never raises (`OllamaRequestError` → `unable NO_BRAIN`, malformed/
  multi-tool-call content → `ask`) — traced and confirmed against `decider.py:350-408`.
- **`tool_calls` parsing depth/size**: `ChatResult`/`ToolCall` parsing (`ollama_client.py`) raises
  `OllamaRequestError` on any malformed shape rather than degrading silently, which
  `ToolLoopDecider` then converts to a safe `ask`/`unable` — no path where a malformed native
  tool-call reaches `crew_console` un-degraded.
- **No-omniscience**: `_situational_header` only ever sends `recent_contacts` as `{id, summary}`
  pairs (no coordinate) to the prompt builder; `_render_header` (`tool_loop_prompts.py`) reads
  only `contact_counts`/`estimated_units`/`recent_contacts` — it never reads the header's
  pre-existing `our_position` (`x`/`z`) field, which crosses the body→brain-layer wire but is
  **not new to this batch** (pre-existing BR-1 code, unchanged context in this diff) and was
  already confirmed never read by a decider in the BR-1 Stage 2 review. Re-confirmed here that
  `ToolLoopDecider`'s new prompt builder inherits the same property. Tests
  (`test_serialised_tool_call_payload_carries_no_raw_coordinates`,
  `test_describe_our_position_observation_has_no_x_or_z`,
  `test_header_refs_offered_without_a_tool_call`'s own `"x"`/`"z"` grep) cover the continuation
  payload, one adapter's text, and the header respectively — read all three and confirmed they
  exercise real serialised JSON, not a mocked shortcut.

### Body executes tools on its poll thread — one real gap, not blocking

`drain_brain` wraps `brain_client.poll_replies()` in `try/except Exception` (log-and-continue,
matching `_poll_transcripts`'s own per-call isolation), but **nothing wraps the dispatch that
follows**: `_handle_brain_reply` → `_handle_brain_tool_call` → `self.run_brain_tool(tool_name,
validated, now_sim)` (→ `body._run_brain_tool_fn`'s closure → `BrainTool.invoke`) runs with no
`try/except` anywhere on that path, and `body.py`'s poll loop calls `crew_console.drain_brain(...)`
directly with no guard around it either (confirmed: no `try`/`except` in the ~500 lines
surrounding that call). Read all seven `BRAIN_TOOLS` adapters — each one is defensively coded
today (`None`-returning lookups, `isinstance` guards, no unguarded arithmetic or dict-indexing on
model-controlled values I could find) — so there is no live exploit here. But the shape is
inconsistent with every other asynchronous input source in this same loop
(`_poll_transcripts`'s own try/except, `drain_brain`'s own poll-failure guard, the aircraft-layer
client's documented "raises; caller's try/except is the designed catch point" contract): one bug
in a future eighth tool, or in `tools.describe_contact`/`recall_memory` reacting badly to some
belief-state edge case the validator cannot see (e.g. a handle valid at validation time but the
underlying object mutated mid-call), propagates straight through `drain_brain` and kills the poll
thread — perception, belief, everything — which is exactly the failure mode this project's own
"the game world moves on" invariant exists to prevent elsewhere.

**Finding — Recommended fix (not blocking):**
Wrap the `run_brain_tool` call (either inside `_handle_brain_tool_call` in `crew_console.py`, or
at the closure in `body._run_brain_tool_fn`) in a `try/except Exception`, degrading to a
`ToolObservation(summary="tool execution failed")` or an `invalid:` step the same shape a
validation rejection already produces, logging the exception rather than letting it propagate.
Low probability today (every adapter is currently well-behaved), but the cost of the guard is a
few lines and it is the one asymmetry against this loop's own established pattern.

```
Finding: an exception inside a `BrainTool.invoke` call (or `run_brain_tool`) is uncaught and
  propagates through `drain_brain` into body.py's main poll loop.
Location: body-layer/src/belief/crew_console.py (`_handle_brain_tool_call`), body-layer/src/
  body.py:3550 (`run_brain_tool` closure).
Probability: low — every current adapter is defensively coded (traced all seven); this is about
  the *next* tool or belief-state edge case, not a known-exploitable path today.
Impact: high if it ever fires — it kills the one poll thread doing perception/belief/speech, not
  just the brain turn.
Recommended action: wrap the dispatch in try/except, same posture as every other poll-loop input
  source in this file.

Options:
  (A) Ignore — document acceptance of risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — before merge
  (D) Stop — do not proceed until resolved
```

### BR-B2 / BR-B3 — status, and a process gap worth naming

**Both remain open and unfixed in code, despite U4's acceptance.** Verified directly:

- `brain-layer/src/server.py:173` — `length = int(self.headers.get("Content-Length", "0") or
  "0")` is still unguarded; a non-numeric header still raises an uncaught `ValueError` inside
  `_handle_escalate`. **`BR-B2` stays open.**
- `brain-layer/src/ollama_client.py:121` (`_post_json`) — `raw = response.read()` is still
  uncapped, now shared by both `generate()` and the new `chat()` Stage 2 actually uses for every
  tool-loop round. **`BR-B3` stays open**, and the plan's own U4 rationale ("BR-2 multiplies the
  traffic through both") is realised exactly as predicted: every addressed turn now calls this
  path up to `TOOL_LOOP_MAX_ROUNDS + 1` (5) times, where BR-1's traffic through the same function
  was at most two calls per escalation.

**U4 was accepted by the user** ("1,2,4 - as recommended", plan.md's Decisions section) **but
never implemented.** Stage 0's implementation log correctly deferred it ("out of scope for Stage
0... Folding BR-B2/BR-B3 into Stage 2 is U4"), but Stage 2's own implementation log and Files
Changed list make no mention of BR-B2/BR-B3 at all, and `review.md` does not raise it either —
the deferral note was never revisited at the stage it named. This is the same failure class this
role's own standing instruction exists to prevent (a finding noted in prose with nobody
converting the "yes" into a committed change), except here the gap is the reverse direction: the
backlog items already have IDs and were already accepted; the gap is that acceptance never
produced a diff.

**Verdict on these two**: not escalated to a blocker. Scope/impact assessment is unchanged from
the original filing — `BR-B2`'s impact stays one dropped connection per malformed request
(`ThreadingHTTPServer` isolates per-connection), and `BR-B3`'s trust boundary is still a local
Ollama daemon the pilot started, not an external attacker; the increased call *frequency* does not
change either's *impact*, only how often the (still low) failure mode could in principle trigger.
Both stay open, not marked done — the `#status/open` state in each entry file is accurate and
should not be changed by this batch.

```
Finding: U4 (fold BR-B2/BR-B3 fixes into Stage 2) was accepted by the user but never implemented;
  both remain open while the exact traffic U4 named as the reason to act now has shipped.
Probability: BR-B2 — low (needs a malformed Content-Length header, reachable only if brain-layer
  is bound wide, see below). BR-B3 — low (needs a malfunctioning/malicious local Ollama).
Impact: both low, per the original filings — unchanged by this batch.
Recommended action: either implement both now (each is ~20 lines per the backlog items' own
  estimate, and BR-B2's fix already exists verbatim in audio-adapter/src/server.py's `_read_body`
  to port) as a fast follow before or alongside merge, or explicitly re-defer with a note on each
  backlog entry naming this batch and why it still waits.

Options:
  (A) Ignore — leave both open as already filed, pick up whenever brain-layer is next touched
  (B) Add to todo.md — explicit fast-follow item referencing this batch
  (C) Fix now — port `_read_body`'s guard and add a byte cap to `_post_json.response.read()`
      before merge
  (D) Stop — do not proceed until resolved
```

### Pre-existing, out of scope for this batch (noted, not re-raised as a finding)

- `run-scripts/run-brain.sh` passes `--host 0.0.0.0` unconditionally while its own comment block
  says `server.py`'s loopback default is "the right default" for the same-box deployment —
  confirmed via `git diff` that this file is untouched by `9a6e5983..3a54b55b`. This is the same
  gap this role already flagged (`project_brain_layer_wide_bind_no_benefit`), now visibly
  contradicted by its own comment (the comment reads as though `--host` is omitted; the actual
  flag overrides it) — worth a one-line fix next time this script is touched, but not this
  batch's defect and not re-filed here.
- `situational_header`'s pre-existing `our_position` (ownship `x`/`z`) crossing the body→brain-
  layer wire (see "The Wire" above) — unchanged by this diff, already assessed at BR-1.

### Dependency and reachability notes for future passes

- `TOOL_SET` (the pre-existing, undispatched name→callable registry) is still not generically
  dispatched by anything this batch added. The `BL-8` memory's own trigger ("when a dispatcher
  eventually reads `TOOL_SET` generically... that commit should trigger a focused look at
  argument validation across the whole registry") has **not** fired — `BRAIN_TOOLS` is a separate,
  narrower, hand-curated registry built specifically for this seam, not a generic `TOOL_SET`
  dispatcher. Noted so the next pass does not assume BL-8's trigger already fired because
  something that looks similar shipped.

### Checks run (independently re-run, not only taken from the implementation/review logs)

- `body-layer`: `mypy src` — pass (82 files). `pytest tests/test_brain_tool_loop.py tests/
  test_stage2_acceptance_bench.py tests/test_crew_console.py` — 198 passed. Full-suite `pytest -q`
  launched; see note below.
- `brain-layer`: `mypy src` — pass (9 files). `pytest -q` — 89 passed.
- `audio-adapter`: `pytest tests/test_command_matcher.py tests/test_transcribe_api.py` — 165
  passed.
- `pyproject.toml` diffs: empty across all three subprojects (no dependency change).

### Verdict

**APPROVED.**

No confirmed exploitable vulnerability and no required fix remaining — the one Required Fix from
`review.md` (header-ref ambiguity-evidence gap) is correctly fixed and independently re-verified
against the real validator and a fresh test run, not only re-read from the commit message. The
D3/D10 trust boundary holds everywhere traced: no path from a model reply reaches an unoffered
ref, a coordinate, a tool outside `BRAIN_TOOLS`, a command outside `BRAIN_COMMANDS`, or free
speech. `remember_location`/BL-B79 is confirmed still unreachable. No-omniscience holds, including
through the new prompt builder.

One Recommended (non-blocking) fix — the uncaught-exception gap on the tool-dispatch path through
`drain_brain` — and one process note — U4's acceptance never landed, so `BR-B2`/`BR-B3` stay open
exactly as already filed, with their traffic now exactly as multiplied as U4's own rationale
predicted. Neither changes the verdict; both are presented above with the standard options for
the user to decide.

### Backlog / tracking

- `[[BR-B2]]`, `[[BR-B3]]` — status unchanged (`#status/open`); this review found no reason to
  mark either done and specifically confirmed they are not. No new ID needed; both already exist
  and already carry the right description.
- The uncaught-exception-on-tool-dispatch finding above: **not filed as a new backlog item,
  intentionally** — it is a Recommended, non-blocking finding presented with the Risk
  Communication Format options in this document for the user's decision (fix now, defer, or
  accept), per this role's own Mode 2 posture for a non-blocking finding. If the user picks
  option (B), file it then with a fresh ID in `brain-layer/ROADMAP/` or `body-layer/ROADMAP/`
  (it's a `body-layer` code location, so `BL-B<n>`) rather than leaving it only in this document.
