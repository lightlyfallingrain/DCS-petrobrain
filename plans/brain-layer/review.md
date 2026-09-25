### Review Summary

Reviewed `feature/brain-layer` at `d6b537b` — BR-1 Stage 1 (the async round trip proven with no
model). Scope: new `brain-layer/` subproject plus body-layer's escalation/reply/revalidation
wiring. Focus per the task brief: the three-way merge-conflict resolution done by the orchestrator,
D4 staleness revalidation, D3 newest-wins, D11's structural/judgement split, module independence,
and graceful degradation when the brain is absent/slow/wedged. Test counts, lint/type-check
results, and the cross-process live check were already established and are not re-verified here.

**All six focus areas check out; no required fixes.**

- **Merge resolution 1 (`logger.py`)** — confirmed by reading the merged file directly:
  `crew_console.drain_brain(runner.last_t_sim)` sits inside the `try:` block, after
  `drain_events`, before the `except Exception: logger.exception(...)` guard closes
  (`body-layer/src/logger.py:1146-1195`). A brain-reply exception is caught by the same
  log-and-continue guard as everything else in the poll body; it cannot silently kill the thread.
- **Merge resolution 2 (`voice_commands.py`)** — `PendingConfirmation.bearing_degrees` is fully
  gone; every remaining `bearing_degrees` occurrence in the branch is a `slots["bearing_degrees"]`
  dict-key access (`crew_console.py`), not a reference to the retired field. `contact_pick` and
  `slots` coexist as documented, mutually exclusive, both committed correctly (`_handle_brain_ask`
  sets `contact_pick`; the voice confirm path sets `slots`). Confirmed nothing on the branch still
  expects the old field.
- **Merge resolution 3 (`crew_console.py` import conflict)** — both `render_*` families import
  cleanly from `belief.speech` (13 names, including the four new ones); no collision, no
  duplicate/shadowed name.
- **D4 staleness revalidation** — `_handle_brain_reply`/`_handle_brain_pick`/`_handle_brain_ask`
  implement the plan's table exactly: age check first (`BRAIN_REPLY_MAX_AGE_S`, discard silently);
  `pick`+present → act; `pick`+gone → "lost him"; `ask`+≥2 survivors → ask; `ask`+1 survivor →
  confirm via the new `PendingConfirmation.contact_pick` field, never a silent act; `ask`+0 → "lost
  him". The candidate list revalidated is `parse.referenced_contact_candidates` — the payload's
  *original* offered list — not anything the reply itself claims, exactly as D4 specifies ("acting
  on a contact id that has since been merged into another contact" is structurally impossible: the
  id is checked against the live store at drain time via `_find_contact`, not trusted from the
  reply). Verified with a direct test read
  (`test_drain_brain_pick_contact_deleted_during_delay_yields_lost_him`) that deletes the contact
  between escalation and reply and asserts "lost him," not silent action.
- **D3 newest-wins** — `brain-layer/src/job.py`'s `JobSlot` is a generation counter, not a queue;
  a superseded worker's `decide()` is allowed to finish but its result is dropped at
  `is_current()` immediately before publish (`server.py:_run_job`), proven end-to-end over real
  HTTP by `test_superseded_job_reply_is_discarded_not_delivered`. Client-side, `BrainLayerClient`
  mirrors this with its own single-slot overwrite. The `awaiting_reply_to`-matches-current-question
  exception is **honestly not implemented** — `job.py`'s own docstring says so explicitly and
  correctly notes nothing in Stage 1 ever sets `awaiting_reply_to` on an outgoing payload, so
  building the exception now would be untestable dead code. This is the right call, not a gap:
  `awaiting_reply_id()` never returns non-`None` from this client in Stage 1, so the exception
  path is unreachable by construction until Stage 3 wires it.
- **D11 structural reasons** — `structural_unable_reason` lives in `brain-layer/src/decider.py`
  as a pure, decider-agnostic function: empty `referenced_contact_candidates` → `NO_MATCH`,
  `matched_intent is None` → `NO_SUCH_COMMAND`, both read directly off the wire payload with no
  model/decider consultation. `StubDecider.decide` calls it before falling back to a bare `ASK`.
  Correctly excludes `NO_LINE_OF_SIGHT` (needs a world-model LOS call this process has no access
  to; nothing in Stage 1 emits a place-directed command that would need it) — documented, not
  silently dropped.
- **Module independence** — grepped the whole branch: no `belief`/`body` import anywhere under
  `brain-layer/src`; no `brain_layer`/`decider`/`job` import anywhere under `body-layer/src`.
  `brain-layer/pyproject.toml` declares `dependencies = []`, confirmed by direct read. `server.py`
  is stdlib `http.server.ThreadingHTTPServer`, a structural copy of `audio-adapter/src/server.py`,
  with its own docstring explaining the deliberate FastAPI refusal — matches every other
  subproject's zero-dependency convention and the project's "new dependency is escalation-worthy"
  rule. The plan's own affected-files table names FastAPI in one line with no Decision backing it;
  the implementer's choice to follow existing convention instead, and to document the deviation
  from the plan's own file table, is the correct call.
- **Absence/slow/wedged brain (D7)** — `handle()` never blocks (hands off to a background worker,
  returns in microseconds) and never raises (catches `URLError`/`OSError`, logs, continues) —
  confirmed by direct read of `brain_client.py`. `poll_replies()` raises `BrainLayerError` on
  transport failure, but `CrewConsole.drain_brain` wraps the call in a bare `except Exception` and
  logs-and-continues, matching the existing `_poll_f10_commands`/`_poll_transcripts` division. A
  wedged (accepts-but-never-responds) brain bounds the escalate POST to 0.5 s on the *background*
  worker thread (never touches the poll thread) and bounds `poll_replies()`'s synchronous GET to a
  5.0 s timeout on the poll thread itself — that is a real, if bounded, stall on the crew-text poll
  thread, but it is not a new risk: it is the identical default (`_DEFAULT_TIMEOUT_S = 5.0`)
  `belief/audio_client.py` already uses for its own synchronous transcript poll, so this mirrors
  existing precedent rather than introducing a new failure mode. Worth remembering if `brain-layer`
  turns out to hang under load in practice (see Optional Refinements).
