# First sortie with DCS-driven LOS — log analysis

Dated: 2026-10-05. The user flew the first sortie carrying `X-B29` (DCS-driven batched line of
sight) and could not judge it from the cockpit — *"I can't tell about DCS LOS directly from
flight"* — which is expected: LOS is a gate, and a gate that works correctly is invisible. This is
the log read in its place.

Sources: `~/dcs-detection-trace.jsonl` (3.55 GB; the new-schema region begins at byte offset
2,448,471,603 — the file is appended to, not replaced, so the head is a previous sortie),
`~/dcs-belief-truth.jsonl`, `~/dcs-speech.jsonl`. **`win-mac-sync/from-windows/dcs.log` is stale
(13:09, pre-flight)**, so none of the Hook's own counters — `bridge_call_ms`, `units_in_wedge`,
`sightlines_computed` — could be read. Everything below is inferred from the body-layer side.

Sortie: **1.64 M trace rows, t_sim 0 → 4,234 s (70.5 min), 2,104 polls past the player bubble.**

---

## 1. The live path works, and buildings occlude — the headline result

**101,091 rows carry a live verdict.** The three fields are internally consistent: every
combination observed is exactly `live_los_clear = building_clear AND terrain_clear`, with no
contradictory rows.

| building_clear | terrain_clear | live_los_clear | rows |
|---|---|---|---|
| True | True | **True** | 40,362 |
| True | False | False | 39,030 |
| False | False | False | 11,950 |
| **False** | **True** | **False** | **9,861** |

**That last row is the new capability, and it fired 9,861 times across 118 distinct objects.**
Terrain was clear and a *building* blocked the sightline — something that could not happen in this
project before today, in either path. The blocked objects are ordinary mission traffic (T-55,
BTR-80, GAZ-66, HMMWV, infantry) and include a **`5p73 s-125 ln` SAM launcher**, which is exactly
the case where being wrongly visible matters.

`los_skew_s`: median **0.16 s**, max **0.94 s**, against `LOS_MAX_AGE_S = 3.0`. Verdicts are fresh;
staleness is not a problem.

**No contact was ever admitted on a `False` live verdict** (3,435 admissions with a verdict, all
`True`). The gate is doing its job rather than being advisory.

---

## 2. The unusual thing: the LOS feed is intermittent, and the fallback is carrying most admissions

This is the finding worth acting on, and it is precisely the failure Security's deep analysis
predicted and called unobservable without reading the log.

**Of 14,703 admitted rows, only 3,435 (23 %) had a live verdict. The other 11,268 fell back to the
offline primitive** — world-model's SRTM-grid LOS with its 12 m tolerance, i.e. the path the user
has just ruled obsolete for live use.

Per-poll coverage is **bimodal, not partial**:

- **38 % of polls fully covered** (every past-gaze unit has a verdict)
- **19 % of polls have zero coverage** — not one verdict
- median per-poll coverage **0.44**

Zero-coverage polls **cluster into runs**, which rules out per-unit join failures and points at the
feed stopping: **211 distinct outages**, the longest **20.7 s / 10 consecutive polls** (t_sim
2172–2193), with several 7–11 s runs. The gap between verdict-bearing polls has a **median of
1.63 s** — already longer than the intended 1 Hz publish — **p90 4.33 s and a maximum of 60.9 s**.

A 61-second hole means more than a missed tick. Candidate causes, none yet distinguished:

1. **The look-direction directive stops being sent or applied**, so the Hook computes a wedge that
   no longer matches where Petrovich is looking and returns units body-layer does not ask about.
2. **The Hook's own publish stalls** — the `dostring_in` call failing, the socket wedging, or the
   bridge returning an error that is swallowed.
3. **A unit-name join mismatch** that happens to correlate in time rather than per unit.

`dcs.log` would separate these immediately, and it was not captured. **That is the single most
valuable thing to collect on the next flight.**

### A second, odd detail inside the same finding

Rows **missing** a verdict have a *lower* median true range (**3,820 m**) than rows **with** one
(**6,750 m**). If this were the 128-sightline cap truncating a nearest-first list, the misses would
be the *far* ones. It is the opposite, which is further evidence against truncation — and only
**11 of 2,104 polls** had more than 128 units past the gaze gate at all, so the cap is essentially
never reached.

