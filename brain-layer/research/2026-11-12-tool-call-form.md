# Stage 0 — tool-call form measurement (`plans/brain-tool-calls/plan.md`, BR-2)

Status: **stub — run pending.** Written by the Implementer alongside `brain-layer/tools/
stage0_tool_call_probe.py` and `brain-layer/tools/stage0_cases.json`; the tables below are empty
and the conclusions are placeholders. **Agent sandboxes have no route to Ollama and must not try
to reach it** (plan Stage 0, citing BR-1.2) — this run has to happen on the user's Mac, with a real
`qwen3:4b-instruct-2507-q4_K_M` behind a live Ollama daemon.

## Question

Which tool-call *form* does the model handle better: Ollama's native `/api/chat` `tools`, or a
closed one-line grammar in the style of this subproject's own BR-1 `prompts.py`
(`CALL <tool> <json-args>` / `FINAL command|answer|ask|unable ...`)? Plan D1 leaves the choice to
this measurement and says the wire to body-layer is the same structured JSON either way, so
nothing downstream depends on which form wins — this note's job is to pick one, and to pick
`num_ctx` and the tool-call round cap body-layer's BR-2 Stage 2 will build against.

## Method

`stage0_tool_call_probe.py` plays "body": for each of the 15 acceptance-set cases in
`stage0_cases.json` (one per bullet of the plan's "Acceptance set (A1 categories)" section,
including both `FIXED_COMMAND_ONLY` cases and the `CANNOT_ANSWER` case), it drives the model
through up to 4 tool-call rounds (`MAX_TOOL_ROUNDS`, standing in for the not-yet-built body-side
tunable `BRAIN_MAX_TOOL_ROUNDS`, plan D9's default) plus one final round, answering every tool call
from the case's own canned observations, and records per round: wall latency, prompt/eval tokens
from Ollama's own reply, whether the line was well-formed, whether the tool call matched the
expected step, and whether the final reply matched what the case expects.

Run both forms at both `num_ctx` values (R3's candidates: a smaller context may not fit the tool
block, command list and up to 4 observations):

```sh
cd brain-layer
PYTHONPATH=src .venv/bin/python tools/stage0_tool_call_probe.py \
    --model qwen3:4b-instruct-2507-q4_K_M --form both --num-ctx 2048 4096 \
    --cases tools/stage0_cases.json --out /tmp/stage0_results_2048_4096.json
```

If 2048 and 4096 need separately isolated numbers (e.g. to check whether a longer-context run pays
a measurable per-token overhead independent of correctness), rerun per value:

```sh
PYTHONPATH=src .venv/bin/python tools/stage0_tool_call_probe.py \
    --model qwen3:4b-instruct-2507-q4_K_M --form both --num-ctx 2048 \
    --cases tools/stage0_cases.json --out /tmp/stage0_results_2048.json
PYTHONPATH=src .venv/bin/python tools/stage0_tool_call_probe.py \
    --model qwen3:4b-instruct-2507-q4_K_M --form both --num-ctx 4096 \
    --cases tools/stage0_cases.json --out /tmp/stage0_results_4096.json
```

The script prints a per-case verdict line and a markdown summary table (correct/total, mean/max
round latency, max prompt tokens, cases needing more than 2 tool-call rounds) to stdout; the
`--out` JSON carries every round's raw reply text for closer reading if a case fails in a way the
summary doesn't explain.

## Results

**To be filled in from the run.** Paste the printed summary table(s) here, one per
`(form, num_ctx)` combination the run above produced:

```
(paste `stage0_tool_call_probe.py`'s stdout summary table here)
```

Per-case detail worth keeping (which cases failed, in which form/num_ctx, and the raw reply text
from the `--out` JSON for each failure):

```
(to be filled in)
```

## Conclusions

**To be filled in from the run.** This section should answer, in order:

1. **Which form** — native `tools` or the closed grammar — is more reliable across the 15 cases,
   and by how much. If one form is clearly worse, say which failure mode dominates (malformed
   lines, wrong tool, wrong final reply, exceeded round budget).
2. **`num_ctx`** — does 2048 fit the tool block, command list and worst-case observation history
   (R3), or does a case fail only at 2048 and pass at 4096? If 4096 is needed, note the ~0.5 GB
   resident-footprint cost the plan already estimated (unconfirmed, D6's earlier measurement was
   for a far smaller prompt).
3. **The round cap** — did any case genuinely need more than 2 tool-call rounds, and did any case
   exceed `MAX_TOOL_ROUNDS` (4) without reaching a final reply? If several needed 3+, say whether
   that argues for raising `BRAIN_MAX_TOOL_ROUNDS`'s default once it exists as a tunable (plan D9),
   or whether it is a prompt-design problem instead.
4. **The chosen form, `num_ctx`, and round cap** for BR-2 Stage 2 to build against — one line each,
   with the evidence above as the reason.

## Open follow-ups

- Nothing yet — to be filled in if the run surfaces a genuine design question (a case the fixture
  itself got wrong, a prompt wording that needs the same kind of fix Measurement 4 found for
  `DISCRIMINATE_PROMPT`, etc.) rather than a simple pass/fail.
