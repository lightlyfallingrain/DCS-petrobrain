### Goal

Redesign `belief.groups`' cohesion test so size-relative spacing and installation kind-coherence
both decide whether contacts form one `Group`, release the infantry over-merge constraint the
2026-10-01 debug pass found a pinned test enforcing, and change group re-disclosure from
re-speaking the whole roster to speaking only what changed — now built against worked utterance
examples rather than inferred rules, with damage/destruction narration and landmark anchoring
scoped out as separate follow-on plans (see "Effort/Value" below).

**Revision note (2026-10-01, second pass).** Three further Explore rounds landed after this plan's
first draft and settled every open decision; two of them changed its substance, not just its
blanks — see "What changed in this revision" at the end of this file for the full diff. The
controlling documents list below is updated accordingly; where any of the newer notes disagree
with this plan's own earlier prose, the notes win (per their own stated precedence).

---

### Controlling documents, read in full before this plan

- `plans/group-cohesion-redesign/explore-notes-delta-taxonomy.md` (2026-10-01) — **controlling**:
  the delta taxonomy as worked utterances, plus the damage/destruction perceptual-grounds addendum.
- `plans/group-cohesion-redesign/explore-notes-scope-and-landmarks.md` (2026-10-01) — **controlling**:
  clock-handle confirmation, landmark anchoring, and the Cold War SHORAD scope narrowing.
- `plans/group-undermerging/explore-notes.md` (2026-10-01) — the original cohesion answers
  (size-relative spacing, kind-coherence, infantry `EAGER`). Controlling over any earlier assumption
  in `debug.md` or `plans/group-reporting/plan.md`.
- `plans/group-undermerging/debug.md` — the re-trigger fix already merged (the whole-text-diff bug),
  and the reverted uncertainty-budget cohesion experiment this plan does not resurrect.
- `body-layer/research/2026-10-01-sam-site-geometry.md` — real-world SAM emplacement geometry,
  which discredited this plan's original 1000 m guess and grounds the now-settled 500 m cap.
- `plans/group-reporting/explore-notes.md` (2026-09-28) and `plans/group-reporting/plan.md` — the
  model this plan modifies: `Group`/`GroupStore`, the disclosure ladder, the four cues (proximity,
  common fate, figure-ground/local-density, similarity), and the "no spoken split/merge event"
  decision this plan revises (Decision 8 below).
- `plans/group-detectability/plan.md` — the perception-layer sibling (`group_salience.py`,
  `GROUP_COHESION_GAP_UNIT_WIDTHS` = 10.0, angular currency). Different layer, different question,
  deliberately separate constants — do not conflate with this plan's belief-layer backstop.
- `body-layer/src/belief/groups.py` — current mechanism, read in full; its own docstring already
  records most of the history above and the exact reasoning this plan builds on.
- `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md` — confirms
  `getLife()`/`getLife0()` are reachable but **not yet wired** into the production telemetry hook or
  any body-layer client; checked directly against `aircraft-layer/dcs-export/petrobrain-mission-
  telemetry-hook.lua` and `body-layer/src/aircraft_client.py` while writing this revision — neither
  carries a health field today. This is why damage/destruction narration is scoped out below.

---

### Settled, folded in without further discussion

- **Installation cohesion cap: a single flat ~500 m value.** Covers the real-world fixed-site
  evidence (S-75 ≈160-230 m diameter, S-125 ≈60 m launcher spacing) with margin, and explicitly does
  **not** try to also cover dispersed mobile-battery or SHORAD-battery spacing (see §1 below for what
  that means for class membership).
- **Single-vehicle systems (Osa/SA-8, Tor/SA-15, Tunguska/SA-19, Shilka/ZSU-23-4, and by the same
  reasoning Strela-1/SA-9, Strela-10/SA-13) are excluded from the installation rule entirely.** Each
  is its own radar and launcher; two a kilometre apart are two threats. Whether they are battery-mates
  is the ordinary size-relative test's job, not a flat installation cap's.
- **`EAGER` cohesion policy: `OP_INFANTRY` only, no backstop at all.** Not extended to any other
  class.
- **`test_2c_transcript_fixture_renders_four_lines_not_seven` is rewritten**, per AGENTS.md's
  "existing tests must be rewritten rather than extended" escalation — user-confirmed, not silently
  changed.
- **A leading-threat change speaks a delta, not a full line.** This **reverses** the first draft's
  "leader change → always full disclosure" branch — see §4 below.
