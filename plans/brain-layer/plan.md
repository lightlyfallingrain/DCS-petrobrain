# BR-1 — the brain layer's first real slice

**Branch:** `feature/brain-layer` · **Planned:** 2026-09-24/25 (architect, opus)

**Binding source:** `plans/brain-layer/explore-notes.md` (this branch). That file records an
`/explore` conversation with the user and **outranks the older concept documents wherever they
disagree** — in particular `docs/concept/PETROBRAIN_RUNTIME.md`'s "Runtime LLM role" section, which
casts the model as the phrasing layer on every structured event. The user's answers contradict that
directly, and this plan follows the user.

Two further user constraints arrived mid-design and are treated as binding on the same footing:

> "Brain cannot be synchronous. It may be able to process only one thing at a time (hopefully
> more), but it cannot block anything, the game world moves on."

> "brain does need to be pretty fast. That means small model. Brain architecture and inference it
> has to do, must support small model operations."

The second is an **architectural** constraint, not a deployment one: the design may only ever ask
the model to do things a small model is actually good at. If a behaviour needs a large model, the
design is wrong, not the model.

---

## What was measured before designing

Every latency and reliability figure below was measured on the user's own machine (Apple M1 Max,
32 GB, macOS) on 2026-09-25, through the already-installed Ollama daemon. Nothing here is taken
from a published benchmark.

### Measurement 1 — reasoning tokens dominate latency, not model size

Same prompt (a JSON-emitting "decide what to do about this utterance" call, the shape the older
concept doc implies), warm model, thinking suppressed as far as the CLI allows:

| model | wall time | note |
|---|---|---|
| `qwen3:14b` | **16.0 s** | correct answer, well-formed JSON |
| `qwen3:4b` | **32.7 s** | *slower than the 14B*, and the answer text was a verbatim echo of the transcript |

The 4B being twice as slow as the 14B is the finding. `/no_think` does not reliably suppress
qwen3's reasoning trace, and the reasoning trace — not the parameter count — is what costs the
seconds. **A reasoning model's thinking budget is what blows a 5–10 s target**, and a smaller
reasoning model can be worse, not better.

### Measurement 2 — a closed, short answer collapses the latency to nothing

Reframed as pick-from-a-closed-list, output capped at one line:

| model | cold (incl. load) | warm | output tokens | prompt tokens |
|---|---|---|---|---|
| `llama3.2:3b` | 1.36 s | **0.13–0.17 s** | 6 | ~155 |
| `qwen2.5:7b-instruct` | 1.79 s | **sub-second** | 6 | ~155 |

`llama3.2:3b` measured 770 tok/s prompt eval, 100 tok/s generation.

**This is the single most consequential number in the plan.** At six output tokens the brain is
two orders of magnitude inside the user's 5–10 s budget. Latency therefore stops being the binding
constraint on model choice — **memory residency and reliability become the binding constraints**,
and the design can afford a materially better model than "as small as possible" would suggest.

### Measurement 3 — small models silently guess, which is the one thing this project forbids

Three cases, plain pick-from-list prompt. Candidates: `CONTACT_7` (T-72, 2.1 km, near Gemerek
village) and `CONTACT_12` (T-72, 3.4 km, on the road).

| pilot said | correct answer | `llama3.2:3b` | `qwen2.5:7b-instruct` |
|---|---|---|---|
| "keep an eye on the tank by the village" | `PICK CONTACT_7` | ✅ `PICK CONTACT_7` | ✅ `PICK CONTACT_7` |
| "keep an eye on that tank" (genuinely ambiguous) | `ASK` | ❌ `PICK CONTACT_12` | ❌ `PICK CONTACT_7` |
| "the grass over there is looking rather brown today" | `SAYAGAIN` | ❌ `PICK CONTACT_12` | ✅ `SAYAGAIN` |

Both models **silently picked** on a reference that genuinely did not resolve. That is exactly the
failure `belief/voice_commands.py`'s module docstring already names as behaviour #2 — *"Ambiguous
is never a silent best guess"* — and it is not fixable by buying a slightly bigger model.

### Measurement 4 — the fix, and it works on both models

Reframed so the **code** owns the ambiguity finding and the model may only *override* it by
quoting evidence from the pilot's own words:

> The code has ALREADY established that the pilot's reference is ambiguous. Your ONLY job is to
> decide whether the pilot's own words contain something that singles out one candidate. You must
> quote those words verbatim. Reply `PICK <id> BECAUSE <words>` or `ASK`. Use `ASK` unless the
> pilot's words clearly name something true of one candidate and not the other.

Same ambiguous case ("keep an eye on that tank"):

| model | reply | outcome after the deterministic validator |
|---|---|---|
| `qwen2.5:7b-instruct` | `ASK` | **asks** ✅ |
| `llama3.2:3b` | `PICK CONTACT_7 BECAUSE "tank"` | `"tank"` is true of *both* candidates → pick **rejected** → **asks** ✅ |

The 7B got it right on its own; the 3B got it wrong and **the validator caught it**, because the
model was forced to name its evidence and the evidence did not discriminate.

**Conclusion that shapes the whole design: model quality determines how often Petrovich *asks*,
never whether he *acts wrongly*.** Model choice becomes a tuning knob rather than a correctness
dependency. That is what makes it safe to treat the model as swappable.

