# Sortie 2026-10-05 refinements

Four small, independent post-flight fixes from the user's own debrief after flying `896369e`
(merged X-B29, DCS-driven LOS). No knowledge-graph query was possible — `graphify-out/` does not
exist yet in this worktree ("No graph yet. Build it with /graphify, then query.") — so every claim
below is grounded by reading the current source and `plans/` directly, not by a graph lookup.
Treat the graph's silence as "not built," never as "nothing exists here."

Each item is staged as its own independently-mergeable branch. They touch disjoint call sites in
disjoint files (one touches `audio-adapter`, the other three touch `body-layer` only, and within
`body-layer` they touch `enrichment.py`/`tools.py`, `crew_console.py`/`groups.py`,
`perception/gaze.py` respectively — no file is shared across two items), so the independence
claim holds.

---

### Item 1 — the location fragment: precedence, direction, distance bands, road watched-gate

**This item grew well past its one-line billing mid-plan** (the user's follow-up correction below)
and is now the largest and highest-exposure item of the four — it changes the line the pilot hears
on *every* contact report, not just the road case it started as. **Recommend splitting it into its
own branch, separate from items 2-4**, which stay small and can merge independently without waiting
on this one.

**Goal, restated from the correction.** Replace today's confidence-ranked semantic-fact pick (one
fragment, `max(semantic, key=confidence)`) with a **fixed-precedence** location fragment —
settlement, then terrain feature, then road, highest available wins — phrased as `<direction> of
<feature>, <distance band>`, with no metres figure. The road-only watched-gate from the original
ask survives as one piece of this, not the whole of it (see Q1 below).

**What's actually there (verified).**

- `semantic_facts_for` (`enrichment.py:409`) is position-only, never sees `Contact` or
  `attention`. `WorldEnrichmentCache.get_or_compute` (`enrichment.py:632`) keys its cache only on
  `Contact.last_position`, not `contact.attention` — so, exactly as in the original design, nothing
  about this change can live inside the cache or the position-only builder without creating a
  stale-cache bug when attention changes with no position change. The precedence/direction/band
  selection has to happen at the *consumption* site, same as the watched-gate did.
- The one selection site is `speech.py`'s per-contact report builder (`speech.py:944-947`):
  `best = max(semantic, key=lambda fact: fact["confidence"])`. **This is the only caller that needs
  to change.** `tools.py`'s `_our_position_summary` (`tools.py:751`) runs the identical-looking
  `max(semantic_facts, key=confidence)` but over *ownship's own* position, not a contact's — there
  is no "watched" concept for ownship and no reason ownship's ambient-status line should adopt a
  contact-report precedence rule designed around a pilot deciding whether to climb or fire. **Left
  unchanged, explicitly, and that is the full answer to "what else relies on this comparison."**
  Group disclosure (`speech.py:1017`) already drops `semantic` entirely and needs no change either.
