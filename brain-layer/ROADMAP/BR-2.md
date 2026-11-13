# BR-2 — The brain cannot call a single tool: `TOOL_SET` has no dispatcher

- [ ] **BR-2 — Wire a real tool-call path from brain-layer to body-layer's `TOOL_SET`.** #status/open
  Filed 2026-10-17 at user direction (*"Create own milestone item of the tool set for brain"*), from
  the BL-8 batch's own findings. **This is a milestone in its own right, not a stage of anything** —
  it is the single thing standing between a growing, documented, tested query surface and a brain
  that can use any of it.

  **The finding, established twice independently during BL-8.** `body-layer/src/belief/tool_api.py`'s
  `TOOL_SET` is a `name -> description -> callable` registry, frozen as a contract since BL-6 and now
  17 entries wide. **Nothing in this repo dispatches one.** Grepped during BL-8's security pass and
  again by DoD, across `brain-layer/`, `body-layer/src/logger.py`, `belief/brain_client.py` and
  `belief/brain_reply.py`: no call site resolves a tool name to its callable and invokes it. So every
  tool in that registry is reachable only from body-layer's own tests.

  Two consequences, both recorded at the time:

  - **BL-8's whole recall surface is inert.** `recall_memory`, `remember_location` and the
    `get_contact_history` memory fold were built, reviewed and merged (2026-10-17, `01f5e3d9`), and
    the brain cannot reach one of them. DoD's milestone-completion answer named this as *the real
    next dependency* rather than any BL-8 stage.
  - **`ToolSpec.fn` signatures are still a free design choice** — the implementer's own memory note
    (`.claude/agent-memory/implementer/project_tool_set_has_no_dispatcher_yet.md`) records this as a
    constraint for whoever builds the dispatcher: nothing yet depends on their shape, so the shape is
    decidable now and expensive to change later.

  **One already-filed item is gated on this milestone, and the ordering matters.** `[[BL-B79]]`
  (2026-10-17 security pass): `remember_location`'s `label: str | None` has no length cap or
  validation between the tool call and the write, unlike `belief/brain_reply.py`'s validated
  structured-reply path. It was correctly rated fix-when-reachable *because* no dispatcher exists —
  so **building the dispatcher is what makes `BL-B79` live.** Close it in this milestone, not after.

  **What this milestone has to decide**, none of it settled:

  - The transport. BR-1 already established an HTTP seam between brain-layer and body-layer
    (`belief/brain_client.py`); whether tool calls ride that or get their own path is open.
  - `ToolSpec.fn`'s calling convention and how arguments arrive from a model — the D10 trust boundary
    (`belief/brain_reply.py`) is the established pattern for re-validating anything a model returns
    against body-owned data, and a tool *call* is the same class of thing as a model *reply*: it must
    not be able to name a contact id or a command body did not offer.
  - Which tools the brain may call at all. 17 entries is not obviously the right exposed set, and
    `remember_location` is the first **write** tool — the registry has until now been read-only from
    the brain's side.
  - Ollama serialises generation (BR-1.2's performance verdict, APPROVED — MONITOR), so a tool call
    inside a model turn has a latency cost that was never measured because nothing could make one.

  **Planned 2026-10-31: `plans/brain-tool-calls/plan.md`** (goal check and the user's answers in
  `alignment.md` / `explore-notes.md` beside it). Decided there: tool calls ride the existing
  escalate/poll seam and execute on body's poll thread (no body tool server); `ToolSpec.fn` is
  never model-called, the brain calls `BrainTool.invoke(ctx, args)` over a body-bound context;
  commands go through `handle_command` via an explicit allowlist and the `[[BL-B102]]` referent;
  routing is by wake word; `[[BL-B79]]` closes by making a mark label the pilot's verbatim words.
  Four user decisions (U1–U4) open. Status stays open until implemented.

  **Stages 0–3 merged 2026-11-13 (`feature/brain-tool-calls`, DoD-PASSED, `#needs-flight`). Status
  stays open — this milestone is not done.**

  **What shipped.** The tool loop end to end, on real `qwen3:4b-instruct-2507-q4_K_M` behind
  native `/api/chat` `tools` (Stage 0's own measured pick). Addressed utterances
  ("Petrovich, ...") now route to the brain instead of silently escalating or acting on a stripped
  phrasebook parse (D4); unaddressed, unanchored fallthrough is deterministic and never calls the
  model (U1, accepted — this **revises** `plans/inbound-speech/plan.md`'s "Decision 4 REVISED
  AGAIN", whose own implicit second route to the brain is now superseded, pointer added there).
  The brain can call seven read-only query tools (`find_contact`, `get_contacts`,
  `describe_contact`, `get_contact_history`, `find_place`, `describe_our_position`,
  `recall_memory`) through `BrainTool.invoke` over a body-bound `ToolContext` — never `ToolSpec.fn`
  directly, never a coordinate, never `now_sim` from the wire — and can dispatch 30 allowlisted
  commands through the real `handle_command` path via a planted `[[BL-B102]]` `Mention`, so a
  brain-carried command produces the identical readback/task/marker state as the phrasebook
  (E3, confirmed by a direct differential test). Weapons/sight/flight tokens are excluded from the
  brain entirely (U2, accepted) rather than confirmed-then-acted; `[[BL-B79]]` is closed by
  construction (`remember_location` stays unexposed until Stage 6, and a mark label can only ever
  be a verbatim run of the pilot's own words when it ships). `[[BR-B2]]`/`[[BR-B3]]` (U4, accepted)
  are fixed on this branch too, as a security-review fast-follow after being accepted-but-never-
  built through Stage 2 (see Notable Discoveries below).

  **Stage 0 verdict** (`brain-layer/research/2026-11-12-tool-call-form.md`, three runs on the
  user's own Mac against live Ollama, agent sandboxes having no route to it): native `/api/chat`
  `tools`, not a closed one-line grammar (13/15 vs 8/15 once two prompt defects were fixed —
  the prompt, not the model, was the dominant failure in run 1's 0/15 on both forms);
  `num_ctx=2048`; `BRAIN_MAX_TOOL_ROUNDS=4`. Round latency ~0.5 s mean / ~3.5 s worst.

  **Required fix (Reviewer, one round):** a header-seeded, ≥2-candidate "recently mentioned"
  contact offer was skipping D3's ambiguity-evidence check entirely (not just leniently passing
  it) — the no-evidence trust `[[BL-B102]]`'s single-referent pronoun resolution legitimately gets
  does not generalise to a header that can offer several genuine candidates. Fixed by pushing a
  ≥2-member header into `turn.candidate_sets`; re-reviewed APPROVED, independently reproduced
  red-then-green.

  **Security (deep analysis) — APPROVED, two findings, both fixed on this branch rather than
  deferred:** (1) U4's two backlog items (`[[BR-B2]]`/`[[BR-B3]]`) were accepted by the user and
  then **never implemented through Stage 2**, despite Stage 0's own implementation log correctly
  naming Stage 2 as where the fold would land — caught only by Security reading the two call
  sites directly, not by either Reviewer pass. Fixed on this branch; both entries now `#status/done`
  with a resolution line naming this branch. (2) a Recommended, non-blocking finding — nothing
  wrapped the `run_brain_tool` dispatch call in `drain_brain`, inconsistent with every other
  poll-loop input source in `body.py` — also fixed on this branch (`try/except Exception`,
  degrades to `unable NO_ANSWER`, logs rather than propagating).

  **Performance — NEEDS MITIGATION, one fix, applied:** `find_contact`/`get_contacts`'s brain-tool
  adapters were enriching every admitted contact (world-model `describe_position` +
  `terrain_divide_qualifier`) before the 5-item display cap discarded the work — 8–18 s mean, up
  to a measured 30–66 s tail, at a realistic 132–142-contact sortie scene, reachable on the
  brain's own judgement every addressed turn rather than only on an explicit "report everything."
  Fixed: cap applied before enrichment, not after, scoped to the two brain-tool adapters only;
  every other caller (`report_all`, the phrasebook `report`/`watch` loops) is unaffected by
  construction (`limit=None` default). The sibling `crew-query-path` report-path finding stays
  MONITOR + Architect escalation, unentangled with this fix.

  **What remains, deliberately unbuilt.** Stage 4 (landmark `where` on `report` — **absorbs**
  `plans/crew-query-path/plan.md`'s own Stage 5, pointer added there), Stage 5 (`say`, gated on
  the first flight showing which questions the template forms cannot carry), Stage 6
  (`remember_location` + closing `[[BL-B79]]`'s live path), Stage 7 (fly and tune the three
  tunables, and remove BR-1's now-unreachable classify/discriminate prompts if U1 holds up).

  **`#needs-flight`.** Nothing in this batch has talked to a live Ollama from body-layer end to
  end (Stage 0's probe did, standalone, against the real tool-loop prompts but not through body's
  own escalate/poll wire) — and BR-1 itself has never flown. Test card:
  `docs/acceptance/2026-11-13-br2-brain-tool-calls-sortie.md`.

  **Inspect-and-adapt.** This batch does not change what the next milestone should be — Stage 4
  was always the next planned increment and is unaffected — but it does invalidate one downstream
  assumption: `plans/inbound-speech/plan.md`'s implicit "heard clearly, no match → brain" route is
  now dead code's worth of design (superseded by U1, pointer added), and
  `plans/crew-query-path/plan.md`'s own Stage 5 should not be independently resumed — it is
  absorbed into this milestone's Stage 4, pointer added there too. Both pointer edits are done as
  part of this roadmap update, not left for a future reader to discover independently.

  **Prerequisite reading**: `plans/brain-layer/plan.md` (BR-1's two stages and the D10 boundary),
  `body-layer/src/belief/tool_api.py`'s own docstring (which records the BL-6 freeze, BL-7's
  rejection of `get_mission_phase`, and BL-8's extension to 17 with the fold-versus-extend
  reasoning), and `plans/bl8-mission-memory/plan.md` Decision 5.
