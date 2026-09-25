# brain-layer/CLAUDE.md

Subproject instructions for the Brain Layer. Augments root `CLAUDE.md` --
read that first for overall Petrobrain architecture; this file adds
stack/testing/structure specifics that apply only within `brain-layer/`.

See `plans/brain-layer/plan.md` (`BR-1`) for the full design -- D1-D11's
decisions, what was measured before designing, and the Stage 1-4
implementation sequence this subproject is being built against.

## What this is

A separate subproject and a separate process (D1), spoken to over
HTTP/JSON -- the default cross-subproject seam per root `CLAUDE.md`'s
module-independence rule (the body-layer<->world-model in-process import
is the *sole* sanctioned exception, and this is not it). `brain-layer`
turns one escalated player utterance (body-layer already ran its own
deterministic grammar over it and could not act) into one reply drawn
from a closed vocabulary -- `PICK <id> BECAUSE <words>`, `ASK`,
`CONFIRM <token>`, or `UNABLE <reason>` -- structured as JSON on the wire,
never free prose (D5: the model classifies against a closed set, it never
writes what Petrovich says -- `belief.speech` on the body side owns every
word actually spoken).

**Fire-and-forget, always** (D2). `POST /escalate` returns `202` before a
decision exists; the caller polls `GET /replies/poll` to drain whatever
has been decided since the last poll. Nothing in this process's HTTP
surface ever blocks a caller waiting for a `Decider` to finish -- that is
the one invariant every other design choice here serves, per the user's
own constraint: "the game world moves on."