*(Models pulled onto the user's disk during this investigation: `qwen3:4b` 2.5 GB, `llama3.2:3b`
2.0 GB, `qwen2.5:7b-instruct` 4.7 GB — and, in the 2026-09-25 follow-up pass,
`qwen3:4b-instruct-2507-q4_K_M` 2.5 GB and `granite4:micro` 2.1 GB. `qwen3:4b` is not recommended
for anything and can be deleted.)*

**The measurements above stand as the record of how D6's criteria were arrived at, and those
criteria are unchanged. D6's *choice* is not what is recorded here any more** — see D6 itself, and
`body-layer/research/2026-09-25-small-model-measurements.md`. The four findings that mattered
(reasoning tokens rather than model size set latency; a closed answer collapses latency to
nothing; small models silently guess on a genuinely ambiguous reference; and the verbatim-quote
validator fixes that on every model tried) all survived the re-measurement intact.

---

## Goal

Give Petrovich a second, slow, deliberative loop that turns free-text speech he cannot parse into
one of three honest responses — **"unable, `<reason>`"**, **"confirm `<command>`?"**, and **"which
one — A or B?"** — without ever blocking the 5 Hz perception loop and without ever inventing world
state.

---

## Scope

**In scope — three behaviours, all riding one idle round trip, no new tools:**

1. Heard clearly, maps to nothing Petrovich can do → **"unable, `<reason>`"** (D11).
2. Heard clearly, plausibly a command the deterministic grammar missed → **"Confirm `<command>`?"**,
   committed or discarded by the existing yes/no mechanism.
3. Heard clearly, refers to a contact but two or more fit → **"which one — the one by the village,
   or the one on the road?"**, answered by the pilot naming one.

**Explicitly not in scope** (named here so nobody designs them in; sequencing at the end):

- Reference resolution as a general capability, conversational memory, mission relevance, the
  mission briefing, attack run, interrupt/resume, autonomous danger reporting.
- **The general `unable <reason>` vocabulary is still BR-6's.** BR-1 ships the three specific
  reasons D11 names, which are free from state the code already holds — not a mechanism for
  attaching a reason to arbitrary refusals.
- **Any change to `belief/tools.py`.** The tool API is frozen at 15 tools since BL-6. BR-1 needs
  **zero** tool calls — all three behaviours are answerable from the `EscalationPayload` alone.
  If implementation finds it needs a sixteenth tool, that is an escalation to the user, not a
  design decision.
- Any change to the deterministic speech path. Contact reports, readbacks, clock/range and threat
  callouts stay sub-second and never touch a model.

---

## The seam as it actually is (surveyed, not assumed)

- `belief/escalation.py` — `BrainClient.handle(payload) -> **None**`. **The protocol is already
  fire-and-forget**: it was never designed to return an utterance. `awaiting_reply_id()` is a
  separate query, and `EscalationPayload.awaiting_reply_to` already exists. Neither has ever
  returned non-`None`. Nothing in the existing seam forces synchrony.
- **There is no reply path at all.** `_handle_utterance` calls `handle_player_utterance(...)` and
  then `return []`. That `[]` is the dead end this slice exists to fill.
- `belief/crew_console.py` — `handle_transcript` already implements act/confirm/say-again bands
  deterministically, and `_act_on_voice_decision`'s `"fallthrough"` (i.e. `verb_anchored=False`)
  routes to `handle_line` → `_handle_utterance` → escalation → silence. **The fallthrough band is
  the brain's territory and it is currently 100% silent.**
- `belief/voice_commands.py` — `PendingConfirmation` + `classify_yes_no` + `CONFIRM_WINDOW_S`
  (8.0 s) is a **working confirm round trip**. BR-1 reuses it; it does not build a second one.
- `belief/tool_api.py` — `TOOL_SET` is deliberately **transport-agnostic**: *"no HTTP this
  milestone; the registry is what a thin HTTP/RPC adapter would wrap later."* There is no tool
  server. Body-layer today is a pure HTTP **client** (`aircraft_client`, `audio_client`) and has
  never been a server.
- `logger.py` — `--brain-client debug|null` is the selection point; `_run_crew_text_poll_loop`
  already drains two external sources per tick (`_poll_f10_commands`, `_poll_transcripts`). That is
  the established pattern for pulling asynchronous input into the loop.

---

## Decisions

### D1 — The brain is a separate subproject and a separate process (`brain-layer/`), spoken to over HTTP

**Provenance:** code + project rule, not the explore conversation.

Root `CLAUDE.md`: HTTP/JSON across a subproject boundary is the default; the body-layer↔world-model
in-process import is the *sole* sanctioned exception. `brain-layer/` gets its own venv and is
started like `aircraft-layer` and `audio-adapter` already are.

The usual counter-argument — "but then the brain can't call the 15 tools" — **does not apply to
BR-1**, which needs zero tool calls, and is weaker than it looks in general: `parse_utterance`
already runs `find_contact` body-side and puts the narrowed candidates in the payload. That is
§3.3's own design (*"body-side deterministic matching… the brain supplies the phrase and picks
among the candidates"*), and it is also exactly what the small-model constraint demands — the code
narrows, the model picks. Building an HTTP tool server is therefore deferred until something
actually needs one, and may never be needed.

The decisive practical argument is **prompt iteration**. The next month of this layer's life is
tuning prompts. In-process, every prompt edit costs a body-layer restart and the loss of all
contact belief; out-of-process, the brain restarts alone and the sortie continues.