- **`plans/group-reporting/plan.md` Decision 8 gets its pointer note at merge time**, per this role's
  standing instruction to amend open decisions a newly merged plan invalidates — not done now, because
  this plan has not merged yet.
- **Naval formations stay out of scope** (unchanged from the first draft — see "Effort/Value").

---

### What's already built and reusable — size-relative spacing exists today

`belief/groups.py`'s `_cluster_contacts` already runs **two** thresholds per pair and takes the
tighter:

1. a **relative** test: `GROUP_PROXIMITY_GAP_RATIO (3.0) × local median nearest-neighbour gap`
   (figure-ground, scene-density-scaled, no absolute constant), and
2. an **absolute backstop**, in **unit widths**: `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS (20.0) ×
   mean(pair's own believed physical size)`, from `perception.object_model.profile_for(contact.
   last_class_raw).size_m`, falling back to `GROUP_REPORTING_UNKNOWN_SIZE_M (7.0)` when the believed
   classification resolves to no real type.

This already answers the trucks-vs-ships framing in the original explore notes: a 1 km gap between
6 m trucks fails the ~140 m backstop and stays split, while the same gap between larger believed
objects scales the backstop up. No new size source and no new architecture is needed for this axis —
this plan's job on it is unchanged from the first draft: make the installation case not try to use
this currency at all (§1), not retune its multiplier.

---

### 1. Kind-coherence — the central design question, and a real bug found while re-deriving it

**The honest source is still perceptual, via ED's own `op_class` bucket** (`perception.object_model.
ObjectTypeProfile.op_class`) — never a DCS `object_type` string, never group/country metadata, same
no-omniscience boundary `_representative_size_m` already crosses for the size axis.

**But `op_class` alone cannot carry the installation/single-vehicle distinction, and this is a real
finding from re-reading `object_model.py` for this revision, not a restatement of the first draft.**
`OP_SRSAM` currently buckets **both**:

- `"s-125"` (SA-3) — a genuine fixed multi-component site (central radar + separate launcher
  revetments), exactly the case the now-settled 500 m cap is grounded for, **and**
- `"osa"` (SA-8), `"strela-10"` (SA-13), `"strela-1"` (SA-9), `"tor 9a331"`/`"chap_torm2"` (SA-15) —
  every one of which is a **single-vehicle system**, settled above as *excluded from the installation
  rule entirely*.

So the first draft's design — `AIR_DEFENSE_INSTALLATION_CLASSES: frozenset[str]` keyed on `op_class`
— would merge an Osa and an SA-3 launcher 400 m apart as "one installation," which is exactly what
the settled single-vehicle exclusion forbids. `op_class="OP_SRSAM"` is not a usable installation-
membership key; it conflates two systems the plan is now required to treat oppositely. (`"kub "`
(SA-6, multi-component) is its own `OP_MRSAM` bucket and does not have this problem; S-300's
components are already one `OP_LRSAM` bucket, also fine; **S-75/SA-2 has no keyword entry at all** —
it falls back to `DEFAULT_OP_CLASS`/unknown size today, a pre-existing gap this plan does not close
but flags, since S-75 is squarely in the settled Cold War SHORAD-adjacent era scope.)

**Revised design: a second, orthogonal, per-profile tag — not a second `op_class` reading.**

- `ObjectTypeProfile` gains `installation_component: bool = False`. Authored per keyword entry in
  `object_model.py`'s existing hand-authored table, same posture as every other guess there (a
  stated, revisable call, not a validated doctrine table): `True` for `"s-125"` and `"kub "`
  (and, once a keyword exists for it, S-75); `False` (the default, so every existing entry needs no
  edit) for `"osa"`, `"strela-10"`, `"strela-1"`, `"tor 9a331"`, `"chap_torm2"`, `"shilka"`,
  `"zu-23"`/`"zu23"`, and everything else.
- `AIR_DEFENSE_INSTALLATION_CLASSES` from the first draft is **dropped** — it was the wrong key.
  `groups.py`'s pair test instead checks **both** members' `profile.installation_component is True`.
- `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M: Final[float] = 500.0` (was 1000 m; the real-geometry
  research and the user's settled answer both move this down — grounded in S-75/S-125 doctrine,
  not the discredited 236-838 m DCS test-sortie measurement).
- Composition with the relative/density test is unchanged from the first draft:
  `min(relative_threshold, backstop)` — the relative test still governs everything, so this does not
  become an unconditional "any two installation parts anywhere merge" rule.
- A **mixed** pair (one `installation_component=True`, one not) gets the **ordinary** size-relative
  backstop, same as the first draft's reasoning, now on the corrected key.

**This finding does not change §2's scope decisions or settle Decision D's remaining open item** (the
500 m cap's own era/family qualifier, from `explore-notes-scope-and-landmarks.md` §4's "Open"
bullet) — it only fixes the mechanism that implements the already-settled cap, and it should be
flagged to the user as a correction found during this revision, not something they were asked about
directly.

---

### 2. Asymmetric error tolerance — a per-class cohesion policy, not a hard-coded list

Unchanged from the first draft and now fully settled, no open items remain here.

```python
class CohesionBackstop(Enum):
    STRICT = "strict"   # today's unit-widths backstop (default for every class)
    EAGER = "eager"      # no backstop at all -- relative/density test is the only gate
