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
