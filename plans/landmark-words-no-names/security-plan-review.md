## Security Plan Review: landmark-words-no-names (F7)

**Retroactive.** Root `CLAUDE.md`'s "New feature"/"Refactor" role sequences call for a Security plan
review immediately after Architect and before Implementer. For this feature the sequence instead
ran Architect → Implementer → Reviewer → Performance Reviewer → Security (deep analysis) → Reviewer
(re-review) — the plan-review step was simply not invoked at the right point, and no user override
is on record. This review reconstructs the plan-stage gate against `plans/landmark-words-no-names/
plan.md` as originally written, then separately asks whether running it on time would have changed
anything, following the format set by `plans/emitter-visibility/security-plan-review.md`.

### Dependencies Checked

- The plan's "What already exists here" section makes no explicit dependency-posture statement
  (unlike some other plans in this repo that state "no new dependency" outright), so this was
  verified rather than taken on faith.
- `git diff main...HEAD -- '*/pyproject.toml'` — empty. No subproject manifest changed.
- `git diff main...HEAD -- body-layer/src/belief/enrichment.py body-layer/src/belief/speech.py
  world-model/src/query/describe.py | grep '^\+.*import'` — the only new import anywhere in the
  diff is `import tuning` in `enrichment.py`, which is this project's own existing constants loader
  (`body-layer/src/tuning.py`), already used by every other constant in that file (confirmed:
  `tuning.real(...)` calls already present above the new one). `speech.py` and `describe.py` add no
  imports at all.
- **Verdict: CLEAN. No dependency change.** The plan's silence was accurate, same disposition as
  the `emitter-visibility` precedent.

### Design Findings

1. **No new input-trust boundary.** The plan's "Affected Modules" section adds one field
   (`SettlementInfo.area_m2`) to an existing read-only query (`describe.py`'s `_settlement_info`),
   sourced from a tag the same function already reads two lines above for an unrelated purpose
   (`_preferred_settlement`'s tie-break). Verified independently: `feature.tags.get("area_m2")` is
   populated only by `world-model/src/build/ingest_osm.py`'s offline build pipeline from a computed
   `ring_area_m2` float — never supplied at body-layer runtime, never derived from mission (`.miz`)
   data, never network-received. No new attacker-reachable input is introduced; this is additive
   read access to data the store already carries.
2. **No expansion of the brain-facing `TOOL_SET` surface or mission memory.** The plan's own text
   states `belief.tools` and `admission.py`/`marks.py` are left untouched because they read
   `SemanticFact.text`/`feature_id` directly rather than through `speech.py`. Verified independently
   against the actual diff, not the plan's claim: `git diff --name-only main...HEAD` lists no change
   under `body-layer/src/belief/tools.py`, `mission_memory/admission.py`, or `mission_memory/
   marks.py` — those three files do not appear in the changed-file list at all. The plan's argument
   holds against the code as it stands, not only as described.
3. **No no-omniscience invariant risk.** The plan is explicit that this is a wording-only change:
   the new size word is computed from the *same* `SettlementInfo` the settlement name already came
   from, and `SemanticFact.text`/`confidence`/`provenance` are unchanged for every kind. This is the
   correct framing for a feature that touches speech rendering — the risk this invariant guards
   against (Petrovich knowing more than he could perceive) is categorically not implicated by a
   change that only narrows what is *said*, never what is *known*. The plan's own "Second-order
   effect" section reaches the same conclusion and names the one live boundary question (brain
   reading tool results aloud as free text) as explicitly out of scope, correctly deferred rather
   than silently ignored.
4. **New tunable's bounds are sane.** `BUILT_UP_VILLAGE_MAX_AREA_M2: Final[float] = tuning.real(...,
   1_000_000.0, lo=100_000.0, hi=5_000_000.0, status="judgement")` as planned. Checked against
   `tuning.real`'s own contract (`body-layer/src/tuning.py:402`): both bounds and the default are
   literal floats (not computed expressions), the key is absent from `_COUPLED_KEYS`
   (`tuning.py:305`, currently the three scan/decay keys only) so no cross-key coupling trap
   applies, and the rendered `defaults.toml` line (`BUILT_UP_VILLAGE_MAX_AREA_M2 = 1000000.0`)
   matches the planned default — checked in the rendered file, not just the `#:` source comment,
   per this role's own standing habit. A 1 km² default for the village/town cutoff is an
   unvalidated first guess exactly as the plan's own "Risks & Unknowns" section says, same status as
   this module's other placeholder radii (`NEAR_FACT_RADIUS_M`, `TERRAIN_QUALIFIER_MAX_M`) — not a
   security concern, a tuning concern the plan already flags for post-merge flying.
5. **No new file-system, IPC, or deserialization surface.** The plan's changes are confined to a
   pure in-process data flow (world-model query → enrichment `feature_id` encoding → speech string
   formatting), no new endpoint, no new file read/write, no new wire format. The `feature_id`
   encoding change (colon-delimited segments) is parsed only with `str.partition`/`str.split`, never
   evaluated or used to build a path/query — the plan does not specify this parsing detail, but
   nothing in the plan's design implies anything riskier than string splitting either.
6. **No auth/access-control gap.** Single-player, LAN-only project; this feature narrows disclosure
   (drops names and distance figures from speech) rather than widening it.

No finding here rises to "known CVE," "high-risk design pattern without justification," or "missing
safeguard the plan should have specified but didn't" at a severity that would block.

### Verdict

**APPROVED**

### Would this have changed anything, had it run on time?

**No material change.** The three things a plan-stage review exists to catch before code is written
— a new dependency, an untrusted-input path, and an expansion of the brain-facing/mission-memory
surface or the no-omniscience invariant — were all already addressed in the plan's own "What already
exists here" section, and all three check out against the actual diff, not just the plan's
assertions (see Design Findings 1–2 above). There is no design alternative the plan left unexamined
that a plan-stage reviewer would have pushed back on: the `feature_id` middle-segment encoding is a
natural reuse of an existing seam (the plan itself frames it that way — "reuses that seam rather
than adding a parallel discriminator field"), and the one open scope question in the plan (coastline
losing its distance figure as a generalisation beyond what the user explicitly said) is a product
judgment call, not a security one.

The deep-analysis pass (`plans/landmark-words-no-names/security-review.md`) reviewed the actual
implementation and reached the same three conclusions this review reaches independently — clean
dependency posture, `TOOL_SET`/mission-memory untouched, no-omniscience invariant not implicated —
plus one additional, implementation-level finding the plan could not have surfaced because it only
exists once code is written: the untyped `area_m2` tag read raising `TypeError` on a
hand-corrupted store, correctly left low-severity and "not filed, intentionally" there. That is
exactly the division of labor this project's two-gate sequence is designed to produce — the plan
gate confirms the design does not create a problem; the deep-analysis gate catches what only the
written code can show. Nothing here suggests the deep-analysis pass's conclusion would have been
different, or arrived at differently, had this review run first.

No action required before DoD on this gate's account; `plans/landmark-words-no-names/
security-review.md` already stands APPROVED and is the gate that matters for the code that shipped.
