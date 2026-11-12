### Implementation Summary

Stage 0 of `plans/brain-tool-calls/plan.md` (BR-2): the tool-call-form measurement probe,
fixture, research stub and tests. Agent sandboxes have no route to Ollama and did not attempt
one — the deliverable is the tooling the user runs on the Mac, plus a stub research note with the
exact command lines to fill it in.

### Files Changed

- `brain-layer/src/ollama_client.py` — added `OllamaUsage`, `ToolCall`, `ChatResult` dataclasses;
  `chat()` (native `/api/chat` with `tools`, for Stage 0's "native" form) and
  `generate_with_usage()` (same request as `generate()`, also returning `prompt_eval_count`/
  `eval_count`). Both share request/response handling via a new `_post_json` helper.
  `generate()` itself is unchanged in behaviour (now a thin wrapper over
  `generate_with_usage()`), so `decider.OllamaDecider` is untouched. **`chat()` reproduces
  `generate()`'s own unbounded `response.read()` — `[[BR-B3]]`, still open — rather than fixing
  it here**; flagged below rather than silently carried.
- `brain-layer/tools/stage0_tool_call_probe.py` (new) — the CLI. Loads `stage0_cases.json`,
  builds a byte-stable system prompt per form (R3), drives each case through up to
  `--max-rounds` tool-call rounds (default 4, standing in for the not-yet-built body-side
  `BRAIN_MAX_TOOL_ROUNDS`) plus one final round, answering every tool call from the case's own
  canned observation, and records per round: latency, prompt/eval tokens, well-formedness, step
  match, and final-reply correctness. Prints a per-case verdict line and a markdown summary
  table (correct/total, mean/max round latency, max prompt tokens, cases needing >2 rounds) per
  `(form, num_ctx)`; `--out` writes the full per-round JSON.
- `brain-layer/tools/stage0_cases.json` (new) — 15 cases, one per utterance in the plan's
  "Acceptance set (A1 categories)" section (the two place-report bullets and the two
  `FIXED_COMMAND_ONLY` bullets are each two separate cases), the shared 7 query-tool specs,
  `BRAIN_COMMANDS`-shaped allowlist, header fixtures (clock/range/landmark text only, no x/z per
  D2), canned observations, and expected step sequence + final reply. Includes both
  `FIXED_COMMAND_ONLY` cases and the one `CANNOT_ANSWER` case the task asked for explicitly.
- `brain-layer/research/2026-11-12-tool-call-form.md` (new) — stub: question, method, the exact
  `PYTHONPATH=src .venv/bin/python tools/stage0_tool_call_probe.py ...` command lines (joint and
  per-`num_ctx`), empty results tables, and a conclusions section with the four questions it
  needs to answer, marked "to be filled in from the run."
- `brain-layer/tests/test_ollama_client.py` — extended the fake Ollama server to also answer
  `/api/chat` and to carry configurable `prompt_eval_count`/`eval_count`; added tests for
  `chat()` (tool-call parsing, no-tool-call content, malformed `tool_calls`, missing `content`,
  unreachable server) and `generate_with_usage()` (counts returned, counts default to 0 when
  absent, and a regression test that `generate()`'s own two-argument-in/text-out contract is
  unchanged by the refactor).
- `brain-layer/tests/test_stage0_tool_call_probe.py` (new) — loads the probe module via
  `importlib` (mirroring `body-layer/tests/test_generate_effector_registry.py`'s pattern for a
  `tools/` script not on `pythonpath`). Covers the grammar parser (`CALL`, all four `FINAL ...`
  shapes, malformed text, case-insensitivity), native `tool_calls` extraction (single call,
  multiple calls → not well-formed, content-only final, malformed content), the case loader
  (a small inline fixture, plus a test that loads the actual shipped `stage0_cases.json` and
  checks its tool/case counts and that both `FIXED_COMMAND_ONLY` cases and the one
  `CANNOT_ANSWER` case are present), `find_observation`'s by-tool-name matching, and the round
  loop itself driven by scripted fake clients (`_FakeGrammarClient`/`_FakeNativeClient`) for:
  call-then-final, a malformed reply ending the turn, exceeding the round cap, the native form's
  call-then-final path, and a transport error being recorded rather than raised out of the loop.

### Tests Added

See the `test_ollama_client.py` and `test_stage0_tool_call_probe.py` bullets above — 25 new test
functions in total (11 in `test_ollama_client.py`, 14 in `test_stage0_tool_call_probe.py`).

### Checks

(brain-layer/ — `cd brain-layer`; no committed `.venv` existed in this worktree, so one was
created fresh with `python3.12 -m venv .venv && pip install ruff mypy pytest`, matching the
subproject's declared tool versions, not a project dependency change)

- `ruff format src tests tools`: pass (formats cleanly; see note below)
- `ruff check src tests tools`: pass — "All checks passed!"
- `mypy src tools`: **3 pre-existing errors, none from this change** — `tools/
  live_cross_process_check.py:29-31`, `import-not-found` on `belief.brain_client`/
  `belief.escalation`/`belief.utterance`. That file predates this task, is untouched by it, and
  was never covered by the subproject's own documented `mypy src` command (only `tools` passed
  on this task's wider check command reaches it). `mypy src tools` restricted to this task's own
  files (`src/ollama_client.py`, `tools/stage0_tool_call_probe.py`) is clean.
- `pytest -q`: pass — 74 passed (up from 49 before this change: 25 new).

**Note on `ruff format ... tools`**: it also reformats `tools/live_cross_process_check.py`
(pure whitespace, two `print(f"...")` calls wrapped onto their own lines) — a pre-existing file
this task did not touch otherwise. Reverted that file after each format/lint pass so this
branch's diff stays scoped to Stage 0's own deliverables; whoever next edits that file will hit
the same reformat and may want to land it as its own small commit.

### Notable Discoveries

- **The plan's acceptance-set bullet list is 15 utterances, not 13.** Re-reading "Petrovich,
  anything near Gemerek? and ...report south of Gemerek" and "arm the weapons" / "turn left" as
  the two separate utterances each bullet actually names (rather than one bullet = one case)
  gives 15, not the ~13 a first skim suggests. Both the fixture and its loader test assert 15;
  said here because a future reader recounting bullets by eye will plausibly land on 13 too.
- **`BRAIN_MAX_TOOL_ROUNDS` does not exist yet** (plan D9 is body-side, Stage 1+, not built in
  this stage) — the probe's `MAX_TOOL_ROUNDS = 4` is a local stand-in at the same default, not
  an import, so Stage 2's real tunable and this probe's cap can drift independently once the
  real one ships. Worth re-measuring Stage 0 if that default changes before BR-2 Stage 2.
- **`chat()`'s read-cap gap is the only place this task touched code BR-B3 already flags.**
  Folding BR-B2/BR-B3 into Stage 2 is U4 (accepted, "recommend yes" in the plan) — out of scope
  for Stage 0, which is why `chat()` was written to match `generate()`'s existing (uncapped)
  style rather than fixing it ahead of that stage. Noted in `ollama_client.py`'s own module
  docstring as well as here.
- **The native form's "well-formed" bar for >1 tool call is a judgement call, not something the
  plan specifies.** Ollama's `/api/chat` allows a `tool_calls` array with more than one entry;
  this probe only ever acts on the first and records the round as not well-formed when there is
  more than one, since D3's "one round, one tool" rule has no stated native equivalent. If the
  real model routinely returns multiple tool calls per round, Stage 2's design will need an
  explicit decision here, not an inherited probe default.
