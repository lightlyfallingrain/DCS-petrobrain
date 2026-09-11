### Goal
Stand up a first `brain-layer` prototype — a small/fast-model LLM service that answers the
escalated-utterance path body-layer's BL-5a/BL-5/BL-6 work already built a seam for, replacing
`NullBrainClient`/`DebugPrintBrainClient` with a real `BrainClient` over HTTP, without letting the
model see or say anything body-layer's tools didn't actually return this turn.

**Recommend re-invoking this role with an opus override before implementation starts.** This plan
touches four things this role's guidance calls out as its own complexity/risk category on their
own (coordinate/spatial schema is not one of them, but "new subprocess + bidirectional HTTP
protocol" plus "LLM-in-the-loop hallucination boundary" plus "new subproject's tech-stack/dependency
choice" plus "extending an already-built, already-tested protocol's method signature"
(`BrainClient.handle`) stacked together is exactly the kind of cross-cutting design judgment sonnet
depth is more likely to under-examine than the single-axis cases the heuristic names explicitly).
I produced this plan at sonnet depth per the task; flagging per this role's own instructions rather
than silently deciding it's fine.

### What PB-6 is, and what this plan deliberately excludes
`docs/concept/PETROBRAIN_RUNTIME.md`'s milestone list names this slot exactly:
**PB-6 — Small LLM interface: "Add natural-language reference resolution and response
generation."** PB-1..PB-5 are done (mapped 1:1 to BL-1..BL-5 per `body-layer/ROADMAP.md`); PB-6 is
open and unclaimed by any other subproject's roadmap — no numbering collision.

Scope is the **reactive** half only: the player says something body-layer's deterministic parser
(`belief/utterance.py`) can't handle, and it's escalated through the seam BL-5a already built
(`belief/escalation.py`'s `EscalationPayload`/`BrainClient`, `belief/crew_console.py`'s
`_handle_utterance`). The brain resolves the reference, may call read/act tools, and produces one
reply.

Explicitly **not** this plan:
- **Proactive speech** (brain deciding unprompted "this is worth mentioning") — that's PB-9
  ("mission-aware proactive behavior"), gated on Mission Understanding existing, which it doesn't.
  `get_situation`/`get_contacts` polling to decide what to volunteer is a PB-9-shaped feature, not
  a PB-6 one.
- **SRS/TTS/STT** — PB-7/PB-8, unstarted, require an SRS adapter this plan doesn't touch. The
  prototype stays text-in/text-out, same as BL-5a's own precedent ("the text-only version... is
  the thing to build first").
- **A capable/senior reasoning model, model-swapping, or the Mission Interpreter's escalation
  path** ("senior model escalation" in `PETROBRAIN_RUNTIME.md`) — out of scope; PB-6 is the small
  fast local model only, and per `division-or-responsibility.md`'s compute-topology note, model
  swap in Ollama is only acceptable at briefing/on-ground — this milestone doesn't swap at all,
  one model, always loaded.
- **Multi-turn `ask_player` round trips** — `BrainClient.awaiting_reply_id()` exists in the
  protocol already but is never exercised by either stand-in; this plan's real implementation also
  leaves it returning `None` always. A brain that can ask a clarifying question and have the next
  utterance routed back to it is a real extension of `crew_console.py`'s routing (`_handle_line`
  would need to check `awaiting_reply_id()` before treating a fresh line as a fresh utterance) —
  not done here, flagged as the natural PB-6b/PB-6c follow-up.

### Existing seam, read carefully before designing on top of it
- `belief/escalation.py`'s `BrainClient` Protocol currently has `handle(payload) -> None` and
  `awaiting_reply_id() -> str | None`. **`handle` returns nothing today** — neither stand-in
  produces speech, consistent with "no brain exists yet." A real brain needs to hand a reply back
  somehow; see Decision 1.
- `belief/crew_console.py::_handle_utterance` calls `handle_player_utterance(...)` and discards
  the return value entirely (`return []` unconditionally on the escalation path). This is the one
  place that needs to change to speak anything back.
