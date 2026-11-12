### Goal

Make the "stated as fact" vs. "last I saw" vs. "handed to the kneeboard" distinction track how far
a contact could actually have moved since it was last seen — not a flat elapsed-time half-life —
while a unit that genuinely cannot move (dug-in, or a fixed multi-component SAM site) stays stated
as fact for as long as it is believed to exist at all, and every contact that leaves working memory
leaves a mission-memory note carrying its last-seen place and time.

Scope is BL-B112 only, per the goal check's accepted split: wording, the fixed/stopped
distinction, and the write half of the lost→kneeboard hand-off. The read-back (report/threat
answers consulting the kneeboard, re-sightings recognised against a note, SAM-envelope warnings
from a noted position) is `[[BL-B115]]`, a separate architect pass — out of scope here, and this
plan does not foreclose it (every field BL-B115 will need is written now).

### Investigator

Dispatched for one narrow fact: which `op_class` bucket HelperAI assigns the SA-2 (S-75) components
this plan adds to `object_model.py` (none of which exist in the table today). Finding (`body-layer/
research/2026-11-12-sa2-op-class-assignment.md`, `fd3545c9`): **the question's premise doesn't
hold** — no DCS/HelperAI source assigns a per-type `op_class` to anything, SA-2 included. The
`OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM` rows already in this table for SA-3/SA-6/SA-10 are this project's
own real-world-range judgment calls, not an ED classification; what was actually verified for them
was only "does this keyword string-match a real DCS `object_type`." Cross-checked against
`body-layer/data/threat_envelopes.json` (Hoggit-wiki real engagement ranges): SA-3 25.0 km
(`OP_SRSAM`), SA-6 35.6 km (`OP_MRSAM`), **SA-2 51.9 km**, SA-10 74.1 km (`OP_LRSAM`). SA-2 sits
between the MRSAM and LRSAM anchors, closer to LRSAM by ratio (70% of SA-10's range vs. 146% of
SA-6's) — genuinely open, not resolvable by further recon. **This plan uses `OP_LRSAM`** on that
ratio, flagged as a Decision below rather than settled silently. `installation_component=True` on
all four new rows, including the rangefinder/trailer, per the investigator's own extension of the
S-300 precedent (a fixed site's non-launcher components get the same `op_class` + `installation_
component=True` as the launcher — "part of this kind of site," not "this object can shoot you").
A reusable fact for the next SAM addition — "`op_class` is this project's judgment, not an ED
source" — is now in `.claude/agent-memory/investigator/`.

### Affected Modules / Files

- `body-layer/src/perception/object_model.py` — new `ObjectTypeProfile.immobile: bool = False`
  field; set it on the S-125/SA-3, Kub/SA-6, S-300/SA-10 rows and new SA-2 rows (see Stage 1); fix
  the S-300 radar rows' `installation_component` (currently `False`, should be `True`).
- `body-layer/src/belief/association_over_time.py` — `contact_growth_rate_mps` reads the new
  `profile.immobile` instead of `profile.installation_component`.
- `body-layer/src/belief/decay.py` — new `distance_since_last_seen_m`; `certainty_of`'s
  tracked/estimated split becomes growth-based; new tunable `LAST_I_SAW_GROWTH_THRESHOLD_M`;
  doc corrections where `POSITION_HALF_LIFE_S`'s role is described.
- `body-layer/src/tuning.py` — `_check_scan_decay_coupling`'s I1 docstring correction (no code
  change to the check itself).
- `body-layer/src/belief/motion.py` — `fold_motion`'s founding-False branch now requires
  `MOTION_STOP_CONFIRM_S` of continuous sub-threshold evidence, same as a demotion, instead of
  adopting "stopped" outright from one reading.
- `body-layer/src/belief/contacts.py` — `from_percept` persists `motion_pending_stop_since_sim`
  from the founding `fold_motion` call (currently discarded).
- `body-layer/src/belief/speech.py` — `render_report_summary`'s "Last I saw" trigger becomes
  certainty-based (`certainty == "estimated"`), not age-based; drops the `stale_window_s` threading.
- `body-layer/src/belief/crew_console.py` — one call site's now-gone `stale_window_s` kwarg.
- `body-layer/src/mission_memory/entries.py` — new `CompositionItem.immobile: bool`;
  `SCHEMA_VERSION` → 2; decode defaults a missing key to `False`.
- `body-layer/src/mission_memory/admission.py` — `_composition_for` sets `immobile`; new
  lost-hand-off write path, a new per-run cursor tracker, wired into the `BL-15` mission-restart
  reset.
- `body-layer/src/body.py` — owns the new tracker instance alongside `FiredOnTracker`, same
  lifetime, included in `_reset_mission_state`.
- Tests: `test_object_model.py`, `test_decay.py`, `test_belief_motion.py`/`test_contacts_motion.py`,
  `test_speech.py`, `test_mission_memory_admission.py`, `test_mission_memory_entries.py`,
  `test_tuning*` (coupling check unaffected but re-run), BL-B111's own expected-area acceptance test.

### Implementation Plan

**Stage 1 — `object_model.py`: fixed vs. mobile is a second, independent bit**

`installation_component` already exists and already does real work: `belief/groups.py`'s cohesion
backstop (`_pair_backstop_m`) and group-level reconciliation (`_installation_of`/`Group.installation`,
`group_matches` test 2) both key off it to keep a fixed site's radar-plus-launcher components
reported and matched as one site. **Reusing that same field for the growth-rate question would
break SA-6 specifically**: today `installation_component=True` on the `"kub "` row is exactly what
makes Kub's radar and launcher cohere as one reported group — correct, and this plan does not touch
that — but the user's explicit override ("SA-6 is a mobile platform… can just up and go") needs
Kub's *growth rate* to stop being zero. One field cannot carry both answers for Kub.

So: add `immobile: bool = False` to `ObjectTypeProfile`, read **only** by
`contact_growth_rate_mps` (next stage) — `installation_component` keeps its existing meaning and
every existing consumer, untouched.

Row changes:

| Keyword row | `installation_component` | `immobile` (new) | Why |
|---|---|---|---|
| `s-125` (SA-3) | `True` (unchanged) | `True` | named fixed by the user |
| `kub ` (SA-6) | `True` (unchanged — cohesion stays) | **`False`** | user's explicit override: self-contained platform, can relocate without redeploying a separate radar |
| `s-300ps 40b6m tr` / `s-300ps 64h6e sr` (SA-10) | `True` (**fixed from `False`** — opportunistic bug fix, see Decision 3) | `True` | named fixed by the user |
| new: `snr_75v`, `rd_75`, `s_75m_volhov`, `s_75_zil_trailer` (SA-2, `op_class="OP_LRSAM"` — see Investigator above) | `True` (new rows, all four) | `True` | named fixed by the user; zero coverage exists today — without these rows SA-2 falls to the `OP_GROUPSOMETHING` default and is treated as an ordinary mobile contact, directly contradicting the explicit example |
| `osa`, `strela-10`, `strela-1`, `tor 9a331`, `chap_torm2`, `chaparral`, `linebacker` | `False` (unchanged) | `False` (unchanged) | self-contained mobile platforms |
| every other row | `False` (unchanged) | `False` (default) | no change |

Real DCS `object_type` strings for the SA-2 rows (`data/dcs_type_to_reporting_name.tsv`):
`SNR_75V` → "SA-2 Fan Song radar", `RD_75` → "SA-2 rangefinder", `S_75M_Volhov` → "SA-2 launcher",
`S_75_Zil_Trailer` → "SA-2 missile trailer". `op_class` per the Investigator note above.

**Stage 2 — `contact_growth_rate_mps` reads `immobile`, not `installation_component`**

One-line change in `association_over_time.py`: `if profile.immobile: return 0.0` in place of the
current `if profile.installation_component: return 0.0`. Everything downstream of this function
(position covariance inflation, the detection-envelope clamp, `belief.groups.group_matches` test 5's
displacement bound via `position_belief.plausible_speed_mps`) is unaffected in mechanism — only
Kub/SA-6 contacts change behaviour, from always-zero growth to the ordinary mobile path
(`UNOBSERVED_MOTION_GROWTH_RATE_MPS` while stopped/unobserved-for-motion, the `OP_MRSAM` class rate
once seen moving). This is a deliberate, real behaviour change, not a side effect — flag it in
Stage 6's acceptance check and in the DoD report, since it is the one place this plan *widens* a
bound rather than narrowing one.

`plausible_speed_mps`'s own `installation_component` kwarg is now provably dead (no real caller
passes `True` — `contact_growth_rate_mps` short-circuits before calling it, and `belief.groups.
_plausible_speed_mps` never had a per-member flag to pass in the first place, by its own docstring).
Leave it or delete it — Implementer's call, no behaviour either way.

**Stage 3 — `certainty_of`: growth-based tracked/estimated split**

```python
def distance_since_last_seen_m(contact: Contact, now_sim: float) -> float:
    """How far `contact` could plausibly have moved since it was last seen —
    `association_over_time.contact_growth_rate_mps(contact) * elapsed_s`. The one
    quantity BL-B112's hedge keys on (growth, not total position uncertainty)."""
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    return contact_growth_rate_mps(contact) * elapsed_s


def certainty_of(contact: Contact, now_sim: float) -> Certainty:
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    if elapsed_s <= OBSERVED_WINDOW_S:
        return "observed"
    if elapsed_s <= LOST_THRESHOLD_S:
        if distance_since_last_seen_m(contact, now_sim) < LAST_I_SAW_GROWTH_THRESHOLD_M:
            return "tracked"
        return "estimated"
    return "lost"
```

New tunable, `belief.decay.LAST_I_SAW_GROWTH_THRESHOLD_M = 500.0` (`lo=100.0, hi=2000.0,
status="agreed-guess"` — the user gave the figure directly, 0.5 km). `decay.py` gains a real,
non-TYPE_CHECKING import of `association_over_time.contact_growth_rate_mps` — verified no cycle:
`association_over_time.py` imports nothing from `decay.py` today (confirmed by grep), and its own
`Contact` reference is TYPE_CHECKING-only, same pattern `decay.py` already uses.

**`LOST_THRESHOLD_S` is untouched** — "lost" stays purely elapsed-time, exactly the user's "use
current implementation" answer. A unit whose growth rate implies it would cross 500 m only *after*
120 s (installations: never; stopped units at 0.3 m/s: ~28 min) goes `tracked → lost` directly,
skipping `estimated` in working memory entirely — consistent with the goal check's own table and
with Finding 6's "one meaning per state." The hedge for such a unit, once it reaches the kneeboard,
is `[[BL-B115]]`'s job, computed from the note's own `as_of_sim` and the new `immobile`/motion
fields this plan writes (Stage 5) — this plan does not compute it there.

**`POSITION_HALF_LIFE_S` keeps its current value and both existing consumers**
(`position_confidence`'s numeric decay; `GROUP_REIDENTIFY_WINDOW_S = 2 × POSITION_HALF_LIFE_S`) —
neither is touched. Only the *prose* needs correcting: `certainty_of`'s tracked/estimated split no
longer reads it. Update:
- `decay.py`'s own comment above the `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` assert (the assert
  itself stays — it still protects `position_confidence`'s decay curve from degenerating, a real,
  separate concern).
- `tuning.py`'s `_check_scan_decay_coupling` module-docstring paragraph describing I1 — same: the
  check and its code are unaffected (nothing it compares changed), only what the comparison is
  *for* needs restating.

No change to I2, `GROUP_REIDENTIFY_WINDOW_S`, or any of their consumers — confirmed not touched by
this redefinition (re-check, Stage 6).

**Stage 4 — "observed not moving" needs a watch, founding included (Q2)**

Today `fold_motion`'s founding branch (`held is None`, `incoming is False`) adopts `"stopped"`
outright from a single sub-threshold reading — the same "adopt the founding claim as-is" rule
`classification.py`/`cardinality.py` use, but `belief.motion`'s own module docstring already marks
motion as structurally different from those two. At Mi-24 ranges a single glance cannot tell a
unit driving straight at the helicopter from one parked (finding 3) — the user's answer: *"a short
watch, for example the existing 5 s stop confirmation, and nothing from one glance."*

Change the founding-False branch to run through the same countdown the demotion branch already
uses, rather than adopting outright:

```python
if held is None:
    since = pending_stop_since_sim if pending_stop_since_sim is not None else now_sim
    if now_sim - since >= MOTION_STOP_CONFIRM_S:
        motion = MotionBelief(state="stopped", confidence=_DEFAULT_CONFIDENCE, established_sim=now_sim)
        return FoldMotionOutcome(motion=motion, pending_stop_since_sim=None)
    return FoldMotionOutcome(motion=None, pending_stop_since_sim=since)
```

`motion` stays honestly `None` ("never observed for movement" — already a real, documented state
for this field) until the watch completes. `contacts.py`'s `from_percept` must start persisting
`motion_pending_stop_since_sim` from this call's outcome — today it discards it
(`fold_motion(None, percept.apparent_motion, percept.t_sim, None).motion` reads only `.motion`),
which would silently drop the countdown for every founding contact and make this change a no-op.

**This changes a previously load-bearing, explicitly documented rule** (motion.py's own module
docstring, "adopt the founding claim as-is"), and the existing test asserting "one founding False
reading → immediately stopped" must be rewritten, not merely extended. User-directed (Q2, "as
recommended") — named here per Escalation Rules so Reviewer does not read it as unauthorized scope.
Update motion.py's module docstring paragraph describing the founding-False case.

This does not fix the underlying 8 arcmin/s angular threshold that produced the false "stopped"
reading in the first place (finding 3's root cause) — a sustained closing approach would still read
"stopped" after 5 s of consistent sub-threshold readings, same as before. That is a separate,
lower-priority accuracy gap, not asked for here (Risks & Unknowns).

**Stage 5 — mission memory: `immobile` travels with the note, and lost writes one**

5a. `entries.py`: add `CompositionItem.immobile: bool`. Bump `SCHEMA_VERSION` to 2.
`_encode_composition` writes it; `_decode_composition` reads `item.get("immobile", False)` —
**every existing on-disk entry predates this field**, so a missing key must default to `False`,
documented explicitly next to the cast. Add a decode-compat test: a hand-written schema-1 JSON
line (no `immobile` key) decodes without error.

5b. `admission.py`'s `_composition_for`: resolve `object_model.profile_for(contact.last_class_raw)`
(the same resolution `contact_growth_rate_mps` already uses) and set
`immobile=profile.immobile` on the built `CompositionItem`. This is what lets `[[BL-B115]]` later
recompute the right growth rate from a kneeboard note alone, without re-deriving it from a type
string the schema does not otherwise carry at this granularity (`op_class`/classification value
here can be a coarse class bucket shared by both a fixed and a mobile system, e.g. `OP_SRSAM`).

5c. New write path, on a `CONTACT_LOST` event — the "write half of the hand-off" the scope proposal
names. `ContactStore.events` already carries every `CONTACT_LOST`/`CONTACT_DETECTED`/
`CONTACT_REACQUIRED` event in order; `FiredOnTracker._scanned_event_count` is the exact existing
idiom for scanning only the events appended since the last `step()` call without rescanning the
whole log. Add a sibling cursor (own field or own small tracker class, Implementer's call) that:

- scans new events since last call for `kind == CONTACT_LOST`;
- for each, resolves the contact (`contacts.contact(event.contact_id)` — the contact is **not**
  evicted from the store on going lost, it stays, decaying, until a real eviction/destroyed path
  elsewhere) and decides whether to write:
  - air-defence: always (mirrors `_maybe_write_air_defence`'s existing "always, no floor" rule);
  - otherwise: **only if `memory.latest_entry(contact.id) is not None`** — it already cleared
    `GROUP_ENTRY_CONFIDENCE_FLOOR` at some point. A contact that never got a first entry (never
    cleared the floor at all — "a single glimpse") gets no lost note either: **same floor, same
    meaning, applied once more** — this is the answer to the explicit open question of how the
    floor and the lost-write interact.
- when it decides to write, **bypasses `RESIGHT_MIN_INTERVAL_S` and `_material_change` entirely**
  (this is a forced terminal snapshot of the last real look, not an ordinary resight) and reuses
  `_build_entry_position`/`_seen_how`/`_motion_info`/`_composition_for`/`_group_link_for` unchanged,
  with `strikes=last_entry.seq if last_entry is not None else None` for the existing continuation
  bookkeeping `query.py`'s debrief tooling already expects.
- **Position/time integrity, verified rather than assumed**: `PositionEstimate.as_of_sim`/
  `fused_at_sim` are only ever updated inside `Contact.record`/`from_percept`, which only run when a
  new percept actually exists for that contact this poll — there is no separate per-poll inflation
  pass over every contact. So for a contact unseen for up to `LOST_THRESHOLD_S`, `position.as_of_sim`
  is already frozen at the last genuine look, not bumped by the write-time `now_sim`. Reusing
  `_build_entry_position` unmodified for this write is therefore correct: it records the **last
  seen** place and time, exactly as the scope requires, not the moment the note was written.

5d. Thread the new tracker through `admission.step`'s signature, `body._mission_memory_step`'s two
call sites, and **`body.py`'s mission-restart reset path** (`_reset_mission_state`). This is the
exact bug `FiredOnTracker.reset_for_new_mission` was itself added to fix: a cursor keyed to
`len(contacts.events)` that is not reset on a genuine DCS mission restart will silently stop
producing output for an arbitrary stretch after every restart, because `ContactStore.events` resets
to empty while the cursor's count does not. Give the new tracker the identical `reset_for_new_mission`
method and wire it into `_reset_mission_state` alongside `FiredOnTracker`'s own call — do not
discover this the way the fired_on rule's own retrofit had to.

**Stage 6 — re-check coupled invariants (no code change expected, verify and document)**

- `callouts.py:856`'s merge-echo suppression (`certainty_of(other, now_sim) != "lost"`) — unaffected,
  still purely `LOST_THRESHOLD_S`-gated.
- `tools.py`'s `"observed"`-filtered call sites (`"visible"` key, `get_situation`'s visible counts,
  `watch`/`unwatch` eligibility) — unaffected, the `"observed"` band is untouched by this plan.
- `tuning._check_scan_decay_coupling` I1/I2 — code and values unchanged (see Stage 3); only I1's
  prose needs correcting.
- `expected_area.py`/`EXPECTED_AREA_MAX_HALF_WIDTH_DEG` — **not edited by this plan**, but its
  feasibility bound is computed from `contact_growth_rate_mps` (already confirmed in that module),
  so Kub/SA-6 contacts' bound changes as a *direct, intended* consequence of Stage 1–2's override —
  see the acceptance check below, which corrects the goal check's own Finding 5 ("unchanged except
  fixed types now at zero" did not anticipate this one system moving the *other* direction).
- `_PHRASING_CERTAINTY` (`tools.py`) — left as-is. It feeds the brain's own LLM-composed phrasing
  (out of this plan's deterministic-wording scope); the words ("recent"/"remembered") stay usable
  even though "tracked"/"estimated" now mean something different internally.

**Stage 7 — report-summary wording tracks the certainty label, not age (Finding 6)**

`speech.py`'s `_is_stale(facts, stale_window_s)` currently triggers "Last I saw, …" on
`last_seen_ago_s > OBSERVED_WINDOW_S` (16 s) — age, not the label. Replace it with a certainty read:

```python
def _needs_hedge(facts: dict[str, object]) -> bool:
    """Whether this contact's report-summary wording should hedge --
    `facts["certainty"] == "estimated"` (never "lost", already dropped from
    report scope; never "observed"/"tracked", stated as fact)."""
    return facts.get("certainty") == "estimated"
```

Drop the `stale_window_s: float` parameter from `render_report_summary`,
`_summary_deferral_clause`, and `_summary_air_defence_freshness_clause` — every call site
(`_is_stale(facts, stale_window_s)`) becomes `_needs_hedge(facts)`. Update
`crew_console.py:4347`'s call site to drop the now-gone `stale_window_s=OBSERVED_WINDOW_S` kwarg.
Leave `last_seen_ago_s`/`_spoken_age_phrase`/`_attack_run_last_seen_phrase` untouched — only the
*trigger* changes, not the age-display wording once hedging is already underway.

No contact can reach `"estimated"` before leaving the `"observed"` window under the new rule: even
the fastest class rate in the table (`OP_TRUCK`, 15 m/s) needs ~33 s to cross 500 m, well past
`OBSERVED_WINDOW_S` (16 s) — so there is no new edge case at the observed/tracked boundary.

### Risks & Unknowns

- SA-2's `op_class` is pending the investigator (see above) — a wrong bucket would misstate SA-2's
  spoken category and threat envelope, not this plan's growth/hedge mechanism.
- Finding 3's root cause (8 arcmin/s angular threshold missing a closing approach) is not fixed by
  Stage 4 — a sustained closing unit can still read "stopped" after a genuine 5 s watch, just not
  from one glance. Residual risk, not newly introduced.
- `[[BL-B115]]` is the only reader of the new `CompositionItem.immobile` field until it lands — if
  that item is deprioritised, the field is written but unused for a while. Harmless (additive,
  already the posture every other per-run log/field in this codebase takes), just worth naming so
  it isn't mistaken for dead code later.
- Kub/SA-6's growth-rate reversal (Stage 2) is the one place this plan *widens* a bound rather than
  narrowing one — worth a specific line in the DoD/acceptance report, not just a passing mention,
  since it is the opposite direction from every other change here and could read as a regression if
  not called out.
- The `fold_motion` founding-case change (Stage 4) is a behaviour change to a previously
  load-burdened, explicitly documented rule, requiring an existing test to be rewritten rather than
  extended — user-directed, named per Escalation Rules so it is not read as unauthorized scope.

### Decisions Requiring User Input

- **SA-2's `op_class`** — genuinely open per the investigator (no ED source assigns one; this
  project's own SR/MR/LR rows are judgment calls, not verified classification). *Plan uses
  `OP_LRSAM`* (closer by range ratio to SA-10 than to SA-6). Flag this to the user as a one-line
  check, not a blocking question — it changes SA-2's spoken category ("long range SAM" vs. "medium
  range SAM") and which threat-envelope entry it draws from, not this plan's growth/hedge mechanism.
- **S-300 (SA-10) `installation_component=True` fix** (Stage 1) — opportunistic: today it is
  `False` (a pre-existing gap, Finding 4), and fixing it gives SA-10's radar/launcher/CP the same
  cohesion grouping S-125 and (unchanged) Kub already get. Not explicitly asked for; recommended
  because it is small, correct, and consistent with the user's own framing of SA-10 as a fixed
  multi-component site. Flagging so it can be vetoed rather than landing silently.
- **SA-11/Buk** — not added. The user's answers name SA-2/SA-3/SA-10/SA-6 explicitly but never
  Buk, and today `object_model.py` has zero keyword coverage for it at all. *Corrected by the plan
  check (main loop, 2026-11-12):* Buk's TELARs each carry their own engagement radar
  (`body-layer/research/2026-10-01-sam-site-geometry.md`) — self-contained mobile platforms, the
  branch of the user's rule that makes SA-6 mobile, not the SA-2/3/10 branch. So when Buk coverage
  is added it defaults to `immobile=False`, unless the user says otherwise then. Left out of this
  plan.
- **`plausible_speed_mps`'s now-dead `installation_component` kwarg** — leave or delete; no
  behaviour difference either way, Implementer's call.
