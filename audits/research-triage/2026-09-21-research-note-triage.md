# Research-note triage — claims that are now false

**Date:** 2026-09-21
**Scope:** all 64 `.md` files under any `*/research/` directory (excluding `.claude/`).
**Question asked:** which factual claims are contradicted by a later note, by the current code, or
by a recorded user correction. Not completeness, not style, not "this could be clearer."

**Why this is narrow and why it matters:** every one of these files is in the knowledge-graph
corpus (`.claude/scripts/graph-corpus-files.sh`). A wrong research note is not merely stale — it
surfaces mid-task through `gq.sh` with a citation and a confidence score attached, which is far
more convincing than the wrong paragraph was on its own. Plans are deliberately excluded from the
corpus and were not examined.

**Method for every correction:** preserve the original, add a clearly-marked correction block
above or beside it, state what is now believed and on what evidence, and — where the error is
instructive — say why it was plausible. `docs/PROCESS.md`, "Superseding a decision." No note's
history was rewritten.

---

## Headline

**27 of the 64 notes received a correction this pass; 37 are clean.** Of the 27: **24 carry a
claim that is simply false or superseded**, 2 carry a claim that cannot now be checked either way
(flagged as unresolved, not guessed), and 1 has only a stale file path.

Three recurring shapes account for most of them, and none is carelessness:

1. **A rigorous negative over one surface, reported as a fact about DCS** (5 notes). A `pairs()`
   enumeration, an exhaustive grep of one directory, a static Lua read — each correct about what
   it searched, each then recorded as the answer to a broader question. This is the project's
   single most common error mode and it has now produced the same failure five times across three
   subprojects.
2. **A hedge that does not survive the next hop** (4 notes). The original says "inferred,"
   "moderate confidence," "filenames not contents"; the citing note says "confirmed." A qualifier
   three paragraphs away does not travel with the sentence — which is precisely what a graph query
   does to a document.
3. **A "current" status line left behind when the same file was appended to** (3 notes). Two files
   contradict *themselves*: a Reproducible Test saying "no live test was run this session" above
   findings recording two live runs, and a reference doc whose header says the call mechanism is
   unprobed above a section giving its calibrated live results.

**The single most consequential finding is not in that taxonomy:** the 2026-09-17 calibration
ladder — the evidence base for every perception constant in `visibility.py` — was captured with
DCS's detection-aid dots enabled, and **neither research note derived from it said so**. The
fixture was marked; the notes were not.

---

## Problems found

### 1. The calibration ladder's contamination was not propagated to the notes

**Notes:** `body-layer/research/2026-09-17-vision-range-calibration-pass2.md`,
`body-layer/research/2026-09-20-calibration-screenshot-set-manifest.md`

**False claim** (pass2, the whole derivation; and manifest, verbatim):

> "Targets are visible only as faint marks on the horizon in the longer-range frames. That
> faintness *is* the measurement."