**Stage 2** (current) adds `OllamaDecider` -- a real local model behind
the same `Decider` protocol, calling a local Ollama daemon over stdlib
`urllib` (`src/ollama_client.py`). `decider.py`'s `structural_unable_reason`
is reused, not duplicated: an empty candidate list is `UNABLE NO_MATCH`
with no model call; no matched verb at all routes to the **classify**
prompt (`CONFIRM <token>` or `UNABLE`); one or more candidates routes to
the **discriminate** prompt (`PICK <id> BECAUSE <words>` or `ASK`,
Measurement 4's exact wording, `src/prompts.py`). `--decider stub|ollama`
(`__main__.py`, **default still `stub`**, deliberately -- preserving
`run-scripts/run-brain.sh`'s existing meaning unchanged rather than
switching what that script runs out from under it; pass `--decider ollama`
explicitly to run the real model) selects between it and Stage 1's
`StubDecider`.

**`Decider.decide()` now runs under its own bounded timeout**
(`server.py`'s `DEFAULT_DECIDE_TIMEOUT_S`, 12.0s) -- a pre-Stage-2
prerequisite from `plans/brain-layer/performance-review.md`: nothing
previously bounded how long a `decide()` call could take, which was
invisible while `StubDecider` was always fast/boundedly-delayed but
becomes a real leaked-thread risk once a call can genuinely hang
(`OllamaDecider`'s own `urllib` timeout, `ollama_client.DEFAULT_TIMEOUT_S`,
5.0s, is the actual fix; the server-side wrapper is a decider-agnostic
backstop). See `server.py`'s own docstring.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`).
  Stdlib only (`http.server`, `urllib.request`, `json`, `threading`) --
  no dependencies declared, the same policy `world-model`/`aircraft-layer`/
  `audio-adapter` all follow. **Not FastAPI**, despite `plans/brain-layer/
  plan.md`'s affected-files table naming it in one line -- see
  `src/server.py`'s own docstring for why that table entry was not
  followed: no Decision in the plan argues for a specific web framework,
  and a new third-party dependency is an escalation-worthy decision
  (`AGENTS.md`) this project has otherwise never taken for its HTTP
  surfaces.
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.

## Commands

```sh
ruff format brain-layer/src brain-layer/tests   # format
ruff check brain-layer/src brain-layer/tests    # lint
cd brain-layer && mypy src                       # type check (strict) -- CWD-only config discovery, see below
pytest brain-layer/tests -q                      # test
```

**mypy config discovery is CWD-only** (same as every other subproject in
this repo -- `mypy_path` in `pyproject.toml` is itself resolved relative
to the working directory `mypy` runs from, not to the config file's own
location): the only correct invocation is `cd brain-layer && mypy src`.

Run a single test: `pytest brain-layer/tests/test_file.py::test_name -q`.

**Running the live server**: `src` isn't installed as a package, same
non-optional-`PYTHONPATH` situation as every other subproject's live
entrypoint. From `cd brain-layer`:

```sh
PYTHONPATH=src .venv/bin/python -m brain_layer --host 0.0.0.0 --stub-delay-s 8
```

`run-scripts/run-brain.sh` wraps this for the standard cross-machine
workflow (see that script and `run-scripts/run-audio-adapter.sh` for the
sibling pattern it follows).

## Testing

Every unit here is testable with no live Ollama process and no live DCS
session -- `StubDecider` makes the whole async round trip provable without
either, which is Stage 1's entire point (plan: "every hard part of the
design ... is provable at the REPL without Ollama running").

## Structure

- `src/decider.py` -- the `Decider` protocol, `structural_unable_reason`
  (D11's two code-decidable `UNABLE` reasons, shared so `OllamaDecider`
  can reuse it rather than duplicate it), `StubDecider` (Stage 1), and
  `OllamaDecider` (Stage 2) -- calls `ollama_client.OllamaClient` with
  `prompts.py`'s two prompt shapes, parses the model's raw text reply
  with `_parse_discriminate_reply`/`_parse_classify_reply` (never raises;
  unparseable text degrades to `ASK`/`UNABLE NO_SUCH_COMMAND`, the same
  no-free-judgement posture `StubDecider` already has). `model`/
  `num_ctx`/`num_predict` are plain fields, never hardcoded (D6: "the
  model is expected to be swapped").
- `src/prompts.py` -- the two prompt shapes as module constants,
  `render_discriminate_prompt`/`render_classify_prompt`.
  `DISCRIMINATE_PROMPT` is Measurement 4's fix reproduced verbatim.
  `CLASSIFY_COMMAND_VOCABULARY` is a curated, no-slot-parameter subset of
  `belief.crew_console.DISPATCHED_COMMAND_TOKENS`, duplicated here
  (module independence) since this offers the classify call what to
  choose from -- the body-side D10 validator (`belief.brain_reply`) is
  the real authority on whether a returned token is legal.
- `src/ollama_client.py` -- `OllamaClient`, stdlib `urllib` against
  Ollama's `/api/generate` (`stream: false`, explicit `num_ctx`/
  `num_predict`). Its own per-request timeout
  (`DEFAULT_TIMEOUT_S`, 5.0s) is the actual fix for a hung Ollama daemon,
  not `server.py`'s wrapper (see that module's own docstring).
  `warm_up()` is D8's mitigation, called once at `__main__.py` startup.
- `src/job.py` -- `JobSlot` (D3's single-in-flight-job, newest-wins
  policy, generation-counter based so a superseded job's late-arriving
  result is silently dropped rather than published) and `ReplyQueue` (a
  bounded FIFO, `audio-adapter/src/transcript_queue.py`'s
  push/drain_all shape).
- `src/server.py` -- `BrainLayerServer`: `POST /escalate` (202,
  fire-and-forget -- submits to `JobSlot`, starts a daemon worker thread,
  never waits on it), `GET /replies/poll` (drains `ReplyQueue`),
  `GET /health`. Structurally a copy of `audio-adapter/src/server.py`'s
  `ThreadingHTTPServer` + handler-factory shape. `_run_job` (the daemon
  worker's body) now races `Decider.decide()` on a throwaway
  `ThreadPoolExecutor` bounded by `DEFAULT_DECIDE_TIMEOUT_S` -- see the
  module docstring for why this is a decider-agnostic backstop, not the
  primary fix for a hung model call.
- `src/brain_layer/__main__.py` -- `python -m brain_layer` entrypoint,
  untested by design (a live-process driver, same posture as every other
  subproject's own `__main__.py`/`main()`). `--decider stub|ollama`,
  `--brain-model` (default `qwen3:4b-instruct-2507-q4_K_M`),
  `--ollama-url`, `--decide-timeout-s`.