**Why this matters beyond coverage:** the fallback is silent. Nothing in the pipeline distinguishes
"DCS says clear" from "SRTM-with-12 m-tolerance says clear", so for 77 % of admissions the pilot
got the old answer while the system reported success. The design intends the fallback to exist; it
does not intend it to be the common case.

---

## 3. Non-LOS: contact identity churn is the standout, and it got worse

| | 2026-10-04 sortie | **this sortie** |
|---|---|---|
| duration | 22 min | **70 min** |
| distinct objects | 258 | 444 |
| distinct contacts | 247 | **554** |
| contacts per object | 0.96 | **1.25** |
| **objects carrying 2+ contact ids** | 102 of 258 (40 %) | **361 of 444 (81 %)** |
| worst single object | 7 contact ids | **13** (a T-55) |

**Four fifths of all real objects were tracked under more than one contact identity.** A Tigr, an
AA8 and a BTR-80 each accumulated 11–12. This is `BL-B24` /
`plans/contact-duplication-ambiguity-runaway/` — the root `ContactStore.ingest` policy that founds a
new contact when two or more existing candidates are plausible — and it is the known-open item the
callout-suppression fixes were explicitly *not* addressing.

The suppression work is doing its job downstream: the pilot reports *"very good improvements on
contact detection and reporting"*, and `cardinality_discrepancy` fell from **58.7 % to 44.2 %** of
rows. But the underlying store is now churning harder than before, and it is being hidden rather
than fixed. **Longer sorties make it worse**: contact lifespan median is 331 s with 161 of 554
contacts living under 30 s.

Position quality is unchanged and healthy: **median error 181 m, p90 599 m** (previous sortie: 286 /
604).

---

## 4. Speech: the pilot used a command that does not exist yet, and `say again` fires on ordinary talk

63 utterances: 44 acted, 7 confirmed, 8 `say_again`, 4 fell through.

**The pilot spoke `"Describe eleven o'clock."` at t_sim 258** — the synonym requested *after* this
flight and not yet built. It fell through, correctly. Worth recording as independent evidence the
synonym is wanted, and the planned `report`→`describe` change would have caught it.

**Three real command attempts that failed**, all plausibly things the vocabulary should accept:

- `"report right."` (0.85) → `say_again`; but `"report left."` (0.83) → `confirm`. **An asymmetry
  between left and right in the same session is a defect, not a recognition accident** — worth a
  direct look at the phrase tables.
- `"cancel all."` (0.77) → `say_again`. `cancel task` / `cancel everything` exist; `"all"` does not.
- `"follow ahead."` (0.82) and `"follow, tech armour."` (0.58) → `say_again`. The known D10
  structured-candidate gap — `follow <descriptor>` still cannot resolve.

**The noise case worth the user's ear:** `"Peace."` (conf 1.00), `"All right."`, `"See you again."`
and `"Can I sell it?"` all produced **`say_again`** — meaning Petrovich audibly asked the pilot to
repeat ordinary speech that was never addressed to him. Four interruptions in a 70-minute sortie is
not severe, but it is the same class of problem as the bare `"quiet"` phrase that was dropped for
`silence`: a confident recognition of something that was not a command. `"Yes."` by contrast fell
through silently, which is the correct behaviour — so the two paths disagree about what to do with
non-commands.

---

## What to do next

1. **Capture `dcs.log` on the next flight.** Without it the feed-outage cause cannot be separated,
   and the Hook's own `bridge_call_ms` / `units_in_wedge` / `sightlines_computed` counters — which
   exist specifically to answer this — were never read.
2. **Treat the intermittent feed as the first real defect of `X-B29`**, ahead of any tuning. The
   mechanism is proven correct; its availability is not.
3. **Add an observable for silent fallback.** Security flagged this as low/low before the flight;
   the flight shows the fallback carrying 77 % of admissions, which upgrades it.
4. `report right` vs `report left` — direct and probably small.
5. Contact churn (`BL-B24`) is now the largest untreated defect in the belief layer.