- **Provenance of what crosses the wire** — `_partial_parse_to_dict`'s candidate serialisation is
  `{"id": candidate.id, "why": candidate.why}`; traced `why` back to `belief/utterance.py`'s
  `_result_to_reference_candidates` (`why=str(result["summary"])`), which is `belief.tools.
  find_contact`'s rendered summary text, not a raw DCS object id or truth-derived position. `id` is
  body's own belief-store contact id (already an existing cross-boundary identifier convention in
  this codebase), not a DCS object id. Confirms the plan's own flagged risk does not materialize.
- **D10 validator's deliberate absence** — confirmed correct rather than a gap: Stage 1's wire is
  structured JSON built directly by `StubDecider` (plain code, nothing to parse), not a model's raw
  one-line text — there is genuinely no free-text step for D10 to validate yet. `brain_client.py`'s
  `_reply_from_dict` does a defensive *structural* (type/shape) parse of untrusted cross-process
  JSON and returns `None` (skip) rather than raising on anything malformed — correctly distinguished
  in its own docstring from D10's future *semantic* validator, and does the right thing for
  Stage 1's actual risk (a malformed/hostile-shaped reply must not raise into the poll loop).

### Required Fixes

None.

### Optional Refinements

- `poll_replies()`'s 5.0 s timeout can stall the crew-text poll thread for up to 5 s if
  `brain-layer` accepts the TCP connection but never responds. This exactly mirrors
  `audio_client.py`'s existing default, so it is not a regression introduced by this slice — but
  the brain is a new third process with a documented "third process to start, one more thing that
  can be down" risk, and unlike the escalate POST (bounded to 0.5 s on a background thread), this
  bound lands on the same thread that drives perception. Worth watching during Stage 4's live
  sortie; if it ever proves to matter in practice, tightening `_POLL_TIMEOUT_S` or moving the poll
  itself off the perception thread would be a cheap, local fix later. (Optional — not a Stage 1
  blocker, consistent with existing precedent.)
- `brain-layer/src/job.py`'s docstring explaining the deferred `awaiting_reply_to` exception is
  good practice worth repeating for Stage 3's implementer: the comment makes it easy to find and
  wire in without re-deriving the reasoning.

### Verdict

APPROVED

### Review Confidence