```

`_OP_CLASS_COHESION_BACKSTOP: dict[str, CohesionBackstop] = {"OP_INFANTRY": CohesionBackstop.EAGER}`,
default `STRICT` for everything not named — identical shape to `object_model._OP_CLASS_
DISTINCTIVENESS`. `EAGER` drops the absolute backstop entirely for a pair where **either** member
resolves to `OP_INFANTRY` (not requiring both). The relative/density test alone decides.

---

### 3. How the three things compose, per pair, concretely

For a pair `(i, j)`:

1. Compute `relative_threshold = GROUP_PROXIMITY_GAP_RATIO × local_median_nn_gap` (unchanged).
2. If **both** members' `profile.installation_component is True`: `backstop =
   GROUP_REPORTING_INSTALLATION_COHESION_CAP_M` (flat, 500 m).
3. Elif **either** member's `op_class` has an `EAGER` cohesion policy: `backstop = math.inf`.
4. Else: `backstop = GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS × mean(pair's sizes)` (today's rule).
5. `pair_threshold = min(relative_threshold, backstop)`; cohere iff the pair's gap clears it.

`installation_component` and `EAGER` never both apply to the same pair in practice (no profile is
authored both ways), so there is still no precedence conflict between (2)/(3): only one of them ever
fires per pair.

---

### 4. The delta taxonomy — rebuilt against the worked utterances, not the rules read off them

**This section is substantially revised from the first draft.** The first draft inferred its taxonomy
from the debug pass's own framing ("re-reports are deltas") before the user gave worked utterances.
The utterances are now the specification; where the design below and an utterance disagree, the
utterance wins. Two concrete corrections fall out of re-deriving it this way:

**Correction 1 — leader change is a delta, not a full re-disclosure.** The first draft reasoned that
a new leading threat reorders the whole line, so only a full restatement could be honest about who
leads. The user's settled answer overrides this directly: *leading-threat change speaks a delta.*
Concretely: `"group 2 o'clock, 3 km"` → ... → `"SRSAM, Shilka, armor 2 o'clock 2.5 km"` never
restates the group from scratch mid-flight; a new leader is announced as its own short clause
(reusing the existing leading-threat phrasing helper near `groups.py`'s `_identification_lead`,
e.g. `"Now leading: SRSAM."`), not by re-speaking every member.

**Correction 2 — membership deltas are not all equal; air-defence membership changes are always
news, even a same-class repeat.** The user's own worked rule: *"one more armor or truck etc makes no
difference — exception, more air defense does make a difference."* The first draft's single
"membership changed → delta for the new members" branch is too coarse: a second truck joining an
already-truck-classed group should say nothing (matches "one more truck makes no difference"), but a
second Shilka joining an already-AAA-classed group **should** speak, even though it is "just another
instance of a class already reported." This needs its own flag, reusing the **same** air-defence
`op_class` bucket membership §1 already has a vocabulary for, but as a broader set than §1's
installation-only flag — `op_class in {OP_SRSAM, OP_MRSAM, OP_LRSAM, OP_SPAAG, OP_ZU23}` regardless of
`installation_component`, since "more air defence is news" applies to single-vehicle SHORAD too
(an Osa joining a group that already has a Shilka is news for exactly this reason). **Flagged as a
decision below** — the exact set is a hand-authored guess like every other vocabulary here, not
re-derived from the examples beyond "the same families §1 already treats as air defence."

