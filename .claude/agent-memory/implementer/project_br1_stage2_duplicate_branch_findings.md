---
name: br1-stage2-duplicate-branch-findings
description: Findings that existed only on the retired duplicate BR-1 Stage 2 branch — PICK is structurally unreachable from a bare ambiguous reference, and real-model latency is ~5x D6's probe figure
metadata:
  type: project
---

Harvested 2026-10-10 from `feature/br1-stage2`, the **duplicate** BR-1 Stage 2 implementation —
the milestone was built twice by two sessions unaware of each other, and `main` took the other
branch (`feature/brain-layer-stage2`, merged `4bc0df9`). The code was folded or deliberately
rejected per `plans/brain-layer/implementation.md`'s "Folding in the duplicate branch", but the
two findings below existed **nowhere on `main`** and would have gone with the branch.

**Why they were nearly lost, and this is the transferable part: both sessions wrote their memory to
the same filename with the same `name:` slug** (`project_br1_stage2_ollama_decider.md`,
`name: br1-stage2-ollama-decider`). Same milestone, same role, so the obvious filename collided —
and whichever landed second would silently replace the other. `main` holds that branch's version;
this file is deliberately named for the *branch*, not the milestone. When a milestone may be
implemented more than once, scope the memory filename to the attempt.

**Finding A — `PICK` is structurally unreachable from a bare ambiguous reference, and this is
provable rather than observed.** `belief.tools.find_contact` requires the *reference text* to be a
substring of the classification value, not the reverse. So for an ambiguous match (needle `"bmp"`
matching both `BMP-1` and `BMP-2`), every substring of that needle is by construction common to
every matched candidate — nothing in it can discriminate. And any extra descriptive word in the
reference breaks the match entirely, giving 0 candidates and `NO_MATCH` rather than an ambiguity.
So a 2+-candidate escalation through *this* grammar never carries transcript text that could
validly discriminate, and `PICK` from that path cannot pass D10 at all.

Confirmed live against the real model, not only argued: `qwen3:4b-instruct-2507-q4_K_M` on a richer
transcript (`"...near the village"`) quoted the **entire transcript** as its `BECAUSE` rather than
the discriminating phrase, and D10 degraded it to `ASK` every time.

**How to apply:** `PICK` is effectively dead until a phrasing surface exists that lets
discriminating text survive alongside an ambiguous reference — not built as of Stage 2. Do not read
"`PICK` never fires in testing" as a model-quality problem or a validator bug; it is the grammar.
This bears on anything downstream that assumes `PICK` is a live path, including Stage 3's A/B
answer leg and `feature/d10-structured-candidates`.

**Finding B — real-model latency is ~5x D6's own table figure, and D6's figure is not wrong, it is
measuring something else.** Measured warm, `num_ctx=2048`, 2026-09-25:

| call | range | mean (n=5) |
|---|---|---|
| discriminate | ~310–340 ms | 318 ms |
| classify | ~118–186 ms | 132 ms |

Both sit comfortably inside the 5–10 s budget, so this is not a performance problem. It matters
because **D6's 38–63 ms table was taken against a minimal bare-candidate probe**, and the gap is
prompt-eval time over the fuller command table — that branch's classify vocabulary was 44 tokens
(see `[[BR-B1]]`, which preserves it). So the figure scales with vocabulary size: cite D6 for the
floor, these numbers for a real prompt, and expect any widening of
`CLASSIFY_COMMAND_VOCABULARY` to move classify specifically.

**Also recorded, for the avoidance of a repeat claim:** this branch *did* run a real model on
2026-09-25. `[[BR-1.2]]` says "nothing in this feature has ever talked to a real model", which is
true of the branch `main` took — whose sandboxes had no route to `127.0.0.1:11434` — and false of
this one. Both halves matter: the gates have been exercised against real model output, and the
milestone is still unflown.

**Finding C — a plan's own worked example is a better test oracle than a hand-written fixture.**
Both D10 defects that branch found were found the same way: by writing the plan's own worked
example (`PICK CONTACT_7 BECAUSE "tank"` against two T-72s) as a test and watching it fail — not by
re-reading the plan more carefully. A hand-written "obviously passes" fixture encodes the author's
reading of the spec, so it agrees with whatever the implementation already does; the spec's own
example was chosen by whoever understood the hard case. The same shape recurred in the fold, where
two existing tests on the *other* branch were asserting the buggy quoted output as correct.

**Checked, and NOT harvested, because `main` already has them:** that branch's Findings 1 and 2 —
`matched_intent is None` cannot mean unconditional structural `NO_SUCH_COMMAND` (resolution: route
to a classify call), and D10's "not equally true of another candidate" needing the three-part
transcript/chosen-`why`/not-other-`why` check — are both in `main`'s sibling memory under different
wording, with the same resolutions. Its poll-timeout note was deliberately rejected at the fold
(`implementation.md` item 5: `main` solved it structurally instead). So this file plus `[[BR-B1]]`
is the whole of what was branch-only.

Related: [[BR-1.2]], [[BR-B1]], and `main`'s own
[sibling memory](project_br1_stage2_ollama_decider.md) from the branch that shipped.