Full read — plan.md (D1-D11, full), implementation.md (implementer's own log, full), and every file
in the "Where to spend the review" list read directly from the merged branch tip
(`logger.py`'s poll loop, `voice_commands.py` in full, `crew_console.py`'s escalation/D4/D8/D9
methods, `escalation.py` in full, `decider.py` in full, `job.py` in full, `server.py` in full,
`brain_client.py` in full, the new `speech.py` render functions, `utterance.py`'s
`ReferenceCandidate`/`why` construction, `tools.py`'s `find_contact`, `pyproject.toml`, and targeted
greps for cross-subproject imports and `bearing_degrees`/TODO/debug-print residue). Two of the six
Stage 1 acceptance tests read in full and confirmed non-vacuous. Test counts, ruff/mypy results, and
the cross-process live check were already established per the task brief and not re-run.

---

## Stage 2 review — `OllamaDecider`, D10 validator, the two non-blocking prerequisites

**Commit reviewed:** `35e6de0` (`feature/brain-layer-stage2`), diffed against its parent `6b8a86e`.
Scope: `OllamaDecider` (`brain-layer/src/decider.py`), the two prompt shapes (`prompts.py`), a
stdlib Ollama HTTP client (`ollama_client.py`), D10's validator (`body-layer/src/belief/
brain_reply.py`, new), and the two pre-Stage-2 prerequisites from `performance-review.md`
(`poll_replies()` off the shared poll thread; `Decider.decide()` under its own bounded timeout).

### 1. The non-blocking invariant — holds structurally

Read `brain_client.py`, `server.py`, `crew_console.py`'s `drain_brain`, and re-ran the client- and
console-level wedge tests directly (see Verification below). Findings:

- **`poll_replies()` no longer touches the network on the caller's thread.** It now starts a
  persistent background thread lazily on first call; that thread loops `GET /replies/poll` forever
  into an internal buffer (`_poll_loop`/`_poll_once`), sleeping `_POLL_LOOP_INTERVAL_S` (0.2 s)
  between healthy rounds and `_POLL_RETRY_BACKOFF_S` (1.0 s) after a failure. `poll_replies()`
  itself only drains that buffer under a lock — microseconds, regardless of whether the far side is
  healthy, down, or wedged. This is exactly the fix the performance review asked for (mirror
  `handle()`'s own shape), not a partial mitigation.
- **`Decider.decide()` runs under its own bounded timeout** (`server.py`'s `_run_job`, a throwaway
  single-worker `ThreadPoolExecutor` bounded by `DEFAULT_DECIDE_TIMEOUT_S`, 12.0 s,
  `shutdown(wait=False)`). Correctly documented as a decider-agnostic backstop, not the primary
  fix — the primary fix is `OllamaClient`'s own `urllib` timeout (5.0 s, `DEFAULT_TIMEOUT_S`),
  which is what makes `decide()` actually return. Both bounds sit entirely on the already-detached
  per-`/escalate` daemon worker thread — `POST /escalate` itself still responds `202` before any of
  this runs, unchanged from Stage 1, confirmed by re-reading `_handle_escalate` (submits to
  `JobSlot`, starts the worker, responds immediately — no join).
- **A genuinely-hung `decide()` call still leaks one thread permanently** (`ThreadPoolExecutor`'s
  own worker, abandoned via `shutdown(wait=False)`, since Python cannot preempt a blocked thread).
  This is explicitly documented in three places (`server.py`'s docstring, `brain-layer/CLAUDE.md`,
  implementation.md's "Notable Discoveries") as an accepted, bounded residual risk contingent on
  `OllamaDecider`'s own 5 s timeout actually firing — not hidden. Given the plan's own framing
  (`decide_timeout_s` is "bounded, not tuned... Stage 4 is where real-sortie numbers replace every
  constant like this one"), this is proportionate for the stage, not a gap to hold up Stage 2 over.
- **Queues stay bounded.** `brain-layer`'s `ReplyQueue` is `deque(maxlen=64)` (unchanged from
  Stage 1); the client-side `_poll_buffer` is unbounded in principle but drained at least once per
  0.2 s and holds "almost always 0-1 items" per its own docstring — verified by reading `_poll_loop`
  (every iteration appends then immediately would be drained by the next `poll_replies()` call on
  the crew-text thread, itself called once per ~1 s poll tick).
- Re-ran `test_drain_brain_tick_rate_unaffected_by_a_wedged_brain` and
  `test_poll_replies_tick_rate_unaffected_by_a_wedged_server` directly against a real raw-socket
  TCP-accept-then-never-answer listener (not mocked) — both pass, 20 ticks against a wedge complete
  in well under 1 s total, down from the pre-fix 5015 ms *per call*. This is a real, not merely
  claimed, verification of the invariant the whole stage exists to protect.

**Verdict on this axis: the invariant holds, both prerequisites are genuinely fixed (not just
timeout-value tweaks), and the one remaining gap (a permanently-hung call leaking one thread) is
correctly scoped as "mitigated, not eliminated" rather than misrepresented as solved.**

### 2. D10 validator — correctly implements the spec, but has a real gap the plan's own worked
   example does not exercise

`belief/brain_reply.py` implements all six D10 rules faithfully, including the "must not be equally
true of another candidate" rule as a literal-substring check against both the chosen and every
other candidate's `why` text. `test_wrong_pick_because_tank_degrades_to_ask` is present, matches the
plan's own worked example exactly, and passes (confirmed by direct run — see Verification).

**Required-fix-level finding: a `BECAUSE` clause the model wraps in literal quotation marks breaks
the verbatim check, converting a genuinely correct `PICK` into a spurious `ASK`.** The
`DISCRIMINATE_PROMPT` instructs the model, in plain English, to *"quote those words verbatim"* —
a phrasing that plausibly invites a literal `"…"` in the reply, and `brain-layer/tests/
test_decider.py::test_ollama_decider_candidates_present_calls_discriminate_prompt` already exercises
exactly this: it scripts the fake Ollama server to answer `PICK CONTACT_7 BECAUSE "near Gemerek"`
and asserts the parsed `because` is `'"near Gemerek"'` — quote characters included — as the
*expected*, correct output of `_parse_discriminate_reply`. Neither `_parse_discriminate_reply` nor
`brain_reply._validate_pick` strips surrounding quote characters before the substring check. Traced
end to end (reproduced directly, not just read):

```
_parse_discriminate_reply('PICK CONTACT_7 BECAUSE "near Gemerek"')
  -> {'kind': 'pick', 'contact_id': 'CONTACT_7', 'because': '"near Gemerek"'}

validate_brain_reply(BrainReply(..., because='"near Gemerek"'), parse,
                      "keep an eye on the tank near Gemerek", tokens)
  -> BrainReply(kind='ask', ...)   # degraded — should have passed through as a correct PICK
```

The transcript and the candidate's own `why` text both contain `near Gemerek` (no quotes) — a human
or a careful model reading the prompt's own `Candidates:` block (which contains no quote marks
anywhere) would reasonably reproduce the phrase either with or without wrapping quotation marks, and
only one of those two reproductions currently validates. This is not a hypothetical: a fix for
precisely this class of defect (unquoting `BECAUSE` evidence) exists in this repository's git
history under commit `bee408b` ("Unquote the model's BECAUSE evidence, and stop it quoting whole
sentences") — but that commit is **not an ancestor of `35e6de0`** (confirmed via `git merge-base
--is-ancestor`), so it is not part of what is being reviewed here and this defect is live on this
branch. Given D6's own finding that small-model accuracy is sensitive to exactly this kind of
formatting variance, and that this failure mode fails *safe* (a correct pick degrades to an honest
`ASK`, never a wrong pick) rather than unsafe, this does not violate the no-omniscience invariant —
but it directly undercuts the stage's own acceptance criterion ("ask is rendered... a required test
is the safety net's only proof") by making the validator reject legitimate evidence on a coin-flip
of the model's punctuation habits, which will read as Petrovich asking far more than the design
intends.

**Recommended fix:** strip a single matching pair of leading/trailing quote characters (`"`, `'`,
and possibly typographic quotes `"`/`"`) from `because` in `_parse_discriminate_reply` (syntactic,
brain-layer side) and/or normalize in `brain_reply._validate_pick` before the substring checks
(semantic, body-layer side — the more defensive location, since it is the actual trust boundary).
Add a regression test that pipes a quote-wrapped `OllamaDecider` response through
`validate_brain_reply` end to end (the two existing test suites currently only exercise each half in
isolation — `test_decider.py` tests parsing, `test_brain_reply.py` tests validation, and neither
tests the composition with a quoted value, which is exactly how this gap survived).

### 3. D11's `NO_SUCH_COMMAND` routing — independent read agrees with the implementer's own flag

