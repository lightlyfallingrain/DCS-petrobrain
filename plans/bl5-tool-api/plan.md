### Goal
Formalize `body-layer/src/belief/tools.py`'s existing plain functions as a named, documented,
fixed tool surface (`plans/body-layer/plan.md` §3.1/§3.3's BL-5 subset), and build the three
tools whose machinery does not exist yet — `find_place`, `get_situation`,
`describe_our_position` — so a human can hold a useful tactical conversation using only these
twelve tools by hand, no LLM involved.

### Context (confirmed before planning)

- Of BL-5's twelve named tools, nine already exist in `tools.py` with matching or near-matching
  signatures: `get_contacts`, `describe_contact`, `get_contact_history`, `find_contact`,
  `set_attention`, `watch_area`, `get_attention_state`, `acknowledge_event`, and `list_events`
  (§3.3 calls this last one `poll_events` — see Decision 4 below). `find_place`,
  `get_situation`, `describe_our_position` are genuinely net-new.
- `describe_our_position`/`get_situation` need ownship position + world-model reverse-geocoding.
  `belief.enrichment.EnrichmentContext` already carries a live `ownship: OwnshipState`, updated
  every poll by `logger.ConsolePerceptionRunner.run_once` — no new plumbing needed to get at
  ownship state, just a required (non-optional) `EnrichmentContext` parameter on these two tools,
  unlike the contact tools' optional one (see Decision 3).
- `world-model/src/query/` has no text-name → position lookup today — only
  `describe_position` (position → description) and `store.reader.all_features`/
  `features_in_bbox`/`nearest_feature` (bbox/nearest, not name search). `find_place` therefore
  needs a small new world-model-side function, not just body-layer composition (see Decision 2).
- No Investigator pass needed — this milestone is intra-repo composition over already-verified
  machinery (BL-0..BL-4, BL-2.6, world-model M5), the same posture as BL-3's world-enrichment
  milestone.

### Affected Modules / Files

- `world-model/src/query/search.py` (new) — `find_place_by_name(conn, text, kinds=None) ->
  list[PlaceMatch]`: case-insensitive substring match over `StoredFeature.name` across
  place-shaped kinds (`settlement`, `named_place`, `airfield`, `navaid` — the same kind list
  `describe_position` already treats as place-bearing), via `store.reader.all_features`. Returns
  a representative point per match (first geometry vertex for `Point` features; centroid for
  `LineString`/`Polygon`) plus `kind`, `name`, `feature_id`, and a simple confidence (`1.0` exact
  case-insensitive match, `0.6` substring) — mirrors `find_contact`'s ranked-candidates shape on
  the body-layer side, kept deliberately simple rather than fuzzy-matched (see Risks).
- `world-model/tests/test_query_search.py` (new) — control-point-style test: a known settlement
  name in the test fixture DB resolves via `find_place_by_name`, per `world-model/CLAUDE.md`'s
  testing rule for spatial queries.
- `body-layer/src/belief/tools.py` — add `find_place`, `describe_our_position`, `get_situation`,
  `poll_events`. `find_place` calls `query.search.find_place_by_name` through the existing
  world-model in-process seam (same seam `enrichment.py` already uses via `query.describe`) and
  wraps each match in the `{facts, summary, phrasing_hints}` triple. `describe_our_position`
  calls `query.describe.describe_position` on `enrichment.ownship.x/z` and formats a
  `{facts, summary, phrasing_hints}` result the same way `enrichment.semantic_facts_for` does for
  contacts. `get_situation` aggregates: contact counts (total/visible/watched), the
  highest-attention contact (`priority` > `watch` > most-recently-observed `visible`, in that
  order — deterministic, no relevance score since BL-6 hasn't built one), unacknowledged event
  count, and `describe_our_position`'s own summary line, into one `{facts, summary,
  phrasing_hints}` result. `poll_events` is `list_events(store, unacknowledged_only=True)` under
  a name matching §3.3's tool list exactly (see Decision 4) — a one-line wrapper, not a rewrite
  of `list_events`.
- `body-layer/src/belief/tool_api.py` (new) — the "actual callable surface" the milestone brief
  asks for: a `TOOL_SET: list[ToolSpec]` naming all twelve BL-5 tools with the plain-language
  description each carries in §3.3 (verbatim where §3.3 already wrote one), plus which `tools.py`
  function each maps to. This is what turns "twelve functions happen to exist" into "the
  documented tool API" — the artifact a brain-layer prototype or a future transport wraps,
  without committing to *how* it's wrapped yet (see Decision 1).
- `body-layer/src/belief/console.py` — new commands so a human can exercise all twelve tools by
  hand (BL-5's literal acceptance test): `place <text>` → `find_place`, `situation` →
  `get_situation`, `position` → `describe_our_position`. `events`/`ack <id>` already map to
  `poll_events`/`acknowledge_event`'s semantics — documented, not duplicated (Decision 4).
- `body-layer/tests/test_tools.py` — tests for `find_place`, `describe_our_position`,
  `get_situation` (including the enrichment-required, not-optional signature).
- `body-layer/tests/test_tool_api.py` (new) — asserts `TOOL_SET` contains exactly the twelve
  named tools and each entry's `fn` is callable/importable (a registry-completeness test, not a
  behavioral one — behavior is covered where each tool is actually implemented).
- `body-layer/tests/test_console.py` — tests for the three new commands.
- `plans/body-layer/plan.md` — no content change planned; BL-5's entry already scopes correctly,
  confirmed against this plan.

### Implementation Plan

1. **World-model: `find_place_by_name`.** Add `query/search.py`, its `PlaceMatch` result
   dataclass, and the control-point test. This unblocks body-layer's `find_place` without
   touching `describe.py`. Run world-model's own format/lint/type/test before moving on — the
   root `CLAUDE.md` in-process seam means a broken world-model function fails body-layer's mypy
   too.
2. **`describe_our_position` + `get_situation`.** Build on the now-required `EnrichmentContext`
   pattern; validate against a fixture `ContactStore` + fake `EnrichmentContext` (mirroring
   `test_enrichment.py`'s existing fixture style). This is the minimal useful slice — a human can
   already ask "where are we" and "what's the situation" by hand.
3. **`find_place` (body-layer side) + `poll_events` alias.** Wraps step 1's world-model function;
   `poll_events` is a one-line addition once named.
4. **`tool_api.py` registry + console commands.** Wires everything built above into the
   documented, enumerable surface and the human-operable console commands. Run the full
   acceptance test by hand against a replay/console session: contacts, attention, places, events,
   situation, position — a full tactical conversation using only the twelve tools.
5. **Refine.** Tune `get_situation`'s highest-attention selection and `describe_our_position`'s
   phrasing against a couple of real console sessions, same "tune later, structure now" posture
   `phrasing_hints.certainty`'s thresholds already use in §3.4.

### Decisions Requiring User Input

None — the four questions raised before planning all resolved to local, reversible calls
(reasoning below), and no architectural conflict with `CLAUDE.md` invariants surfaced.

**Decision 1 — Transport: in-process only, no HTTP this milestone.** The milestone brief says
"over HTTP or in-process" but nothing downstream needs a wire transport yet: BL-5a is explicitly
typed-input/printed-output *in-process* per its own plan entry, and BL-6/BL-7 don't name a
transport requirement either. §7's "Tool-set freeze point is the end of BL-7, not BL-5" note
means the tool surface itself is still expected to grow — standing up HTTP now would mean
versioning a wire contract twice (once now, again at BL-7) for no consumer in between. `tool_api.
py`'s registry is deliberately transport-agnostic (name → description → callable) so adding HTTP
later is a thin adapter over it, not a redesign. Revisit only if a real out-of-process consumer
appears before BL-7.

**Decision 2 — `find_place` touches world-model, scoped small.** No text-name search exists in
`query/`; the alternative (body-layer reaching into `store.reader.all_features` directly) would
break the "go through `query`'s public API" precedent `enrichment.py` already established for
this seam. A ~30-line `query/search.py` wrapping the existing `all_features` call is the smaller,
more consistent change.

**Decision 3 — `describe_our_position`/`get_situation` take a required `EnrichmentContext`, not
an optional one.** Every existing contact-facing tool makes `enrichment` optional so it degrades
gracefully to BL-2's pre-enrichment shape. These two tools have no meaning without world-model
access and ownship state — there is no smaller "BL-2-shape" fallback to degrade to — so making it
required (and raising, not silently returning an empty result, if called without one) is more
honest than pretending a degraded mode exists.

**Decision 4 — `poll_events` is a one-line wrapper around `list_events(unacknowledged_only=True)`,
not a rename.** `console.py`'s `events` command already calls `list_events` with that exact
default, i.e. BL-4 already built poll semantics — §3.3's naming is just forward-reference drift
from before `tools.py` existed. Renaming `list_events` would touch `console.py` and its tests for
no behavioral gain; adding `poll_events` as the name the tool registry actually exposes (while
`list_events` stays as the more general two-mode function console already uses) satisfies both
the milestone's exact tool-list wording and "don't rewrite existing tests" from `AGENTS.md`'s
Escalation Rules.

### Risks & Unknowns

- **`find_place_by_name`'s matching is deliberately naive (substring, not fuzzy/synonym).** "the
  LZ" or "the ridge to the west" (§3.3's own examples) won't resolve against a DCS/OSM feature
  name at all — those need either a mission-plan lookup (LZ) or a spatial/directional query
  (ridge to the west), neither of which BL-5 builds. `find_place` will only resolve names that
  are literally close to a stored feature's `name` field. Document this gap explicitly in the
  tool's description string so a future caller (brain or human) doesn't expect more than it
  delivers — this is the same "don't fake what BL-6 hasn't built" discipline `get_contacts`'s
  `filter` docstring already applies to `"threats"`/`"near_aircraft"`.
- **`get_situation`'s "highest-priority thing" has no real priority signal yet** (relevance is
  BL-6). The attention-based ordering is a reasonable stand-in but will look naive once real
  threat assessment exists — expected, not a defect, but worth flagging so BL-6 doesn't have to
  reverse-engineer why `get_situation` picked what it picked.
- **BL-8 memory-model awareness (per the 2026-09-10 note):** `get_situation`'s aggregate is
  computed fresh per call from existing state, not a new persisted structure — nothing here adds
  a field/store shape that would need reshaping for a future mission-end export.
- **Console acceptance testing is manual** (per `tools.py`'s established pattern) — no automated
  end-to-end "full conversation" test; `test_console.py`'s per-command tests plus a manual
  session pass stand in for it, consistent with how BL-4's acceptance was verified.

### Second-Order Effect

Closes out the BL-5 subset named in §6, which per §8's "Unblocks" note makes a brain-layer plan
writable and cheaply prototypable by hand against `tool_api.py`'s registry — but the registry
should be read as provisional scaffolding, not a frozen contract, since §7 explicitly holds the
freeze point at BL-7: BL-5a's `say`/`ask_player` and BL-7's `scan_area`/`get_task_status`/
`cancel_task` will extend `TOOL_SET` rather than replace it, so a brain-layer prototype built
against this milestone's surface should expect to grow, not stabilize, before BL-7.
