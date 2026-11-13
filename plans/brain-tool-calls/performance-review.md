### Performance Review

BR-2 (brain tool calls), Stages 0-3 batch, `feature/brain-tool-calls` @ `3a54b55b` (fast-forwarded
onto this worktree's `415fa135`; tree clean before and after). One pass for the whole batch, per
root `CLAUDE.md`'s "Agents" cadence. No hard real-time budget applies yet (Runtime phase has not
started) — this reviews the 1 Hz body-layer poll thread's practical cost and whether threat
callouts stay structurally untouched by brain work, not a frame budget.

**Inputs read:** `plans/brain-tool-calls/plan.md` (D1 cost model, D6, R3), `implementation.md`
(all four stage logs + the review fix), `brain-layer/research/2026-11-12-tool-call-form.md`,
`plans/brain-layer/plan.md` (BR-1.2's "APPROVED — MONITOR: Ollama serialises generation" verdict).
Source read: `body-layer/src/belief/tool_api.py`, `crew_console.py` (`drain_brain` and the
`BrainTurn`/`_start_brain_turn`/`_post_tool_continuation`/`_header_contact_refs` chain),
`escalation.py`, `belief/tools.py`, `belief/enrichment.py`, `body.py` (`_run_brain_tool_fn`, the
poll loop's `_wait_for_next_tick`); `brain-layer/src/tool_loop_prompts.py`, `decider.py`,
`brain_layer/__main__.py`.

**Measurement method, stated per the dispatch's own instruction:** body-layer has no route to a
real world-model database in this sandbox. Mechanism (call counts, which code paths run, payload
shapes/sizes) is measured directly against the real `belief.tool_api`/`belief.tools` code, using
the exact `describe_position`/`project_terrain_aware`/`divides_between` monkeypatch fixture
`test_callouts.py`/`test_tools.py` already use for their own `EnrichmentContext` — so the *call
count* and *code path* numbers below are real, not estimated. The real per-call *wall-clock* cost
of `describe_position` is not re-measured here (no real world-model DB to query against in this
sandbox, and `.claude/agent-memory/performance-reviewer/feedback_synthetic_store_calibration.md`
is explicit that a synthetic store understates absolute cost 3-12× against the real one — so a
synthetic benchmark here would not have been worth more than citing on-file real numbers anyway).
Three real-SQLite measurements are already on file and are cited as authoritative, not estimated:
`body-layer/research/2026-10-05-performance-review.md` finding 2 (median 51.6 ms / mean 67.8 ms /
max 228.4 ms, 60 distinct positions within 9 km); `.claude/agent-memory/performance-reviewer/
project_report_query_enrichment_dominates.md` (2026-10-10, BL-13 crew-query-path review, same real
`syria-full.sqlite`: 63.25 ms/contact `semantic_facts_for` + 6.77 ms/contact
`terrain_divide_qualifier`, the latter never cached); and `world-model/research/2026-10-05-
performance-review.md` (M7's own committed figure, same real store: mean 136.8 ms / p95 497.7 ms).
The three disagree by up to 2× on the mean and are treated here as a credible range rather than
resolved to one number — all three are real measurements against the same code this diff does not
touch, taken under different load/machine conditions, not estimates standing in for a measurement
that could have been taken.

### Measurements

| What | Method | Result |
|---|---|---|
| `find_contact`/`get_contacts` enrichment calls vs. store size | real code, monkeypatched `describe_position` (see above), 20- and 50-contact stores | `get_contacts()` (no filter) and `get_contacts(filter="visible")`: enrichment runs on **every** contact the filter admits — 20 calls at n=20, 50 calls at n=50, regardless of `BRAIN_TOOL_LIST_CAP=5`. `find_contact("T-72")` (1-in-5 synthetic match rate): 4 calls at n=20, 10 at n=50 — enrichment runs on every *match*, not every candidate, but still before the cap. |
| Real cost of that enrichment, extrapolated | `describe_position` (via `semantic_facts_for`) is the dominant per-contact cost inside `_add_enrichment_facts`; `terrain_divide_qualifier` is a second, smaller, **never-cached** per-call cost (`relative_geometry` is cheap in-memory geometry, negligible next to either) — see `enrichment.py` reading below and the three real-SQLite figures cited above | At 50 contacts, across the three on-file real measurements: **~3.2-6.9 s mean** per `get_contacts()`/broad `find_contact` call if most of those 50 are cache-misses this poll (63-137 ms/contact mean, plus a guaranteed, cache-independent ~340 ms floor from `terrain_divide_qualifier` alone), **~11-25 s at the measured p95/worst-case tail** (228-498 ms/contact). At the sortie-scale contact counts the 2026-10-05 body-layer review actually measured (132-142 live contacts, well above the plan's own 20-50 framing): **~8.3-18.1 s mean, ~30-66 s at the tail**, same mechanism. |
| Cache-miss realism | read `WorldEnrichmentCache`/`ENRICHMENT_CACHE_POSITION_GRID_M` (50 m cell, keyed per contact id) | Not a cold-start-only cost. Any contact that moves >50 m between two enrichment reads is a fresh miss; a moving ground contact does this every few seconds at normal speed. A contact never yet enriched this session (never spoken about, never `describe_contact`'d) is always a miss the first time a brain tool call reaches it. So a busy, mixed-motion 20-50+ contact scene will **not** settle into an all-cache-hit steady state — some fraction of the store is cold on any given call. |
| Where this sits relative to pre-existing cost | read `crew_console.py`'s phrasebook `report_all`/`report`/line ~2987/3286/5050 | **The mechanism is not new.** `report_all` already calls `get_contacts(self.store, now_sim, enrichment=self.enrichment)` with no filter — same full-store-before-cap enrichment, same cost, already live today. BR-2 does not introduce this cost; it adds a second, LLM-driven caller of the same cost, reachable more often (every addressed utterance can trigger `get_contacts`/`find_contact`, vs. a player explicitly saying "report everything") and without the player's own sense of "I just asked for the big one." |
| Tool executions per poll (D6's claim) | read `drain_brain` | Confirmed: `tool_executed_this_poll` gates the reply batch to **at most one** tool execution per poll, structurally — a second `tool_call` reply in the same batch is simply not acted on this poll. |
| Does anything in the new code run per poll with no turn active? | read `drain_brain`, `_expire_overdue_brain_turns`, `_speak_stand_by_if_due` | Both iterate `self._brain_turns` (empty dict when idle) → O(1), plus the pre-existing `brain_client.poll_replies()` network check (unaffected by this diff). Confirmed near-zero when idle. |
| Payload per continuation POST | real `BRAIN_TOOL_SPECS`/`BRAIN_COMMAND_SPECS` + a representative round-3 payload (5 header refs, 3 steps) | **5,572 bytes total; 4,102 bytes (74%) is `tools`+`commands`**, re-sent byte-identical every round (confirmed by reading `_post_tool_continuation`: both kwargs are the same module-level tuples every call). A 4-round turn moves roughly 20 KB total body→brain-layer, over localhost/LAN. |
| Is resending `tools`/`commands` every round worth fixing? | the above, judged against transport cost | No. ~4 KB/round is negligible next to the ~0.5-3.5 s of model time D1 budgets per round (R3's KV-cache point is about the *Ollama-facing* system-prompt prefix staying byte-stable, which `tool_loop_prompts.build_system_prompt` already guarantees and `test_system_prompt_is_identical_across_rounds` already proves — not about this body↔brain-layer wire). The plan's own open question ("are they? should they be sent once per turn?") is answered: yes they are resent, and the bytes are too small to be worth a protocol change. |
| `_header_contact_refs` cost | read: bounded by `BRAIN_TOOL_LIST_CAP=5`, called once per `_start_brain_turn` (turn start only, not per round/poll) | Up to 5 `describe_contact` enrichment calls, once per addressed utterance. Comparable to one bounded tool call; acceptable. |
| Poll-cadence effect of a slow tool call | read `body._wait_for_next_tick` | Confirmed: the poll loop sleeps to a deadline and clamps missed time to zero on overrun — a slow `drain_brain` tool execution does not queue extra ticks, but it does consume the next poll's slot in real wall-clock time. A multi-second enrichment stall inside one `drain_brain` call delays `drain_events`/threat-callout processing for the *next* poll by that same duration — a real, if occasional, hole in callout cadence, not a violation of D6's structural "callouts never touch Ollama" claim (that claim is about the model call, and holds), but a gap in the plan's own weaker framing ("the guarantee is structural, not timing-based"). |
| Model kept warm for the new decider | read `brain_layer/__main__.py` | `ollama_client.warm_up(...)` runs for `--decider tool_loop` the same as `ollama`/not `stub` — confirmed, D6's "kept warm" holds for `ToolLoopDecider` too. |
| `keep_alive` between rounds | read `ollama_client.chat`/`decider.py` | Not set explicitly anywhere in this diff; Ollama's own default keep-alive applies. Rounds inside one turn are seconds apart (well inside any sane default); not a concern for this batch. MONITOR if a flight ever shows an inter-round cold reload. |
| Checks | `cd body-layer && .venv/bin/ruff check src tests` / `.venv/bin/mypy src` / `.venv/bin/pytest -q`; same for `brain-layer` | body-layer: ruff clean, mypy clean (82 files), pytest 3265 passed/4 xfailed. brain-layer: ruff clean, mypy clean (9 files), pytest 89 passed. All green, run fresh from this worktree. |

### Findings

#### `get_contacts`/`find_contact` enrich every admitted contact before the brain-facing adapter caps to 5

- **Location:** `body-layer/src/belief/tools.py` — `get_contacts`/`find_contact` build a full
  `_contact_result` (which runs `_add_enrichment_facts` → `WorldEnrichmentCache.get_or_compute` →
  `describe_position` on a cache miss) for every contact the filter/search admits, *before*
  `body-layer/src/belief/tool_api.py`'s `_list_contacts_adapter`/`_find_contact_adapter` apply
  `_cap(..., BRAIN_TOOL_LIST_CAP=5)` to the result for display. The cap discards the enrichment
  work on everything past the first 5, it does not avoid doing it.
- **Risk:** at a realistic sortie-scale contact count (132-142, the 2026-10-05 body-layer review's
  own measured scene, well above this plan's 20-50 framing), one `get_contacts()`/broad
  `find_contact` call from the brain is on the order of **8-18 s mean, up to a measured ~30-66 s
  tail**, of blocking SQLite-bound work on body-layer's single poll thread — during which the
  *next* poll (threat callouts, sight tracking, speech draining, everything else `body.py`'s poll
  loop does) is delayed by that same wall-clock amount (confirmed via `_wait_for_next_tick`'s
  tick-debt-absorption design: the delay is absorbed as a one-time gap, not queued, but it is a
  real gap, and `project_bl11_measured_outcome`'s own on-file figures show this exact mechanism
  already causing ~2% of *ordinary* polls to overrun 1.0 s before any brain tool call is added).
  D6's own per-poll cap ("at most one tool execution per poll") does not bound this: the cap is on
  *count* of tool executions, not on the *cost* of the one it allows. This is not hypothetical
  scaffolding risk — it is the exact scenario D6 asked this review to measure, confirmed by reading
  the real code path, with the real per-call cost taken from three independent on-file
  measurements rather than estimated.
- **Not new, but newly more exposed — and already flagged once before on a sibling path.**
  `report_all` already pays this identical cost today (`get_contacts(self.store, now_sim,
  enrichment=self.enrichment)`, no filter, same `tools.py` code path) — this is an inherited
  `belief.tools`/`belief.enrichment` design point, not a regression BR-2 introduces.
  `.claude/agent-memory/performance-reviewer/project_report_query_enrichment_dominates.md` records
  the *identical* mechanism found on the `crew-query-path` report feature (2026-10-10) and filed as
  "MONITOR + Architect escalation rather than a change request, because every fix changes a shared
  tool or the position the range is computed from" — i.e. that verdict was about the fix being
  architecturally entangled with `report`'s own slot filtering, not about the risk being small.
  What BR-2 changes is *frequency and agency*: a player says "report everything" deliberately and
  rarely; a model can call `get_contacts`/`find_contact` on its own judgement on every addressed
  turn, including for a narrow question ("which one's the BMP") where the pilot never asked for a
  full-store dump — and unlike `report_all`'s shared position-rendering concern, this path has no
  entanglement forcing a shared-tool redesign.
- **Action:** NOW, scoped to BR-2's own two adapters — narrower than, and independent of, the
  still-open `crew-query-path` escalation.
- **Mitigation:** cap before enriching, not after, inside `belief.tool_api.py`'s two adapters only.
  `_find_contact_adapter`/`_list_contacts_adapter` call `tools.find_contact`/`tools.get_contacts`,
  which interleave filtering/sorting with per-contact enrichment inside one list comprehension —
  the smallest fix is an optional `limit` parameter on `tools.find_contact`/`get_contacts`, applied
  *after* the existing filter/sort and *before* the enrichment step, with a `None`/unlimited
  default that leaves every existing caller (including `report_all`, and whatever the open
  `crew-query-path` escalation eventually does) byte-for-byte unchanged. This does not require or
  presume the larger shared-tool redesign the older escalation is waiting on; it only moves where
  `BRAIN_TOOL_LIST_CAP` is applied for these two call sites, from after enrichment to before it.
  This is a Stage-3-batch-scoped code change, not an architectural one — routed back through
  Implementer → Reviewer per root `CLAUDE.md`'s "change request re-enters the loop" rule, not
  applied by this review directly.

#### Resent `tools`/`commands` block, per continuation round

- **Location:** `body-layer/src/belief/crew_console.py` `_start_brain_turn`/
  `_post_tool_continuation`, both passing `tools=BRAIN_TOOL_SPECS`/`commands=BRAIN_COMMAND_SPECS`
  into `handle_player_utterance` every round.
- **Risk:** none at the measured scale. 4,102 of a 5,572-byte round-3 payload is this
  byte-identical block; over a full 4-round turn, roughly 20 KB total on a local/LAN HTTP hop.
  Explicitly the plan's own open question ("are they? should they be sent once per turn?") —
  answered here: yes, resent every round, and too small to justify a protocol change. The R3
  concern this plan actually cares about (Ollama's own KV-cache reuse) is a different, already-
  closed question: `tool_loop_prompts.build_system_prompt` is byte-stable per turn and
  `test_system_prompt_is_identical_across_rounds` proves it.
- **Action:** MONITOR (effectively closed — recorded so the plan's open question has a real
  answer rather than staying open by omission).

#### Poll-cadence hole from a slow `drain_brain` tool execution

- **Location:** `body-layer/src/belief/crew_console.py` `drain_brain` → `_handle_brain_tool_call` →
  `run_brain_tool` (synchronous on the poll thread), combined with `body.py`'s
  `_wait_for_next_tick` deadline-clamp.
- **Risk:** this is the mechanism the first finding's numbers describe, stated structurally rather
  than by its size: *any* tool call whose execution exceeds `poll_interval_s` (1.0 s default)
  steals exactly that much wall-clock time from the next poll's cadence, with no compounding debt
  (by design — "the worst possible behaviour on a thread that is already behind" is explicitly
  avoided) but also no protection against the gap itself. D6's "threat callouts never touch Ollama"
  guarantee holds (no model call sits in this path), but its own text already flags this as
  "structural, not timing-based" — this review confirms that caveat is load-bearing, not boilerplate:
  on the Mac that also hosts Ollama (`project_compute_topology` memory), a multi-second enrichment
  stall on body's poll thread also means that poll's CPU is unavailable for whatever else is
  running concurrently, compounding BR-1.2's own on-file MONITOR ("Ollama serialises generation, so
  one slow reply can chain-drop several subsequent utterances").
- **Action:** MONITOR, contingent on the first finding's fix. Capping before enriching (above)
  removes the realistic path to a multi-second stall; if that fix lands, this risk shrinks to the
  size of a normal `describe_contact`/`find_place` call (bounded, already acceptable), and no
  separate action is needed here.

#### Everything else checked and found proportionate

- At most one tool execution per poll: confirmed structural (D6).
- Near-zero per-poll cost with no brain turn active: confirmed (`_expire_overdue_brain_turns`/
  `_speak_stand_by_if_due` are O(1) over an empty dict; `poll_replies()`'s own network check
  predates this diff).
- `_header_contact_refs`: bounded to 5 enrichment calls, once per turn start, not per round/poll —
  acceptable, same order of cost as one ordinary tool call.
- Model kept warm for `ToolLoopDecider`: confirmed (`__main__.py`'s warm-up call covers it).
- No per-request allocation surprises in `crew_console.py`'s new `BrainTurn`/`ToolStep`
  bookkeeping: all bounded by `BRAIN_TOOL_LIST_CAP`/`BRAIN_MAX_TOOL_ROUNDS`, no unbounded
  accumulation found.

### Verdict

**NEEDS MITIGATION** — one concrete, scoped fix (cap `find_contact`/`get_contacts` enrichment
*before* the 5-item display cap, not after, in `belief.tool_api.py`'s two adapters), re-entering
the Implementer → Reviewer loop per root `CLAUDE.md`'s change-request rule. Everything else in
this batch (payload size, per-poll cap, idle-state cost, warm-up, header-ref cost) is proportionate
or already closed by the plan's own design and is confirmed here, not merely assumed.

**Related agent memory** (searched before and during this review, per root `CLAUDE.md`'s "when to
query it"): `project_report_query_enrichment_dominates`, `project_enrichment_cache_axes`,
`project_bl11_measured_outcome`, `feedback_synthetic_store_calibration` — all performance-reviewer
memory, all consulted; this review adds `project_br2_tool_adapter_enrich_before_cap` recording
the new, narrower exposure and the fact that a narrower fix is available for it.