D11's text is genuinely self-contradictory taken literally: "no resolved verb *is* `NO_SUCH_
COMMAND`... **neither needs asking**" reads as fully structural, but the plan's own scope item 2
("plausibly a command the deterministic grammar missed" → `Confirm <command>?`) and Stage 2's own
acceptance line ("confirm work[s] for real") both require a live model judgement call to ever
produce a real `CONFIRM` for an unmatched verb. Taken at face value, D11 would make scope item 2
unsatisfiable.

The implementation's resolution — treat `structural_unable_reason`'s own "usually" (not "always")
as the seam, route `NO_SUCH_COMMAND` to the **classify** prompt (a `CONFIRM <token>`/`UNABLE`
judgement call) while keeping `NO_MATCH` (empty candidate list) fully structural with no model
call — is the only reading that satisfies both texts simultaneously, and it is the one already
flagged, in the same terms, in `implementation.md`'s own "Notable Discoveries." Independently
checked against the no-omniscience/code-owns-truth invariant: the model is not given free rein
here. It can only ever emit `CONFIRM <token>` for a token drawn from `CLASSIFY_COMMAND_VOCABULARY`
(and even that is re-validated body-side against the full `DISPATCHED_COMMAND_TOKENS`, see §4
below) or `UNABLE` — it is classifying free speech against a closed, code-owned vocabulary, exactly
the shape D5 defines as the model's one legitimate job ("mapping free speech onto a closed intent
set the regex table... could not match. That is interpretation, and it is the whole value"). It
does not get to decide *that* `NO_SUCH_COMMAND` is the right category (code already decided that,
structurally); it only gets to decide whether one specific narrow vocabulary word applies. No
invariant violation.

**This is correctly a SUGGESTION, not a required fix**: get the user/architect's explicit sign-off
that this reading of D11 is the intended one before Stage 4's live sortie, since it is a genuine
interpretive call on ambiguous plan text rather than a settled decision — but the code itself does
the right, and only workable, thing.

### 4. `CLASSIFY_COMMAND_VOCABULARY` — confirmed accuracy-only, not safety

Traced the full path: `prompts.CLASSIFY_COMMAND_VOCABULARY` (7 tokens, no slot parameters) is only
ever used to build the prompt text offered to the model. The reply is validated by
`crew_console.CrewConsole._handle_brain_reply` → `validate_brain_reply(..., DISPATCHED_COMMAND_
TOKENS)` — the **full** body-owned token set (`crew_console.DISPATCHED_COMMAND_TOKENS`, ~30+
tokens), not the narrower classify vocabulary. A model cannot get a token dispatched merely by
naming something outside `CLASSIFY_COMMAND_VOCABULARY` (it was never offered that as an option to
begin with), and the narrower list changes only what the model *can plausibly return*, never what
the validator *will accept* — confirmed by reading, not just by the docstring's own claim. Narrowing
the vocabulary can only ever cause a missed `CONFIRM` (degrading to `UNABLE`), never an
incorrectly-dispatched command. Accuracy-only, as documented.

### 5. Scope — clean

`belief/tools.py`, `belief/tool_api.py`, and everything under `perception/` are absent from the
diff (confirmed via `git diff --stat`). No new tool, no change to the tool-freeze. `belief/
voice_commands.py` is also untouched in this stage (Stage 1's `contact_pick` extension stands
unmodified). The A/B answer leg (`awaiting_reply_id`/`awaiting_reply_to`'s consumption) is not
wired — Stage 3 remains unbuilt, as scoped.

### Verification (re-run directly, not taken on the implementer's word)

Built a throwaway venv and ran every command both subprojects' own `CLAUDE.md` "Commands" sections
specify, from this worktree, against the actual Stage 2 tree:

- `brain-layer/`: `ruff format --check` — 11 files already formatted. `ruff check` — all checks
  passed. `cd brain-layer && mypy src` — success, 7 source files. `pytest brain-layer/tests -q` —
  **35 passed**, matching implementation.md's own reported count exactly.
- `body-layer/`: `ruff format --check` — 111 files already formatted. `ruff check` — all checks
  passed. `cd body-layer && mypy src` — success, 52 source files. `pytest body-layer/tests -q` —
  **1288 passed, 4 xfailed**. (Note: this worktree's baseline at the parent commit `6b8a86e` is
  1275 passed/4 xfailed, not the `1139` implementation.md cites — that figure was Stage 1's own
  baseline from an earlier point in the branch's history; several intervening commits on this
  branch since Stage 1 added tests unrelated to this stage. The stage's own net addition, +13
  passing over its actual parent, is smaller than the diff's ~30 new/changed test bodies because
  several Stage 1 tests were *rewritten in place* — e.g. the two `PICK`-carrying tests fixed to
  carry a D10-valid `BECAUSE`, correctly attributed in "Notable Discoveries" — not purely additive.
  Zero regressions either way, confirmed by running, not inferred.)
- Also independently reproduced the wedge scenario at the socket level (a raw `socket` that accepts
  and never answers) against both `BrainLayerClient.poll_replies()` and `CrewConsole.drain_brain`,
  and reproduced the quote-character defect in §2 directly against the installed code (not merely
  read) — see the transcript in that section.

**On the live-Ollama gap:** the fakes (real loopback HTTP servers, not mocked `urllib`) are faithful
for what they test — transport semantics, timeout behaviour, JSON shape, `stream: false`/explicit
`num_ctx`/`num_predict` — and that is genuinely the bulk of Stage 2's own risk surface (the
non-blocking invariant). They cannot and do not validate real model behaviour against the actual
prompts, and §2's finding is the concrete proof of why that gap matters: it is exactly the kind of
defect (a model's own natural completion habit interacting with a hand-written parser) that a fake
server scripted by the implementer will not surface unless the implementer specifically thinks to
script that response — which is a knowledge problem, not a sandbox-access problem, and would not
have been fixed by live Ollama access alone. A live smoke test before Stage 4's sortie remains
worth doing (already flagged by the implementer), but is not what would have caught §2 fastest —
a wider set of adversarial scripted responses in `test_decider.py`/`test_brain_reply.py` would have.

### Required Fixes

- **Strip quote characters from a `PICK ... BECAUSE <words>` reply's evidence before D10's
  verbatim-quote check**, in `_parse_discriminate_reply` (`brain-layer/src/decider.py`) and/or
  `brain_reply._validate_pick` (`body-layer/src/belief/brain_reply.py`) — a model that follows the
  `DISCRIMINATE_PROMPT`'s own "quote... verbatim" instruction by literally wrapping its answer in
  quotation marks currently has a correct `PICK` spuriously degraded to `ASK`. Add a test that pipes
  a quote-wrapped model response through the full `OllamaDecider` → `validate_brain_reply` path
  (see §2).

### Optional Refinements

- Get explicit user/architect sign-off on the `NO_SUCH_COMMAND` → classify-prompt reading of D11
  before Stage 4's live sortie (§3) — the code's behaviour is correct and the only reading that
  satisfies the plan's own scope item 2, but it resolves a genuine textual contradiction in D11 that
  the plan itself never settled explicitly.
- A live Ollama smoke test (`--decider ollama` against `qwen3:4b-instruct-2507-q4_K_M`) before
  Stage 4, as implementation.md already flags — not because the fakes are unfaithful to HTTP
  behaviour, but because only a real model's actual completions (quoting habits, whitespace,
  incidental chattiness) will surface the next defect in this same family as §2.
- `executor.shutdown(wait=False)` in `server.py`'s `_run_job` leaves one abandoned
  `ThreadPoolExecutor` worker thread per genuinely-hung `decide()` call that ignores its own
  `OllamaClient` timeout entirely (documented, accepted risk — Python cannot preempt a blocked
  thread). Worth a coarse ceiling (e.g. refuse new escalations, or log loudly, past N concurrently
  abandoned workers) only if Stage 4's live sortie ever shows Ollama actually wedging past its own
  5 s `urllib` timeout — no evidence that happens today, so not worth building preemptively.

### Verdict

**APPROVED WITH MINOR FIXES** — one required fix (§2, the `BECAUSE` quote-stripping gap), narrow
and mechanical to apply, with an existing precedent fix in the repository's own history to draw
from. Everything else — the non-blocking invariant, the D10 validator's structure, the D11 routing
judgement call, the vocabulary-narrowing safety boundary, and scope — is sound.

### Review Confidence

Full read of every file touched by the `35e6de0` diff (`decider.py`, `prompts.py`,
`ollama_client.py`, `server.py`, `brain_client.py`, `brain_reply.py`, `crew_console.py`'s diff,
`__main__.py`, both `CLAUDE.md` updates, `implementation.md`'s Stage 2 sections in full) plus a
re-read of `plan.md`'s D1-D11 and Stage 2 section. Not a spot check: every check command in both
subprojects' `CLAUDE.md` "Commands" sections was re-run directly against the actual Stage 2 tree
(not taken from implementation.md), and the §2 defect was reproduced by direct execution, not
inferred from reading. The one acknowledged gap is a live-Ollama smoke test, which no reviewer in
this sandbox can perform (network access to a live Ollama daemon is denied here exactly as it was
for the implementer) — flagged as an optional refinement, not silently skipped.

---

## Stage 2 fold review

Reviewed `e3fce0e` ("Fold br1-stage2 into brain-layer-stage2: fix the BECAUSE quoting defect") and
`8253fba` (implementer memory), diffed against `dc0fa08` (the Stage 2 review this fold answers).
This is a review of a change made in response to a review, per `AGENTS.md`'s rule that such fixes
get the same reading as the code they patch.

### Required Fixes

None.

### Findings (all check out)

- **The required fix is fixed, and at the right layer.** `decider._unquote`/`_QUOTE_PAIRS` strip
  exactly one matched surrounding quote pair (straight or typographic) from `PICK ... BECAUSE
  <words>`'s evidence before it ever reaches `_parse_discriminate_reply`'s return dict — read in
  full (`brain-layer/src/decider.py`). Checked for bypass and over-eager stripping directly against
  `_PICK_BECAUSE_RE = r"^\s*PICK\s+(\S+)\s+BECAUSE\s+(.+?)\s*$"` (no `re.MULTILINE`, so a reply with
  any leading/trailing prose outside the one line fails the match entirely and degrades to `ASK` —
  consistent with the new "EXACTLY ONE line" prompt instruction, not a hole the fix has to cover).
  Mismatched-type quoting (opens `"`, closes `'`) and unbalanced quoting are both deliberately left
  unstripped for D10 to reject, per the function's own docstring and confirmed by
  `test_unquote_leaves_an_unbalanced_quote_alone`/`test_unquote_leaves_a_mid_string_quote_alone` —
  a quote genuinely part of the evidence (mid-string) is preserved. No reply shape found that
  bypasses the fix while still reaching D10 as a `pick`.