- `terrain_qualifier` (the divide-crossing "next valley"/"beyond the ridge" fact,
  `speech.py:933-944`) already **overrides** the whole selection outright, before it runs at all —
  that precedence is pre-existing, unrelated to this change, and stays exactly as-is (see Q-new
  below for why the user's own example phrase looks like it touches this and almost certainly
  doesn't).

**Q1 — does the watched-only road gate still apply under the new precedence? Flagged prominently,
per instruction, and built as (a).** Two readings:
- **(a) (recommended, and what this plan builds):** the gate still applies to roads specifically —
  a road fragment fires only when there is no settlement, no terrain feature, *and* the contact is
  watched/priority. Precedence alone does not fix the original complaint in open desert with no
  settlement and no relief — exactly where the noise was, since that's where roads were the only
  thing nearby at all.
- **(b):** precedence alone supersedes the gate — roads rarely win now, so no extra check is
  needed.

Built as a single, named predicate (`_road_fragment_eligible(attention_level) -> bool` or
equivalent) that gates the road branch of the new precedence picker only — deletable in one line if
the user says (b) without touching settlement/terrain branches at all.

**1. Precedence mechanism.** Each `SemanticFact.feature_id` already carries a stable per-kind
prefix (`"settlement:"`, `"road:"`, `"ridge:"`/`"valley:"`, plus `"inside_settlement:"`,
`"water:"`, `"landcover:"`, `"coastline:"` — none of which the user named). Replace the confidence
pick with a fixed-order lookup over the *kind* prefixes: `inside_settlement`/`settlement` first,
then `ridge`/`valley`, then `road` (gated by Q1's predicate), each checked by prefix against the
list speech.py already receives. **Open sub-question, not named by the user:** water/landcover/
coastline facts are not in the three named kinds at all. Recommend they stay a confidence-ranked
fallback *below* the three named ones (today's degrade-gracefully behavior preserved for a position
with no settlement/terrain/road nearby but water or landcover is) — flagging this as a default
needing the same confirm-or-reject the user gave Q1, not inventing it silently. This replaces the
`max(..., key=confidence)` call at `speech.py:944-947` with a small ordered lookup function; nothing
about `SemanticFact`'s own fields needs to change for this part.

**Why confidence stopped mattering is now explained, not just observed.** `_FEATURE_CONFIDENCE_
NUMERIC` (`enrichment.py:143-148`) maps `"low"` to `0.4`; the ridge/valley position-qualifier fact
(`enrichment.py:484-498`, Decision 3's "on a ridge"/"in a valley") is built from `TerrainLineInfo.
confidence`, which the terrain layer reports as `"low"` — so it loses to almost anything at
`"medium"`/`"high"` under the old `max(confidence)` rule. That is the mechanism behind "terrain
never reached the pilot before this morning," confirmed by reading the actual confidence value, not
inferred. A fixed precedence makes this comparison moot for the three named kinds, by design.

**2. Direction, from the feature to the contact.** This landed this morning
(`plans/terrain-feature-probing/plan.md` Revision 3 Stage 4, confirmed live in
`world-model/src/query/describe.py`): `RoadInfo`, `SettlementInfo`, `WaterInfo`, and
`TerrainLineInfo` all now carry `bearing_deg: float | None` — the compass bearing *from the
feature's closest point to the query position* (`None` only when distance is exactly zero, no
direction to report). `describe.py`'s own docstrings confirm this is exactly what `BL-B14`'s two
blocked wording items ("200 metres north of the road", "next to the road, north side") were waiting
on. **This closes `BL-B14`'s world-model dependency note for real** — update that backlog item to
record the two wording bullets as now buildable, since the thing they were blocked on is done (the
backlog entry itself already says "this bullet does not go to `[x]` — the two wording items... are
still unbuilt," so the correct edit is to mark them buildable/in-progress here, not to close the
whole bullet).

I checked `geometry.signed_side_of_polyline` (`world-model/src/geometry/__init__.py:339`) as a
possible "which side" mechanism for the road case specifically, since it already exists and gives a
left/right-of-the-line answer. **It's the wrong primitive here and I'm not using it**: its sign is
relative to the polyline's own point-storage order (left/right of travel direction as the points
happen to be stored), which has no stable mapping to a compass word — the same road could read
"left" or "right" depending on which end of the array came first, and nothing canonicalizes that
order. `bearing_deg` (closest-point-to-target compass bearing) doesn't have that problem and already
exists on every one of the three relevant info dataclasses, so it's the one mechanism, used
uniformly for all three kinds: snap `bearing_deg` to the nearest of the 8 cardinal/intercardinal
compass words.

**That word table already exists, twice over, and should be de-duplicated, not copied a third
time.** `crew_console.py`'s private `_SECTOR_SCAN_LABELS: dict[Sector, str]` (line ~363) already
maps `belief.attention.Sector` to exactly this word set ("north", "northeast", ...), and
`crew_console.py` already has its own `_nearest_sector(degrees)` using `belief.attention.SECTORS`/
`_SECTOR_CENTER_DEG`/`angular_delta_deg`. Promote `_SECTOR_SCAN_LABELS` to `belief/attention.py` as
a public constant (e.g. `SECTOR_COMPASS_WORDS`) next to `Sector`/`SECTORS`, which already live
there; `crew_console.py` keeps its existing call sites unchanged by importing the promoted name
instead of defining its own. `enrichment.py` then imports the same constant plus a small
`_nearest_sector`-equivalent (or the existing one, if it's cheap to import from `attention.py`
without creating a cycle — `attention.py` already imports from `perception.gaze`/`perception.
geometry`, and `enrichment.py` already imports from `perception.geometry`, so this is a sideways
import, not new layering). This is a real duplication-removal, not a new abstraction for its own
sake (per the "do not introduce a new abstraction unless it removes clear duplication" rule) —
there would otherwise be three near-identical 8-entry dicts across two files.

**Wording templates, one per kind, each anchored to BL-B14's or the user's own example rather than
invented:**
- **Settlement:** `"<direction> of <label>, <band>"` — the user's own example, "south of village,
  near."
- **Road:** within the existing `on`/`next to` bands (<100 m), append the side rather than lead
  with direction — `"next to the road, <direction> side"`, matching `BL-B14`'s own target wording
  exactly. Beyond 100 m (the new `near`/`medium distance` bands), switch to the settlement-style
  lead-with-direction form — `"<direction> of the road, <band>"` — since `BL-B14`'s other target
  example ("200 metres north of the road") already leads with direction once the metres figure
  is replaced by a band.
- **Terrain feature:** reuses Decision 3's existing `"on a ridge"`/`"in a valley"` text
  (`_TERRAIN_POSITION_TEXT`, `enrichment.py:229`-ish) as the feature name, then appends direction
  and band the same way road does beyond its on/next-to bands: `"in a valley, <direction>,
  <band>"` — this is the literal shape of the user's own example, "in next valley, north, medium
  distance," read as "in a valley" (Decision 3's phrase, not a divide crossing) plus the direction/
  band suffix every other kind gets. See Q-new below for the one place I'm not fully confident that
  reading is right.

**Q-new (mine, not yet put to the user — flagging it the same way Q1 was flagged to me, since I
don't get to resolve it unilaterally either).** The user's own terrain example, "in next valley,
north, medium distance," is ambiguous between two readings I can't tell apart from one example
alone:
- **(i) (what this plan builds):** "in [a] valley" is Decision 3's existing on-ridge/in-valley
  position-qualifier text (a fact *about the contact's own position*, nothing to do with ownship),
  with direction/band computed from `TerrainLineInfo.bearing_deg`/`distance_m` the same way as the
  other two kinds. The divide-crossing "next valley" fact (`terrain_divide_qualifier`,
  ownship-relative, already overriding the whole selection per the paragraph above) is **not**
  touched by this item at all.
- **(ii):** the user is actually invoking the divide-crossing mechanism by name ("next valley"
  literally), and wants *that* fact's own fixed phrasing extended with direction/band too — which
  would mean touching `speech.py:933-944`'s override branch, a different code path than the one
  this item otherwise redesigns, and a materially different (bigger) change: `terrain_divide_
  qualifier` is explicitly ownship-relative and recomputed every call (never cached), so "direction"
  there would need to mean something else entirely (direction of the crossing? of the target from
  ownship?) — underspecified either way.

  I'm building (i) because it reuses an existing, already-well-specified mechanism and matches
  every other kind's design in this item; (ii) would need its own follow-up conversation about what
  "direction" even means for a divide-relative fact before it could be specified at all. If (ii) is
  what was meant, say so and this sub-piece gets reopened as its own small plan rather than folded
  in here.

**3. Distance bands — first guesses, to be flown, named explicitly as such per this project's own
calibration convention (same status as `TERRAIN_QUALIFIER_MAX_M`/`GROUP_PROXIMITY_GAP_RATIO`).**

Reconciling with prior art required finding out which distance axis each existing band actually
measures — they are **not all the same axis**, which matters for whether they're reusable here:

| band | measures | axis | status |
|---|---|---|---|
| `"on {label}"` | contact ↔ feature | feature-proximity | shipped, `_ON_FEATURE_MAX_M` = 10 m |
| `"next to {label}"` | contact ↔ feature | feature-proximity | shipped, 10–100 m |
| `"very close"` | **ownship ↔ contact** | ownship-range | shipped, `_VERY_CLOSE_RANGE_M` = 500 m, used only in the clock/range fragment (`speech.py:807-825`) |

**"Very close" is not reusable here.** It bands the ownship-to-contact range spoken in the clock
fragment ("armor 11 o'clock, very close"), a different measurement from the contact-to-feature
distance this item bands. I checked rather than assumed, since the user's message named it as
prior art to reconcile with — it doesn't conflict, because it isn't on the same axis at all; it's
just not evidence for where "near"/"medium distance" should sit either.

The two new bands extend the existing feature-proximity ladder (`on`/`next to`) upward, within each
kind's own existing "worth mentioning at all" ceiling — which differs by kind and already exists
(`NEAR_FACT_RADIUS_M` = 1000 m for settlement/road; `TERRAIN_QUALIFIER_MAX_M` = 300 m for terrain,
tighter):

| band | range (settlement/road) | range (terrain) |
|---|---|---|
| `on` | < 10 m | < 10 m |
| `next to` | 10–100 m | 10–100 m |
| `near` | 100–400 m | 100–300 m (TERRAIN_QUALIFIER_MAX_M) |
| `medium distance` | 400–1000 m (NEAR_FACT_RADIUS_M) | **unreachable** |

**Flagging the unreachable cell rather than quietly shipping it:** terrain's existing 300 m
dominance ceiling (`TERRAIN_QUALIFIER_MAX_M`) is tighter than settlement/road's 1000 m
(`NEAR_FACT_RADIUS_M`), so under these first-guess numbers a terrain feature can never be far
enough away to earn "medium distance" — it either qualifies as `near` or doesn't fire at all. That
may be exactly right for terrain (a ridge/valley over 300 m away is deliberately not "dominant"
enough to report per Decision 3), or it may mean terrain needs its own wider two-band split. Not
resolved here — flown data settles it, same as every other number in this table.

**Scope confirmed unchanged from the original ask:** group reports still drop `semantic` entirely
(`speech.py:1017`), so none of this item touches group-report wording.

**Implementation plan:**
1. Promote `_SECTOR_SCAN_LABELS` from `crew_console.py` to `belief/attention.py` as
   `SECTOR_COMPASS_WORDS`; update `crew_console.py`'s call sites to import it.
2. Add a `_direction_word(bearing_deg: float | None) -> str | None` and
   `_distance_band(distance_m: float, *, near_max_m: float, medium_max_m: float | None) -> str`
   pair to `enrichment.py`, using the promoted table and the band figures above (parameterized per
   kind so terrain's unreachable `medium distance` cell is a natural consequence of its own
   existing ceiling, not a special case).
3. Build the three wording templates (settlement / road-with-side-then-direction-split /
   terrain-feature) as functions in `enrichment.py`, each consuming the already-existing
   `distance_m`/`bearing_deg` fields on `RoadInfo`/`SettlementInfo`/`TerrainLineInfo`.
4. Add `attention_level: Attention` to `_add_enrichment_facts`'s signature (as in the original
   design) and build the single named `_road_fragment_eligible` predicate for Q1(a); the other two
   branches (settlement, terrain) are never gated by attention.
5. Replace `speech.py:944-947`'s `max(semantic, key=confidence)` with the fixed-precedence lookup
   (settlement → terrain → road, each only if the branch actually fired a fragment this call;
   water/landcover/coastline as a confidence-ranked fallback below the three, per the open
   sub-question above) — leave `tools.py:751`'s own `max(...)` call for ownship's position summary
   untouched.
6. Update `BL-B14` (`body-layer/BACKLOG.md`): mark the two direction-dependent wording bullets as
   now unblocked/in-progress under this item, rather than leaving them reading as still blocked on
   world-model.
7. Tests: direction word correctness at each of the 8 octant boundaries; band boundaries at each
   kind's own ceiling (including the terrain "medium distance never fires" case as an explicit,
   named test rather than an accidental gap); precedence order with two and three kinds
   simultaneously in range; Q1(a)'s road gate (watched vs. not, with no settlement/terrain in
   range either way); the terrain-feature wording under reading (i) only, per Q-new.

---

### Item 2 — "describe" as a synonym for "report"

**Goal:** recognize "describe"/"describe contacts" as additional phrasings for the existing
`report_all` command.

**Whose job is whose:** a pilot who says "describe" meaning "report" and gets "unable, no such
command" loses trust in voice as primary input (root `CLAUDE.md`'s own stated direction: "voice is
primary"). Fixing recognition is squarely in the "understand what's out there" value bucket.

**Correcting the premise I was handed.** The brief suggested two places hold synonyms and must
stay in sync. I checked both candidates and that is not the shape of this codebase:

- `audio-adapter/src/vocabulary.py`'s `PHRASES["report_all"] = ("report", "report contacts", "what
  do you see")` (line ~310) is the one and only place voice phrasings for this token are declared.
  `command_matcher.py`'s `VERB_ANCHOR_WORDS` is *derived from* `PHRASES` at import time (its own
  comment, vocabulary.py:277), so a new phrasing there automatically becomes an anchorable verb —
  nothing else to touch for voice recognition.
- `body-layer` deliberately holds **no copy** of that phrase table at all —
  `belief/voice_commands.py`'s own module docstring is explicit: "`audio-adapter`'s
  `command_matcher.py` owns everything mechanical... body-layer never imports it... reproduced
  here as plain arguments so body-layer holds no copy of that module or of `vocabulary.py`'s
  phrase table." `CrewConsole.handle_command`/`handle_transcript` only ever see an
  *already-resolved* token string (`"report_all"`) plus the matcher's scores — they never
  re-match a phrase. `crew_console.py:484`'s `_TOKEN_DESCRIPTIONS["report_all"] = "report"` is a
  confirm-prompt *display* string keyed on the resolved token, not an input-matching table — it
  renders identically regardless of which phrasing triggered the match, so it needs no edit.
- Typed free text (`CrewConsole.handle_line` → `belief.utterance.parse_utterance`) has no "report"
  command at all today — its `_PATTERNS` table only recognizes `set_attention`/`describe_contact`
  sentence forms (`watch X`, `where's X`, `status X`). `describe_contact` there is a pre-existing,
  *unrelated* intent name (single-contact description by reference) — there is no "describe"
  literal pattern in that table, so no name collision exists, and bare "report"/"describe" typed
  as a sentence does not resolve there either way, unaffected by this change.

So this is a **one-file, one-line edit**: `audio-adapter/src/vocabulary.py`.

**Checked the trap that killed bare "quiet" (`PHRASES["silence"]`'s own documented rejection,
vocabulary.py ~347-367): a short, common word scores dangerously close to an unrelated token under
the fuzzy matcher and was rejected for exactly that reason.** "Describe" is six letters, phonetically
distinct from every existing anchor verb (`scan`, `watch`, `follow`, `report`, `cancel`, `stop`,
`silence`), and is not a word used conversationally in this cockpit's existing vocabulary — the
collision risk "quiet" had (close to no existing token, but an everyday word liable to appear in
ordinary speech near the mic) does not apply the same way. I did not re-run the `SequenceMatcher`
bench myself; flagging that as the one open check rather than asserting it's clear from inspection
alone.

**Implementation plan:**
1. Add `"describe"` and `"describe contacts"` to `PHRASES["report_all"]`, mirroring the existing
   `"report"`/`"report contacts"` pair.
2. Add/extend a command-matcher test fixture asserting `"describe"` alone and `"describe contacts"`
   resolve to `report_all` above `MATCH_FLOOR`/`VERB_FLOOR` with no separation-check collision
   against any other token's phrasings.
3. No `body-layer` or `crew_console.py` change — confirmed above.

---

### Item 3 — `follow`/`watch group <where>` tags every member as watched

**Goal:** when a `follow`/`watch` command resolves to a contact that is part of a multi-member
`belief.groups.Group`, mark every member of that group watched, not just the one contact the
resolver happened to pick.

**Whose job is whose:** the pilot thinks in terms of "that convoy," not "that one blip inside it" —
tagging only the lead vehicle as watched means the rest of the convoy silently falls back to
ordinary decay/report cadence the moment it's the one the pilot *didn't* point at. Watching the
whole thing he actually meant is squarely in the "evade/attack" value bucket (a convoy he's tracking
for an ambush or a bypass needs its laggards reported too).

**A naming collision that has to be surfaced before this is built, not after.** The `follow`/`watch`
resolver (`_resolve_follow_target`, `crew_console.py:1275` `_descriptor_score`) already has a
descriptor word **spelled "group"** — but it means something different from what the user is
asking for. `audio_adapter.vocabulary.DESCRIPTOR_WORDS` includes `"group"` as one of the closed
set of classification words (`armor`/`truck`/`infantry`/`sam`/`aaa`/`ship`/`group`), and on the
body-layer side `_descriptor_score`'s `"group"` branch (per its own comment at `crew_console.py:275`,
"not a classification match at all") scores against `facts["cardinality"].lo > 1` — i.e. it picks
the single `Contact` whose own estimated unit-count is more than one (a detected *blob*, from
`belief.cardinality`). That is **not** `belief.groups.Group` (`groups.py:258`) — the persistent,
world-space association of several *separately-tracked* `Contact` ids built by `group-reporting`'s
`GroupStore`. A pilot saying "follow group" today picks one multi-unit-estimate contact and watches
only that one contact id; it has nothing to do with `GroupStore` membership at all.