**Rejected:** a `body-layer/src/brain/` module. Cheaper for BR-1 by about a day, but it makes the
brain non-restartable, contradicts the module-independence default, and gives the capable-model
briefing (explore notes §8) nowhere natural to live.

**Cost, stated honestly:** a third process to start, a third venv, one more thing that can be down.
Mitigated by D7 — when the brain is unreachable, body behaves exactly as it does today.

### D2 — `handle()` returns immediately; replies arrive by polling

**Provenance:** user constraint ("Brain cannot be synchronous… it cannot block anything").

`BrainLayerClient.handle(payload)` does one HTTP POST with a short timeout (0.5 s), returns, and
that is all. The brain replies into its own queue. Body drains it once per poll tick with
`crew_console.drain_brain(now_sim)`, placed next to the existing `drain_events` /
`_poll_f10_commands` / `_poll_transcripts` calls in `_run_crew_text_poll_loop`.

This adds one method to the `BrainClient` protocol:

```python
def poll_replies(self) -> list[BrainReply]: ...
```

Changing `escalation.py`'s protocol is allowed; changing `tools.py` is not. `NullBrainClient` and
`DebugPrintBrainClient` return `[]`, so their documented behaviour is unchanged.

**Why polling rather than a callback or a thread handing lines to `_print`:** every other
asynchronous input into this loop already arrives by polling, `_print` is not thread-safe, and a
poll keeps all speech on the one thread that owns `CalloutScheduler`'s occupancy model.

**The POST itself must not block either.** A 0.5 s timeout on a 5 Hz loop (200 ms budget) is still
too long if the brain is wedged. The client therefore posts from a single-slot background worker
thread; `handle()` hands over and returns in microseconds. If the worker is busy, D3 applies.

### D3 — One job in flight; the newest utterance wins

**Provenance:** user constraint ("only one thing at a time… hopefully more" — treated as one).

The brain holds **at most one** job. A new escalation arriving while one is in flight **replaces**
it; the abandoned job's reply is discarded by `utterance_id` when it lands.

**Not FIFO.** The second utterance is usually the more important one — *"no, the other one"*,
*"cancel that"* — and a queue answers the stale question first. Answering a 10-second-old question
after the pilot has moved on is worse than not answering it.

**One exception:** an utterance whose `awaiting_reply_to` matches the currently-open question is the
*answer* to it, not a replacement, and must not cancel anything.

**Revisit if:** the pilot's own speech turns out to routinely arrive in pairs where both matter.
Cheap to change — it is one policy check in the brain's job slot.

### D4 — A reply is validated against *current* belief before it is spoken or acted on

**Provenance:** user constraint ("the game world moves on").

In the seconds a reply takes, a contact can be lost, reclassified, or merged into another. So every
contact id in a reply is re-checked against the store at drain time, not at question time.
`EscalationPayload.t_sim` already gives the question's age for free.

| situation at drain time | Petrovich does |
|---|---|
| reply older than `BRAIN_REPLY_MAX_AGE_S` (**20 s**, unmeasured, see Risks) | discard silently, log it |
| `PICK <id>`, contact still present | act, and read back as today |
| `PICK <id>`, contact gone | **"lost him"** — a new `render_lost_contact` template. Not silence: the pilot asked for something and deserves to know why nothing happened |
| `ASK`, ≥2 candidates still present | ask, using the survivors |
| `ASK`, exactly 1 candidate still present | the ambiguity resolved itself — **confirm** the survivor rather than acting on it, because "only one left" is not the same as "the pilot meant this one" |
| `ASK`, 0 candidates still present | **"lost him"** |
| `CONFIRM <token>` | no contact id to revalidate; proceed |

**Acting on a contact id that has since been merged is the failure mode being designed out.** The
id check is the whole defence and it is deterministic.

### D5 — The model classifies against a closed set; it never writes what Petrovich says

**Provenance:** user constraint (small-model architecture) + Measurements 2–4.

The model's entire output is one line drawn from a closed vocabulary — `PICK <id> BECAUSE <words>`,
`ASK`, `CONFIRM <token>`, or `SAYAGAIN`. Six tokens, measured. **The spoken line is rendered by
`belief/speech.py` from body-owned templates and the candidates' own `why` strings.** The model
never phrases anything.

This is stricter than *"code owns truth, models own interpretation and language"* — it takes
language away from the model too. That is deliberate for BR-1: it is the only way to keep the
round trip sub-second, it makes the output trivially validatable, and Measurement 1 showed the free-
generation alternative produced a transcript echo where a sentence was wanted. The model is still
doing the thing only it can do — **mapping free speech onto a closed intent set the regex table in
`utterance.py` could not match.** That is interpretation, and it is the whole value.

Checked against each of the small-model constraints:

- *One narrow decision per call* — ✅ two prompt shapes, each one question. The classify call and
  the discriminate call are separate calls, not two reasoning steps in one.
- *Closed output vocabulary* — ✅ a contact id from a code-assembled list, or a token from
  `DISPATCHED_COMMAND_TOKENS`, or one of two refusals.
- *Small, pre-narrowed context* — ✅ ~155 prompt tokens, measured. `parse_utterance` supplies the
  candidates; the store is never dumped.
- *No arithmetic, geometry or ranking* — ✅ the model never sees a bearing to compute or two ranges
  to compare. Ranges appear only as already-rendered English inside a candidate's `why`.
- *Classification over generation* — ✅ throughout.
- *No chain-of-thought dependency* — ✅ and enforced by model choice (D6).