- **The composition-test split closes the gap, and does so by transitivity across three already-
  covered links, not by two isolated assertions.** Traced the whole chain a real reply travels:
  (1) `decider.decide()` (the actual entrypoint `server.py` calls, not a private helper) is asserted
  end-to-end in `brain-layer/tests/test_decider.py::test_ollama_decider_candidates_present_calls_discriminate_prompt`
  to return `because: "near Gemerek"` (unquoted) for a fake model reply of `BECAUSE "near Gemerek"`;
  (2) the dict→JSON→`BrainLayerClient._reply_from_dict` passthrough is exercised, unmodified by this
  fold, in `body-layer/tests/test_brain_client.py` (`because: "near Gemerek"` in, same value on the
  resulting `BrainReply`); (3) the new
  `test_pick_because_survives_the_exact_quoting_a_real_model_produces` proves that exact value
  passes `validate_brain_reply`. Each link uses the real production function, not a re-implementation
  standing in for it, so a future edit that reopens the seam (e.g. `decide()` stops calling
  `_unquote`, or `_reply_from_dict` starts mangling the field) breaks one of these three tests rather
  than passing silently. The one gap this doesn't close: no single automated test runs the full wire
  path with an actual JSON-over-HTTP round trip through `server.py` for a quoted reply (only the
  manual, assertion-free `live_stage2_decider_check.py` tool does that) — worth noting as an optional
  refinement, not a blocker, since transitivity across three real-function tests already gives most
  of the same guarantee module independence allows without a cross-subproject import.