**Unchanged from the first draft, re-checked against the utterances and holding:**

- Never spoken yet → full disclosure (`"group <where>"`).
- First time any member crosses from undifferentiated to differentiated → full disclosure, once
  (`"AAA in the group"` reads as full because, with one member known, full and delta coincide; no
  utterance contradicts treating this branch as "full").
- A **new class** appearing in the group → always news (`"SAM and something"` → `"SAM and armor"`).
- Type refinement within an already-known class (`"there's a zsu"`, `"Shilka and zsu"`) is **not**
  this plan's mechanism to speak — it already reaches the pilot via each member's own
  `CONTACT_CLASSIFICATION_CHANGED` event, which fires per member regardless of grouping
  (`belief/callouts.py`'s own docstring: only `CONTACT_DETECTED`/`CONTACT_REACQUIRED` are filtered
  for a grouped contact). The group's own voice stays silent for this case, as the first draft had
  it — re-checked against the examples, not re-assumed, and it holds.
- Members only departed, no new arrivals → silent at the group level — **and this is reinforced, not
  changed, by the new damage/destruction mechanism** (see "Effort/Value" below): when a departure is
  caused by a unit burning, the pilot already hears that from the unit's own perceptual callout
  (`"burning"`), so the group staying silent on the membership loss avoids a double announcement
  rather than needing new group-level logic.
- A non-leading member's own classification refining, already differentiated, same membership →
  silent at group level, for the same per-member-event reason as type refinement above.

**Revised taxonomy table:**