**So the real fix doesn't key off the descriptor word "group."** It keys off whatever contact the
resolver ends up picking, through whichever descriptor/clock/range combination won — `_handle_follow`
and `_handle_watch_nearest` both already resolve to exactly one winning `contact_id`
(`crew_console.py:1420`, `:1231`). The fix: after that resolution, look up
`self.store.group_for_contact(contact_id)` (`ContactStore` already delegates this to its own
internal `GroupStore`, per `contacts.py:707` — no new wiring needed, `GroupStore` is already owned
by `ContactStore`, not a separate object `CrewConsole` would need to be handed). If a `Group` with
`len(member_contact_ids) > 1` comes back, mark every member watched, not just `contact_id`.

**Implementation plan:**
1. In `_handle_follow` and `_handle_watch_nearest`, after resolving the winning `contact_id`, call
   `self.store.group_for_contact(contact_id)`.
2. If it returns a `Group` with more than one member: for each `member_contact_ids` entry, call the
   same watch mechanism already used for the single-contact case (`watch_contact_task` when
   `self.tasks` is configured, else `set_attention(..., "watch", ...)`) — same call, just looped
   over the member set instead of the single id.
3. Readback: extend `render_watch_nearest_readback` (or add a sibling) to name the group case —
   "watching the group, N contacts" or similar, rather than silently reusing the singular phrasing
   that would misreport how many contacts are now actually watched. This needs a concrete wording
   decision (see below).