### D6 — Default `qwen3:4b-instruct-2507-q4_K_M`; fallback `granite4:micro`; both a config value, not a constant

**Provenance:** measured on this machine, not published benchmarks. **Revised 2026-09-25** — see
`body-layer/research/2026-09-25-small-model-measurements.md`. The original pick
(`qwen2.5:7b-instruct` / `llama3.2:3b`) came from measuring what happened to be on the disk; the
user objected that qwen2.5 dates from September 2024 and asked for the current landscape to be
surveyed by search before anything was pulled. Both replacements beat the incumbent pair outright.

| | `qwen3:4b-instruct-2507-q4_K_M` (default) | `granite4:micro` (fallback) |
|---|---|---|
| On disk | 2.5 GB | 2.1 GB (3.4B params) |
| **Resident, Ollama default 32k ctx** | **7.5 GB** | **5.0 GB** |
| **Resident, `num_ctx=2048`** | **2.9 GB** | **2.3 GB** |
| Warm latency, closed answer | **38–63 ms** | **30–49 ms** |
| `<think>` trace observed | never, 0 of ~20 runs including adversarial | never |
| Ambiguous reference ("that tank", two T-72s) | **ASK 5/5** | **ASK 5/5** |
| Discriminating reference ("by the village") | PICK correct 4/4 | PICK correct 3/4, ASK 1/4 |

**The margin is not marginal.** The incumbent's *best* behaviour — asking rather than guessing on a
genuinely ambiguous reference — is what both replacements do by default, at **under a tenth of the
latency and roughly half the disk**. `qwen3:4b-instruct-2507` is architecturally non-thinking: the
`<think>` capability is absent from the weights, so there is no flag that can fail to suppress it,
which is precisely how plain `qwen3:4b` reached 32.7 s.

**Set `num_ctx` explicitly — the default costs 4.6 GB of nothing.** Resident footprint is about
three times disk size at Ollama's default 32768 context, and almost all of that gap is KV cache.
BR-1's prompts are **~155 tokens**. Measured on this machine 2026-09-25: dropping to
`num_ctx=2048` takes the default model from 7.5 GB to **2.9 GB** and the fallback from 5.0 GB to
**2.3 GB**. Earlier drafts of this decision argued footprint from *disk* size, which understated
the real cost by 3x and would have made the two-tier budget below look impossible. Stage 2 sets
`num_ctx` explicitly rather than inheriting the default.

**Tag correction, found by measuring rather than reading:** bare `qwen3:4b-instruct-2507` does
**not** resolve on Ollama — only quant-suffixed tags do, hence `-q4_K_M`. `granite4:micro` resolves
directly, with no `ibm/` prefix.

**The validator stays load-bearing, and this was confirmed rather than assumed.** Neither model has
a hidden thinking budget, but **both fabricate a plausible, non-verbatim justification when the
prompt invites deliberation or loses its tight one-line formatting instruction** — `qwen3` told to
"think step by step" produced 575 tokens over 11 s and picked wrong; both models picked wrong when
the formatting instruction was removed. D10's verbatim-quote check caught every one of those
failures. So the production prompt's terseness is a load-bearing part of the design, not a style
choice, and the validator is not redundant with a better model.

#### Superseded, kept for the reasoning

The original measurement that set D6's *criteria* — which stand unchanged, and which the new picks
were judged against.

| | `qwen2.5:7b-instruct` (default) | `llama3.2:3b` (fallback) |
|---|---|---|
| Ollama tag / size | `qwen2.5:7b-instruct`, 4.7 GB (q4_K_M default) | `llama3.2:3b`, 2.0 GB |
| Warm latency, 6-token answer | sub-second | 0.13–0.17 s |
| Cold, incl. load | 1.79 s | 1.36 s |
| Mandatory thinking budget | **none** | **none** |
| Rejects nonsense unprompted (M3 case 3) | ✅ | ❌ |
| Refuses an ambiguous reference (M4) | ✅ on its own | ❌, caught by the validator |

**Why not a qwen3:** measured at 16 s and 32 s (Measurement 1). Its thinking budget cannot be
reliably switched off from the CLI and is the entire latency problem.

**Why not smaller than 3B:** nothing smaller was tested, and the 3B is already the one that guesses.

**Memory:** the brain model sits alongside whisper `small.en` (~0.5 GB) and, *between sorties*,
`qwen3:14b` (9.3 GB) for the Mission Interpreter. The user's own compute-topology note has the
model swapping only at briefing or on the ground, so the runtime model is chosen once per sortie
and lives for its duration — 4.7 GB resident is comfortable on 32 GB.

**Untested but plausible if the 7B disappoints in flight:** `granite3.3:8b`, `mistral:7b-instruct`.
Named as candidates, not recommendations — nobody has run them on this box.

**The model is expected to be swapped.** `--brain-model` is a brain-layer CLI argument with the
default above; no model name is compiled into any logic. One command re-checks the plan's load-
bearing number:

```sh
cat plans/brain-layer/probe-prompt.txt | ollama run <model> --verbose
```

### D7 — Absence is silence; being half-heard is a question

**Provenance:** explore notes §3, refining `NullBrainClient`'s documented posture.

The explore notes retire *"silence is honest, a guessed response is not"* as the **only** answer,
not entirely. Precisely:

| case | behaviour | changed by BR-1? |
|---|---|---|
| Nothing heard — the adapter's signal gate rejected the clip | nothing reaches body at all | no |
| Garbled, verb-anchored, below `CONFIRM_FLOOR` | deterministic **"say again"** — speech not understood | no — **already works, brain never sees it** |
| Marginal, verb-anchored, confirm band | deterministic "Confirm X?" | no — **already works** |
| Heard clearly, no verb anchor (`fallthrough`) | **silence today → one of the three behaviours** | **yes, this is BR-1** |
| Brain unreachable, wedged, or timed out | silence, exactly as `NullBrainClient` | no |

**Worth saying plainly, because the brief's framing invites the opposite conclusion: the classic
"STT clearly failed → say again" case is already deterministic and does not reach the brain at
all.** What reaches the brain is a different failure — speech heard perfectly that maps to no
available action — and it answers **"unable"**, never "say again". See D11.

### D8 — "Stand by" is decided by body, deterministically, and needs no model

**Provenance:** explore notes §1.

The poll loop knows an escalation is in flight and knows how long. If no reply has landed within
`STAND_BY_AFTER_S` (**2.0 s**, unmeasured), it speaks "stand by" **once** per question, through the
normal `_print` funnel. No model involvement, no risk of the stand-by itself being slow.

On the measured numbers this will almost never fire in BR-1 — which is the honest outcome, and the
mechanism still earns its place because it fires on the one case that *does* exceed it: the first
call after the model is evicted from memory (1.4–1.8 s cold, and worse under memory pressure).
Mitigate by issuing one throwaway warm-up generation when `brain-layer` starts.

### D9 — The brain's confirm reuses `PendingConfirmation`; the A/B answer reuses `awaiting_reply_to`

**Provenance:** code survey; the explore notes require asking rather than guessing but not the
mechanism.

A `CONFIRM <token>` reply sets `CrewConsole._pending_confirmation` — the same field, window
(`CONFIRM_WINDOW_S`) and `classify_yes_no` vocabulary the voice path already uses. **There is not a
second confirm mechanism.** The only difference is provenance: the token came from the brain rather
than from `command_matcher`.

An `ASK` reply cannot use that mechanism, because the answer is not yes/no. It instead uses the
round trip the seam was built for and has never exercised:

1. Brain returns `ASK`; body renders *"which one — the one by the village, or the one on the road?"*
   from the candidates' `why` strings and records the question id.
2. `BrainClient.awaiting_reply_id()` now returns non-`None` **for the first time in this codebase.**
3. The pilot's next utterance is escalated with `awaiting_reply_to` set to that id.
4. The brain runs the *same* discriminate prompt, now against the answer text ("the road one"),
   where the discriminator does resolve.

Two brain calls, each sub-second measured. No new state machine, no new yes/no vocabulary, and it
puts the dormant half of the protocol to its designed use.

### D10 — The validator is deterministic, body-side, and not optional

**Provenance:** Measurements 3 and 4.

Every reply passes a pure function before anything happens:

1. The reply is one of the four allowed forms, or it is **rejected**.
2. `PICK <id>` — `<id>` must be one of the candidate ids *this payload supplied*. Not "a contact
   that exists": one that was offered. Rejected otherwise.
3. `PICK … BECAUSE <words>` — `<words>` must appear literally (case-insensitively) in the
   transcript, **and** must not be equally true of another candidate. This is what turned the 3B's
   wrong `PICK CONTACT_7 BECAUSE "tank"` into a correct `ASK`.
4. `CONFIRM <token>` — `<token>` must be in `DISPATCHED_COMMAND_TOKENS`. Rejected otherwise.
5. `UNABLE <reason>` — `<reason>` must be one of D11's three tokens. Rejected otherwise.
6. **Any rejection degrades to `ASK` if there are candidates, else to `UNABLE NO_MATCH`** (D11 —
   previously "say again", corrected 2026-09-25: the speech was heard perfectly by construction, so
   asking for it again is the wrong answer). A rejection is never an error the pilot hears about and
   never silence — it is Petrovich asking, or saying plainly that he cannot, instead of guessing.

Where the "equally true of another candidate" test gets its text: the candidate `why` strings the
code already assembled. No new data, no geometry, no model involvement.

### D11 — "Unable" carries a reason, from a closed set the code owns

**Provenance:** user, 2026-09-25, resolving the first open decision above — *"'unable `<because>`'
is of course most useful"*, and then, on whether BR-1 should carry it: *"since cheap, do it"*.

BR-1's first behaviour is **"unable, `<reason>`"**, with the reason drawn from a closed set. The
three that are free — knowable from state the code already holds at the moment of escalation, with
no new mechanism, no tool call and no geometry:

| reason | when | what the code already knows |
|---|---|---|
| `NO_SUCH_COMMAND` | verb-like, but nothing in the vocabulary is close | `partial_parse` resolved no verb; `DISPATCHED_COMMAND_TOKENS` is the whole vocabulary |
| `NO_MATCH` | a command that needs a referent, and nothing fits | `parse_utterance` already ran `find_contact`; the payload's candidate list is empty |
| `NO_LINE_OF_SIGHT` | a place-directed command, no LOS to it | the same world-model LOS the engagement block already calls |

Spoken as *"unable, no such command"*, *"unable, I don't see it"*, *"unable, no line of sight"* —
final wording is `speech.py`'s, per D5, and never the model's.

**The code decides the reason wherever it can, and it usually can.** Two of the three are
structural: an empty candidate list *is* `NO_MATCH`, and no resolved verb *is* `NO_SUCH_COMMAND`.
Neither needs asking. The model is consulted only where genuine judgement remains — and in that
case it returns a token from this closed set, validated body-side by D10 exactly like `CONFIRM` and
`PICK`, with the same degrade-rather-than-guess posture.

