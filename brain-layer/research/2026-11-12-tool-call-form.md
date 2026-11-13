# Stage 0 — tool-call form measurement (`plans/brain-tool-calls/plan.md`, BR-2)

Status: **done, 2026-11-13.** Three runs on the user's Mac against a live Ollama with
`qwen3:4b-instruct-2507-q4_K_M` (the user ran the commands; agent sandboxes have no route to
Ollama, BR-1.2). Probe: `brain-layer/tools/stage0_tool_call_probe.py`, fixture
`brain-layer/tools/stage0_cases.json`. Raw per-round replies for the last run were read from the
`--out` JSON.

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

```sh
cd brain-layer
PYTHONPATH=src .venv/bin/python tools/stage0_tool_call_probe.py \
    --model qwen3:4b-instruct-2507-q4_K_M --form both --num-ctx 2048 4096 \
    --cases tools/stage0_cases.json --out /tmp/stage0_results.json
```

The script prints a per-case verdict line and a markdown summary table to stdout; the `--out`
JSON carries every round's raw reply text.

## Results

Three runs, each after a prompt change the previous run forced. The prompt is part of the result:
the form question could not be answered until the prompt stopped being the dominant failure.

### Run 1 — both forms, both `num_ctx`: 0/15 everywhere

| form | num_ctx | correct/total | mean round latency (s) | max round latency (s) | max prompt tokens | cases needing >2 rounds |
|---|---|---|---|---|---|---|
| grammar | 2048 | 0/15 | 0.43 | 3.50 | 625 | 0 |
| grammar | 4096 | 0/15 | 0.32 | 1.84 | 625 | 0 |
| native | 2048 | 0/15 | 0.36 | 2.05 | 1006 | 0 |
| native | 4096 | 0/15 | 0.42 | 2.32 | 1006 | 0 |

Every case ended in one round with no tool call. Raw replies: `FINAL unable no contact offered
yet`, `FINAL answer form ["CONTACT_5"]`, `FINAL ask []`. Two prompt defects, not model limits:

- `FINAL answer <form>` was never given the list of forms, so the model wrote the literal word
  `form`. Unable reasons were not listed either.
- The header is empty at the start of most turns, and the prompt said "never invent a contact".
  The model read the two together as "nothing offered, so unable" and never called a tool. The
  native form had no sentence saying tool calls are how to look things up.

Fix (commit `94710370`): enumerate the four answer forms and the unable reasons; state that an
empty header means *look it up*; three worked examples; a native-form sentence pointing at the
tools.

### Run 2 — both forms, both `num_ctx`

| form | num_ctx | correct/total | mean round latency (s) | max round latency (s) | max prompt tokens | cases needing >2 rounds |
|---|---|---|---|---|---|---|
| grammar | 2048 | 8/15 | 0.41 | 3.97 | 1584 | 6 |
| grammar | 4096 | 8/15 | 0.36 | 2.15 | 1584 | 5 |
| native | 2048 | 12/15 | 0.47 | 2.98 | 1584 | 1 |
| native | 4096 | 12/15 | 0.48 | 2.97 | 1584 | 1 |

Grammar's dominant failure: five or six cases ran out the round budget without a final reply
(`A1_two_shilkas`, `A2_near_gemerek`, `A2_south_of_gemerek`, `A4_which_bmp`, `A5_keep_an_eye`).
Native's three misses, from the raw replies:

| case | rounds | what the model did | cause |
|---|---|---|---|
| `A1_where_two_shilkas_discriminated` | 2 | `find_contact shilka` → `FINAL answer contacts [CONTACT_2, CONTACT_3]` | did not use "by the village" to pick one; honest degrade (pilot hears both), not a wrong action |
| `A2_report_south_of_gemerek` | 5 | `find_place gemerek` five times in a row, observation ignored | stuck loop; nothing told it not to repeat a listed call |
| `A5_keep_an_eye_on_the_tank` | 2 | `find_contact tank` → `FINAL command watch_nearest {"target": "CONTACT_10"}` | commands were bare tokens, so it did not know `follow` takes the target and `watch_nearest` takes none |