4. Tests: a multi-member `Group` resolved via `follow`/`watch_nearest` marks every member's
   `Contact.attention == "watch"`; a single-member (ungrouped) contact behaves exactly as today
   (regression guard); the readback names the group case distinctly from the single-contact case.

**Effort/value check (per `AGENTS.md`, since this is the item that turned out materially different
from its one-line billing).** The one-line-looking ask ("tag all units in that group as watched")
is a small, bounded change *given* the static reading below — `GroupStore` and the member-id list
already exist, and `group_for_contact` is already wired into `ContactStore`. It only grows
expensive if built as **live membership-following** (a "watched group" concept that keeps
re-resolving who's a member and auto-watches new arrivals/auto-unwatches departures across a
`Group` split/merge, which `groups.py`'s own docstring already describes as id-preserving on one
side and id-churning on the other). That would need a new persistent "this id names a watched
*group*, not a watched contact" concept paralleling `AttentionArea`'s dynamic re-evaluation, plus
split/merge-aware re-tagging logic nothing in this codebase has today. **Recommend the static
snapshot** (tag today's members, once, at command time) as the whole of this item; the dynamic
version is a different, bigger feature with no clear pilot-value gap over the static one for a
single sortie's convoy-tracking use case. State this explicitly rather than quietly building the
cheap version while the ask reads as the expensive one.

**Known, pre-existing condition this item uses more aggressively, not a new one.** The watch count
is already uncapped — `plans/dcs-driven-los/performance.md:120-126` names an `AttentionArea` as
already able to "pull an arbitrary number of contacts into watch-equivalent attention," with the
per-watched-contact tick cost (iterative LOS projection, `_terrain_aware_world_position`'s
`max_iterations` branch at `enrichment.py`'s own read of `contact.attention == "watch"`) scaling
with watch-list size, and that was **APPROVED, no action** as pre-existing. This item can mark many
contacts watched in one command (a large convoy), which is a bigger single-shot jump than
`AttentionArea`'s gradual growth, but it is the same mechanism already accepted — not a new
performance class to design around now.

---

### Item 4 — `scan ahead` sweeps 11-12-1, not a static 12 o'clock

**Goal:** `scan ahead` should cycle the naked-eye focus cone through 11 → 12 → 1 o'clock on the
existing scan-dwell loop, the same structural mechanism `scan left`/`scan right` already use for
their own three-hour spans, instead of staring fixed at 12 o'clock forever.

**Whose job is whose:** "scan ahead" reading as "stare dead ahead" means Petrovich misses anything
drifting into the 11 or 1 o'clock edge of the forward arc during a commanded scan — directly a
detection gap in front of the aircraft, the one direction most contacts-to-evade-or-attack actually
appear from.

**Correction received mid-task, now the plan's basis (superseding what I was initially briefed
with):** this is **not** a cone-widening change. 11-12-1 is three clock hours of sweep, visited one
hour at a time on the same dwell loop `scan left`/`scan right` already run — structurally identical
to them, just with `ahead`'s own three-hour list instead of theirs.

**What's actually there (verified).** `perception/gaze.py`'s `_SECTOR_LEGS` table (line 245) is
exactly the per-sector hour-sequence data `scan_at` cycles through:
```python
_SECTOR_LEGS: Final[dict[RelativeSector, tuple[int, ...]]] = {
    "ahead": (12,),
    "left": (11, 10, 9),
    "right": (1, 2, 3),
    "full": SCAN_PLAN,
}
```
`"ahead"` is a one-element tuple. `gaze_at` (`gaze.py:419`) indexes `legs[index]` where `index =
min(int(elapsed_s // FOCUS_DWELL_S), len(legs) - 1)` — with `len(legs) == 1`, `index` is always `0`
and the gaze never advances off `12`; the module's own docstring already names this as deliberate
degenerate behaviour for a single-leg sector. `left`/`right` already prove the cycling mechanism
works for a three-hour span. **This is a one-line data change**: `"ahead": (12,)` → `"ahead": (11,
12, 1)`. No new code path, no change to `gaze_at`, `ScanPlan`, or any caller.

**The LOS cone is unaffected, and here is why, stated plainly so a later reader doesn't go looking
for a cone change that must not happen.** `logger.py`'s look-direction push (`logger.py:511-521`)
reads `gaze_at(ownship.t_sim, self.scan_plan)` — the exact same function, same `ScanPlan` — every
poll, and derives `(_hour_for_gaze(gaze), LOOK_DIRECTION_FOV_HALF_DEG)`. `LOOK_DIRECTION_FOV_HALF_DEG`
is a fixed `90` (`logger.py:1009`), independent of which o'clock hour is currently active and
independent of this change entirely — it was already wide enough to cover whichever single hour the
naked eye is looking through, for `left`/`right`'s existing three-leg cycling. Widening `_SECTOR_LEGS`
for `ahead` to three legs makes it cycle through the exact same `_hour_for_gaze`/`post_look_direction`
path `left`/`right` already exercise every poll; nothing about the cone's width, the push mechanism,
or the FOV argument changes. (I was initially told this needed checking for a cone-widening
interaction; that concern is retracted — see the correction above — and this paragraph records why,
so the retraction isn't silently lost if this plan is read later without the conversation that
produced it.)

**The real behavioural effect, worth naming rather than settling here.** `FOCUS_DWELL_S` is `2.0`;
previously `"ahead"` dwelled on 12 o'clock continuously (never cycling — `len(legs)-1 == 0`). With
three legs, `cycle_s = len(legs) * FOCUS_DWELL_S = 6.0`s, so each hour is now revisited only once
per 6 seconds (dwelling 2s, then 4s looking elsewhere) — a real reduction in how often dead-ahead
specifically is looked at, in exchange for the 11 and 1 o'clock edges now being looked at at all.
This is the same scan-cadence tradeoff `todo/backlog.md`'s existing dwell/revisit-interval item
already carries as an open, unsettled question (not resolved by this plan, not newly introduced by
it) — `scan ahead` now joins `scan left`/`scan right` in that same open question rather than being
exempt from it. No action proposed here beyond naming it.

**Implementation plan:**
1. `perception/gaze.py`: change `_SECTOR_LEGS["ahead"]` from `(12,)` to `(11, 12, 1)`.
2. Update the module/`_SECTOR_LEGS` docstring comment (currently says `ahead -> just 12`) to match.
3. Tests: `gaze_at` over a full `ahead`-commanded `ScanPlan` cycle visits 11, 12, and 1 in order,
   each for `FOCUS_DWELL_S`; confirm `left`/`right`/`full` behaviour is unchanged (regression guard,
   since they share `gaze_at`/`ScanPlan` with this table); confirm `_hour_for_gaze`/look-direction
   push still fires correctly at each of the three legs (no change needed to that function, but the
   existing poll-loop test fixture should now see three distinct pushed hours over one `ahead` scan
   cycle instead of one unchanging hour).

---

### Cross-cutting notes

- **Staging order, revised**: Item 1 is no longer the second-smallest — it is now the largest and
  should be its **own branch**, built and reviewed independently of the other three. Suggested
  order: Item 4 (smallest, most isolated) → Item 2 (one-file, no body-layer change) → Item 3 (one
  real design decision, bounded) → **Item 1 on its own branch**, not gated behind the other three
  and not holding them up either.
- **Subprojects touched**: `body-layer` for items 1, 3, 4 (item 1 also touches `world-model` only
  to the extent of *reading* the already-merged `bearing_deg` fields — no further world-model
  change needed); `audio-adapter` for item 2 only. Each touched subproject's own format/lint/
  `mypy --strict`/`pytest` gate must run — `cd body-layer && .venv/bin/mypy src` (CWD-only config
  discovery, per that subproject's `CLAUDE.md`) and the equivalent for `audio-adapter`.
- **No new dependency, no schema change, no cross-subproject coupling beyond what already exists**
  for any of the four.

### Second-order effects

- **Item 1** is now a bigger second-order lever than its original billing: it establishes
  *precedence* (settlement > terrain > road, confidence demoted to a fallback tier) as this
  project's answer to "which single landmark fact does a contact report lead with," which any
  future semantic-fact addition (a new `describe_position` field) now has to slot into that
  ordering explicitly rather than just appending to a confidence-ranked list. It also promotes
  `_SECTOR_SCAN_LABELS` out of `crew_console.py` into `belief/attention.py` as a shared constant —
  a small, deliberate de-duplication that later direction-wording work (anywhere else a bearing
  needs a spoken compass word) should now reuse rather than reinventing a fourth copy.
- **Item 2** — none identified; purely additive recognition surface.
- **Item 3** sets a precedent: the first command that mutates more than one `Contact`'s belief state
  from a single player utterance. A later milestone building per-contact undo/cancel semantics (the
  existing `cancel_watch` token) needs to decide whether cancelling one group member's watch should
  also offer "cancel the whole group" — not resolved here, since the static-tag design makes every
  member an ordinary independently-watched contact afterward with no group-watch record kept.
- **Item 4** — none identified beyond the named open dwell-cadence question, which already existed
  for `left`/`right` before this change.

### Decisions Requiring User Input

- **Item 1, Q1 (the user's own, already answered as (a) — restated here as the thing actually being
  built, not still open):** the watched-only gate applies to the road branch only, under the new
  settlement → terrain → road precedence. Listed here for visibility since it's the one piece of
  the original ask that survives unchanged inside a much larger redesign.
- **Item 1, Q-new (mine, genuinely open):** whether the terrain-feature branch's direction/band
  wording is about Decision 3's existing "on a ridge"/"in a valley" position fact (reading (i),
  what this plan builds) or about the ownship-relative divide-crossing "next valley" fact (reading
  (ii), a materially different and currently underspecified change). See Item 1's own "Q-new"
  paragraph for the full reasoning — needs a one-line confirmation before Stage 3/5 of that item's
  implementation plan starts.
- **Item 1, water/landcover/coastline's place in the new precedence** (not named by the user,
  defaulted here to "confidence-ranked fallback below the three named kinds") — confirm or
  reassign before merge.