**Why this does not widen the slice.** The general `unable <reason>` vocabulary — arbitrary
refusals with arbitrary explanations — stays BR-6's. What BR-1 adds is three specific reasons that
already exist as facts in the payload, plus one more closed-vocabulary answer the validator
already has the shape to check. D10's fallback changes accordingly: **a rejected reply degrades to
`ASK` when there are candidates, and to `UNABLE NO_MATCH` when there are none** — which is more
honest than the "say again" it previously degraded to, since by construction the speech was heard
perfectly.

---

## Affected modules / files

**New — `brain-layer/` subproject**

| file | what |
|---|---|
| `brain-layer/CLAUDE.md`, `pyproject.toml`, `README.md` | subproject scaffolding; own venv; ruff + mypy --strict + pytest, matching every other subproject |
| `brain-layer/src/server.py` | FastAPI: `POST /escalate` (202, fire-and-forget), `GET /replies/poll` (drain), `GET /health` |
| `brain-layer/src/job.py` | the single-slot job holder and newest-wins policy (D3) |
| `brain-layer/src/decider.py` | `Decider` protocol; `StubDecider` (deterministic, optionally slow — Stage 1) and `OllamaDecider` (Stage 2) |
| `brain-layer/src/prompts.py` | the two prompt shapes, verbatim, as module constants |
| `brain-layer/src/ollama_client.py` | stdlib `urllib` POST to `/api/generate`, `stream=false`, low `num_predict` |
| `brain-layer/tests/` | decider tests against recorded payloads; validator is body-side so it is tested there |

**Changed — `body-layer/`**

| file | what |
|---|---|
| `src/belief/escalation.py` | add `BrainReply`; add `poll_replies()` to the protocol; `[]` in both stand-ins. `EscalationPayload` gains the candidate list the brain needs — it is already in `partial_parse`, so this is serialisation, not new belief |
| `src/belief/brain_client.py` *(new)* | `BrainLayerClient` — HTTP, single-slot worker thread, mirrors `audio_client.py`'s shape exactly (its own client, no import of `brain-layer/`) |
| `src/belief/brain_reply.py` *(new)* | the D10 validator. Pure functions, no I/O — the most heavily tested file in the slice |
| `src/belief/crew_console.py` | `drain_brain(now_sim)`; D4 revalidation; D8 stand-by; set `_pending_confirmation` from a brain confirm; render the A/B question |
| `src/belief/speech.py` | `render_disambiguation(candidates)`, `render_lost_contact()`, `render_stand_by()` |
| `src/logger.py` | `--brain-client http`, `--brain-url`; call `drain_brain` in `_run_crew_text_poll_loop` |
| `run-scripts/run-brain.sh` *(new)* | start the brain, matching the existing run-script family |

**Not changed:** `belief/tools.py`, `belief/tool_api.py`, `belief/voice_commands.py`,
`belief/callouts.py`, `belief/threat.py`, anything under `perception/`.

---

## Implementation plan

### Stage 1 — the async round trip, proven with no model at all

`brain-layer/` skeleton, both endpoints, and a **`StubDecider` with a configurable artificial
delay**. Body-side: `BrainLayerClient`, `drain_brain`, D4 revalidation, D8 stand-by, D3 newest-wins.

Shippable and flyable on its own: a free-text line that produces silence today produces a real
spoken response, end to end, over the LAN, with zero model risk. Set the stub's delay to 8 s and
every hard part of the design — non-blocking, stand-by, staleness, newest-wins — is provable at the
REPL without Ollama running.

**Acceptance:** with the stub at 8 s, the perception loop's tick rate is unchanged (measure it),
"stand by" is spoken once at 2 s, and a contact deleted during the delay yields "lost him".

### Stage 2 — the model decider

`OllamaDecider` behind the same `Decider` protocol, the two prompts, and the D10 validator on the
body side. `--brain-model`, defaulting to `qwen3:4b-instruct-2507-q4_K_M` (D6, revised 2026-09-25). Warm-up generation at startup.

Shippable: say-again and confirm work for real. Ask is rendered but its answer is not yet acted on.

**Acceptance:** the four measured cases above reproduce through the real pipeline, including the
3B's wrong `BECAUSE "tank"` being converted to `ASK` by the validator. That case is a required test
— it is the safety net's only proof.

### Stage 3 — the A/B answer leg

`awaiting_reply_id`/`awaiting_reply_to` wired through; the pilot's answer re-enters the discriminate
prompt. This is the first non-`None` `awaiting_reply_id` in the codebase's history.

**Acceptance:** "keep an eye on that tank" → "which one — the one by the village, or the one on the
road?" → "the road one" → watch set on `CONTACT_12`, readback as normal.

### Stage 4 — one sortie, then tune

Fly it. `STAND_BY_AFTER_S`, `BRAIN_REPLY_MAX_AGE_S`, the prompts and the model are all expected to
move exactly once after this, the way `inbound-speech`'s constants did.

---

## Risks and unknowns

- **`STAND_BY_AFTER_S` (2.0 s) and `BRAIN_REPLY_MAX_AGE_S` (20 s) are unmeasured.** Both are round
  guesses at human patience, like `CONFIRM_WINDOW_S` before them. Stage 4 is where they get real
  values. Stated as such rather than dressed up.