- `belief/speech.py`'s `OutgoingSpeech.author` is a closed `Literal["body_template"]` today
  because "the brain-written class is §2.1's class 3, not built by this milestone" — that
  milestone is this one. The three speech classes per `division-or-responsibility.md`'s outbound
  gate: class 1 = readbacks/contact-reports/urgent-calls (body-written, done); class 2 is not
  separately named in the source docs beyond "judgement and advice... anything conversational" —
  reading `speech.py`'s own docstring, the project's actual two-way split is **templated (body)
  vs brain-written**, i.e. what the task brief calls "class 1" vs "class 3" are the only two real
  categories in the code today. This plan treats "class 3" (brain-written) as the single thing
  it's adding — do not invent a class 2.
- `belief/tools.py`'s tool functions take **server-side context as explicit leading params**
  (`store: ContactStore`, `enrichment: EnrichmentContext | None`, `tasks: TaskStore`, and
  `now_sim: float`) ahead of the brain-facing args (`contact_id`, `filter`, `text`, `radius`,
  etc.). A brain-facing HTTP wrapper around `TOOL_SET` must **not** accept `store`/`enrichment`/
  `tasks`/`now_sim` from the request body — those are body-layer's own live instances and sim
  clock. Binding them server-side and only exposing each tool's remaining params is a real
  boundary, not a formality: letting a client supply its own `now_sim` would let it manufacture
  staleness/freshness, and a `ContactStore` obviously can't cross HTTP at all. `ToolSpec` has no
  existing metadata distinguishing "context param" from "brain-facing param" — the adapter has to
  encode this per-tool (see Implementation Plan stage 2).