**Evidence against:** `body-layer/tests/fixtures/vision_calibration.json`'s `_comment` —
*"CONTAMINATED -- READ THIS FIRST (added 2026-09-21). The authoritative PNG set was captured with
DCS's 'detection aid dots' ENABLED (user, 2026-09-21) … Every grade in this fixture therefore
records what was visible WITH that aid, not unaided visibility, and is OPTIMISTIC by an unmeasured
amount that grows with range."* Corroborated by
`body-layer/research/2026-09-21-first-cones-sortie-results.md` and
`2026-09-21-calibration-target-decided.md` ("a **dots-off re-shoot is now the only remaining
precondition** for recalibration").

**Classification:** SUPERSEDED (both).

**Done:** correction block at the top of each. Pass 2's also retires a second claim —
*"`BINOCULAR_RANGE_MULTIPLIER = 4.0` survived untouched"* — which is false: the constant no longer
exists (`perception/optics.py`, "`BINOCULAR_RANGE_MULTIPLIER` is retired, not carried forward
(slice 2A)"). The manifest's correction adds the missing line to its own re-shoot protocol
(**dots off**) and records why an otherwise-thorough note missed it: it recorded everything visible
*in* the frames, and the setting that invalidated them was not in the frames. Capture conditions
that live outside the artefact have to be asked for.

---

### 2. `Object.getVelocity()` — the original note had no forward pointer

**Note:** `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`

**False claim** (finding 10's heading):

> "`LoGetWorldObjects` carries **no velocity** — the movement design must difference in the
> collector"

**Evidence against:** `2026-09-21-unit-velocity-via-mission-scripting.md` — `Object.getVelocity()`
returns a vec3 in m/s for every unit in the **Mission Scripting** environment; it is how Tacview
records speed.

**Classification:** first clause CORRECT, conclusion CONTRADICTED.

**Done:** correction block under the heading. Worth noting the note's own last paragraph *already
named* `Unit.getVelocity()` correctly — the error is entirely in the heading and the framing, not
the evidence, which makes it a clean example of shape (1): the narrow question was answered
rigorously and the answer was then relayed as the broad one.

**Also corrected in the same file:** findings 6 and 7 describe `perception/optics.py` as modelling
"an optic as magnification plus a field-of-view cone, with the same three angular tiers behind it,"
and finding 7 tabulates "Ours, binoculars (M=4.0)". Both describe code that no longer exists —
slice 2A replaced the single magnification with per-tier multipliers (2.42/3.50/3.00). The note's
own recommendation ("do not copy ED's optic recognition ratio without a decision") was followed;
the status line just never got updated.

---

### 3. The ASP-17V slew limits — the *original* note is where ±40° entered

**Note:** `aircraft-layer/research/2026-09-11-quickstart-ru-9k113-manual.md`

**False claim** (final Unresolved bullet):

> "Elevation/vertical limits of the real ПУ ПН (documented as +20°/-15° on the handle icon, p. 70,
> and separately **±40° on the horizontal head icon** on the same figure)"

**Evidence against:** `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md` — both
figures on Рис. 4.20 annotate the **ПУ ПН control console** (the operator's handle), not the
optical head. The head's own field of regard is **±60° lateral, +20°/−15° vertical**, sourced from
the English-language manual §3.4.

**Classification:** CONTRADICTED.

**Done:** correction block on that bullet. The 2026-09-20 note was already corrected; this note —
the one a query on "9K113 slew limits" surfaces alongside it — was not. Two points worth keeping,
both preserved in the block: the vertical pair was *right*, and one-axis agreement is exactly the
evidence shape that makes a wrong reading feel confirmed; and this very note independently
establishes why the two quantities cannot be the same (the operator commands an angular **rate**,
so console deflection and head angle are different kinds of thing).

---

### 4. "Neither ED nor we model dwell" — the origin note was unmarked

**Note:** `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`
(Session 6, Q4)

**False claim:**

> "since no accumulation mechanism was found, BL-2.6 is free to design its own dwell/time-weighted
> confidence model without contradicting anything DCS itself does — **there's nothing here to
> imitate or diverge from**; this is a genuinely open design surface"

**Evidence against:** `2026-09-20-dcs-install-detection-deep-read.md` finding 2, reading
`$DCS_INSTALL_PATH/Scripts/AI/Detection.lua`: `average_det_time_max_dist_0_for_ground_units = 10.0`
/ `..._180_for_ground_units = 60.0` (dwell), `motion_factor` up to 1.5× (movement). Slice 2's dwell
design was then built against those numbers
(`body-layer/research/2026-09-21-slice2-model-decisions.md` decision 2).

**Classification:** CONTRADICTED.

**Done:** correction block. The 2026-09-19 desk pass that carried this conclusion forward *is*
properly marked; this note, which originated it, was not. The greps here are all still correct —
`min_angular_radius` really has no Lua consumer in the Mi-24P tree — and the consumer turned out to
be the engine (`wDetector`), which no Lua grep could have reached. Shape (1) again.

**Also corrected in the same file:** the forum bullet asserting the HelperAI target list is
"generated by Petrovich AI **when using missiles**." Disconfirmed live —
`2026-09-11-petrovich-detection-readout.md` finding 2 measured `WeapSelect` (arg 523) at 0.000 =
OFF for five of six populated samples, with `NABL = 1.000` on every one. The gate is observation
mode. This search-snippet was correctly tagged `forum-claim-unverified` and was carried as a
project assumption for three days anyway, shaping two downstream notes.

---

### 5. The 2026-09-10 BL-6 feasibility note: four claims, no forward pointer

**Note:** `aircraft-layer/research/2026-09-10-bl6-petrovich-command-feasibility.md`

Four claims, each explicitly disconfirmed by name the next day, in a note that carried no pointer
to any of them:

| claim | evidence against |
|---|---|
| "No evidence … of any **read-side signal** that directly reports 'Petrovich is scanning' vs 'found N' vs 'idle'" | detection-readout finding 5 quotes this sentence and refutes it: the wheel's down slot carries `SEARCHING`/`TRACKING`/`WAITING` in `list_indication(10)` |
| Unresolved: "whether the AI Wheel offers anything resembling 'scan this area' … **the single biggest open question**" | finding 4: `SRCH 9K113 LOS`, `SRCH PILOT LOS`, `SRCH BRST`, `SRCH FWD` |
| "`list_indication(6)`'s target list is **weapon-selection/attack-mode-gated**" | finding 2: the gate is NABL |
| Unresolved: relationship between `AI_Wheel` and `g_panel` | `2026-09-11-command-injection-surface.md`: different things — `g_panel` is indicator 8, owned by `devices.WEAP_SYS` |

**Classification:** SUPERSEDED.

**Done:** correction table at the top of the file, plus the one claim that survives (`LoSetCommand`
is real and first-party documented, but is the *global* channel and cannot address a cockpit
device). Two of the four were negatives drawn from a surface that could not have shown a positive —
a static Lua read cannot see dynamically-generated wheel text, and a path listing cannot see file
contents.

---

### 6. `mi24p-command-surface.md` — the project's most-cited reference contradicts itself twice

**Note:** `aircraft-layer/research/mi24p-command-surface.md`

**False claim (a)** — the status header, and §1's closing paragraph:

> "The **call mechanism is not yet live-probed** — whether `GetDevice` / `performClickableAction` /
> `get_argument_value` exist inside Export.lua's state is the one unverified link."

**Evidence against:** the probe ran the same day.
`aircraft-layer/research/logs/2026-09-11/README.md`: *"`probe-cmd.log` … `GetDevice`/
`performClickableAction`/`get_argument_value` exist."* And the production
`aircraft-layer/dcs-export/Export.lua` calls `GetDevice(30):performClickableAction(...)` on lines
424-525 in the live BL-6 path.

**False claim (b)** — §4.2:

> "**The axes are velocity, not position.** … Pointing the sight at a bearing therefore means
> closing a loop — command a rate, read 874/876, integrate, stop"

**Evidence against:** §4.1.2 of the *same file*, and
`2026-09-11-command-injection-surface.md`'s "Live probe run 5 — RESOLVED": the AI axis (3060/3061)
is an exactly linear **position** target, ratio `0.440000` at five commanded points, settling inside
0.25 s. `look_at(bearing)` is a single write. Only the player axis (3025/3026) accumulates, which is
what `axis_use_velocity = true` describes.

**Classification:** CONTRADICTED (both).

**Done:** the stale header replaced by a correction block quoting it, and a correction block above
§4.2. This is the file most likely to be quoted from by a query, and it was telling a reader the
opposite of what the section three screens up says.

---

### 7. The F10 note's Reproducible Test and Unresolved sections contradict its own findings

**Note:** `aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md`

**False claim:**

> "No live test was run this session (no DCS box access)."

plus four Unresolved bullets, including *"Whether `net.dostring_in` is still functional … still
untested now"* and *"Contents of the installed `AddCommandRadioF10.lua` were not read this
session."*

**Evidence against:** Findings 7-11 of the same file record a same-day follow-up on the DCS machine
with **two live probe runs**, quote `AddCommandRadioF10.lua` with line numbers, and register an F10
item end to end via `net.dostring_in("scripting", …)`. Approach B then shipped
(`dcs-export/petrobrain-f10-commands-hook.lua`).

**Classification:** CONTRADICTED (self-contradiction — appended findings, unupdated front matter).

**Done:** correction block enumerating what each stale bullet's real status is, and preserving the
two items that genuinely remain open (the minimal `autoexec.cfg` opt-in, and `onRadioCommand`'s
payload).

---

### 8. The `.routes` offline road source — "the live-mission probe is the only route"

**Note:** `world-model/research/2026-09-03-m5-recon.md`

**False claim:**

> "**This is now the largest single unknown in M5**, since 27 removed the hoped-for offline
> alternative — the live-mission probe is the only route to DCS-authoritative roads."

**Evidence against:** `2026-09-03-m5-roadnet-file-recon.md` (later the same day) and
`2026-09-04-m5-roadnet-byte-decode.md` — `Syria.routes` is a flat float64 (x,y,z) point array in
DCS engine coordinates, readable offline. `world-model/CLAUDE.md`: *"**Roads: DCS-native
`.routes`/`.rn4` binary parsing, not live-probe (M5 decision)**. `land.getClosestPointOnRoads` /
`findPathOnRoads` are dropped entirely."* Neither function is called anywhere in
`world-model/src/`.

**Classification:** SUPERSEDED.

**Done:** correction block. The reasoning error is worth the space: "the remaining candidate is the
only route" follows only if the candidate list is complete, and the `.routes` file had not been
opened yet.

---

### 9. A one-digit transcription error in the Syria theatre extent, inherited downstream

**Notes:** `world-model/research/2026-09-05-m7-syria-theatre-extent.md`,
`world-model/research/2026-09-06-m8-geofabrik-osm-recon.md`

**False claim** (extent note, beacons row): latitude range `31.195-38.999°N`.

**Evidence against:** re-running the note's own Reproducible Test against the committed capture
`2026-09-03-m5-nodes-lua-probe.txt` gives the beacon extremes as `lat 31.194762 … 37.999037`. The
x-max beacon is the same object: `position = { 345432.437500, … }`,
`positionGeo = { latitude = 37.999037, … }`. **Every other figure in the row reproduces exactly.**

**The typo is self-refuting from inside the table**, which is why it is worth preserving rather
than silently fixing: the beacon and airbase x-maxima differ by ~3.7 km, and 1.0° of latitude is
~110 km — so the note's own next sentence ("the two independent point sets agree to within ~2-4 km
on every edge") cannot be true of the row as printed.

**Classification:** CONTRADICTED.

**Downstream:** the M8 note takes its working envelope from this table ("lat 31.2–39.0 N") and
carries the wrong northern edge through its coverage reasoning.

**Done:** correction blocks in both. No code was affected — `syria-full` is defined in DCS x/z
(`world-model/src/build/region.py`), not in latitude, so nothing ever read the mistyped figure. The
M8 correction notes the error is in the safe direction: an extract set sufficient for 39.0 N is
still sufficient for 38.0 N.

---

### 10. The tiling gate was cleared against the wrong polygon

**Note:** `world-model/research/2026-09-13-osm-landcover-optimization-validation.md`

**False claim:**

> "**3,359 is nowhere near the tens-of-thousands range** — no tiling follow-up needed based on this
> evidence."

**Evidence against:** `world-model/CLAUDE.md`, OSM-landcover decision entry — *"The tiling gate was
assessed against the wrong polygon and has now been re-measured at theatre scale (2026-09-16) …
Lake Assad is only the largest polygon in the Latakia extract. A full `syria-full` store holds
**Atatürk Baraj Gölü at 13,097 outer + 127 hole = 13,224 vertices** … the margin is ~1.5x, not the
~6x the small-extract figure implied."*

**Classification:** SUPERSEDED. The *decision* survives (still no tiling); the *evidence claim* —
that the measured polygon was representative and the headroom large — does not.

**Done:** correction block. The note's own "What the user should verify" section anticipated this,
which is what makes it instructive: a validation run on a deliberately small extract answers "does
the pipeline work," not "how big does this get," and a threshold gate is the second question
wearing the first one's clothes.

---

### 11. Two `.miz` paths falsified by the real sample

**Note:** `mission-interpreter/research/2026-09-12-miz-file-structure.md`

**False claims:** `mapResource` as a bare top-level zip member; kneeboard pages under
`KNEEBOARD/<AIRCRAFT_NAME>/IMAGES/`.

**Evidence against:** `2026-09-12-miz-validation-against-real-sample.md`, reading a real `.miz`'s
bytes the same day — *"`l10n/DEFAULT/mapResource` (the prior note assumed `mapResource` was a bare
top-level member; **it is actually nested under `l10n/DEFAULT/`**) … and a separate
`KNEEBOARD/IMAGES/` tree (**not `KNEEBOARD/<AIRCRAFT_NAME>/IMAGES/` as the prior note guessed**)."*
It also found a top-level `theatre` file the earlier note did not know existed.
`mission-interpreter/CLAUDE.md` states the validation note is load-bearing wherever the two
disagree.

**Classification:** CONTRADICTED. The later note cross-references back; the earlier one carried no
forward pointer, so read alone it is wrong on both paths.

**Done:** correction table at the top. Both wrong claims are *paths* — the part a secondhand source
reconstructs from memory rather than copies. Every structural claim in the note held up.

---

### 12. The Damascus residual

**Note:** `world-model/research/2026-09-02-m1-coordinate-transform.md`

**False claim** (Finding 7): *"33.42551°N, 36.51851°E — **1594 m** from the published ARP."*

**Evidence against:** `2026-09-03-m1-coordinate-transform-verification.md` Finding 3 — the pydcs
hardcoded `Damascus` point and the live `coord.LOtoLL` point are themselves ~1741 m apart in
DCS-native x/z, so pydcs's own airport point was imprecise and inflated the residual. Measured live
residual: **1137.5 m**.

**Classification:** SUPERSEDED.

**Done:** correction block at the top. Finding 7's conclusions survive intact; what the live check
reassigns is the blame. Of the three candidate explanations the note offers, the wrong one is
(b) — "pydcs's fitted parameters carry residual fitting error" — i.e. the most technical-sounding
of the three. The projection fit was fine; the point fed into it was not.

---

### 13. A citation to a research note that does not exist

**Note:** `world-model/research/2026-09-05-m7-stage0-roadnet-census.md`

**False claim:** *"identical to M5's previously-measured whole-file rate
(`world-model/research/2026-09-04-m5-roadnet-stage2.md`, 220/14,833)"*

**Evidence against:** no such file has ever existed. The only M5 roadnet notes are
`2026-09-03-m5-roadnet-file-recon.md` and `2026-09-04-m5-roadnet-byte-decode.md`. The 220/14,833
figures are real and the claim is correct — they live in `2026-09-04-m5-stage4-validation.md` and
`2026-09-04-m5-stage5-perf.md`.

**Classification:** CONTRADICTED (the numbers are right; the source pointer is fabricated).

**Done:** correction block. Kept rather than silently repointed, because this is the failure mode a
citation is supposed to prevent and instead performed: a filename reconstructed from the
milestone's naming pattern reads exactly like a real one, and nothing in the sentence signals the
source was recalled rather than opened.

---

### 14. Two overstated back-references in the M9 recon

**Note:** `world-model/research/2026-09-12-m9-tactical-landmarks-recon.md`

**(a)** *"across all ~1,186 entries"* — `towns.lua` has **1,182** entry lines (1,151 unique names).
1,186 was that line count minus one, and `2026-09-03-m5-recon.md`'s addendum (findings 30-31) had
already retracted it in those words: *"There were never 4 unparseable entries."* The finding is
unaffected by the denominator; the figure was reintroduced nine days after being retracted.

**(b)** *"(`.sup5` is the same family already reverse-engineered in M2's RasterCharts investigation
… where it was **confirmed** to be a general-purpose ED engine manifest/index type … and **every**
`Map/<Terrain>.sup5` across all installed theatres shares that same header signature)"* — the cited
note says the opposite of both halves. M2 session 2: *"absence of registration data specifically
inside `.sup5` **remains unconfirmed, not ruled out**"* (only the first 64 bytes were read; 615,152
bytes unread), and on the family claim, *"this remains inference from naming/sibling-pattern only,
**not content inspection**."* **No other theatre's `.sup5` header was ever parsed.**