- **Accuracy is measured on three hand-written cases, not a corpus.** They were chosen to be
  adversarial and two of them already broke a model, so they are not flattering — but three cases
  is not a bench. `audio-adapter/research/2026-09-19-corpus-bench-results.md` is the precedent for
  what a real one looks like, and BR-2 should build one before the prompts are tuned further.
- **The pilot's real speech is not these sentences.** Every measured transcript here was written by
  an architect who knew the answer. The prompt will meet accents, clipped radio phrasing, and
  STT noise, and the `BECAUSE` substring test is stricter against a garbled transcript than against
  a clean one — it may push Petrovich toward asking more often than intended. That fails safe, but
  it may fail *annoying*.
- **A third process to start.** Each one is another thing that can be down mid-sortie. Body degrades
  to today's silence, which is a documented acceptable state, but the user now has three services
  to launch.
- **The stale-reply policy can lose a good answer.** Newest-wins (D3) discards an in-flight job if
  the pilot speaks again within a second. On the measured latencies this window is tiny; on a cold
  model it is 1.8 s and a cough could cost a question.
- **Serialising the candidate list into `EscalationPayload` is the first time belief-derived text
  crosses a process boundary to a model.** It contains only what `find_contact` already returns —
  no ground truth — but it is worth the reviewer checking that the `why` strings carry no DCS
  object id or truth-derived position. The identity invariant in `tools.py`'s docstring is the
  thing to check against.
- **`fix/position-belief-runaway` is in flight** (believed positions running to 87 km). The
  candidate `why` strings contain ranges, so a wrong range makes a wrong-sounding question. Not
  designed around, per the brief; it ships first.
- **Four sorties of merged work are unflown.** BR-1 adds a fifth. The stage-1 stub is specifically
  shaped so the risky half can be judged without the model, in case the sortie budget is tight.

---

## Decisions requiring user input

**Both resolved 2026-09-25. Kept here with their original framing, because the first one was
resolved by correcting the question rather than by answering it.**

1. **RESOLVED — it is "unable", and it carries a reason. See D11.** This decision was posed as
   *"say again" vs "unable" for fluent speech with no mapping*, recommending "say again" on the
   grounds that it invites a rephrase and is the user's own word. **The question was malformed.**
   The user's correction:

   > *"'say again' means speech not understood. 'unable' means action not available.
   > 'unable `<because>`' is of course most useful."*

   They are not two wordings of one response. They answer **two different failures**, and choosing
   between them for a single case is a category error. "Say again" was indeed the user's word — for
   the STT-failure case, which D7 shows never reaches the brain at all. Everything the brain
   answers for is the other case.

   On the follow-up question of whether BR-1 ships a bare "unable" or carries the reason: **it
   carries the reason**, user direction, on the grounds that it is cheap. See D11 for the closed
   set and why no new machinery is needed.

2. **RESOLVED — do not settle on `qwen2.5:7b-instruct` yet.** The user's objection:

   > *"qwen 2.5 is old, 2 years at this time. many small models have been released in last year.
   > Do investigation on them (not by downloading, but first by web search to check their claimed
   > capabilities)."*

   Correct: qwen2.5 was released September 2024. The recommendation in D6 came from measuring what
   happened to be on the machine plus two quick pulls, not from surveying what exists. A
   The survey and the measurement pass that followed it are both done
   (`body-layer/research/2026-09-25-small-local-model-survey.md` and
   `…-small-model-measurements.md`). **D6 is revised**: `qwen3:4b-instruct-2507-q4_K_M` default,
   `granite4:micro` fallback. D6's *criteria* were untouched by this — they were earned by
   measurement and the new candidates were judged against them.

   The user was right that this was worth checking. Both replacements match the incumbent's best
   behaviour at under a tenth of the latency and half the disk, and the top pick is
   *architecturally* non-thinking rather than thinking-with-a-flag — which is the exact failure
   that made plain `qwen3:4b` twice as slow as a model three times its size.

---

## Second-order effect

BR-1 **unblocks four already-built things that have been idle**: free-text commands, BL-7's mission-
phase relevance (found inert in a sortie on 2026-09-24 and deferred to this layer), MI-5's question
set (built and unwired since 2026-09-12), and BL-8's conversational kneeboard.

It also **narrows** them, usefully: D5 establishes that the runtime model classifies against closed
sets and does not generate prose. Every later slice must either fit that shape or make an explicit
case for the capable model on the ground. That is a constraint the explore notes already anticipated
by placing the mission briefing on `qwen3:14b` before the swap.

And D1 **complicates** one thing honestly: if BR-2 turns out to need real tool calls, body-layer has
to grow an HTTP server wrapping `TOOL_SET`. That is roughly a day, it is what `tool_api.py`'s
docstring already anticipates, and BR-1 deliberately does not pay for it in advance.

---

## Sequencing after BR-1

Sketched from the explore notes; not designed here.

