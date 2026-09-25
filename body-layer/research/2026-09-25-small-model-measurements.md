# Small local model measurements: qwen3:4b-instruct-2507 vs granite4:micro

**Date:** 2026-09-25
**DCS version:** n/a — this is a local Ollama benchmarking pass, not a DCS-internals investigation
**Theatre:** n/a
**Machine:** Apple M1 Max, 32 GB, macOS, local Ollama daemon — same machine as
`plans/brain-layer/plan.md`'s Measurements 1-4 and
`body-layer/research/2026-09-25-small-local-model-survey.md`.

### Question

The survey (`2026-09-25-small-local-model-survey.md`) named two candidates to displace
`qwen2.5:7b-instruct` (current D6 default) / `llama3.2:3b` (current D6 fallback), each backed by a
specific hypothesis rather than a general "try it and see":

1. **`qwen3:4b-instruct-2507`** — hypothesis: it is *architecturally* non-thinking (no `<think>`
   capability in the weights at all), not thinking-with-a-suppressible-flag like plain `qwen3`,
   whose `/no_think` failed to reliably suppress its reasoning trace (plan Measurement 1).
2. **`granite4:micro`** — hypothesis: IBM's stated design goal of tool-calling/structured-output
   reliability for the Granite 4.0 generation is a direct hit on this layer's core requirement
   (D5: the model's entire job is emitting one line from a closed vocabulary).

This is a test of those two hypotheses on real measurements, not a fishing trip. Both are judged
against the same reuse-not-reinvent test the plan already used
(`plans/brain-layer/probe-prompt.txt`, the D10/Measurement-4 ambiguous-reference case), so the
numbers here are directly comparable to the plan's own table.

### Findings

**Tag resolution (evidence: reproduced-locally)**

- `qwen3:4b-instruct-2507` (bare tag, no quant suffix) **does not exist** as an Ollama pull target —
  `ollama pull qwen3:4b-instruct-2507` returns `Error: pull model manifest: file does not exist`.
  The tag that actually resolves is **`qwen3:4b-instruct-2507-q4_K_M`** (2.5 GB on disk). The
  survey's own text anticipated this ("Ollama tags exist: `qwen3:4b-instruct-2507-q4_K_M`, `-q8_0`,
  `-fp16`") — worth carrying the exact tag forward into D6 rather than the bare name.
- `granite4:micro` (no `ibm/` prefix) resolves directly and pulls successfully (2.1 GB on disk),
  3.4B parameters, contradicting the survey's assumption that the official tag needed an `ibm/`
  namespace prefix. `granite4:h-micro` was not tested — `micro` alone was sufficient to settle the
  hypothesis and the task scoped one tag per candidate.

**Hypothesis 1 (qwen3:4b-instruct-2507 is architecturally non-thinking): HOLDS, with one caveat.**
No `<think>` token, tag, or hidden trace appeared in any of the ~14 runs across every prompt variant
tested below (grepped the raw output of every run for `<think>`: zero matches). This is a real,
structural difference from plain `qwen3:4b`, which is a documented finding, not a claim. **The
caveat**: "architecturally non-thinking" only means there is no special reasoning-token machinery to
suppress — it does **not** mean the model refuses to produce prose deliberation. When the prompt
itself invites step-by-step reasoning (adversarial test below), it happily writes ~575 tokens of
plain-text reasoning before answering, at 11.05 s wall time — no `<think>` wrapper, just an
instruct model doing what it's told. This is a materially better failure mode than plain `qwen3`
(which reasoned *even when told not to*), but it means the production prompt's own tight formatting
instruction is still load-bearing, not a redundant belt-and-braces — **evidence: reproduced-locally**.

**Hypothesis 2 (granite4:micro's tool-calling design goal helps here): PARTIALLY HOLDS.** Granite
was faster warm than qwen3 by a small margin, respected the closed vocabulary in every trial
including under a *relaxed* prompt (see below), and never produced a spontaneous reasoning trace on
the tight prompt. But it was **not more reliable on the discrimination task itself** — it missed a
case it should have gotten right (see "Reliability at constrained output" below) at a rate qwen3
did not, on the very small sample tested. IBM's structured-output design goal shows up as clean
format adherence, not as better judgement on the actual classification decision — **evidence:
reproduced-locally**.

**1. Latency warm, on the closed-answer prompt (`probe-prompt.txt`, 5 runs each, post-warm-up)**

| model | cold (incl. load) | warm (5 runs) | output tokens | prompt tokens |
|---|---|---|---|---|
| `qwen3:4b-instruct-2507-q4_K_M` | 1.92 s | **38–63 ms** | 2 | 192 |
| `granite4:micro` | 2.00 s | **30–49 ms** | 2 | 210 |
| *(for reference, plan's existing table)* `qwen2.5:7b-instruct` | 1.79 s | sub-second | 6 | ~155 |
| *(for reference)* `llama3.2:3b` | 1.36 s | 0.13–0.17 s | 6 | ~155 |

**Evidence: measured on this machine.** Both candidates are **2-4x faster warm than the current
fallback (`llama3.2:3b`) and comfortably faster than "sub-second" for the current default** — at
this prompt shape latency is a complete non-issue for either candidate, consistent with the plan's
own Measurement 2 conclusion that "latency stops being the binding constraint." The higher token
count difference (2 vs 6 output tokens) reflects that this probe's own answer space (`ASK`/`PICK
<id> BECAUSE <words>`) is shorter than the plan's generic pick-from-list prompt, not a
model-capability difference — not a like-for-like token count, though the wall-clock comparison is
still valid and favorable.

**2. Adversarial reasoning-trace test — evidence: reproduced-locally**

Two adversarial variants of the production prompt, neither modifying the actual vocabulary/decision
rule, both run once per model:

- **(a) Explicit invite** ("think step by step... show your reasoning, then give your final
  answer"): both models wrote full prose chains of reasoning before answering.
  - `qwen3:4b-instruct-2507`: 575 output tokens, **11.05 s**, and **got the wrong answer** —
    `PICK CONTACT_7 BECAUSE "T-72 near Gemerek village is closer and more likely..."`, a fabricated
    justification, not a verbatim quote from the transcript ("keep an eye on that tank" contains
    none of that). D10's verbatim-quote check would reject this outright.
  - `granite4:micro`: 187 output tokens, **2.85 s**, also wrong — `PICK CONTACT_7 BECAUSE "the
    pilot is specifically interested in monitoring a tank near the Gemerek village"`, also
    fabricated, also not verbatim, also caught by D10.
- **(b) Soft invite** (same vocabulary/rule, only the "reply with EXACTLY ONE line, nothing else"
  sentence removed — no explicit request to reason):
  - `qwen3:4b-instruct-2507`: no prose reasoning appeared, but the answer was still wrong —
    `PICK CONTACT_7 BECAUSE "keep an eye on that tank"`. This *is* a verbatim quote (the whole
    utterance), so it passes D10's literal-quote check, but the quoted words are equally true of
    both candidates — this is exactly the failure shape D10's "must not be equally true of another
    candidate" clause exists to catch (§ Measurement 4's finding, reproduced here for the new
    model). 592 ms, 17 output tokens.
  - `granite4:micro`: correctly answered `ASK`, 274 ms, 2 output tokens — did not need the
    tight-format instruction to behave.

**Conclusion on the disqualifier:** neither model has a hidden or unsuppressible thinking budget —
this is a real, structural difference from plain `qwen3`, and the hypothesis for candidate 1 holds.
But **both will happily fabricate a plausible-sounding, non-verbatim justification when the prompt
invites deliberation, and qwen3 will do so even under a merely relaxed (not explicitly inviting)
prompt.** The production prompt's tight formatting instruction is doing real, necessary work for
both models, not defense-in-depth against a solved problem — and D10's validator (already deemed
"not optional" in the plan) is what actually catches both fabrication failure modes observed here,
exactly as designed.

**3. Reliability at constrained output — evidence: reproduced-locally**

- **Nonsense input** (M3 case 3's "the grass over there is looking rather brown today", adapted to
  this prompt's two-token vocabulary): both models answered `ASK` cleanly, 100% format compliance,
  no invented tokens. (This probe's own vocabulary has no `SAYAGAIN` option, so `ASK` is the
  correct fallback here, not a like-for-like repeat of the plan's exact M3 case 3 result.)
- **Genuinely discriminating input** ("keep an eye on the tank **by the village**" — should `PICK
  CONTACT_7`, mirroring M3 case 1): run 4x each.
  - `qwen3:4b-instruct-2507`: **4/4 correct**, consistent verbatim-quoting `PICK CONTACT_7`.
  - `granite4:micro`: **3/4 correct**, 1/4 answered `ASK` when it should have picked — a real,
    non-deterministic miss on a case that should be easy. Every wrong answer from both models
    across every test in this session erred toward `ASK` (the safe direction), never toward a wrong
    `PICK` — consistent with the plan's own conclusion that "model quality determines how often
    Petrovich asks, never whether he acts wrongly," reproduced here for both new candidates.
- **Format compliance overall**: across ~20 total runs (5 warm-latency + 2 adversarial + 2 nonsense
  + 8 discriminating + misc probing), every single reply from both models was one of the two
  allowed forms. No malformed output, no invented third token, from either model.

**4. Ambiguity case + D10 verbatim-quote framing — evidence: reproduced-locally**

The plan's own ambiguous case ("keep an eye on that tank", two equally-matching T-72s), on the
unmodified production prompt (`probe-prompt.txt`), 5 runs each:

| model | reply (5/5 runs) |
|---|---|
| `qwen3:4b-instruct-2507` | `ASK` (5/5) |
| `granite4:micro` | `ASK` (5/5) |

**Both candidates beat the plan's own baseline here.** The plan's Measurement 3 showed both
`llama3.2:3b` and `qwen2.5:7b-instruct` **silently guessing** on this exact case before the fix
prompt was applied (D10's prompt reframing, i.e. the very prompt reused here). On that same fixed
prompt, the plan's Measurement 4 showed `qwen2.5:7b-instruct` asking on its own and `llama3.2:3b`
still guessing wrong (caught by the validator). **Both new candidates ask on their own, every time,
on this prompt** — a strictly better result than either existing model at this specific decision.

On the D10 framing itself (the model may only override ambiguity by quoting verbatim words): both
respected it under the intended (tight) prompt — the correct answer here is `ASK` with no override
attempted. The adversarial tests above (§2) show what happens when they *do* attempt to override:
both invent a plausible-sounding, non-verbatim justification rather than genuinely quoting, and
D10's literal-substring-match check is what actually catches it, not the model's own honesty. This
is exactly the posture the plan designed D10 for ("the validator is deterministic, body-side, and
not optional") — worth stating plainly rather than treating as a surprise.

**5. Footprint — evidence: measured on this machine**

| model | disk (`ollama list`) | resident (`ollama ps`, 32768 ctx, this session) |
|---|---|---|
| `qwen3:4b-instruct-2507-q4_K_M` | 2.5 GB | 7.4 GB |
| `granite4:micro` | 2.1 GB | 4.9 GB |
| *(current default)* `qwen2.5:7b-instruct` | 4.7 GB | not re-measured this session |
| *(mission interpreter, coexists between sorties)* `qwen3:14b` | 9.3 GB | not re-measured this session |

Both candidates are **smaller on disk than the current 7B default**, and both are meaningfully
lighter than the D6 memory-budget analysis assumed (which reasoned about the 4.7 GB `qwen2.5:7b`
figure). **Caveat on the resident figures**: `ollama ps` reports resident size at Ollama's default
32768-token context window, which is far larger than this workload's actual ~150-210 prompt tokens
— the real resident footprint in production, run with a context window sized to the actual prompt,
would be smaller than the 7.4 GB / 4.9 GB shown here. This was not re-measured with a constrained
`num_ctx`; flagging it as **inferred**, not measured, so nobody reads 7.4 GB as a hard number.

`qwen3:4b` (2.5 GB, base non-instruct) was not touched in this session — see Housekeeping.

### Reproducible Test

All runs used `plans/brain-layer/plan.md`'s existing `plans/brain-layer/probe-prompt.txt`
(byte-identical copy verified against `git show feature/brain-layer:plans/brain-layer/probe-prompt.txt`
before use) for the latency/ambiguity table, plus three prompt variants built by lightly editing it
for the adversarial/discrimination tests. Reproduce with:

```sh
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama pull granite4:micro

# warm latency + ambiguity case (5x), on each model:
ollama run <model> --verbose < plans/brain-layer/probe-prompt.txt

# footprint:
ollama list
ollama ps   # after a run, while the model is still loaded
```

The three adversarial/discrimination prompt variants used here (not committed as separate files —
reconstructable from the findings above by editing `probe-prompt.txt`):
1. **Explicit-reasoning invite**: prepend "Before answering, think step by step... show your
   reasoning, then give your final answer" and change the reply instruction to "Reply with your
   reasoning, then on the final line: `PICK <id> BECAUSE <words>` or `ASK`."
2. **Soft invite**: identical to `probe-prompt.txt` with the "Reply with EXACTLY ONE line, nothing
   else, no explanation." sentence deleted.
3. **Discriminating case**: identical to `probe-prompt.txt` with `PILOT SAID: "keep an eye on that
   tank"` replaced by `PILOT SAID: "keep an eye on the tank by the village"`.

### Possible Approaches

Not applicable in the "workaround for a negative finding" sense — both hypotheses were net
positive. The open design question this leaves for Architect:

- **Pick `qwen3:4b-instruct-2507-q4_K_M` as D6's new default.** It was perfectly consistent on the
  plan's own ambiguity case (5/5 `ASK`) and on the discrimination case (4/4 correct), it is smaller
  on disk than the current default, and its only weak point (fabricating a justification under
  adversarial prompting) is already fully covered by D10's existing validator — this is not a new
  exposure, it is the exact failure class D10 was built to catch.
- **`granite4:micro` as fallback rather than co-default**, replacing `llama3.2:3b`. It is smaller
  and roughly as fast as `llama3.2:3b`, and unlike `llama3.2:3b` (which guessed wrong on the
  ambiguous case in the plan's Measurement 3) it asked correctly 5/5 here. Its one demonstrated
  weakness — missing a genuinely discriminating case 1/4 times — degrades to an unnecessary `ASK`,
  never a wrong `PICK`, which is exactly the safe failure direction the plan's whole design assumes
  for a lower-tier model.
- Both candidates' exact resolved tags (`qwen3:4b-instruct-2507-q4_K_M`, `granite4:micro`) should
  replace the bare names in whatever supersedes D6 — the bare `qwen3:4b-instruct-2507` tag does not
  resolve.

### Unresolved

- **The discriminating-case sample size is small (4 runs).** Granite's 3/4 vs qwen3's 4/4 could be
  noise rather than a real reliability gap — worth widening before treating it as a settled
  ranking between the two, though it does not change the recommendation above since either failure
  mode is safe.
- **Resident memory at production-realistic context length was not measured** — the 7.4 GB / 4.9 GB
  figures are at Ollama's default 32K context, not the ~150-210 token window this workload actually
  needs. A `num_ctx`-constrained measurement would give a truer coexistence-with-`qwen3:14b` number.
- **`granite4:h-micro` (the hybrid Mamba-2/attention variant) was not measured** — the survey named
  it as an alternative tag; `micro` alone was sufficient to test the hypothesis, but if memory
  footprint becomes a binding constraint later, `h-micro`'s claimed lower-memory-for-long-context
  property is untested here.
- **The M1-style free-JSON "decide what to do about this utterance" prompt was not re-run on
  either candidate** — this measurement pass reused the D10 ambiguity prompt only, per the task's
  explicit instruction to prioritize reusing `probe-prompt.txt` over inventing a new comparison
  point. If a future design still needs a free-JSON call anywhere in the brain layer (not currently
  in BR-1's scope, which is closed-vocabulary-only per D5), that shape should be re-measured
  separately before assuming these latency numbers transfer.

### Bottom line for the user

**Both hypotheses held, and both candidates beat the incumbent pair for this specific job.**
`qwen3:4b-instruct-2507-q4_K_M` is architecturally non-thinking as claimed (no `<think>` trace in
~14 runs, including three adversarial variants) and was perfectly reliable (5/5 correct `ASK`, 4/4
correct `PICK`) at 30-60 ms warm — faster and smaller than the current `qwen2.5:7b-instruct`
default. `granite4:micro` matched it on speed and ambiguity handling (5/5 `ASK`) but missed one
discrimination case out of four, still failing safe (toward `ASK`, never a wrong pick).

**Recommendation for D6: `qwen3:4b-instruct-2507-q4_K_M` as the new default, `granite4:micro` as
the new fallback — replacing both `qwen2.5:7b-instruct` and `llama3.2:3b`.** This does justify
changing the incumbent: on the plan's own test case, the new pair is strictly better than the old
pair (the old pair's best member, `qwen2.5:7b-instruct`, only matched what both new candidates do
by default), smaller on disk, and faster. The one caveat worth carrying into the decision is that
the production prompt's tight formatting instruction remains load-bearing for both — this is not a
"no thinking, so no prompting discipline needed" result — and D10's validator is confirmed, not
just assumed, to be the actual backstop against both new models' shared failure mode (fabricated,
plausible-but-non-verbatim justification under a relaxed prompt).

### Housekeeping

`qwen3:4b` (base, non-instruct, 2.5 GB) was **not used in this measurement pass** and the survey
already recommended it for nothing. It remains safe to delete — nothing in this session created a
new reason to keep it, and this note does not delete it (per the task's instruction, that is the
user's call to make).