Fix (commit `646b433e`): a one-line meaning per command token (`command_notes` in the fixture),
and a rule never to repeat a call already listed under "So far this turn".

### Run 3 — native only, `num_ctx` 2048

| form | num_ctx | correct/total | mean round latency (s) | max round latency (s) | max prompt tokens | cases needing >2 rounds |
|---|---|---|---|---|---|---|
| native | 2048 | 13/15 | 0.58 | 3.44 | 1801 | 1 |

`A1_two_shilkas` and `A2_south_of_gemerek` now pass. Remaining misses:

| case | what the model did | what body's D3 validation would do with it |
|---|---|---|
| `A3_wheres_mark_one` | `FINAL command where_is_it {"target": "MARK_1"}` | a memory ref in a `contact_ref` slot: type check rejects it, one recovery round |
| `A5_keep_an_eye_on_the_tank` | `FINAL command watch_nearest {"target": "CONTACT_10"}`, same as run 2 despite the note | `watch_nearest` has no slot schema: unknown slot rejected, one recovery round |

Neither is a wrong action reaching the pilot. Both are the kind of reply D3's validator turns into
an `invalid: <why>` observation and a retry inside the round budget.

The user also tried `qwen3:14b` and reported it "awfully slow"; not measured further, the 4B
model is the target.

## Conclusions

1. **Form: native `/api/chat` `tools`.** 12/15 and 13/15 against grammar's 8/15, and one case
   over two rounds against five or six. Grammar's dominant failure is running out the round budget
   with no final reply; the model handles a structured `tool_calls` field better than a text line
   it has to compose itself. Final replies stay a closed `FINAL …` text line in `content`, which
   the model produces reliably in both forms.
2. **`num_ctx`: 2048.** 4096 changed no verdict in either form. The largest prompt seen was 1801
   tokens (a 5-round case), so 2048 fits the worst case measured with ~250 tokens to spare. Thin:
   Stage 2 must keep observations capped (plan D2, lists ≤ 5) and should log prompt tokens per
   round so a flight can show if the margin is being eaten. 4096 stays the fallback if it is.
3. **Round cap: 4 is right.** With the prompt fixed, the only case over two rounds was a referent
   case that still finished in four. The one budget exhaustion in run 2 was a stuck repeat, which
   is a validation problem (below), not a cap problem.
4. **Build against: native tools, `num_ctx` 2048, `BRAIN_MAX_TOOL_ROUNDS` 4.** Round latency
   ~0.5 s mean, ~3.5 s worst (first round after the prefix changes), so a three-round turn is
   roughly 2–6 s of model time plus plan D1's ~1.5 s/round transport.

## Design inputs for Stage 2, from the misses

- **Reject a repeated identical call.** Run 2's `find_place` loop burned the whole budget on one
  call. Body should treat a `(tool, args)` already in this turn's steps as invalid (`invalid:
  already called, see observation N`), costing one round, so the budget cannot be spent on a loop.
- **`command` finals carry an optional `because`.** The two-Shilka case resolved in run 3, but
  only because the prompt pushed it; plan D3's rule (a target drawn from a multi-candidate set
  needs verbatim evidence or degrades to "which one?") needs the slot to exist on the wire.
- **The invalid-call observation must name the fix.** Both run-3 misses are one-word corrections
  (`follow`, not `watch_nearest`; `memory`, not `where_is_it`). "invalid: watch_nearest takes no
  target; follow does" is the whole recovery round.
- **The prompt text here is the starting point for `ToolLoopDecider`'s prompt**, including the
  command notes and the three examples. Keep the system prompt + tools + commands a byte-stable
  prefix (R3, KV-cache reuse); run 3's 3.4 s worst round was the first round of a case, i.e. the
  prefix being re-evaluated after the previous case's different suffix.

## Open follow-ups

- The command-notes block is prose the model has to read; Stage 2 should derive it from
  `BRAIN_COMMANDS`' slot schemas so the two cannot drift.
- `A5` failed the same way twice with the note present. If it survives into the real decider,
  try naming `follow` in the `watch`-shaped example rather than adding more rules.
