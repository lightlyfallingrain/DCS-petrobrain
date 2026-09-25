# Small local model survey for the brain layer (web search only, no pulls)

**Date:** 2026-09-25
**DCS version:** n/a — this is a web/publication survey, not a DCS-internals investigation
**Theatre:** n/a

### Question

`plans/brain-layer/plan.md` (D6, branch `feature/brain-layer`) picks `qwen2.5:7b-instruct` as the
runtime model for the brain layer's closed-vocabulary classify/discriminate calls, with
`llama3.2:3b` as fallback. Both were chosen from what happened to be on disk plus two quick pulls,
not from a survey of what exists. The user's objection: qwen2.5 is from September 2024 — two years
old as of today — and many small models have shipped since. This note surveys what has actually
been released in roughly the last 12–18 months and is available through Ollama, judged against the
brain layer's specific requirements (closed-vocabulary single-call answers, no chain-of-thought
dependency, sub-second warm latency, reliable structured/constrained output), **without pulling or
running anything**. Measurement against those criteria is deliberately left for a follow-up.

Written to `body-layer/research/` rather than `brain-layer/research/` because `brain-layer/` does
not exist yet as a subproject — the plan that will consume this lives at `plans/brain-layer/plan.md`
and the nearest existing module directory is `body-layer/`.

### Findings

**What's actually shipped in the window (confidence: read from primary source unless noted)**

