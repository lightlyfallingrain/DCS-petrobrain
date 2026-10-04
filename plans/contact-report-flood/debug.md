### Debug Report

### Observed Issue

Live mid-flight complaint, in the user's own words: *"The contact detection and grouping has
improved, but still when there are units around, I hear a near constant stream of contact
reports. It becomes noise, there is no signal. It also feels like many of those reports were
about the same units."*

Investigated from a real sortie snapshot (`sortie-1004/belief-truth.jsonl`, 1677 lines,
`sortie-1004/detection-trace.jsonl`, 266,700 lines) covering `t_sim` 682.3-1027.9 (5.76 min).
23 spoken lines over that span, ~4/min sustained — confirming the orchestrator's first-pass rate.
50 distinct real `object_id`s, 34 distinct `contact_id`s.

### Hypothesis

**Confirmed: genuine contact churn, not a disclosure-policy question.** This is a different
sortie shape from `plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md` (which found
near-1:1 contacts:objects with almost no re-founding, and attributed that sortie's noise to
*singular-callout policy*, not churn). This sortie shows **real re-founding events**, reproduced
below from the raw per-tick association output (`detection-trace.jsonl`), not inferred from
`belief-truth.jsonl`'s own contact↔object join (which `plans/contact-fragmentation-at-range/
debug.md` already flagged as unreliable — it re-resolves to "whichever object is nearest now,"
and this sortie's log shows the same artifact: `CONTACT_21` nearest-joins to 10 different
`object_id`s over the flight, which is the join drifting, not 10 real re-founding events).

**Mechanism, precise**: `NakedEyePerceptionSource._build_observations`' object-permanence
continuity (module docstring point 6, `src/perception/naked_eye_source.py`) resolves by
*majority object overlap* across a poll's clusters. When the o'clock scan cone's sweep (or a new
vehicle entering the gaze window) causes **several already-separately-tracked contacts' objects to
fold into one supercluster on a single poll**, the rule can only inherit *one* historical identity
— whichever cluster holds the majority vote (ties broken by lowest observation-id string,
documented as "physically meaningless, only deterministic"). **Every other contact whose object(s)
got absorbed into the merged cluster is simply abandoned**: it receives no further observations,
and nothing tells `ContactStore` its object moved into the surviving contact rather than
vanishing — it just decays toward `lost` on the ordinary clock. The merged cluster continues under
the winning id, and if it later re-splits, the re-split correctly traces back through that single
surviving lineage (every member's own `_object_id_to_last_observation_id` entry was overwritten to
the merged id regardless of whether it won the vote) — so this is not an unbounded snowball, but it
is a **one-time, irreversible loss of 2+ already-known identities per merge event**, each loss
re-triggering a "first sighting" callout for ground the pilot has already been told about.

This is the same mechanism class `plans/contact-fragmentation-at-range/debug.md` diagnosed
("three things churn [continuity]: the gaze sweeps... the gate is marginal at range...
`NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` throttles admission") and partially mitigated (raising that cap
3→5 on 2026-09-25) without re-flying against a denser scene. This sortie's scene is denser than
that mitigation was validated against, and demonstrates the mechanism the fragmentation debug
predicted but never captured live: **merging**, the mirror image of the "splitting" case the
continuity rule's own design (`plans/group-contact-model/plan.md`'s Splitting section) was built
and tested for.

### Evidence

**Live-trace reproduction, one tight cluster of real vehicles, `t_sim` 699-751:**

Six close T-55/BTR-80-type objects (`16843520`, `16843776`, `16844032`, `16844288`, `16844800`,
`16845056`), all within the gaze cone's sweep near 4-4.5 km range, produced **5 distinct contact
ids** (`CONTACT_3/4/5/7/8`) across just 4 admission events in 52 seconds — and **6 separate speech
lines** for this one patch of ground in that window (`t_sim` 699.073, 704.407, 714.452, 719.994,
730.885, 751.247 — "ground, 12 o'clock...", "A couple of contacts...", "ground, 1 o'clock..." x2,
"A couple of contacts..." x2). Traced poll-by-poll via `detection-trace.jsonl`'s
`observation_id`/`cluster_member_object_ids`:

| `t_sim` | cluster membership | continues | result |
|---|---|---|---|
| 699.073 | `{16844288,16845056}` | — | founds `CONTACT_5` |
| 699.073 | `{16844800}` | — | founds `CONTACT_7` |
| 714.452 | `{16844032}` | — | founds `CONTACT_8` |
| 730.885 | unchanged | re-observed | `CONTACT_5`/`7` continue |
| 750.011 | `{16844032,16845056}` | `CONTACT_8` | `16845056` switches from `CONTACT_5` to `CONTACT_8` |
| 751.247 | `{16843776,16844032,16844288,16844800}` | `CONTACT_4` | **absorbs `CONTACT_5`'s and `CONTACT_7`'s objects; both abandoned** |
| 751.247 | `{16843520,16845056}` | `CONTACT_3` | **absorbs `CONTACT_8`'s remaining object; abandoned** |

At 751.247 the 4-member supercluster's vote was a genuine, non-tie majority once `16843776`'s own
established identity (`CONTACT_4`, 1 vote, already 2 polls old) is counted alongside `16844288`'s
(`CONTACT_5`, 1 vote) and `16844800`'s (`CONTACT_7`, 1 vote) — a 3-way tie resolved by the
documented lowest-id tie-break, landing on `CONTACT_4`. This is reproduced deterministically
(no tie-break dependency) in a new regression test, below.

**Sortie-wide corroboration**: 11 of 50 real objects show >1 distinct `contact_id` over the
flight in the *raw association output* (not just the unreliable belief-truth join) — each one a
re-founding event of this same shape.

**Regression test** (new): `body-layer/tests/test_naked_eye_source.py::
test_merging_previously_separate_contacts_abandons_the_minority_identities`. Three
already-independent, already-identified clusters (2+1+1 real objects) are established over two
polls, then a third poll adds two new objects that single-link-chain all of them into one
six-member supercluster — exactly what a scan sweep admitting one more vehicle into view does,
with nothing needing to physically move. The merge resolves to the clean majority (2 votes, no
tie to break — not an edge case a better tie-break would fix), and the two 1-vote identities are
confirmed absent from the result: nothing further ties them to the surviving contact.

### A second, unrelated density anomaly — explained, not a defect

The task also flagged `CONTACT_27/29/30` (292/585/583 belief-truth rows in the final 17 `t_sim`
seconds) as possibly a second defect. It is not load-bearing for the flood complaint:

- `detection-trace.jsonl` shows **123,232 rows at the single final `t_sim`** (1027.876) against a
  normal tick's ~400 — a ~306x blow-up confined to one instant.
- `DetectionTraceWriter.write_poll` (the writer that actually clears the shared
  `DetectionTraceCollector` each poll) is unchanged and correct — verified by reading it; this
  is not the collector-never-cleared bug that shape would suggest.
- **No speech was produced during or after the blow-up** — the last spoken line is at `t_sim`
  1027.271, strictly before it. The pilot never heard anything from this.
- The pattern (sim time frozen while real-time polling continued for roughly 300 extra 1-second
  cycles, each a legitimate but redundant re-observation of an unmoving scene, each stamped with
  the same frozen `t_sim`) is consistent with DCS being paused or the aircraft-layer connection
  serving a static cached snapshot during the window this debug snapshot was captured in — exactly
  when a live sortie would be paused to pull a diagnostic copy of the logs. It produced log volume,
  not cockpit noise, and is out of scope for this fix.

### Fix Applied

**None — escalating, per this role's own constraint** ("if the fix requires architectural change,
stop and escalate to the Architect") and consistent with the two prior debug passes on this exact
mechanism class:

- `plans/contact-fragmentation-at-range/debug.md` (2026-09-25): diagnosed, mitigated (cap 3→5),
  explicitly left the ambiguity/continuity policy question open.
- `plans/contact-duplication-ambiguity-runaway/debug.md`: same class of decision (what the
  ambiguity/continuity rule should do when it has more than one live candidate), formally
  escalated to Architect, never patched.

This is a third occurrence. The two previous reports both concluded the available fixes are
design tradeoffs, not mechanical bugs — this one confirms that reading for the *merge* direction
specifically (the splitting rule's mirror image, which the original plan never analysed because it
only modelled one parent splitting, not several independent parents colliding). No version of a
localized patch is available that doesn't change this documented policy:

- The tie-break (`lowest observation-id string, lexicographic not numeric`) is explicitly
  "physically meaningless, only deterministic" per its own docstring — fixing its lexicographic-
  vs-numeric mismatch would not change the actual defect (still an arbitrary pick among tied
  claims, still abandoning the others) and is not worth a commit on its own.
- Reproduced the user's symptom with a **clean majority vote, no tie at all** — so "pick a better
  tie-break" is not even the relevant lever here. The actual decision needed is: what should
  happen to the identities a merge discards (reconcile them into the surviving contact's history so
  `ContactStore` knows, suppress the "first sighting" callout for a contact whose position closely
  overlaps a very-recently-abandoned one, or something else) — the same class of call the two prior
  reports already routed to Architect.

### Verification

Confirms the diagnosis and the new regression test only — no production code changed.

- `.venv/bin/ruff format src tests` — 1 file reformatted (the new test), re-verified clean.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy src` — passed, no issues (53 source files; the new test lives in `tests/`, which
  this subproject's own `mypy src` command does not cover, matching existing practice).
- `.venv/bin/pytest tests -q` — **1389 passed, 4 xfailed** (baseline on `main` was 1388 passed, 4
  xfailed; the one new test accounts for the difference, no regressions).

### Recommendation for the Architect pass

Decide the policy for a continuity **merge** of 2+ previously-independent, already-identified
contacts (the splitting rule's mirror image, never analysed by the original plan):

1. Reconcile the discarded contacts' identities into the surviving one (so `ContactStore` learns
   their objects moved, rather than treating them as simply gone) — closest to "no information
   lost," but a `Contact`-to-`Contact` merge is new territory for the belief layer.
2. Suppress the spontaneous "first sighting" callout when a freshly-surviving contact's position
   closely overlaps a contact that went `lost` very recently (bounds the *symptom* — redundant
   callouts — without touching the continuity/ambiguity mechanism itself).
3. Something else informed by real DCS mission-object spacing distributions, which neither prior
   debug pass had in hand either.

This is the fourth time this mechanism class has surfaced (`contact-fragmentation-at-range`,
`contact-duplication-ambiguity-runaway`, `BL-B24`, and now this). Worth deciding once rather than
re-diagnosing a fifth time.