| condition | what's said |
|---|---|
| never spoken | **full** disclosure |
| leading member changed (new leader, leader gained, or leader lost) | **delta**: a short "now leading" clause naming the new leading threat — **not** a full restatement (Correction 1) |
| first time any member crosses from undifferentiated to differentiated | **full** disclosure, once |
| a **new class** joins the group's composition | **delta**: compose just the new class via the existing `_group_composition_clause` |
| a member of an already-known **air-defence** `op_class` joins (new instance, same class) | **delta**: "more air defence is always news" (Correction 2) — flagged below, membership of this set is a decision |
| a member of an already-known **non-air-defence** class joins (e.g. another truck/armor) | **silent** — "one more truck/armor makes no difference" |
| members only departed, no new arrivals, same leader | **silent** — a destruction departure is already told via the member's own burning callout; a lost-from-view departure is correctly silent |
| nothing above (e.g. non-leading member's own type refinement, already differentiated, same membership) | **silent** at group level — told via that member's own `CONTACT_CLASSIFICATION_CHANGED` |

`Group` still gains the three new fields from the first draft (`last_spoken_member_contact_ids`,
`last_spoken_leading_contact_id`, `last_spoken_differentiated`), carried over unchanged on
reconciliation, reset only for a freshly founded group. `GroupStore.mark_spoken` still grows the two
extra fields. The mechanics of *how* each branch is computed are unchanged from the first draft
(§4's original prose on `render_group_disclosure`'s structure, `content_signature`, and the two
existing `== last_spoken_signature` checks staying as a defensive fallback) — only the **branch
conditions** above changed.

---

### Affected Modules / Files

- `body-layer/src/perception/object_model.py` — `ObjectTypeProfile` gains `installation_component:
  bool = False`; set `True` on the `"s-125"` and `"kub "` entries (new finding, §1).
- `body-layer/src/belief/groups.py` — `CohesionBackstop` enum, `_OP_CLASS_COHESION_BACKSTOP`,
  `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M` (500.0, revised from 1000.0); `AIR_DEFENSE_
  INSTALLATION_CLASSES` from the first draft is **removed**, replaced by the `installation_component`
  profile check; a new `AIR_DEFENSE_OP_CLASSES` frozenset for the delta taxonomy's Correction 2
  (distinct constant from the installation check — same families, different question, do not merge
  them into one flag); `_cluster_contacts`'s per-pair backstop computation (§3); `Group` gains the
  three new `last_spoken_*` fields; `GroupStore.mark_spoken` signature change; `reconcile`'s
  carry-over of the new fields.
- `body-layer/src/belief/speech.py` — `render_group_disclosure`'s trigger logic rewritten per the
  revised taxonomy in §4 (leader-change now delta, new air-defence-membership delta branch); a new
  small helper for the "now leading" delta clause and a helper for composing a delta line over a
  member-id subset (reusing `_group_composition_clause`).
- `body-layer/src/belief/callouts.py` — the `mark_group_spoken`/`mark_spoken` call sites pass the new
  fields; no change to `group_priority`'s tuple shape.
- Tests: `test_groups.py` (cohesion-policy and kind-coherence cases, now against the
  `installation_component` flag and the 500 m cap, plus a pinned case proving an Osa 400 m from an
  S-125 launcher does **not** merge as an installation), `test_speech.py` (taxonomy cases including
  the two corrected branches), `test_callouts.py` (integration across a tick sequence),
  **`test_2c_transcript_fixture_renders_four_lines_not_seven` rewritten** (explicit AGENTS.md
  escalation, user-confirmed).
- `body-layer/ROADMAP.md` — milestone entry.
- `plans/group-reporting/plan.md` — Decision 8 amendment, at merge time (see "Settled" above).

**Not touched:** `perception/group_salience.py`, `perception/clustering.py` (different layer,
confirmed still a different question); `belief/cardinality.py`, `belief/classification.py`
(read-only); naval/ship profiles (Effort/Value); anything in `aircraft-layer/` or a new health/damage
channel (Effort/Value); landmark/world-model disclosure policy (Effort/Value).

---

### Implementation Plan

**Stage 1 — per-class cohesion policy (the infantry release).** `CohesionBackstop` enum,
`_OP_CLASS_COHESION_BACKSTOP`, wire `EAGER` into `_cluster_contacts`. Unchanged from the first draft.
*Acceptance, no sortie needed:* rewrite `test_2c_transcript_fixture_renders_four_lines_not_seven`'s
expected line count for the now-eager infantry pair/triple; add a new pinned test proving a
non-infantry pair at the identical 260 m/500 m geometry still does **not** merge.

**Stage 2 — kind-coherence for air-defence installations, on the corrected key.**
`installation_component` field on `ObjectTypeProfile`, author it `True` for `"s-125"`/`"kub "`,
`GROUP_REPORTING_INSTALLATION_COHESION_CAP_M = 500.0`, the backstop-selection order in §3.
*Acceptance, no sortie needed:*
  - a synthetic fixture pinned to the real 236-838 m S-300 spacing (the only live-trace example
    available), confirmed to form one group — this exercises the `OP_LRSAM` installation path, which
    is unaffected by the `OP_SRSAM` fix;
  - a **new** synthetic fixture pinned to an Osa and an S-125 launcher placed ~400 m apart, confirmed
    to **not** merge as an installation (this is the regression test for the bug this revision found —
    it would incorrectly merge under the first draft's `AIR_DEFENSE_INSTALLATION_CLASSES` design);
  - one offline replay of the 2026-10-01 trace's S-300 segment (`CONTACT_3/8/15/16`,
    `/Users/sg/dcs-detection-trace.jsonl` + `/Users/sg/dcs-belief-truth.jsonl`), the same replay
    method `debug.md` already proved works, confirmed to form one four-member group at its true
    spacing.

**Stage 3 — the delta taxonomy, rebuilt against the worked utterances.** `Group`'s three new fields,
`mark_spoken`'s signature, `render_group_disclosure`'s rewritten trigger per the revised §4 table
(including both corrections).
*Acceptance, no sortie needed:* one synthetic test per taxonomy row — new group, leader change
(asserting a **delta** clause, not a full restatement — this is the row most likely to regress
silently back to the first draft's behaviour if copied carelessly), first-differentiation,
new-class-membership-delta, air-defence-repeat-membership-delta, non-air-defence-repeat-membership-
silence, departure-silence, non-leading-refinement-silence. Then one full replay of the 2026-10-01
trace end to end (reusing `debug.md`'s replay harness): confirm no group re-speaks its full roster
for a reason already covered by an individual event, that the delta line fires exactly where a new
member joins mid-flight, and that a leader change never re-speaks the full composition.

**Stage 4 — docs and ROADMAP.** Module docstring updates (including the `installation_component` vs
`op_class` distinction and why `AIR_DEFENSE_INSTALLATION_CLASSES` was replaced), `plans/
group-reporting/plan.md` Decision 8 amendment, `body-layer/ROADMAP.md` entry.

**Deliberately not a stage of this plan:** damage/destruction narration and landmark anchoring. See
"Effort/Value" below for why, and what each would need as its own plan.

---

### Risks & Unknowns

- **`GROUP_REPORTING_INSTALLATION_COHESION_CAP_M` (500 m) and the new `AIR_DEFENSE_OP_CLASSES`
  membership for Correction 2 are both one-source-of-evidence guesses** — the cap now rests on real
  doctrine research rather than a discredited DCS test-sortie measurement, which is firmer than the
  first draft's basis, but it is still unchecked against an actual Cold War-era mission's unit
  placement. Expect both to move after the first sortie that exercises either path.
- **S-75/SA-2 has no `object_model.py` keyword entry at all**, so it currently falls back to
  `DEFAULT_OP_CLASS`/unknown size and cannot be flagged `installation_component=True` even though it
  is squarely in the settled Cold War SHORAD-adjacent scope. Not fixed by this plan — flagged so it
  is not silently assumed covered.
- **Kind-coherence is still bounded by, not a replacement for, the relative/density test** — two
  genuinely distinct installations of the same family, close enough in a dense scene that the local
  median gap is inflated, could in principle still single-link chain together. Unchanged risk from
  the first draft, now scoped to the corrected `installation_component` key.
- **The delta taxonomy's "silent" branches still rely on `CONTACT_CLASSIFICATION_CHANGED` firing per
  grouped member**, as documented but not independently instrument-verified by this plan. Stage 3's
  implementation should verify this directly, not re-derive it blind from the docstring — unchanged
  flag from the first draft.
- **The new `installation_component` field is a second axis layered onto `ObjectTypeProfile` next to
  `op_class`**, and future keyword entries need both set correctly and independently (an entry can be
  air-defence without being an installation component, e.g. Osa, or an installation component that
  isn't air-defence, hypothetically). This is a real increase in how many judgments the hand-authored
  table carries per entry — same honest-guess posture as the rest of that table, but worth naming as
  a cost, not papering over it as "just one more field."

---

### Effort/Value

**Naval formations stay out of scope**, unchanged from the first draft — illustrative only, no flown
evidence, the general size-relative backstop already handles a ship pair correctly if one is ever
flown.

**Damage/destruction narration (explore-notes-delta-taxonomy.md's addendum) is scoped out of this
plan — it is an aircraft-layer dependency this plan should not assume exists, and is sized like its
own milestone, not a stage.** Checked directly, not inferred: `aircraft-layer/dcs-export/petrobrain-
mission-telemetry-hook.lua`'s per-unit loop carries `getVelocity()` only — `getLife`/`getLife0` are
confirmed *reachable* by the 2026-09-24 research note but are not wired into the hook, there is no
corresponding schema/endpoint (unlike velocity's own `GET /unit_velocity/latest`, a precedent this
work would need to repeat), and `body-layer/src/aircraft_client.py` has no health-reading method. The
value is real — "smoking"/"burning" narration, gated correctly on observability, is exactly the kind
of grounded perceptual detail this project wants — but building it means: a new Lua field, a new
`aircraft-layer` schema and endpoint (repeating `plans/movement-detection/plan.md`'s own shape), a new
body-layer client method, a new field on `Percept`/`Observation` that must pass the same visibility
gate as every other perceived property (the hard part — health is ground truth, and the no-omniscience
invariant means a burning unit behind a ridge must say nothing), and a new lifecycle event kind
(`CONTACT_DAMAGED`/`CONTACT_BURNING`) with its own speech templates. None of that touches `belief.
groups`. **Recommend a separate plan** (e.g. `plans/unit-damage-state/plan.md`), gated on the
aircraft-layer change happening first, and on upgrading the research note's "inferred" DCS-smoke-
threshold agreement to a live-observed one before committing to a narration threshold — a cheap
investigator probe (shoot a unit, watch when smoke starts, log `getLife()/getLife0()` at that moment)
rather than guessing. This plan's §4 departure-silence branch already assumes the eventual mechanism
will speak per-member, independently of the group (see §4's reinforcement note), so nothing here
needs to change when that plan lands.

**Landmark anchoring (explore-notes-scope-and-landmarks.md §2) is scoped out of this plan, but its
disclosure policy is now answered (2026-10-01, fourth round) and worth designing against here, since
the question that was open is no longer the reason to defer it.** The user's answer gives two
independent tests a landmark candidate must pass — **extent** (small relative to the precision
wanted: a village localizes, a city spanning kilometres does not) and **local uniqueness** (one road
among few is a reference, one among many is noise) — plus **combination** as the designed-in
ambiguity resolver (*"in valley, south of village"*), not a fallback. Checked against the actual
schema while recording this: `query.describe.SettlementInfo.subtype`/`NamedPlaceInfo.subtype` already
carry `village`/`town`/`city`, so the **extent test is answerable today**, not a data gap — but
**local uniqueness has no existing query support**: `describe_position` returns only the *nearest*
feature of each kind, never a count-within-radius, so this needs a small new `world-model/src/query/`
addition, not only a body-layer disclosure rule. **The extent test is also the same relative-to-own-
size principle this plan's §1 cohesion rule already uses** (spacing-vs-unit-size, usefulness-vs-
feature-size) — worth building as one shared idea if the follow-on plan's architect agrees, rather
than two independently-tuned rules that happen to rhyme.

**Checked directly against the real `syria-full.sqlite` while writing this (not the schema alone),
and the extent test has better data than the schema docstrings alone suggested — this is not a
gap:**

- `settlement` rows (OSM-derived, Polygon geometry) carry `tags_json.area_m2` **on every row
  sampled**, not just a `subtype` label. `area_m2` is the honest form of "a city spans kilometres" —
  measured extent, not a class proxy — and should be preferred wherever the feature has it.
  `subtype` breaks down `built_up` 24,499 / `village` 1,533 / `town` 128 / `city` 22.
- `named_place` rows (DCS `towns.lua`, Point geometry) have **no extent at all** — a point has no
  area — so they must fall back to `subtype` (`village` 15,863 / `peak` 4,824 / `town` 838 /
  `city` 75 / `dam` 262, plus 1,182 untyped) for the extent test, never `area_m2`.
- **`built_up` is 24,499 of 26,182 settlement rows (94%) and is not a place class** — it is
  unnamed-landcover built-up area, not a village/town/city a crew member would name. The follow-on
  plan needs to check whether `built_up` rows even carry a name before treating them as landmark
  candidates; an unnamed polygon cannot be spoken regardless of how well it passes the extent test.
- **The two kinds overlap and will double-count a real place** — a village plausibly exists as both
  a DCS `named_place` point and an OSM `settlement` polygon, under names that need not match (one is
  DCS's own gazetteer, the other OSM's). The follow-on plan needs an explicit source-of-truth rule
  for *which name a crew member says*, which is a different question from which geometry is
  authoritative for position. The project's standing rule (DCS geometry authoritative, external GIS
  augments) answers the geometry question; it does not by itself answer the naming question, and the
  user's own framing of the source choice (*"OSM settlement data should give us coverage"*) suggests
  OSM `settlement` as the naming source when both exist, but this should be confirmed by that plan's
  own architect rather than assumed from this aside.

This remains out of this plan's own stages because it still cuts across more than group cohesion (the
initial position callout, the "report" roll-up, and movement-towards-landmark phrasing all want it,
not just the group path) and still needs a new query capability (local-uniqueness, above), which is
implementation work this plan should not absorb mid-revision. **Recommend its own plan** (e.g.
`plans/landmark-anchoring/plan.md`) — an Explore pass is no longer strictly required since the
disclosure-policy question that would have motivated one is now answered, though the architect taking
that plan should re-read this section (including the area_m2/overlap findings above) rather than
re-deriving it. Sequence it after this plan merges, not blocking it. **Do not design it to block on
`feature/terrain-landform-features` Stages 3-5** (valley/ridge adjacency/bearing/callout, unbuilt) —
village/road/water coverage is available today and is most of the value the user actually asked for
(villages are explicitly the best case); valley/ridge/mountain join additively once that work lands.

**Net effect of both deferrals: this plan stays sized to what the user is actually waiting on** — the
cohesion fix and the noise reduction from the 2026-10-01 sortie — rather than growing by two
cross-cutting features whose own open questions (an aircraft-layer dependency; a disclosure-policy
decision needing the user's own voice) would otherwise stall it.

---

### Second-Order Effect

Unchanged from the first draft: this **unblocks `BL-B11`** (threat-based report prioritisation) once
a group's cohesion correctly reflects installation structure. It **complicates** `plans/
group-reporting/plan.md`'s deferred Stage 5 (common fate): that stage will need to compose with
*three* cohesion inputs instead of two, and should be designed against this plan's `min()`
composition shape. **Additionally**, deferring landmark anchoring to its own plan means that plan
will need to re-check this plan's delta taxonomy (§4) once written — a landmark-anchored movement
callout ("trucks moving north, towards \<village\>") is exactly the kind of group-member delta this
plan's taxonomy governs, so the two plans' disclosure logic needs to compose, not duplicate.

---

### Decisions Requiring User Input

1. **`AIR_DEFENSE_OP_CLASSES` for the delta taxonomy's Correction 2** (which classes make "more air
   defence" always news) — recommend the same families §1 treats as air-defence for cohesion
   purposes (`OP_SRSAM`, `OP_MRSAM`, `OP_LRSAM`, `OP_SPAAG`, `OP_ZU23`), applied regardless of
   `installation_component`, since the examples' reasoning ("more air defence does make a
   difference") is about threat class, not installation structure. Flag because this is this
   revision's own inference from the examples, not a family list the user named directly.
2. **The `installation_component` fix (§1) is a correction found while re-deriving the plan, not
   something explicitly asked about** — confirm the `"s-125"`/`"kub "` = `True` assignment and the
   500 m cap's grounding in the SAM-geometry research note, since it changes which pairs the
   installation path can ever apply to (narrower than the first draft's `op_class`-keyed design).
3. **Deferring damage/destruction narration and landmark anchoring to their own plans** (Effort/Value
   above) — both are real, wanted features; this plan recommends sequencing them after this one
   merges rather than folding them in. Damage/destruction has an unbuilt aircraft-layer dependency.
   Landmark anchoring's disclosure policy is now answered (extent + local-uniqueness + combination,
   see Effort/Value), but it still needs a new world-model query (count-within-radius, for the
   uniqueness test) and spans more than the group-cohesion path, so it stays its own plan rather than
   a stage here. Confirm or say to fold either back in.
4. **The first-differentiation branch staying "full" rather than being re-examined like the leader-
   change branch was** — no utterance contradicts this, but it was not re-confirmed by name the way
   leader-change was. Recommend leaving as-is; flagging since this revision changed its sibling
   branch for a similar reason.

---

### What changed in this revision (for the record)

- §1 kind-coherence: replaced `AIR_DEFENSE_INSTALLATION_CLASSES` (an `op_class`-keyed set) with a new
  `installation_component: bool` field on `ObjectTypeProfile`, after finding `OP_SRSAM` conflates the
  fixed S-125 site with four single-vehicle systems the settled scope requires excluded. Cap value
  1000 m → 500 m, now grounded in real SAM-site-geometry research rather than a discredited
  measurement.
- §4 delta taxonomy: rebuilt against worked utterances rather than inferred rules. Leader change:
  full → **delta** (reversed, per settled answer). New: an air-defence-membership-repeat delta branch,
  distinct from the existing non-air-defence-repeat silence, per "more air defence is always news."
- Damage/destruction narration and landmark anchoring: added as explicit out-of-scope items with
  Effort/Value reasoning, rather than being open questions within this plan's own stages.
- **Fourth round (same day, mid-revision):** the user answered "when does a landmark earn a
  mention" directly — extent + local-uniqueness + combination — recorded verbatim in
  `explore-notes-scope-and-landmarks.md` §5. Folded into the landmark-anchoring Effort/Value
  section as design-against guidance for the follow-on plan (including the found gap: no existing
  world-model query supports the local-uniqueness test, and the extent test's shared principle with
  this plan's own §1 cohesion rule). Landmark anchoring stays out of this plan's stages — the reason
  for deferral shifted from "disclosure policy still open" to "cuts across more than this plan, and
  needs a small new query capability" — but it no longer strictly needs its own Explore pass first.
- **Fifth round (same day):** checked against the real `syria-full.sqlite` — `settlement` rows
  carry measured `area_m2` (the extent test's honest input, not just a `subtype` proxy),
  `named_place` rows are points with no extent and must use `subtype`, `built_up` is 94% of
  `settlement` rows and is unnamed landcover rather than a place, and the two kinds overlap and can
  name the same real village differently. Folded into the Effort/Value section as findings for the
  follow-on plan, including an open naming-source question (DCS geometry is authoritative for
  position; this is the separate question of which name a crew member says).
- All six of the first draft's "Decisions Requiring User Input" are resolved by the explore rounds and
  folded into "Settled" above, except the parts of Decision 3 (cap value/membership) this revision's
  own `installation_component` finding reopened narrowly, and Decision 5's first-differentiation half
  (carried forward as new Decision 4 above, unchanged in substance).