**Classification:** CONTRADICTED (both).

**Done:** correction blocks on both. (b) is the cleanest instance of shape (2) in the corpus: the
bullet's own evidence tag correctly reads `inferred`, and the prose in front of it says
"confirmed." The citation supplied the confidence the evidence line withheld.

---

### 15. "None of the terrain-mesh candidates share the `landscape4::` magic"

**Note:** `world-model/research/2026-09-03-m5-terrain-file-formats.md`

**False claim:**

> "**The only remaining static-file candidates are unread, single-purpose, differently-named binary
> formats, none sharing the `.rn4`/`.routes` `landscape4::` magic**"

**Evidence against:** `2026-09-05-m7-terrain-mesh-elevation-relitigation.md` Finding 4, reading the
real head-bytes capture (`2026-09-04-m5-terrain-files-deep-probe-raw-2.txt`, from line 446):
`surface/Syria.onlay.sup4` carries the header **`landscape4::lSuperficialFile`**. The same pass
identified `Syria.ng5` as `navGraph5File` (guessed "unclear" here) and `Syria.surface5` as
`landscape5::Surface5File`.

**Classification:** CONTRADICTED.

**Done:** correction block. The practical outcome did not change — the relitigation deferred the
mesh route on decode cost and called `Syria.surface5` "a genuinely new, non-trivial lead," not a
dead end — but the terrain-mesh NO-GO this section argues for was resting on a premise the bytes
contradict. The note **flagged its own weakness in the same breath** (the parenthesis says the
magic string was matched against filenames, not contents, and proposes the probe that later
disproved it). The hedge was correct and written down; the bolded sentence in front of it is what
travels.