| | slice | gated on |
|---|---|---|
| **BR-2** | Reference resolution as a capability — "where is the T-72?" → belief + world-model enrichment → *"10 o'clock, 2 km, north of V, between road and hill"*. Needs a real accuracy corpus first. | BR-1; a bench |
| **BR-3** | Conversational memory — "keep an eye on him" … "still there?". Belongs with **BL-8's memory layer**, not invented inside the brain (explore notes §4). | BR-2, BL-8 |
| **BR-4** | Mission relevance — wiring BL-7's inert `mission_phase` and MI-5's question set into what Petrovich attends to. | BR-2 |
| **BR-5** | Attack run — target resolution (one brain call) plus deterministic boresight-relative guidance at a high callout rate. **Gated on the damage probe** (`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`); miss detection deferred by the user. | probe, BR-2 |
| **BR-6** | Refusal with reason (`unable <reason>`), interrupt/resume as a stack on `threat.py`. | BR-4 |
| **BR-7** | The mission briefing — on the ground, on the **capable** model (`qwen3:14b`), before the swap. Natural consumer of MI-5. | BR-4 |
| **BR-8** | **The second, thinking tier** — see below. | BR-4 |

Deferred by the user and not scheduled: LOS-deferred tasks, unrequested advisory, chattiness when
nothing is happening.

---

## BR-8 — a second, thinking tier for questions where delay is acceptable

**Provenance:** the user, 2026-09-25, unprompted — *"Could also keep a thinking model locally for
complex questions where delay is ok?"* Recorded now, built later. Nothing in BR-1 depends on it.

### Why it is worth doing, and it is not the obvious reason

The obvious reading is "a smarter model answers harder questions". The more valuable effect is the
opposite direction: **a slow tier removes the pressure on the fast tier to be good enough for
everything.** Much of this plan's discipline — closed vocabularies, the D10 validator, one narrow
decision per call — exists partly because a 4B model is all there is. With a second tier available,
the fast tier can stay deliberately narrow on purpose rather than by necessity. This *strengthens*
the constraint rather than relaxing it.

### The memory budget, measured

Measured on this machine 2026-09-25 (see D6). On 32 GB unified memory, with DCS on the Windows box
so nothing here competes with the sim:

| | resident |
|---|---|
| fast tier, `num_ctx=2048` | 2.9 GB |
| thinking tier (`qwen3:14b`, q4, default 32k ctx) | **14 GB, measured 2026-09-25** |
| whisper `small.en` | ~0.5 GB |
| **total** | **≈17.4 GB of 32 GB** |

All three measured on this machine. An earlier draft estimated the thinking tier at 11–13 GB by
scaling from the 4B figures; the measured value at default context is higher. A reduced `num_ctx`
would bring it down, as it does for the fast tier, but a thinking tier plausibly wants real context
to think with — so the 32k figure is the honest one to budget against rather than the flattering
one.

### The Mission Interpreter should share this model, and that removes a constraint

**Provenance:** the user, 2026-09-25 — *"Since we're going to have a thinking model for in-flight,
MI probably should use the same model."*

He is right, and the consequence is larger than saving disk. The Mission Interpreter already runs
`qwen3:14b` (MI-4, merged 2026-09-12) for offline synthesis between sorties. If the in-flight
thinking tier is the *same* model, then it is **one model serving both**, loaded once — and the
memory budget above is the whole story rather than one half of it.

**It also softens the model-swap constraint the compute-topology note assumes.** That note has the
model swapping only at briefing or on the ground, precisely because a swap mid-sortie is
impossible. If briefing and in-flight deliberation share weights, there is less to swap: the
briefing model *is* the thinking tier, already warm, already resident — which is exactly what the
user's keep-warm requirement asks for, arrived at from the other direction.

**One thing to check when this is designed**, because it is where the idea could fail: Ollama holds
a loaded model with one set of options, so MI's offline use and the in-flight tier must agree on
`num_ctx` — or Ollama will hold two instances and the budget doubles. MI's synthesis plausibly
wants more context than an in-flight question does. Settle on a single context size that serves
both, or accept that they are genuinely two residents and re-budget. Do not assume they share for
free.

### The user's own constraint, and why it is the load-bearing one

> *"thinking model must be kept warm for duration of mission, it's useless otherwise. need a
> trigger from DCS when mission starts and ends."*

This is the requirement that shapes the design, not the model choice. A 12 GB model that is not
resident pays a cold load of meaningful seconds on first use, which turns "delay is acceptable"
into "delay is unpredictable" — and an unpredictable pause is exactly what a crew member must not
have. So residency is not an optimisation here; it is the feature.

Ollama's `keep_alive` is the mechanism. What it needs is a mission lifecycle signal to bracket.

### The trigger already exists — this is a forwarding job, not a new mechanism

*Checked rather than assumed, 2026-09-25.* `onSimulationStart` and `onSimulationStop` are already
live in three shipped Hook scripts (`petrobrain-f10-commands-hook.lua`,
`petrobrain-mission-telemetry-hook.lua`, `petrobrain-f10-probe-hook.lua`). Today they set a local
flag and write a line to `dcs.log`; **nothing forwards them off the Windows box.**

So what is missing is the forwarding and the seam, not the DCS-side detection: a small addition to
an existing Hook's callback, a collector endpoint, and a body-layer read — the same shape as the
F10-command and unit-velocity channels already in production. Worth knowing before this is scoped
as a research problem.

A mission lifecycle signal is also independently useful beyond this: it is the honest boundary for
the model swap the user's compute-topology note already assumes, and the natural reset point for
per-sortie state.

### Two things to settle when this is designed, not now

1. **Routing must be deterministic.** Which tier answers a question cannot itself be a model
   decision — that puts a model call in front of every model call. Code routes by question class:
   closed-vocabulary picks to the fast tier, open questions to the slow one.
2. **"Stand by" (D8) is what makes the slow tier tolerable**, and this is its first real consumer.
   Today it fires against a stub delay.