- **Item 1, distance-band figures** (`near`/`medium distance` boundaries, and the terrain
  "medium distance never fires" consequence of reusing `TERRAIN_QUALIFIER_MAX_M` as-is) — first
  guesses per this item's own table, meant to be flown and corrected, not approved as final.
- **Item 3 readback wording** for the "just watched N contacts as a group" case — needs the user's
  own phrasing preference (the project's established pattern: match what Petrovich would actually
  say, per `enrichment.py`'s own "the roadmap's own worked example" precedent for this kind of
  wording decision), not an invented string.
- **Item 3 scope**: confirmed as a *static* one-time tag of today's members, not live
  membership-following — flagged above under the effort/value check. If the user wants live
  following instead, that is a materially larger, separate design (a watched-group concept
  surviving `Group` split/merge) and should be scoped as its own plan rather than folded into this
  sortie's refinement set.

---

## Decisions settled by the user, 2026-10-05 (after the plan was written)

All three "Decisions Requiring User Input" are now answered. The plan above stands except where
these override it.

### 1. The terrain fact is **both** — divide-relative when a divide fires, position-relative otherwise

The user's example *"in next valley, north, medium distance"* was ambiguous between the two terrain
facts that both merged this morning. Answer: **both, whichever applies**, which is the precedence
`feature/terrain-callout-stages-345` already ships — the divide-relative form (1 divide crossed)
takes precedence, the position form (`"in a valley"` / `"on a ridge"`) competes otherwise.

