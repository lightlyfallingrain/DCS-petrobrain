### Implementation Summary

BR-1 Stage 1: the async round trip proven with no model at all
(`plans/brain-layer/plan.md`). New `brain-layer/` subproject (its own
venv, stdlib-only HTTP) with `POST /escalate` (fire-and-forget, D2),
`GET /replies/poll`, `GET /health`, a single-in-flight-job newest-wins
policy (`job.JobSlot`, D3), and `StubDecider` -- deterministic, no
Ollama, a configurable artificial delay. Body-side: `BrainLayerClient`
(never blocks the poll loop, D2, with its own client-side newest-wins
mirror of D3), `CrewConsole.drain_brain` (D8's deterministic "stand by",
D4's full revalidation table), and four new body-written speech
templates (D5).

### Files Changed

**New subproject `brain-layer/`**
- `brain-layer/pyproject.toml`, `CLAUDE.md`, `README.md`, `.gitignore` —
  subproject scaffolding, stdlib-only (`dependencies = []`), matching
  every other subproject's own convention.
- `brain-layer/src/decider.py` — `Decider` protocol; `structural_
  unable_reason` (D11's two code-decidable `UNABLE` reasons — `NO_SUCH_
  COMMAND` from `partial_parse.matched_intent is None`, `NO_MATCH` from
  a matched intent with zero candidates — shared so Stage 2's
  `OllamaDecider` can reuse rather than duplicate it); `StubDecider`
  (configurable `delay_s`, an optional `reply` override for test
  control).
- `brain-layer/src/job.py` — `JobSlot` (D3's newest-wins, a generation
  counter so a superseded job's late-arriving result is silently
  dropped) and `ReplyQueue` (bounded FIFO, `audio-adapter`'s
  `TranscriptQueue` shape).
- `brain-layer/src/server.py` — `BrainLayerServer`: `POST /escalate`
  submits to `JobSlot`, starts a daemon worker thread, responds `202`
  before the worker necessarily finishes; `GET /replies/poll` drains
  `ReplyQueue`; `GET /health`. Stdlib `http.server.ThreadingHTTPServer`,
  a direct structural copy of `audio-adapter/src/server.py` — **not
  FastAPI**, despite the plan's own affected-files table naming it; see
  below.
- `brain-layer/src/brain_layer/__init__.py`, `__main__.py` — `python -m
  brain_layer` entrypoint, `--stub-delay-s` wired through to
  `StubDecider`.
- `brain-layer/tests/test_decider.py`, `test_job.py`, `test_server.py`.

**Changed `body-layer/`**
- `src/belief/escalation.py` — `BrainReply` (`utterance_id`, `kind`,
  plus the fields only that `kind` populates) and `poll_replies() ->
  list[BrainReply]` added to the `BrainClient` protocol; both stand-ins
  return `[]`.
- `src/belief/brain_client.py` (new) — `BrainLayerClient`: `handle()`
  hands the payload to a single-slot background worker thread and
  returns in microseconds (never blocks, D2); a `handle()` call landing
  mid-POST overwrites that slot (this client's own local newest-wins
  mirror of D3, distinct from `brain-layer`'s own server-side
  `JobSlot`). `poll_replies()` is a plain synchronous GET. `_reply_
  from_dict` is a defensive structural parse (skip malformed items) —
  explicitly not D10's semantic validator, deferred to Stage 2 (see
  "Notable Discoveries").
- `src/belief/crew_console.py` — `STAND_BY_AFTER_S` (2.0s, unmeasured)
  and `BRAIN_REPLY_MAX_AGE_S` (20.0s, unmeasured) constants;
  `_pending_escalations`/`_stand_by_spoken_for` fields; `drain_brain`,
  `_speak_stand_by_if_due`, `_handle_brain_reply`,
  `_handle_brain_confirm`, `_handle_brain_pick`, `_handle_brain_ask` —
  D4's full revalidation table plus D8's stand-by. `_handle_utterance`
  now records every escalation in `_pending_escalations` before handing
  it to `brain_client.handle`.
- `src/belief/voice_commands.py` — `PendingConfirmation.token` widened
  to `str | None`; new `contact_pick: tuple[str, PartialParse] | None`
  field for D4's "confirm the survivor" case (a contact-reference
  confirm, distinct from a command-token confirm — "there is not a
  second confirm mechanism" only holds for the *window/vocabulary*, not
  for what committing it does). `handle_transcript`'s affirm branch
  checks `contact_pick` first and re-runs the originally-escalated
  intent (`_act` via `dataclasses.replace`) rather than dispatching a
  token.
- `src/belief/speech.py` — `render_unable`, `render_lost_contact`,
  `render_stand_by`, `render_disambiguation` — all body-written (D5),
  the decider only ever names a reason/token.
- `src/logger.py` — `--brain-client http|debug|null` (`http` requires
  `--brain-url`), wires `BrainLayerClient`; `crew_console.drain_brain`
  called in `_run_crew_text_poll_loop` right after `drain_events`.
- `body-layer/CLAUDE.md` — updated "What this is" (brain is now a real
  HTTP peer, not "not built yet"), `--crew-text` section, and new/
  extended Structure entries for `escalation.py`/`brain_client.py`/
  `crew_console.py`/`speech.py`.

**Other**
- `run-scripts/run-brain.sh` (new) — mirrors `run-audio-adapter.sh`'s
  `pushd`/`PYTHONPATH=src`/`.venv/bin/python -m <package>` shape exactly.

### Tests Added

**`brain-layer/tests/`** (20 tests)
- `test_decider.py` — `structural_unable_reason`'s two structural cases
  plus the genuine-judgement `None` case; `StubDecider`'s delay/no-delay
  timing, structural fallback, and `reply` override (with a copy-not-
  alias check).
- `test_job.py` — `JobSlot` first-submit/newer-supersedes-older;
  `ReplyQueue` push/drain ordering and draining-empties.
- `test_server.py` — real-loopback-server tests, including the two most
  directly tied to Stage 1's stated acceptance: `test_escalate_returns_
  202_immediately_even_with_a_slow_decider` (POST never blocks
  regardless of decider latency) and `test_superseded_job_reply_is_
  discarded_not_delivered` (D3 proven end to end over real HTTP, not
  only at `JobSlot`'s own unit level).

**`body-layer/tests/`** (28 new tests)
- `test_brain_client.py` (new, 8 tests) — a fake stdlib-`http.server`
  loopback server (not an import of `brain-layer/`, module independence)
  proving `handle()` posts correctly, returns immediately even against a
  1s-delayed server response, and never raises when unreachable;
  `poll_replies()` parses valid replies, skips malformed items, and
  raises `BrainLayerError` on an unreachable server.
- `test_crew_console.py` (11 new tests) — the plan's own Stage 1
  acceptance framing, directly: `test_drain_brain_speaks_stand_by_once_
  at_the_threshold` and `test_drain_brain_pick_contact_deleted_during_
  delay_yields_lost_him`. Plus the rest of D4's table (pick-present-acts,
  ask-two-survivors, ask-zero-survivors, ask-one-survivor-confirms-then-
  affirms), D9's confirm reuse, D11's unable wording, D4's staleness
  discard, an untracked-utterance-id discard, and a poll-failure
  log-and-continue.
- `test_speech.py` (8 new tests) — the four new render functions,
  including the unrecognised-reason degrade and the 3-candidate cap.
- `test_escalation.py` (1 new test, 1 extended) — `poll_replies()` on
  both stand-ins.

### Checks

**brain-layer/**
- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (run from `cd brain-layer`): pass, 5 source files
- `pytest tests -q`: pass, 20 passed

**body-layer/**
- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (run from `cd body-layer`): pass, 48 source files
- `pytest tests -q`: pass, 1139 passed, 4 xfailed

### Notable Discoveries

- **`feature/brain-layer`'s real pre-existing test baseline is 1111
  passed / 4 xfailed, not main's 1192.** The task's stated baseline
  ("feature/brain-layer has no code changes yet, so [main's 1192] is
  your baseline too") does not hold: the branch's merge-base with main
  predates `feature/watch-reporting` and `fix/position-belief-runaway`,
  both merged to main since. Verified by `git archive`-ing both
  `feature/brain-layer`'s pre-my-work tip and `main` into isolated
  scratch trees and running `pytest` in each directly (the
  `pythonpath`-override trap this project's memory warns about) — the
  branch tip collects 1115 tests (1111 passed + 4 xfailed) against
  `main`'s 1196 (1192 + 4 xfailed), an 81-test gap that is entirely
  pre-existing branch staleness, not anything this stage touched (one
  whole file, `tests/test_threat.py`, is simply absent on this branch).
  My own changes add 28 new passing body-layer tests on top of that
  1111 baseline (1111 -> 1139), zero regressions either way. This is
  not something to silently rebase around mid-implementation-task — the
  plan's own D6/model-choice section shows this branch has already
  taken two separate rounds of user-directed investigator work since it
  diverged, so rebasing onto main was left for the user/orchestrator to
  decide, not done unilaterally here.
- **`decider.py`'s "structural vs. judgement" split resolved a real
  ambiguity in the task brief.** The task flagged that `NO_SUCH_COMMAND`/
  `NO_MATCH` are "decided structurally by code rather than by any
  decider" and asked where that logic belongs rather than reflexively
  putting it in the stub. Resolution: a shared, decider-agnostic pure
  function (`structural_unable_reason`) inside `brain-layer/src/
  decider.py`, callable by both `StubDecider` today and `OllamaDecider`
  (Stage 2) before either reaches for model-specific logic — not
  body-side (the round trip is meant to be exercised end to end even
  for these cases, per Stage 1's own acceptance framing) and not
  duplicated per-decider.
- **The wire format between brain-layer and body-layer is structured
  JSON (a `BrainReply`-shaped dict), not free text.** D5/D10's "one line
  drawn from a closed vocabulary" language describes what a *model*
  internally produces (Stage 2's `OllamaDecider` prompt/parse step) —
  it is not the wire contract between the two processes. `StubDecider`
  is plain code with nothing to parse, so it constructs the structured
  reply directly. This also means `belief/brain_reply.py` (the plan's
  own affected-files table, and D10's validator) is **not built in
  Stage 1** — the plan's own stage table places the D10 validator in
  Stage 2 ("`OllamaDecider` ... and the D10 validator on the body
  side"), and Stage 1's wire has no free-model-text step to validate.
  `belief/brain_client.py`'s `_reply_from_dict` does a purely structural
  (type/shape) parse of untrusted cross-process JSON, which is good
  practice regardless of D10 and not a substitute for it.
- **`server.py` deliberately does not use FastAPI**, despite the plan's
  own affected-files table naming it in one line. No Decision (D1-D11)
  argues for a specific web framework, every other subproject in this
  repo (`world-model`, `aircraft-layer`, `audio-adapter`) declares
  `dependencies = []`, and root `CLAUDE.md`/`AGENTS.md` both treat a new
  third-party dependency as escalation-worthy. Built on stdlib
  `http.server.ThreadingHTTPServer` instead, a direct structural copy of
  `audio-adapter/src/server.py`'s existing shape. Documented in
  `server.py`'s own docstring and `brain-layer/CLAUDE.md`.
- **D4's "confirm the survivor" case needed a small, genuine extension
  to `PendingConfirmation`**, not a shortcut. The design explicitly
  forbids silently acting on an `ASK` narrowed to one candidate ("only
  one left" is not the same as "the pilot meant this one"), but the
  existing confirm mechanism (`PendingConfirmation.token` ->
  `handle_command`) has nothing to commit to for a *contact reference*
  rather than a command token. Resolved by adding a mutually-exclusive
  `contact_pick: tuple[str, PartialParse] | None` field, committed via
  `dataclasses.replace(parse, referenced_contact_id=contact_id)` into
  `_act` — reuses the exact confirm-band window/vocabulary (D9's "not a
  second confirm mechanism") while still routing to the right action.
- **The worktree this task started in was stale scaffolding from an
  unrelated prior task** (its branch tip, already merged into `main`,
  was `f89a949`, a position-belief-runaway commit with no relation to
  `feature/brain-layer`). Reset with `git checkout -B
  worktree-agent-a5dd86f123c1b00d0 feature/brain-layer` (a permitted,
  non-destructive rewrite of the worktree's own throwaway branch ref,
  not `git reset --hard`, which is denylisted) after confirming via
  `git merge-base --is-ancestor` that the stale tip was already fully
  contained in `main` and therefore nothing was lost.
- **Scope held to Stage 1 exactly**: no `OllamaDecider`, no prompt text,
  no `belief/brain_reply.py` D10 validator, no wiring of `awaiting_
  reply_id`/`awaiting_reply_to`'s answer leg (Stage 3) beyond the field
  already existing on `EscalationPayload`/serialised across the wire.
  `belief/tools.py`/`belief/tool_api.py` untouched, per the plan's
  explicit "zero tool calls" scope note.
- **Not covered by an automated test**: the plan's literal "perception
  loop's tick rate is unchanged" claim with a live 8s stub, measured
  against a real running `brain-layer` process. Both halves of the
  mechanism that make this true are unit/component-tested on their own
  side of the HTTP boundary (`BrainLayerClient.handle()` returns in
  <0.2s regardless of a 1s-delayed fake server response;
  `BrainLayerServer`'s `POST /escalate` responds in <0.5s regardless of
  a 1s `StubDecider` delay) — a true cross-process, both-services-
  running measurement is left as a live/DoD acceptance check rather
  than a subprocess-spawning integration test, per this project's
  existing split between automated and live acceptance testing.