- **Prompt changes push in the safe direction, checked against D5 and D6.** `DISCRIMINATE_PROMPT`'s
  narrowed BECAUSE instruction ("quote ONLY the single distinguishing word or short phrase... NEVER
  quote the whole sentence") and the added "EXACTLY ONE line, nothing else, no explanation" sentence
  on both prompts constrain the model further rather than inviting the deliberation D6 measured
  (a "think step by step" instruction produced 575 tokens and a wrong pick). `test_prompts.py`'s
  `test_render_discriminate_prompt_includes_transcript_and_candidates` explicitly asserts `"step by
  step" not in prompt.lower()`. No conflict with D5 (model classifies against a closed set, never
  writes what Petrovich says): traced `BrainReply.because` — it is consumed only inside
  `belief/brain_reply.py`'s validator (`because = reply.because`), never rendered as crew speech;
  nothing in this fold routes free model text to the player.
- **The two deliberate fold omissions are correctly justified.** The older branch's poll-timeout
  shortening (`3fc8dc1`, 5.0s → 0.5s on `BrainLayerClient.poll_replies()`) fixed a real risk in that
  branch's architecture, where `poll_replies()` ran synchronously on the shared crew-text poll
  thread. Read `body-layer/src/belief/brain_client.py` on this branch directly: `poll_replies()`
  starts a lazy background `_poll_worker` thread on first call and the synchronous call only ever
  drains an in-memory buffer — confirmed structurally different, and confirmed by
  `test_poll_replies_tick_rate_unaffected_by_a_wedged_server` (20 calls against a real wedged raw
  socket, `elapsed < 1.0`) that the crew-text thread never touches the wedge. This architecture
  predates the fold commit (untouched by `dc0fa08..e3fce0e`), so "genuinely redundant" holds. The
  wider `CLASSIFY_COMMAND_VOCABULARY` (older branch: ~30 scan/report-bearing tokens vs. this
  branch's smaller set) is confirmed to be additional phrasing recognized for the same
  `structural_unable_reason`/`CONFIRM` mechanics, not a new code path or a widened safety surface —
  an accuracy-only scope decision, correctly left out per the commit message.
- **The non-blocking invariant is untouched and re-verified against real listeners, not mocks.**
  Reran both raw-socket wedge tests directly:
  `body-layer/tests/test_brain_client.py::test_poll_replies_tick_rate_unaffected_by_a_wedged_server`
  (client level, built on a hand-rolled `socket`-based `_WedgedServer` that accepts and never reads/
  writes, explicitly *not* `http.server` "so no HTTP-level machinery can accidentally answer the
  request") and
  `body-layer/tests/test_crew_console.py::test_drain_brain_tick_rate_unaffected_by_a_wedged_brain`
  (`CrewConsole.drain_brain` level) — both pass. `test_brain_reply.py::test_wrong_pick_because_tank_degrades_to_ask`
  also passes, confirming D10's wrong-evidence rejection still works after the unquoting change (i.e.
  the fix didn't also loosen the verbatim/specificity check itself, only removed the quote-character
  false negative).
- **No Stage 3 leakage.** Grepped `plans/brain-layer/implementation.md`'s new content — the only
  `Stage 3`/`awaiting_reply` mention is a docstring cross-reference, no code. `git diff --stat
  dc0fa08..e3fce0e` confirms `belief/tools.py`, `belief/tool_api.py`, and `perception/` are untouched.

### Test counts and checks (re-run directly, not trusted from the commit message)

Re-ran both subprojects' full command sets against a `git archive` snapshot of `e3fce0e` in a fresh
scratch tree with fresh venvs (this worktree is `main`-based, not on `feature/brain-layer-stage2` —
see the "worktree-main-based-pytest-pythonpath-trap" memory; ambient checkout state was not trusted):

- brain-layer: `ruff format --check` clean, `ruff check` clean, `mypy src` (`cd brain-layer`) clean,
  `pytest tests -q` → **44 passed**. Matches the claimed 35 → 44.
- body-layer: `ruff format --check` clean, `ruff check` clean, `mypy src` clean, `pytest tests -q` →
  **1289 passed, 4 xfailed**. Matches the claimed 1288 → 1289 / 4 xfailed unchanged.

Both subprojects' numbers match the commit message's claims exactly; no discrepancy found.

### Optional Refinements

- No single automated test exercises the full JSON-over-HTTP wire path (`decider.decide()` →
  `server.py` response → `BrainLayerClient` → `BrainReply` → `validate_brain_reply`) for a quoted
  reply in one run — only the three-link transitive coverage above, plus the manual
  `live_stage2_decider_check.py` tool. Given module independence forbids a cross-subproject test
  import, this is likely as close as this project's conventions allow without a new mechanism (e.g.
  a shared JSON fixture file both suites load) — not asking for one now, just naming the residual gap
  for whoever next touches this seam.

### Verdict

APPROVED

### Review Confidence

Full read of the diff (`decider.py`, `prompts.py`, all four touched/added test files, the new
`live_stage2_decider_check.py` tool's docstring, `implementation.md`'s new content) plus direct reads
of `brain_client.py` and `crew_console.py`'s `drain_brain` to confirm the background-thread
architecture claim. Both subprojects' full format/lint/type/test command sets re-run from scratch
(fresh venvs, `git archive` snapshot of `e3fce0e`, not the ambient worktree checkout) and matched
against the commit's claimed numbers exactly. The three wedge/regression tests named in the task
brief re-run individually and confirmed passing against real sockets, not mocks. Not independently
re-run: the older branch's own historical CI state (trusted via direct diff read against `bee408b`
and `3fc8dc1` instead).