**The hard part this hands the implementer, and it must not be papered over**: the two facts are
*about different things*, so the direction word means different things with each.

- `"in a valley, north"` — the contact is in a valley, and it is north **of that valley's own
  reference point** (the closest point on the landform line). Feature-relative, same as
  `"south of village"`. Well-defined.
- `"next valley, north"` — **north of what?** The divide fact is a relation between *ownship and
  the contact*, not between the contact and a feature. There is no feature-relative origin to take
  a bearing from.

Work out what the direction means in the divide case before writing it. Two defensible readings —
pick one, say why, and make it easy to change:

- **Drop the direction word for the divide form.** *"armor, 3 o'clock, next valley, medium
  distance"* already carries bearing (the o'clock) and range (the band). The direction adds
  nothing a pilot can act on, and the fragment stays short — which is the standing instruction.
  **This is my recommendation**; it is also the quieter option, consistent with every callout
  decision the user has made this week.
- **Take it from the nearest valley line's own closest point**, i.e. treat the divide form as the
  position form plus a divide qualifier. Defensible, but it quietly asserts the contact is *in*
  that valley, which the divide fact does not establish.

### 2. Water sits **with** terrain features, not below road

Revised precedence: **settlement → terrain feature + water → road → coastline / landcover.**

The user's reasoning, in their choice: a river or lake shore is a landform a pilot navigates by,
peer to a ridge or valley rather than a fallback. Coastline and landcover stay below road — the
coast is kilometres long and landcover is a region, so neither is a point a pilot can steer by the
way a lake shore is.