---

### 16. Latakia's SRTM tile

**Note:** `world-model/research/2026-09-04-m5-stage3-smoke-rung.md`

**False claim:** *"The Latakia region's lat/lon envelope (~35.0-35.5N, **~35.85-35.95E**) needs a
**different** tile (`N35E035.hgt`)"*

**Evidence against:** `2026-09-04-m5-stage0-census.md` §2 computes the same region's bounding box
from the same definition: **35.335238 / 35.834131 / 35.520883 / 36.060946**. The east edge is
36.06°E, so the region straddles the `E035`/`E036` tile boundary and needs both.

**Classification:** CONTRADICTED (by a sibling note in the same milestone, from the same region
definition).

**Done:** correction block. The note guesses at this two paragraphs later ("the region may straddle
a tile boundary, unconfirmed") while its own sibling had already computed the number. Nothing
downstream was affected — the Latakia store was deliberately built with no `--srtm-tile` at all.

---

### 17. Three smaller items in the M2 RasterCharts recon

**Note:** `world-model/research/2026-09-03-m2-rastercharts-recon.md`

- *"(confirmed Turkish military chart series, session 3)"* — session 3 says *"consistent with a
  standard 1:250,000-scale-class military/aeronautical chart series (JOG-A … or a close
  equivalent), **moderate confidence**"*: a NATO-standard series, not attributed to any nation's
  military. What session 3 established as Turkish is the **terrain the chart depicts**. Two errors
  in one parenthesis — a hedge became a confirmation, and the subject of "Turkish" slid from the
  ground to the publisher. **CONTRADICTED**; corrected inline.
- *"the right order of magnitude for the full Syria theatre's known extent (~500–600 km)"* —
  measured extent is **762 × 710 km** (`2026-09-05-m7-syria-theatre-extent.md`, which says it
  supersedes this). The ~524 km/side arithmetic is unchanged and still the right order of
  magnitude; only the figure it was compared against was a guess. **SUPERSEDED**; marked inline.
- The three-F10-map-modes claim in the session 4 addendum is already corrected **in-file** by
  session 10 ("'Alt' is a *fourth*"), so no edit was needed. **But see the open item below** — the
  user-level auto-memory still records the three-mode version.

---

### 18. Smaller corrections applied elsewhere

| note | claim | status |
|---|---|---|
| `aircraft-layer/.../2026-09-06-aircraft-layer-live-runtime-io.md` | "`LuaExportActivityNextEvent` … is the documented mechanism for throttling"; recommends running "at a throttled rate via `LuaExportActivityNextEvent` (e.g. 10-20 Hz)" | **CONTRADICTED** — implemented that way and it did not work. `LuaExportAfterNextFrame` fires every frame regardless; the real gate is a `last_export_t` check. `aircraft-layer/CLAUDE.md`: *"Do not rely on `LuaExportActivityNextEvent`'s return value to throttle anything."* A DCS documented-vs-observed divergence, not a misreading. |
| same file, finding 5 | "There is no confirmed API that hands back 'what Petrovich/the Mi-24P's sensors currently perceive' as structured data" | **CONTRADICTED** — `list_indication(6)` does exactly that and is in production. The survey of the *sensor-export* family was right about every function it tested; the answer was on the cockpit-indicator surface instead. Shape (1). |
| `aircraft-layer/.../2026-09-09-object-model-keyword-coverage.md` | "Finding 4's `"tank"` false-positive bug is **unfixed**"; "`S-3B Tanker` … **still** gets `OP_ARMORED`" | **CONTRADICTED** — `object_model.py` carries no bare `"tank"` keyword any more; the follow-up took the remove-it option, with the reasoning recorded in the module. |
| `aircraft-layer/.../2026-09-09-pb15-ambient-callout-live-probe.md` | "PB-1.5's **current** `NAKED_EYE_RANGE_CAP_M = 2500`" | **SUPERSEDED** — now 10000.0. Marked, noting the *finding* in that section (the pilot's "if the player can see it, Petrovich should") is what drove the change and is now the project's stated calibration target. |
| `aircraft-layer/.../2026-09-11-command-injection-surface.md` | "the gate is most likely **weapon mode**, arg 523" | **CONTRADICTED** (NABL). Correctly tagged `forum-claim-unverified` and genuinely worth testing — the probe this section designs is what disproved it. Marked so a reader arriving at the paragraph alone does not carry it forward. |
| same file | section heading "**CORRECTION: the axes are NOT positional**" | Reversed 90 lines below in the same file ("run 5 — RESOLVED"). A pointer was added *at the heading*, because a heading is exactly the fragment a graph query lifts, and this one loses its reversal. |
| `aircraft-layer/.../2026-09-19-ptt-gate-feasibility.md` | cites `srs-adapter/research/2026-09-17-tts-audio-transport-recon.md` | Path no longer resolves — the subproject is `audio-adapter/`. Corrected in place with a note. |
| `body-layer/.../2026-09-21-aspect-magnification-and-distinctiveness.md` | see item 19 | **CONTRADICTED** |

---

### 19. A circular derivation in the newest body-layer note

**Note:** `body-layer/research/2026-09-21-aspect-magnification-and-distinctiveness.md`

**False claim:**

> "As a fraction of nominal magnification: binocular **0.61×** … The binocular figure is close to
> the ~0.67 stabilisation penalty adopted on 2026-09-20 by argument alone — **an independent
> arrival at roughly the same number**."

**Evidence against:** the table's `M` column gives the binocular as 4.0, but 4.0 is **not** its
nominal magnification. `BINOCULAR_OPTIC` is a Б-6 **6×30**, and 4.0 is already 6× glass times the
~0.67 handheld-stabilisation penalty — stated in `perception/optics.py`'s `BINOCULAR_OPTIC`
docstring, `body-layer/ROADMAP.md` line 1076 (*"a Б-6 6×30 at M=4.0 — derived as 6× glass × a ~0.67
unstabilised-platform penalty"*), `plans/detection-cones-slice1/plan.md`, and `NOTES.md`.

So 2.42 / 4.0 = 0.61 divides by a figure with the penalty already baked in, and recovering ~0.67
from it is **circular, not confirmatory**. Against the real nominal 6×, the measured presence gain
is **2.42 / 6 = 0.40×** — a materially harsher stabilisation penalty than the one adopted by
argument, not "roughly the same number."

**Classification:** CONTRADICTED.

**Done:** correction block. The ×3.3 and ×10 figures are unaffected (genuine nominal
magnifications), and no constant in `optics.py` was derived from this ratio — the
stabilised-sight-beats-handheld result stands on the raw numbers. **Why it was plausible:** every
other row in that table takes its `M` straight from the instrument's real magnification, so reading
the binocular's the same way is the natural move — and 0.61 landing next to 0.67 supplied exactly
the confirmation that stops a second look. A derived constant sitting in a column of measured ones
is the trap.

---

## Could not determine — flagged, not guessed

### A. `tiny.en`'s error counts are off by one, and the corpus is not in the repo

`audio-adapter/research/2026-09-19-whisper-model-sweep.md`. 95.2% of 252 is 240 correct (the
verbatim column's own denominator agrees: `208/240`), leaving **12** errors — but the row lists
4 safe + 7 unsafe = **11**. Every other row balances exactly. So either the accuracy or one of the
two error counts is wrong.

**Which one cannot be determined from this repository** — the 252-clip corpus is not committed, so
the bench cannot be re-run. Flagged in the note rather than guessed. None of the note's conclusions
depend on it: the argument is that `tiny.en`'s 7 (or 6, or 8) unsafe errors are disqualifying
against `small.en`'s 0.

### B. "OSM power lines are off by ~1 km" is unsupported, and repeated project-wide

`world-model/research/2026-09-13-dcs-power-lines-recon.md` rejects OSM power-line positions as
"off by ~1km vs DCS terrain (consistent with the project's general OSM-vs-DCS residual)." Two
different residuals are being run together:

| figure | what it measures | value |
|---|---|---|
| M1's ~1.0–1.3 km | DCS placement of **point objects** (airport ARPs) vs. published real-world coordinates | ~1137 m |
| M5 Stage 4 Finding 2 | DCS-vs-OSM displacement of **linear features** (roads), measured | **median 5.3 m, p90 47.0 m** |

That finding exists *specifically* because the checklist predicted "~M1's 1.0-1.3km residual" for
roads and the measurement came back two orders of magnitude tighter, with a written investigation
explaining why the point-object figure does not transfer. Power lines are linear features.

**Nobody has measured OSM-vs-DCS power-line displacement.** So the stated justification is
unsupported — but it is not demonstrably *false* either, and the decision it supports (DCS-native
sourcing) rests on a standing project invariant regardless. Recorded in the note as **unresolved**,
not as a correction to the decision. `world-model/ROADMAP.md` carries the same "~1 km offset rules
it out" line, so this is a project-wide assumption rather than a slip in one note.

### C. Notes recording `nearest_road_osm` in `describe_position` output

Several M5/M6 notes quote `describe_position` output containing a `nearest_road_osm` field. That
field no longer exists (`world-model/src/query/describe.py`, `world-model/src/api/server.py`).
**Not filed as false** — they are accurate records of runs made at the time, which is what a dated
research note is for. But a reader treating them as a current API contract would be misled. No
edit made; flagged here because the judgement could reasonably go the other way.

---

## Out of scope but worth surfacing

Two items outside `research/` that this triage tripped over:

- **`~/.claude/projects/.../memory/project_dcs_f10_map_modes.md`** records "3 modes
  (paper/satellite/internal)". The M2 note's own session 10 established a **fourth** ("Alt"). The
  research note is self-corrected; the memory is not, and a memory is consulted more often than a
  1,600-line note.
- **`body-layer/CLAUDE.md`** still documents `BINOCULAR_RANGE_MULTIPLIER` as a live declared
  constant with a `visibility.py` home and an `optics.py` importer, including its full
  4.0 → 8.0 → 4.0 round-trip. It is retired. Same for the `Optic` dataclass signature
  (`magnification`, `boresight_azimuth_deg`), both of which slice 2A/2B replaced.

Neither was edited — both are outside this audit's scope.

---

## Full classification — all 64 notes

`CORRECT` = leave alone. `SUPERSEDED` = its claim was replaced by a later finding.
`CONTRADICTED` = simply wrong. `UNVERIFIABLE` = cannot now be checked.
Notes marked ✎ received a correction block this pass.

### `aircraft-layer/research/` (22 — one is a vendor document, listed after the table)

| note | verdict |
|---|---|
| `2026-09-06-aircraft-layer-live-runtime-io.md` | **CONTRADICTED** ✎ (item 18) |
| `2026-09-07-petrovich-perception-export.md` | CORRECT — hedged throughout; its central leads were confirmed, not refuted |
| `2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` | **CONTRADICTED** ✎ (items 4, 4-also) |
| `2026-09-08-pb1-live-spike-results.md` | CORRECT |
| `2026-09-09-dcs-text-panel-output-channel.md` | CORRECT — its Unresolved items were later resolved, but were honestly scoped when written |
| `2026-09-09-object-model-keyword-coverage.md` | **CONTRADICTED** ✎ (item 18) |
| `2026-09-09-pb15-ambient-callout-live-probe.md` | **SUPERSEDED** ✎ (item 18) |
| `2026-09-10-bl6-petrovich-command-feasibility.md` | **SUPERSEDED** ✎ (item 5) |
| `2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md` | CORRECT |
| `2026-09-11-command-injection-surface.md` | **CONTRADICTED in parts** ✎ (item 18) — already carried two superseded markers of its own |
| `2026-09-11-petrovich-detection-readout.md` | CORRECT — self-corrects extensively and honestly, including preferring the pilot's observation over its own probe |
| `2026-09-11-quickstart-ru-9k113-manual.md` | **CONTRADICTED** ✎ (item 3) |
| `2026-09-11-SUMMARY-petrovich-control.md` | CORRECT |
| `2026-09-13-f10-radio-menu-command-input.md` | **CONTRADICTED** ✎ (item 7) |
| `2026-09-19-ed-native-detection-identification-gap-analysis.md` | CORRECT — already carries a "PARTLY SUPERSEDED" header |
| `2026-09-19-ptt-gate-feasibility.md` | CORRECT except a stale path ✎ (item 18); otherwise a model of self-updating |
| `2026-09-20-dcs-install-detection-deep-read.md` | **CONTRADICTED in parts** ✎ (item 2) |
| `2026-09-21-unit-velocity-via-mission-scripting.md` | CORRECT |
| `mi24p-command-surface.md` | **CONTRADICTED** ✎ (item 6) |
| `logs/2026-09-11/README.md` | CORRECT |
| `reference/README.md` | CORRECT |

(`reference/Sim_ControlAPI.md` is a byte-for-byte vendor copy of an ED document, not a claim
document — excluded from classification, and must not be edited per its own README.)

### `body-layer/research/` (9)

| note | verdict |
|---|---|
| `2026-09-17-vision-range-calibration.md` | CORRECT — already carries a SUPERSEDED header naming its successor |
| `2026-09-17-vision-range-calibration-pass2.md` | **SUPERSEDED** ✎ (item 1) |
| `2026-09-20-9k113-sight-optics-from-manual.md` | CORRECT — already corrected; one stale line ("`visibility.py`'s `BINOCULAR_RANGE_MULTIPLIER` is ×4") left alone, since the surrounding paragraph is explicitly about what the constant meant at the time |
| `2026-09-20-calibration-screenshot-set-manifest.md` | **SUPERSEDED** ✎ (item 1) |
| `2026-09-21-aspect-magnification-and-distinctiveness.md` | **CONTRADICTED** ✎ (item 19) |
| `2026-09-21-calibration-target-decided.md` | CORRECT |
| `2026-09-21-first-cones-sortie-results.md` | CORRECT — it is the note that *surfaced* the dots contamination |
| `2026-09-21-s300-radar-dimensions.md` | CORRECT — every estimate explicitly flagged as such |
| `2026-09-21-slice2-model-decisions.md` | CORRECT |

### `world-model/research/` (26 `.md`)

| note | verdict |
|---|---|
| `2026-09-02-m0-dcs-install.md` | CORRECT |
| `2026-09-02-m1-coordinate-transform.md` | **SUPERSEDED** ✎ (item 12) |
| `2026-09-03-m1-coordinate-transform-verification.md` | CORRECT |
| `2026-09-03-m2-rastercharts-recon.md` | **CONTRADICTED / SUPERSEDED in parts** ✎ (item 17) |
| `2026-09-03-m3-osm-overlay.md` | CORRECT |
| `2026-09-03-m4-dcs-elevation.md` | CORRECT |
| `2026-09-03-m4-elevation-recon.md` | CORRECT — its "no viable offline path" is honestly scoped to what was then unread |
| `2026-09-03-m5-recon.md` | **SUPERSEDED** ✎ (item 8) |
| `2026-09-03-m5-roadnet-file-recon.md` | CORRECT |
| `2026-09-03-m5-terrain-file-formats.md` | **CONTRADICTED** ✎ (item 15) |
| `2026-09-04-m5-first-persistent-model.md` | CORRECT |
| `2026-09-04-m5-roadnet-byte-decode.md` | CORRECT — session 1's negatives are reversed in-file by session 2, with pointers |
| `2026-09-04-m5-stage0-census.md` | CORRECT |
| `2026-09-04-m5-stage3-smoke-rung.md` | **CONTRADICTED** ✎ (item 16) |
| `2026-09-04-m5-stage4-validation.md` | CORRECT — self-corrects in-file |
| `2026-09-04-m5-stage5-perf.md` | CORRECT |
| `2026-09-05-m6-terrain-semantics.md` | CORRECT — constants verified against `terrain/curvature.py`, `terrain/features.py` |
| `2026-09-05-m7-kola-square-vs-rectangle-stress-test.md` | CORRECT |
| `2026-09-05-m7-stage0-roadnet-census.md` | **CONTRADICTED** ✎ (item 13) |
| `2026-09-05-m7-syria-theatre-extent.md` | **CONTRADICTED** ✎ (item 9) |
| `2026-09-05-m7-terrain-mesh-elevation-relitigation.md` | CORRECT |
| `2026-09-06-m7-stages-1-2-3-full-build-results.md` | CORRECT |
| `2026-09-06-m8-geofabrik-osm-recon.md` | **CONTRADICTED** ✎ (item 9, inherited) |
| `2026-09-12-m9-tactical-landmarks-recon.md` | **CONTRADICTED** ✎ (item 14) |
| `2026-09-13-dcs-power-lines-recon.md` | **UNVERIFIABLE** ✎ (open item B) |
| `2026-09-13-osm-landcover-optimization-validation.md` | **SUPERSEDED** ✎ (item 10) |

(Also under this directory and not claim documents: `2026-09-03-m5-nodes-lua-probe.txt`,
`2026-09-03-m5-roadnet-files-probe-raw.txt`, `2026-09-03-m5-terrain-files-deep-probe-raw.txt`,
`2026-09-04-m5-terrain-files-deep-probe-raw-2.txt` — raw captures, CORRECT as records and used as
primary evidence for items 9 and 15.)

### `mission-interpreter/research/` (3)

| note | verdict |
|---|---|
| `2026-09-12-miz-file-structure.md` | **CONTRADICTED** ✎ (item 11) |
| `2026-09-12-miz-validation-against-real-sample.md` | CORRECT |
| `2026-09-12-player-slot-skill-field.md` | CORRECT — matches `mission-interpreter/src/schema/build.py`'s `skill in ("Player","Client")` rule |

### `audio-adapter/research/` (4)

| note | verdict |
|---|---|
| `2026-09-17-tts-audio-transport-recon.md` | CORRECT — its central wrong inference is retracted by its own addendum |
| `2026-09-19-corpus-bench-results.md` | CORRECT |
| `2026-09-19-whisper-contract-and-grammar-probe.md` | CORRECT |
| `2026-09-19-whisper-model-sweep.md` | **UNVERIFIABLE** ✎ (open item A) |

---

## What would stop this recurring

Not proposed as work, only as what the pattern suggests:

- **Shape (1) has a one-line fix that costs nothing at write time:** when a finding is a negative,
  state the surface it bounds *in the finding's own sentence* — "no velocity in
  `LoGetWorldObjects`", not "no velocity"; "no dwell constant in the Mi-24P tree", not "no dwell
  model". Five of these would not have happened.
- **Shape (2) is a citation-hygiene problem:** when quoting another note's conclusion, quote its
  evidence tag with it. Four of these inherited a confidence the source never claimed.
- **Shape (3) is mechanical:** when appending findings to an existing note, the Unresolved and
  Reproducible Test sections are part of the append. Two files currently tell a reader the opposite
  of what they contain.
