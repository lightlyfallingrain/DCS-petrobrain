# First sortie with DCS-driven LOS — log analysis

Dated: 2026-10-05. The user flew the first sortie carrying `X-B29` (DCS-driven batched line of
sight) and could not judge it from the cockpit — *"I can't tell about DCS LOS directly from
flight"* — which is expected: LOS is a gate, and a gate that works correctly is invisible. This is
the log read in its place.

Sources: `~/dcs-detection-trace.jsonl` (3.55 GB; the new-schema region begins at byte offset
2,448,471,603 — the file is appended to, not replaced, so the head is a previous sortie),
`~/dcs-belief-truth.jsonl`, `~/dcs-speech.jsonl`, and — supplied by the user after the first draft
of this note — **`~/dcs.log`** (1.8 MB, 7,113 `PetrobrainLineOfSight` lines). That last file
overturned §2's original conclusion; the correction is kept visible rather than edited away.

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

## 2. CORRECTED — `dcs.log` arrived, and it moves the fault from the producer to the consumer

**The first version of this note blamed the DCS-side feed. `~/dcs.log` (captured after the fact,
1.8 MB, 7,113 `PetrobrainLineOfSight` lines) shows that was wrong, and the real finding is larger.**

**The Hook never faltered.** 5,534 LOS polls over 93 minutes of wall clock, 15:40:16 → 17:13:04:

| | |
|---|---|
| wall gap between LOS polls | **median 1.00 s, p90 1.01 s** |
| gaps over 5 s | **1**, of 5.5 s |
| total time inside those gaps | 6 s of 5,568 s (**0 %**) |
| `bridge_call_ms` | med **1.00**, p90 2.00, p99 5.00, **max 26.00** |
| calls over 8 ms / 16 ms / 24 ms | 14 / 4 / **1** |
| units in a result | median **43**, max **71** |
| `fov_half_deg` sent | **90 on all 1,576 directives** |
| hours commanded | 0, 1, 2, 3, 9, 10, 11 — a real scan pattern |

So: a metronomic 1 Hz producer, never truncating (71 against a 128 cap), and a bridge cost that
sits at 1 ms. **The user's hypothesis that a paused DCS caused the gaps does not hold either** —
pausing stops `onSimulationFrame`, which would show as wall-clock gaps in this log, and there are
none.

### What is actually slow is **body-layer's own poll loop**

| source | distinct polls | span | median gap |
|---|---|---|---|
| DCS Hook (producer) | 5,534 | 5,568 s wall | **1.00 s** |
| detection trace (consumer) | 2,621 | 4,235 s sim | **1.44 s** |
| belief-truth log (consumer) | 1,340 | 4,233 s sim | **1.43 s**, p90 **4.98 s**, **max 193 s** |

**The poll loop is specified at 5 Hz — 0.2 s — and is observed at roughly 0.7 Hz, about seven times
slower.** The belief log's own rate is 0.32 polls/s. That single fact explains the LOS "outages"
without any fault in the LOS feed: verdicts are published every 1.0 s and consumed every 1.4 s, so
the consumer skips publishes, and whole stretches of sim time pass with no poll at all — the 193 s
maximum gap in the belief log is not a feed outage, it is **body-layer not polling for over three
minutes**.

**This is the finding of the sortie, and it is not an X-B29 defect.** It predates this feature and
affects everything downstream of the poll loop — detection latency, movement detection, callout
timing, every decay half-life that assumes a 5 Hz tick. The LOS work merely made it visible, by
adding a producer with a known, independently-logged cadence to compare against.

Cause unknown and not diagnosable from these logs. Candidates, in rough order of suspicion: the
world-model LOS fallback (an SQLite query per candidate per poll, on the path that is now carrying
77 % of admissions — see below); the `BL-B26` triple-gather in `CalloutScheduler.tick`; the
detection-trace writer itself; or simple network latency on the aircraft-layer poll. **A timing
instrument around the poll loop is the next step, not more log reading.**

## 3. The fallback is carrying most admissions

This is the finding worth acting on, and it is precisely the failure Security's deep analysis
predicted and called unobservable without reading the log.

**Of 14,703 admitted rows, only 3,435 (23 %) had a live verdict. The other 11,268 fell back to the
offline primitive** — world-model's SRTM-grid LOS with its 12 m tolerance, i.e. the path the user
has just ruled obsolete for live use.

Per-poll coverage is **bimodal, not partial**:

- **38 % of polls fully covered** (every past-gaze unit has a verdict)
- **19 % of polls have zero coverage** — not one verdict
- median per-poll coverage **0.44**

Zero-coverage polls **cluster into runs** — **211 distinct outages**, the longest **20.7 s / 10
consecutive polls**, with the gap between verdict-bearing polls reaching **60.9 s** at worst.

**The first draft of this note read that clustering as the DCS feed stopping, and named three
candidate causes. All three are now excluded by `dcs.log` (§2): the Hook published every 1.00 s
without interruption for the whole flight.** The clustering is the *consumer* not polling — the
same ~0.7 Hz loop, with its own 4.98 s p90 and 193 s maximum gaps. The two findings are one
finding, seen from either side of the seam.

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

## 4. Non-LOS: contact identity churn is the standout, and it got worse

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

## 5. Speech: the pilot used a command that does not exist yet, and `say again` fires on ordinary talk

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

1. ~~Capture `dcs.log`.~~ **Done — the user supplied it, and it exonerated the feed.** See §2.
2. **Instrument the poll loop.** It is running at ~0.7 Hz against a specified 5 Hz, and that is the
   largest finding here. It is a pre-existing defect that X-B29 exposed rather than caused, and it
   degrades everything downstream of the tick.
3. **Add an observable for silent fallback.** Security flagged this as low/low before the flight;
   the flight shows the fallback carrying 77 % of admissions, which upgrades it.
4. `report right` vs `report left` — direct and probably small.
5. Contact churn (`BL-B24`) is now the largest untreated defect in the belief layer.