Within the shared terrain+water tier, order by the existing distance/dominance rule rather than by
kind, and reuse `WaterInfo.bearing_deg` — it landed this morning alongside the others.

### 3. Group watch tags members **once, statically**

*"Tag once, static."* Members at the moment the command is given become watched. A unit that joins
the group afterwards is **not** watched; one that leaves **stays** watched.

No new state, no watch-to-group identity binding, and nothing to maintain as groups split and
merge — which they do. The readback should make the one-time nature audible rather than implying a
standing subscription; something closer to *"watching four"* than *"watching that group"*, so the
pilot is not surprised when a late arrival goes unreported.

### Unchanged by these answers

The watched-only gate on road fragments (reading **(a)**) stands as built — a road fragment speaks
only when there is no settlement, no terrain feature, no water, **and** the contact is watched.
Distance bands remain first guesses to be flown.

---

## The direction word is per-kind, not universal (user, 2026-10-05)

> *"'armor, 3 o'clock, next valley, medium distance' → yes, this is good and enough.*
> *'in a valley, north' → not really informative for valleys. North of village, south of lake, west
> of junction, etc are useful.*
> *for ridges it could be useful, since one side hides and the other exposes → north of ridge or
> near/far side of ridge"*

So the direction word is **not** a uniform decoration on every location fragment. Whether it carries
information depends on the kind of feature, and the rule is about what the pilot can *do* with it:

| feature kind | direction word | why |
|---|---|---|
| settlement, water, junction, road | **yes** — compass (*"north of village"*, *"south of lake"*, *"west of junction"*) | the feature is a point or an edge; which side of it a contact sits on is a real, actionable locator |
| **valley** | **no** | a contact in a valley is *in* it; "north" of a valley floor locates nothing a pilot would use. `"in a valley"` is the whole fact |
| **ridge** | **yes, and it is the most useful case of all** | **one side hides and the other exposes.** Which side a contact is on is a line-of-sight statement, not a map coordinate |
| divide form (`"next valley"`) | **no** | settled above: the fact relates ownship to the contact, so there is no feature to be north of. The o'clock and the distance band already carry it |

### The ridge case deserves its own treatment, and `near/far side` is probably better than compass

The user offers both forms for a ridge — *"north of ridge"* **or** *"near/far side of ridge"* — and
the second is the one that says what the pilot actually wants to know. A compass bearing makes them
do the work of relating the ridge, the contact and their own position; **near side / far side states
the masking conclusion directly**, and masking is the entire reason a ridge is worth naming.

**This is exactly what `geometry.signed_side_of_polyline` is for**, and it reverses the architect's
earlier rejection of that helper — which was correct *for compass mapping* (a polyline's signed side
has no stable compass meaning) and is wrong here. Near/far is not a compass question: evaluate the
sign for **ownship** and for the **contact** against the same ridge line; same sign → near side,
opposite → far side. That is the one thing the helper does well, and it already handles the 180°
ambiguity a bearing subtraction reintroduces.

Two caveats for the implementer:

- **Sign is only meaningful against the *same* line.** A ridge stored as several fragments (they are,
  by construction — cut at tile seams and skeleton junctions) can put ownship nearest one fragment
  and the contact nearest another. Resolve both against one chosen line, or decline to say
  near/far at all rather than comparing signs across two fragments.
- **Near/far is ownship-relative, so it must not be cached** on a per-contact basis — same rule the
  divide count already follows (`WorldEnrichmentCache` holds nothing ownship-dependent).

**Open, and worth the user's ear rather than a decision here:** whether a ridge should say
*"far side of the ridge"* (masking-relevant, ownship-relative) or *"north of the ridge"*
(map-relative, stable) — or both in different circumstances. Build near/far first, since the user
named the masking reason; keep the compass form reachable.