- **Qwen3** (Alibaba, ~April–May 2025) introduced a global thinking/non-thinking toggle across
  sizes including 4B/8B — **evidence: documented** (Qwen's own model cards). This is the family
  already measured on this project's hardware in the plan (Measurement 1): `qwen3:14b` 16.0 s,
  `qwen3:4b` 32.7 s on a free-JSON prompt, because the smaller model's reasoning trace dominated
  cost and `/no_think` in the system prompt did not reliably suppress it — **evidence:
  reproduced-locally** (already in the plan, not re-tested here).
- **Qwen3-4B-Instruct-2507** (Alibaba, ~July 2025) is a *distinct, later* release from base Qwen3:4B
  — **evidence: documented**, Hugging Face model card. "This model supports only non-thinking mode
  and does not generate `<think></think>` blocks in its output" — the non-thinking behavior is
  architectural/training-time, not a runtime flag that can silently re-enable. Alibaba's own card
  claims improvements over the base 4B in "instruction following, logical reasoning, text
  comprehension, mathematics, science, coding and tool usage" — **evidence: documented claim, not
  independently measured**. Ollama tags exist: `qwen3:4b-instruct-2507-q4_K_M`,
  `-q8_0`, `-fp16` (official library) plus community mirrors — **evidence: documented** (ollama.com
  library pages).
- **Qwen3.5 small series** (Alibaba, ~March 2026 — **evidence: documented**, per Ollama's own
  announcement and Unsloth docs) ships 0.8B / 2B / 4B / 9B. Primary-source confirmation (Hugging
  Face model-card discussion threads for the GGUF releases, titled "Enabling or disabling reasoning
  (default is disabled)") states **reasoning is off by default** for this series, with an explicit
  `enable_thinking` flag to turn it back on — **evidence: documented**, but this is the same class
  of "switch" that failed to reliably disable thinking on Qwen3 (per the plan's own Measurement 1),
  so default-off is not the same guarantee as Qwen3-4B-Instruct-2507's architectural non-thinking.
  Ollama officially supports it (`ollama run qwen3.5:4b`, etc.) with native tool calling and
  multimodal claimed — **evidence: documented** (Ollama's own announcement). Very young (six months
  old at most as of today) — low community track record.
- **Gemma 3** (Google, announced 2025-03-12 — **evidence: documented**, Google Developers Blog).
  Sizes 1B/4B/12B/27B, instruction-tuned variants. No thinking/reasoning toggle exists in this
  family at all — it predates the reasoning-toggle trend in small open models, so there is no
  "disable it" question to ask. Google's own materials claim "structured outputs and function
  calling" support and strong multi-step instruction following — **evidence: documented claim, not
  independently measured**. Mature Ollama support (`gemma3:4b` etc., in the official library).
- **Phi-4-mini** (Microsoft, ~February 2025 — **evidence: documented** per community write-ups
  citing the release; not cross-checked against an official Microsoft dated post here). 3.8B dense,
  128K context claimed, native single- and parallel-function-calling support documented by
  Microsoft's own Tech Community blog post on building agents with it — **evidence: documented**.
  No separate reasoning mode in the base `Phi-4-mini`; Microsoft ships reasoning as a *separate*
  model (`Phi-4-mini-reasoning`), so picking the base variant avoids the thinking-mode question
  entirely, similar to Gemma 3. Ollama official library tag `phi4-mini` exists, requires Ollama
  ≥0.5.13 — **evidence: documented**.
- **IBM Granite 4.0** (released 2025-10-02 — **evidence: documented**, Hugging Face model cards /
  AI Wiki summary). Includes `granite-4.0-micro` (~3B, conventional transformer, dense) and
  `granite-4.0-h-micro` (~3B, hybrid Mamba-2/attention, lower memory for long context), plus larger
  h-tiny/h-small variants. IBM's own positioning explicitly names **tool-calling, structured JSON
  output, and agentic reliability** as design targets for this generation — **evidence: documented
  claim, not independently measured**, but notably it is a *design goal being claimed*, not an
  incidental benchmark number, which is a different (stronger) kind of claim than a leaderboard
  score. Apache-2.0 licensed. Official Ollama tags exist: `ibm/granite4:micro`,
  `ibm/granite4:micro-h`, plus quantized variants — **evidence: documented**. No reasoning-toggle
  complexity has surfaced in the search results for this generation; not confirmed either way from
  a primary source stating "no thinking mode exists," so treat as **inferred** until checked
  against IBM's own model card text directly.
- **SmolLM3-3B** (Hugging Face, mid-2025 per community sources — **evidence: forum-claim/community,
  not cross-checked against an official dated release post**). Dual-mode reasoning toggled by
  `/think` / `/no_think` tokens in the prompt — the same *prompt-based* toggle mechanism that failed
  to reliably suppress Qwen3's thinking, so it inherits that risk rather than avoiding it. No
  official Ollama library entry found — it is pulled via `ollama run hf.co/ggml-org/SmolLM3-3B-GGUF:*`
  or community mirrors (`alibayram/smollm3`, `Impulse2000/smollm3`), which is less turnkey and less
  vetted than an official `ollama.com/library/*` tag. Deprioritized on that basis.
- **Ministral 3 family** (Mistral AI, released 2025-12-02 — **evidence: documented**, multiple
  aggregator sources agree on this date though none is Mistral's own blog post directly fetched
  here, so treat the date as **forum/community-corroborated, not primary-source-verified**). Sizes
  3B, 8B, 14B. Mistral's chat-model line has traditionally shipped without a reasoning toggle at
  all (their reasoning models are the separate "Magistral" line) — **evidence: inferred**, not
  confirmed against a Ministral 3 model card directly in this session. Community Ollama tags exist
  (`nchapman/ministral-8b-instruct-2410` is the *older* Ministral-8B-2410, not the new Ministral 3
  — the newer 3B/8B/14B generation's exact Ollama tags were not confirmed in this pass). Flagged as
  a candidate worth a second look, not yet as vetted as the others above.
- **Llama family**: no small (≤8B) release in this window beyond the already-known `llama3.2:3b/1b`
  (September 2024, itself now ~24 months old). Llama 4 (April 2025) is Scout/Maverick, both
  mixture-of-experts with double-digit-billion *active* parameters — not a small-model candidate.
  Meta then pivoted away from open small-model releases toward closed-weight "Muse Spark" (reported
  April 2026) — **evidence: community-reported, not independently verified**. **Llama is not a
  live small-model lead for this window.**
- **Mistral Small 3.1/3.2** (April/June 2025) exist and do tool calling well, but at 24B they are
  well outside "small" for this use case (compare: current pick is 7B) and Mistral 3.2's tool
  parser has open, reported bugs in some Ollama builds (`ollama/ollama` issue #11155) — **evidence:
  forum-claim/GitHub-issue, not verified against a current Ollama build here**. Not a candidate;
  noted only to rule it out explicitly since it's an obvious-looking name.

**Cross-cutting observation on the thinking-mode disqualifier**

At the time D6 was written, the only alternative to qwen2.5 that had been tried was `qwen3`, whose
thinking could not be reliably switched off via `/no_think`. The survey shows the landscape has
since split into two genuinely different mechanisms, not just more of the same:

1. **Architecturally non-thinking models** — no `<think>` capability exists at all in the weights
   (Qwen3-4B-Instruct-2507, Gemma 3, Phi-4-mini base). There is no flag to fail to honour, because
   there is nothing to suppress.
2. **Default-off, prompt/config-toggleable models** — thinking exists and is off by default, but is
   still a switch (Qwen3.5 small series). This is closer to what already failed on plain Qwen3 and
   should be treated with the same suspicion until measured, regardless of the "default disabled"
   framing in its own docs.

This distinction did not exist as cleanly a year ago and is worth encoding in whatever replaces D6:
**prefer category 1 over category 2** when both are otherwise comparable, specifically because the
plan's own Measurement 1 already demonstrated category-2 failure mode once.

### Reproducible Test

None run — this was a web-search-only survey per the task constraint (no pulls, no local
measurement). All "documented" findings above trace to the cited primary source (model card,
official blog post, or `ollama.com/library/*` page); "claim, not independently measured" findings
are the publisher's own stated capability, not a benchmark this project ran. A follow-up
measurement pass (same shape as the plan's Measurements 2–4: warm/cold latency, `/no_think`
reliability if applicable, closed-vocabulary accuracy on the plan's own test cases including the
ambiguous-reference case) is the natural next step and is explicitly out of scope for this note.

### Possible Approaches — shortlist for the follow-up measurement pass

Ranked, each with the specific hypothesis it tests against the current `qwen2.5:7b-instruct` pick:

1. **`qwen3:4b-instruct-2507` (q4_K_M)** — top pick. Same publisher/family as the current default
   (lowest migration risk, same prompt conventions likely transfer), architecturally non-thinking
   (removes the D6 disqualifier by construction rather than by flag), smaller footprint than the
   current 7B pick (~2.5 GB vs 4.7 GB at q4), and one release generation newer with Alibaba's own
   claimed tool-use/instruction-following improvements. **Hypothesis to test:** matches or beats
   `qwen2.5:7b-instruct`'s closed-vocabulary accuracy and "rejects nonsense unprompted" behavior
   (plan's M3 case 3) at lower latency and smaller memory footprint, with no thinking traces ever
   observed in output.
2. **`ibm/granite4:micro` or `granite4:micro-h`** — IBM explicitly targets structured
   JSON/tool-calling reliability as a design goal for this generation, which is a direct hit on the
   brain layer's core requirement rather than a general-capability bet. Different architecture
   family from Qwen (diversifies the comparison rather than just re-testing Alibaba's roadmap).
   **Hypothesis to test:** structured/closed-vocabulary output is at least as reliable as
   `qwen2.5:7b-instruct` at a smaller footprint (~3B dense or hybrid), which — if true — is worth
   reporting to Architect even though it does not remove the validator (D10 is defence-in-depth by
   design, independent of model choice).
3. **`gemma3:4b-instruct`** — a non-Qwen baseline with no reasoning-toggle question at all (the
   family simply doesn't have one), Google's own claimed structured-output/function-calling
   support, and the most mature/widely-used Ollama integration of the three. **Hypothesis to test:**
   comparable latency and reliability to (1) and (2) as a hedge — if Qwen's 2507 tuning turns out to
   have a rough edge on this project's specific narrow prompts, Gemma is the fallback candidate
   rather than reaching back to `llama3.2:3b` (which is the one known to guess on ambiguous
   references per M4).
4. **`qwen3.5:4b`** (stretch, test last if time allows) — newest of the four, native tool calling
   and multimodal claimed, reasoning off by default per a primary source. **Hypothesis to test:**
   whether the "default-off" toggle actually holds under the same adversarial conditions
   (Measurement 1's free-JSON prompt shape) that broke plain Qwen3's `/no_think` — this is
   explicitly the test that would most directly confirm or refute the cross-cutting observation
   above, not a pure accuracy/latency bet.

`llama3.2:3b` stays in the comparison set as the existing fallback and the only candidate already
measured on this machine (0.13–0.17 s warm) — not because the survey found it to still be the best
choice, but because it is the only apples-to-apples baseline until the shortlist above is actually
run.

### Unresolved

- **No candidate above has been pulled or measured on this machine.** Every latency, memory, and
  "reliable at constrained output" claim in this note is the publisher's own claim or a secondary
  source's summary of it — none is a measurement, per the task's own instruction not to present a
  benchmark as though it were latency on this machine. Architect/user should treat this as an
  input to a measurement plan, not a decision.
- **Ministral 3's exact Ollama tags and reasoning-mode status were not confirmed from a primary
  source.** Worth a follow-up look before including it in an active measurement pass; not included
  in the ranked shortlist above for that reason.
- **Granite 4.0's reasoning-mode status ("no thinking mode exists at all" vs. "has one and it's off
  by default") was not confirmed from IBM's own model card text in this pass** — inferred from the
  absence of any reasoning-toggle mention in the sources found, which is weaker evidence than an
  explicit statement. Worth 5 minutes reading the actual `ibm-granite/granite-4.0-micro` model card
  before the measurement pass, since it changes which risk category (1 or 2, per the cross-cutting
  observation above) it falls into.
- **Qwen3.5 small series is six months old at most** (March 2026) — no independent track record of
  its default-off reasoning holding up under adversarial prompts was found; this is exactly what
  candidate 4's hypothesis test is for.
- **Structured-output/tool-calling claims across all vendors are marketing-adjacent copy**
  ("excels at," "state-of-the-art") rather than reproducible numbers in most of what was found; none
  of it should be read as more than a reason to prioritize which model to measure first.

### Bottom line for the user

The search did turn up something meaningfully better-positioned than `qwen2.5:7b-instruct`:
several small models released in the last 12–14 months (`qwen3:4b-instruct-2507` chief among them)
are **architecturally non-thinking** rather than merely toggle-able, which directly targets the
project's own worst measured failure mode (qwen3's thinking budget) without the toggle-reliability
risk. That is a real, checkable improvement over the current pick — not a fishing-trip result — but
it is a hypothesis backed by publisher claims and family reasoning, not yet a measurement. The
existing `qwen2.5:7b-instruct` / `llama3.2:3b` pair stays the working default until the shortlist
above is actually pulled and run through the plan's own measurement harness (same shape as
Measurements 1–4).