- No HTTP server exists in body-layer today — it is only ever an HTTP *client* (of aircraft-layer).
  `aircraft-layer/src/api/server.py`'s `TelemetryAPIServer` (stdlib `http.server.
  ThreadingHTTPServer`, no framework) is the one precedent in this codebase for "a Petrobrain
  subproject serving HTTP," and per `body-layer/CLAUDE.md`'s stdlib-only policy, body-layer's new
  server should follow the same shape, not add a web-framework dependency.

### Affected Modules / Files

**New subproject `brain-layer/`** (own venv, own `pyproject.toml`, own `CLAUDE.md`, `src/`,
`tests/`, `research/` if any DCS-adjacent unknowns turn up — none expected, this subproject never
touches DCS directly):
- `brain-layer/src/server.py` — stdlib `ThreadingHTTPServer` (mirrors `aircraft-layer/src/api/
  server.py`'s shape) exposing `POST /escalate`, accepting `EscalationPayload`'s JSON shape,
  returning `{"text": str} | {"text": null}` synchronously.
- `brain-layer/src/tool_client.py` — HTTP client for body-layer's new tool-server endpoints
  (mirrors `body-layer/src/aircraft_client.py`'s existing shape: `urllib.request`, typed wrapper
  methods, one per tool it's allowed to call).
- `brain-layer/src/reasoning.py` — the actual LLM-driving logic: builds a tool-calling turn from
  the escalation payload, runs the local model, produces a candidate reply, runs it through the
  grounding check (Decision 3), returns final text or `None`.
- `brain-layer/src/model_client.py` — thin wrapper around whichever local model interface Decision
  2 resolves to (most likely Ollama's HTTP API, which needs no SDK — `urllib.request` + `json`
  again, keeping the stdlib-only posture body-layer/aircraft-layer already share).
- `brain-layer/CLAUDE.md` — stack/testing/structure, modeled on `body-layer/CLAUDE.md`'s
  structure.

**`body-layer/src/belief/escalation.py`** — extend `BrainClient.handle()`'s return type from
`None` to `str | None` (the brain's final reply text, or `None` for "no answer within timeout" —
the existing "silence is honest" language already anticipates exactly this shape, it just has no
real implementation to return anything yet). Update `NullBrainClient`/`DebugPrintBrainClient` to
match (`None` unconditionally — the "no brain yet" honest behavior is unchanged, only the type
signature is). `handle_player_utterance` returns `brain_client.handle(payload)` instead of nothing.

**`body-layer/src/belief/crew_console.py`** — `_handle_utterance` uses `handle_player_utterance`'s
returned text: `None` → `[]` (silence, unchanged behavior), a string → `[text]`, spoken through the
existing `_print` funnel exactly like any other line (no new sink, per `_print`'s own docstring
design intent — "a third sink on the same funnel, not a new routing design").

**`body-layer/src/belief/speech.py`** — widen `OutgoingSpeech.author`'s `Literal["body_template"]`
to `Literal["body_template", "brain"]`. Whether `crew_console.py` actually constructs an
`OutgoingSpeech` for the brain path (vs. just appending a plain string, matching today's
`_act`/`drain_events` shape) is Decision 4 below — do this rename either way since it's the one
place "class 3 exists now" needs to become type-true.

**New `body-layer/src/api/tool_server.py`** — stdlib `ThreadingHTTPServer` (same shape as
aircraft-layer's), one route per `TOOL_SET` entry (`POST /tools/{name}`), each handler binding
`store`/`enrichment`/`tasks`/`now_sim` from the server's live objects and unpacking only the
tool's brain-facing args from the JSON body. A generic `TOOL_SET`-driven dispatcher is tempting
but the context/brain-facing param split isn't declared anywhere machine-readable today — first
cut should hand-write one small handler function per tool (12-15 of them, each a few lines) rather
than build a reflection-based dispatcher for a first prototype; revisit if/when this feels
repetitive enough to earn the abstraction (CLAUDE.md: "Do not introduce new abstractions unless
you can name a clear duplication they remove" — at this scale, one match/dispatch function on tool
name plus explicit arg-unpacking per case is plenty, and stays inspectable).

**New `body-layer/src/brain_client.py`** — `HttpBrainClient` implementing the (now `str | None`
-returning) `BrainClient` Protocol: POSTs `EscalationPayload` (JSON-serialized) to
`<brain-layer-url>/escalate` with a configurable timeout; on timeout or any HTTP/connection error,
catches it, logs a warning (mirrors `crew_console.py::_print`'s existing degrade-on-overlay-
failure pattern), and returns `None` — never raises. `awaiting_reply_id()` returns `None` always
(unimplemented, per Explicitly-not-this-plan above).

**`body-layer/src/logger.py`** — `--crew-text` branch: add a third `--brain-client` choice
(`"http"`, alongside existing `"debug"`/`"null"`) wiring `HttpBrainClient`, plus a new
`--brain-layer-url` flag (mirrors `--aircraft-layer-url`'s existing shape) and a
`--tool-api-port`/`--tool-api-host` pair to start `tool_server.py`'s server on its own thread
alongside the existing crew-text poll thread, sharing the same `crew_runner.store`/`enrichment`/
task-store instances `CrewConsole` already holds.

### Implementation Plan

1. **PB-6a — Wire the round trip with no real model** (minimal working version). Build
   `brain-layer/`'s HTTP server returning a fixed stub reply (e.g. echoing back
   `payload.transcript`) and body-layer's `tool_server.py` + `HttpBrainClient` + the
   `escalation.py`/`crew_console.py` signature changes. Prove the whole path end-to-end against
   the `--crew-text` console: type an unparsed utterance, see a brain-originated (stubbed) reply
   printed through `_print`, tool-server responding to a hand-curled `curl` request for at least
   `get_contacts`/`describe_contact`/`get_situation`. No LLM involved yet — this stage validates
   the transport and the context/brain-facing param split, not reasoning quality.

2. **PB-6b — Real model, read-only tool use.** Wire `reasoning.py` to an actual local model
   (Decision 2), grant it read-only tools first (`get_contacts`, `describe_contact`,
   `get_contact_history`, `find_contact`, `find_place`, `get_situation`,
   `describe_our_position`, `get_attention_state`, `poll_events`) via a tool-calling loop, and
   implement the grounding check (Decision 3) before any reply reaches `_print`. Validate against
   a fixed set of escalated utterances run through the replay/console harness (same pattern
   `body-layer/tests/` already uses for deterministic paths) — e.g. "what's that thing near the
   village," "do we still see the BMP," "what's our situation" — checked by hand for (a) correct
   contact resolved, (b) no fabricated id/fact in the reply, (c) reasonable latency.

3. **PB-6c — Act tools.** Extend the granted tool set to the mutating ones (`set_attention`,
   `watch_area`, `scan_area`, `acknowledge_event`, `cancel_task`) once read-only resolution is
   trustworthy. This is a separate stage deliberately: a hallucinated *read* produces a wrong
   sentence; a hallucinated *act* changes body-layer's actual attention/task state. Validate each
   act tool call is grounded in something the utterance actually asked for (harder to check
   mechanically than a quoted contact id — likely stays a manual acceptance pass for this
   prototype, flagged as a real limitation, not solved by this plan).

4. **Validate performance/latency.** Measure round-trip time (utterance → brain-layer → tool
   calls → model inference → reply) against `--crew-text`'s existing text-mode loop. No hard
   target exists yet (PB-6 predates PB-7/PB-8's SRS-realtime constraints), but record a number —
   it directly informs whether PB-7's TTS attachment is viable without a redesign.

5. **Refine.** `brain-layer/CLAUDE.md` write-up, `HttpBrainClient` timeout tuning against measured
   latency, decide whether the hand-written `tool_server.py` dispatch earns the `TOOL_SET`-driven
   abstraction once its real shape (which params are context vs. brain-facing, per tool) is
   settled by stages 1-3 rather than guessed now.

### No-omniscience enforcement (concrete, not restated principle)

- **What the brain can see**: exactly `EscalationPayload`'s fields (transcript, partial parse,
  `situational_header`) plus whatever `tool_server.py`'s endpoints return — both already
  structurally stripped of DCS-truth fields (`belief/percept.py`'s existing invariant, unchanged
  by this plan). Brain-layer has no world-model import, no aircraft-layer client, no DCS access of
  any kind — its only window into the world is body-layer's tool HTTP surface. This is a hard
  module boundary, not a convention: `brain-layer/` never imports anything from `world-model/` or
  `aircraft-layer/`, matching the default "HTTP across a subproject boundary" rule (module
  independence — see the memory note below).
- **What it can never fabricate**: a contact id, place name, or fact not returned by a tool call
  made *during that turn*. Enforced by the grounding check in `reasoning.py`: after the model
  produces a candidate reply, extract every `CONTACT_\d+`-shaped (or whatever the live id format
  turns out to be — check `ContactStore`'s actual id generation before hardcoding a regex) token
  from the text and diff it against the set of ids that appeared in *any* tool result returned
  this turn. Any reply referencing an id outside that set fails the check.
- **What happens on a failed check**: **treat as no answer, not as a retry-with-correction.**
  `escalation.py`'s own existing language is the precedent: "If the brain does nothing within a
  timeout, body says nothing. Silence is honest; a guessed response is not." A grounding failure
  is the same category of event as a timeout — `reasoning.py` returns `None`, `brain_client.py`
  propagates `None`, body-layer stays silent, and the failure is logged server-side on
  `brain-layer` for later inspection. This is a design choice consistent with an already-stated
  project principle, not a new invariant invented for this plan — no escalation needed.
- **Act-tool grounding** (stage 3) is weaker than id-grounding by construction — there's no clean
  mechanical check for "did the player actually ask for this `set_attention` call." Flagged as a
  known gap in Risks, not solved here.

### Risks & Unknowns

- **Synchronous blocking round trip.** `HttpBrainClient.handle()` blocks `crew_console.py`'s
  calling thread for the full tool-loop + inference time. Fine for a text-mode prototype console;
  a real SRS/PTT session (PB-8) cannot block the whole perception/console loop on model latency —
  this plan does not solve that, it only produces a latency number stage 4 uses to size the
  eventual problem.
- **Tool-server has no auth, LAN-only, matches aircraft-layer's existing no-auth precedent** —
  consistent with the current project phase's Security/Performance-Reviewer exemption
  (`CLAUDE.md` Agents section), but worth re-checking once brain-layer's model-hosting choice
  (Decision 2) is resolved, since a cloud-hosted model would mean the tool-server's LAN boundary
  is no longer the only network boundary in the picture.
- **`BrainClient.handle`'s signature change is a real protocol edit to already-shipped, tested
  code** (BL-5a), not new code in a vacuum — `NullBrainClient`/`DebugPrintBrainClient`'s existing
  tests need updating, not just the new `HttpBrainClient`'s.
- **Contact id format assumed but not verified in this plan** — `reasoning.py`'s grounding-check
  regex must match `ContactStore`'s actual generated id shape; check `belief/contacts.py` before
  writing it, don't assume `CONTACT_\d+` from the utterance-id precedent alone.
- **Act-tool grounding has no mechanical check** (see above) — a prototype-level gap, not
  resolved by this plan.
- **`awaiting_reply_id()` staying permanently `None`** means any brain reply that would ideally be
  a clarifying question instead has to either guess or stay silent under the current design — a
  real product-quality gap for a "prototype," acceptable for PB-6 but worth remembering it's
  deferred, not solved.

### Decisions Requiring User Input

1. **Async reply-delivery vs. synchronous blocking HTTP (chosen: synchronous).** The alternative —
   body-layer fires the escalation and brain-layer later pushes the reply back to a new inbound
   body-layer endpoint (`POST /speech/reply`) — better matches `awaiting_reply_id()`'s implied
   future multi-turn design and avoids blocking `crew_console.py`'s thread, at the cost of a third
   HTTP surface and real async-delivery bookkeeping (matching replies back to utterances,
   handling a reply arriving after the "conversation" has moved on). I chose synchronous for
   prototype simplicity and because it's the smaller diff against `BrainClient`'s existing shape,
   but this is a real architectural fork with different future consequences (synchronous will need
   rework to support true clarifying-question round trips; async needs building now for something
   this milestone doesn't exercise) — flagging rather than treating as settled.
2. **Model hosting for brain-layer (real decision, new-dependency-class per `AGENTS.md`'s
   escalation rules).** `division-or-responsibility.md`'s compute topology names Ollama on the Mac
   as the intended local-first target, and root `CLAUDE.md`/project memory both establish that
   posture project-wide. Options: (a) local model via Ollama's HTTP API (no new package, matches
   `body-layer`/`aircraft-layer`'s stdlib-only precedent, but the Mac's actual usable model
   quality/speed for reliable tool-calling + reference resolution is unverified — no benchmark run
   yet); (b) a cloud API for this prototype only, explicitly flagged as not the final architecture,
   to de-risk "is the design even viable" from "is the local model good enough." Not resolving
   this silently — it changes `brain-layer/`'s dependency footprint and its `CLAUDE.md`'s stated
   posture either way.
3. **Grounding-check strictness (chosen: fail-closed/silence on any ungrounded id — see "No-
   omniscience enforcement" above).** Flagging as a decision anyway since it trades a real product
   cost (Petrovich stays silent more often than a looser check would allow) for the safety
   property — the project's own stated principle supports this choice, but the user may want a
   softer behavior (e.g. strip the offending clause and speak the rest) once real model output is
   seen in PB-6b.
4. **Does the brain path construct a real `OutgoingSpeech(author="brain")` object, or just return
   a plain string appended like `_act`'s existing returns?** The former is more inspectable/
   consistent with `speech.py`'s own type (and gives future overlay/logging code something to
   branch on); the latter is the smaller diff matching `_handle_utterance`'s current shape. Marked
   as a decision because it's genuinely reversible/local either way (not escalating per AGENTS.md's
   own "local, reversible" carve-out) — pick whichever the Implementer finds cleaner against the
   actual code, but note the choice in the commit.

### Second-order effect
This unblocks PB-7 (TTS) — for the first time there's real brain-authored text to attach a
voice to, not just body-templates — but it also **locks in the synchronous-blocking shape**
(Decision 1) as the thing PB-8 (STT/live PTT) will have to either accept or rework; a wrong call
here doesn't just cost this milestone, it sets the latency ceiling PB-7/PB-8 inherit.