---

### Review Summary — `d51a25b`, the Security/Performance change-request fold

Reviewed `d51a25b` ("BR-1: close CONFIRM's offered-vocabulary gap; give the live check a
chain-drop scenario") diffed against parent `c1b96b1`, per `AGENTS.md`'s rule that a Security/
Performance change request re-enters the Implementer → Reviewer loop rather than going straight to
DoD. Two changes: (1) `belief/brain_reply.py` gains `OFFERED_CONFIRM_VOCABULARY`, narrowing
`_validate_confirm` to the 7 tokens the classify prompt actually offers, in addition to the
existing ~30-token `DISPATCHED_COMMAND_TOKENS` check; (2) `brain-layer/tools/
live_stage2_decider_check.py` gains scenario 5, firing four utterances 0.3s apart with no wait to
surface the chain-drop pattern the performance review's MONITOR finding named. Worktree was stale
at launch (checked out at an unrelated later "Status" commit on `worktree-agent-a4ffe69c060f7dc3a`)
— recreated with `git checkout -B feature/brain-layer-stage2-review d51a25b` before starting.

**One required fix, documentation-only, low urgency.**

### Required Fixes

- **`OFFERED_CONFIRM_VOCABULARY`'s docstring overclaims "never unsafe" — it only proves the safe
  drift direction, not both.** The docstring (`belief/brain_reply.py`) states: "a legitimate
  `CONFIRM` for a newly-added classify token would be wrongly degraded to `ASK` here until this
  list catches up -- annoying, never unsafe, since a stricter validator only ever refuses, it does
  not admit a token the model was never offered." That is true for exactly one drift direction:
  body's copy lagging behind a *widened* `prompts.CLASSIFY_COMMAND_VOCABULARY` (brain adds a
  token body hasn't caught up to) — the validator only ever gets stricter, so it fails safe.

  It is not true for the reverse: if `prompts.CLASSIFY_COMMAND_VOCABULARY` is ever *narrowed*
  (a token removed from what the live classify prompt actually offers) without the same edit
  landing in body's `OFFERED_CONFIRM_VOCABULARY`, body's copy is now stale-**wide** relative to
  what was genuinely offered in that call. If the removed token is still a real, dispatchable
  command (still in `DISPATCHED_COMMAND_TOKENS` — likely, since removing a token from the classify
  offer list doesn't imply retiring the command itself), `_validate_confirm`'s two-membership-check
  (`OFFERED_CONFIRM_VOCABULARY` AND `dispatched_command_tokens`) still passes it, because body's
  stale copy still lists it. A hallucinated `CONFIRM <that token>` would then validate even though
  the classify prompt the model actually saw in that call never offered it — this is precisely the
  asymmetry-with-`_validate_pick` category this stage's fix exists to close, reopened for whichever
  tokens get removed from the brain-side list and not synced down. Verified this is a real code
  path, not a theoretical one: `_validate_confirm` degrades on failing *either* check (`or`
  short-circuit), so passing requires membership in **both** sets — the stale-wide direction is
  exactly the case where `OFFERED_CONFIRM_VOCABULARY` no longer reflects the true offered set but
  still intersects with `DISPATCHED_COMMAND_TOKENS`.

  Severity is low — this requires a specific, easy-to-miss-but-narrow maintenance mistake (edit
  `prompts.py`'s constant, forget the body-side mirror), and the outcome is not privilege
  escalation, just accepting a `CONFIRM` for a real dispatchable command the model wasn't actually
  offered in that call, i.e. exactly the pre-fix defect's blast radius, scoped down to the removed
  token(s) only. But per this reviewer's own standing rule (a bounded/small-magnitude risk is not
  automatically optional severity when it contradicts a stated invariant/docstring claim — see
  `feedback_bounded_magnitude_isnt_optional_severity.md`), an incorrect safety claim in the one
  place a future maintainer will read before touching this coupling is a required fix regardless of
  how narrow the exposure is: **fix the docstring to state both drift directions honestly** (safe
  one way, reopens the original gap for affected tokens the other way), so nobody editing
  `prompts.CLASSIFY_COMMAND_VOCABULARY` later believes this coupling is unconditionally safe to
  neglect. Consider also updating `prompts.py`'s own comment on `CLASSIFY_COMMAND_VOCABULARY`
  ("a mismatch here costs accuracy, never safety") — written before this stage's fix, and no longer
  fully accurate now that body maintains a mirrored constant whose staleness in the narrowing
  direction *does* have a safety-relevant effect, however narrow.

### Design decision (Change 1) — judged sound

The implementer's reasoning for duplicating rather than wiring the vocabulary through the payload
holds up: `PICK`'s candidate list is genuine per-call data (different contacts every escalation);
the classify vocabulary is a call-invariant module constant (same 7 tokens every time), so
serialising it onto every `EscalationPayload` is pure overhead with no correctness benefit — the
same duplication-across-the-boundary shape the codebase already uses in the other direction
(`prompts.CLASSIFY_COMMAND_VOCABULARY` itself a hand-curated subset of body's
`DISPATCHED_COMMAND_TOKENS`). Confirmed value-for-value: `OFFERED_CONFIRM_VOCABULARY`'s seven
entries match `brain-layer/src/prompts.py`'s `CLASSIFY_COMMAND_VOCABULARY` tuple exactly. No test
compares them across the module boundary and none can without violating module independence — an
acceptable, named gap (see Optional Refinements below), not a defect.

**Tests verified, not just read:**
- `test_confirm_token_actually_offered_by_classify_prompt_passes_unchanged` and
  `test_confirm_of_a_real_but_unoffered_dispatch_token_is_rejected` do test what they claim — ran
  them individually along with the full suite.
- `test_confirm_of_a_hallucinated_unoffered_token_degrades_to_a_safe_confirm_prompt`'s docstring
  claims the safe-degradation path (`_handle_brain_confirm`'s `slots=None` fallback,
  `handle_command`'s "say again" degrade) is "never even exercised" for a reply this validator
  rejects — checked this is architecturally true, not just asserted by the test itself (which only
  calls `validate_brain_reply` directly and checks `result.kind == "ask"`, it doesn't touch
  `CrewConsole`). Traced `crew_console.py`'s `_handle_brain_reply` (lines ~833-853): it calls
  `validate_brain_reply` first and dispatches on the **returned** `reply.kind`, so a reply
  degraded from `"confirm"` to `"ask"` by the validator is routed to `_handle_brain_ask`, never to
  `_handle_brain_confirm` — the claim holds by construction, not just by observation.

### Change 2 — `live_stage2_decider_check.py` scenario 5 — judged effective

Confirmed the scenario can actually surface a chain-drop rather than just look like it can. Read
`server.py`'s `_handle_escalate`/`_run_job`: each `POST /escalate` spawns its own daemon worker
thread **immediately**, which calls `decider.decide()` right away — `JobSlot.is_current` is checked
only once, right before publishing the result, never before starting the decode. This means firing
four utterances 0.3s apart genuinely produces four concurrent `OllamaClient` calls hitting the same
serializing Ollama daemon, not four requests silently pre-empted by `JobSlot` before any of them
reach Ollama — so the scenario's premise (client-side `OllamaClient.DEFAULT_TIMEOUT_S`, 5.0s,
racing against a real model that can take 32.7s to decide, per D6) is real, not an artifact of this
tool's own design. The "superseded" vs. "no evidence either way" verdict split is an honest,
disclosed heuristic (a missing earlier reply is read as "superseded" only if a later one *was*
answered, and the tool explicitly states in its own output that it cannot distinguish a genuine
`JobSlot` supersession from a client-side timeout that happened to coincide with a later reply
landing) — a human reading the output once can tell "answered" from "plausibly superseded, D3
working as designed" from "no evidence either way, could be chain-drop or still in flight," which
is what the task brief asked this to surface. `_post`/`_get` helpers are reused correctly from the
existing scenarios.

### Verification re-run directly (not trusted from the commit message)

- `body-layer/`: `ruff format --check`, `ruff check`, `mypy src` (`cd body-layer`) all clean;
  `pytest tests -q` → **1292 passed, 4 xfailed**. Matches the claimed 1289→1292/4.
- `brain-layer/`: `ruff format --check`/`ruff check` clean on `src`/`tests` (the subproject's own
  `CLAUDE.md`-scoped command set); `mypy src` clean; `pytest tests -q` → **44 passed**, unchanged,
  matching the claim (the new scenario has no automated test, by design, same posture as the rest
  of that tool).
- `ruff format --check tools` (brain-layer, **outside** the subproject's own documented command
  scope) does flag `tools/live_cross_process_check.py` — confirmed **pre-existing and genuinely
  untouched by this commit**: `git diff c1b96b1 d51a25b -- brain-layer/tools/
  live_cross_process_check.py` is empty. The implementer's claim checks out.
- The three named regression/invariant tests re-run individually and pass:
  `test_poll_replies_tick_rate_unaffected_by_a_wedged_server`,
  `test_drain_brain_tick_rate_unaffected_by_a_wedged_brain` (both against real wedged raw sockets,
  not mocks), and `test_wrong_pick_because_tank_degrades_to_ask`.
- No Stage 3 answer-leg creep: diff --stat is confined to `belief/brain_reply.py`,
  `tests/test_brain_reply.py`, `brain-layer/tools/live_stage2_decider_check.py`,
  `plans/brain-layer/implementation.md`, and two agent-memory files. No touch to `escalation.py`,
  `tool_api.py`, or `perception/`.

### Optional Refinements

- A mechanical, import-free sync check (e.g. a small script/test parsing both `prompts.py`'s
  `CLASSIFY_COMMAND_VOCABULARY` and `brain_reply.py`'s `OFFERED_CONFIRM_VOCABULARY` as literal AST
  tuples/frozensets and asserting equality, without importing either module) would convert the
  "human must remember" coupling into an enforced one, without violating module independence. Not
  required at this project phase (single-user, LAN-only, narrow exposure per the Required Fix
  above) — named for whoever next touches either vocabulary list.

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read of both changed files' diffs, `test_brain_reply.py`'s three new tests, and the new
`overlapping_utterances_scenario()` in full. Traced `crew_console.py`'s `_handle_brain_reply`
dispatch and `server.py`'s `_handle_escalate`/`_run_job` worker-thread timing directly to verify
two claims rather than accepting them (the safe-degradation-path-never-reached claim, and the
chain-drop scenario's premise that requests reach Ollama concurrently rather than being pre-empted
by `JobSlot`). Both subprojects' full command sets re-run from scratch against this worktree
(recreated at `d51a25b` after finding it stale) and matched the commit's claimed numbers exactly.
The pre-existing-formatting-drift claim was independently verified via `git diff` on the specific
file, not just re-stated. Not separately re-run: the three prior commits' (`68c4b7d`, `8186e7d`,
`cdb8c7f`) own verification, already covered by the review section above this one.
