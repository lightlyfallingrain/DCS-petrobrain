# Performance Review — BL-13, the crew query path (Stages 1–3)

**Reviewed at** `feature/bl13-crew-query-path` tip **`a44401e`** (`git rev-parse HEAD` returned
`e2e2164` first, a strict ancestor with a clean tree, so `git merge --ff-only a44401e` was run and
HEAD now equals the named tip). Whole-feature diff `e2e2164..a44401e`: Stage 1 `0986caf`, Stage 2
`e95132b`, Stage 3 `b63a006`.

**Checks**: `audio-adapter` **255 passed / 1 skipped**; `body-layer` **1604 passed / 4 xfailed** —
both exactly as the brief expected. (The worktree carries no `.venv`; the root checkout's
interpreters were used read-only with the worktree's own `src` on `sys.path`, which is why the
command differs from `CLAUDE.md`'s.)

**Everything numbered below was measured, not reasoned.** Three harnesses, each carrying its own
can-this-fail probe that was **asserted before any timing was reported**:

| harness | probe | result |
|---|---|---|
| `bench_audio.py` | wrap `parse_band` in a `+1 ms` sleep; the reported `match_transcript` figure must rise by ≥ 0.9 ms | **+1798 µs** seen, and the baseline restored to within 0.6 µs afterwards — PASSED |
| `bench_body.py` | inject `+20 µs/contact` into `descriptor_verdict` and `+200 µs/assemble` into `_summary_air_defence_clause`; both numbers must rise | `_report_scope` 0.017 → **1.068 ms**, summary 0.056 → **0.259 ms** — PASSED |
| `bench_enrich2.py` | the real store must return real facts, and the divide fixture must not be degenerate | 2 semantic facts returned; **0/52 target positions had a divide**, i.e. the fixture *is* degenerate for that one term — recorded as a caveat below rather than quoted as if it were the loaded case |

Harnesses live in the session scratchpad, not in `src/` or `tests/`. The body-layer figures come
from the **real** `world-model/data/world-model/syria-full.sqlite` (738 MB) where they touch the
store, because a synthetic store understates absolutes 3–12× in this project.

The 2026-10-05 whole-subproject pass (`body-layer/research/2026-10-05-performance-review.md`) is the
baseline and is **not** re-derived here: the poll interval is `1.0 s` (`_DEFAULT_POLL_INTERVAL_S`, `logger.py:1098` at this tip — that
review cited `:999` at its own `19143fa`; there is no
5 Hz configuration anywhere), the loop sleeps *after* the work so realised period = work + 1.0 s,
and the term that dominated the tick was `group_salient_ids`, since fixed by BL-11 (poll work
330 ms → 12.6 ms).

---

## Which path each cost sits on — established first, because it decides everything

- **audio-adapter**: `_parse_report_slots` + the verb gate run **per anchored transcript**, in front
  of the phrase table. A transcript arrives when the pilot speaks — seconds apart at best.
- **body-layer**: `_report_scope`, `_band_label_for` and `render_report_summary` are reachable
  **only** from `CrewConsole.handle_command`. Verified by grep: the only callers of
  `_handle_slotted_report`/`_report_scope`/`render_report_summary`/`descriptor_verdict` in `src/`
  are `handle_command`'s dispatch at `crew_console.py:1319` and `_descriptor_score` (the `follow`
  path). **Nothing new leaked into the per-poll path.**
- **But `handle_command` itself runs inside the poll body** (`logger.py:1668-1672`,
  `_poll_f10_commands`/`_poll_transcripts`, synchronously after `drain_events`). So a query's cost
  is not "off the hot path" — it is a **one-off stall of the poll loop**, which is the frame the
  2026-10-05 review's sleep-after-work mechanism puts it in.

---

## Findings

### 1. The report-slot branch is *cheaper* than the phrase table it short-circuits

- **Location:** `audio-adapter/src/command_matcher.py:567-581` (the verb gate and branch),
  `:459-490` (`_parse_report_slots`), `vocabulary.py:917`, `:946`, `:985` (`parse_sector_word`,
  `parse_relative_word`, `parse_band`).
- **Measured**, median of 7 × 2000 calls:

  | transcript | path taken | µs/call |
  |---|---|---|
  | `report left` | new slot branch | **116.3** |
  | `describe armor two o'clock near` | new slot branch, 3 slots | **148.4** |
  | `follow two o'clock` | pre-existing follow branch | 95.0 |
  | `scan left` | phrase table | 684.3 |
  | `report contacts` | phrase table (`report_all`) | 821.1 |
  | `the weather is fine today` | no verb anchor | 547.1 |

  Returning before the phrase table **saves ~500–700 µs** on every slotted query. The plan's own
  risk note ("three more scans of a ≤10-word transcript is nothing, but the branch sits in front of
  the phrase table on the live path") is confirmed in the favourable direction.
- **Each parser is a single pass**, as the plan required: `parse_sector_word` 3.87 µs,
  `parse_relative_word` 3.79 µs, `parse_band` 3.71 µs, against the reused `parse_descriptor`
  3.81 µs and `parse_clock` 3.75 µs. All five together, `_parse_report_slots`, **18.9 µs** — next to
  `_parse_follow_slots`' pre-existing 13.4 µs for three.
- **The verb-branch ordering costs no redundant scan.** `command_matcher.py:549` gates the follow
  branch on a *single* `SequenceMatcher(verb, "follow").ratio()` before calling
  `_parse_follow_slots`, so a `report`/`describe` transcript pays one short-string ratio and no
  parser work before reaching its own branch. The report gate itself is two ratios
  (`_REPORT_VERBS`). Measured end to end above.
- **Action:** none.

### 2. `normalize_for_match` is paid five times per report transcript — real, and not worth fixing

- **Location:** `vocabulary.py:928`, `:951`, `:992` (and `:877`, `parse_descriptor`) — each parser calls
  `normalize_for_match(text).split()` itself, as do the two reused ones.
- **Measured:** `normalize_for_match` is **3.36 µs** of each parser's ~3.8 µs. Hoisting one
  normalisation into `_parse_report_slots` would cut 18.9 µs to roughly **4 µs** — a 4.7× saving on
  a term worth **15 µs per spoken utterance**.
- **Action:** **LATER / never.** 15 µs on a path that fires when a human speaks is not a cost. It is
  noted only so a future reader does not mistake the repetition for an oversight: it is what keeps
  each parser independently callable and testable, which is the same posture `_parse_follow_slots`
  already has.

### 3. `_report_scope` and `render_report_summary` are strictly linear, and ~0.03 ms at sortie scale

- **Location:** `crew_console.py:1971-2076` (`_report_scope`), `speech.py:797-947`
  (`render_report_summary`).
- **Measured** (ms per call; `get_contacts` stubbed so this is the new code alone):

  | n contacts | no slots | clock | sector | relative | band | descriptor | clock+band+descriptor |
  |---|---|---|---|---|---|---|---|
  | **52** | 0.006 | 0.011 | 0.011 | 0.011 | 0.008 | **0.017** | 0.014 |
  | 300 | 0.033 | 0.063 | 0.061 | 0.060 | 0.043 | 0.098 | 0.072 |
  | 1000 | 0.103 | 0.225 | 0.205 | 0.214 | 0.143 | 0.322 | 0.244 |
  | 2000 | 0.204 | 0.430 | 0.435 | 0.420 | 0.296 | 0.672 | 0.489 |

  `render_report_summary`: 0.057 ms at 52, 0.311 ms at 300, 2.047 ms at 2000 — **~1.04 µs per
  in-scope contact, flat**, despite up to three `_assemble` candidates each re-walking `facts_list`
  for the air-defence clause. The utterance stays 17 words at every size, so the word budget's
  drop-order loop terminates in one or two iterations.
- **Superlinearity check, the one the group-reporting review's 300–400 cliff makes worth asking:**
  per-contact cost over a **38× size increase** (52 → 2000) is **0.97×** for the filter and
  **0.97×** for the aggregation. Quadratic would have been ~38×. **Nothing here is superlinear in
  contact count.**
- **Whole new-code cost of one query at the 2026-09-28 sortie's 52 simultaneous contacts:
  0.034 ms** (filter 0.011 + summary 0.023 over the 18 in-scope).
- **Action:** none. This is three orders of magnitude inside anything that could matter.

### 4. Stage 3 made ~63 ms/contact of enrichment dead on the report path — the only finding with a real number behind it

- **Location:** `crew_console.py:2043` — `_report_scope`'s `for result in get_contacts(self.store,
  now_sim, enrichment=self.enrichment)`. `get_contacts` → `tools._contact_facts`
  (`tools.py:350-358`) pays, **per contact, before any slot filter runs**:
  `enrichment.cache.get_or_compute` (terrain-aware position **and** `semantic_facts_for`, i.e. a
  `query.describe.describe_position` call) plus `terrain_divide_qualifier`.
- **What changed:** Stage 3's summary reads only `classification`, `cardinality`,
  `relative_now` and `last_seen_ago_s` (grep over `speech.py:500-950`: those four keys and no
  others). `_report_scope` reads `relative_now` plus `descriptor_verdict`'s
  `classification`/`cardinality`. **Neither reads `facts["semantic"]` or
  `facts["terrain_qualifier"]`.** The path Stage 3 replaced *did* read both — `_render_report_lines`
  → `render_group_full_disclosure` → `_contact_report_text` (`speech.py:1410-1421`). So the work is
  not newly *performed*; it is newly **discarded**, for every report command, since all four token
  families (`report_all`, `report_clock_*`, `report_bearing_*`, `report`) now route to the summary
  and `_render_report_lines` is dead code.
- **Measured against real `syria-full.sqlite`, warm page cache (so these are floors):**

  | term | per contact | at n=52 | cached? | read by BL-13's path? |
  |---|---|---|---|---|
  | `semantic_facts_for` (`describe_position`) | **63.25 ms** | **3,289 ms** | yes, per contact id / 50 m cell | **no** |
  | `terrain_divide_qualifier` | **6.77 ms** | **352 ms** | **never** | **no** |
  | *the whole of Stages 1–3's own new code* | 0.00065 ms | **0.034 ms** | — | yes |

  *Caveat, from the harness's own probe:* 0/52 fixture positions had a divide between them, so
  6.77 ms is `terrain_divide_qualifier`'s **no-divide** cost. The loaded case is higher, not lower.
- **Risk, concretely:** `handle_command` runs in the poll body, so one `report` query stalls
  perception and callouts for as long as it takes. At the sortie's 52 contacts that is **~3.6 s on a
  cold enrichment cache** and **~352 ms even on a fully warm one** (the divide term is never
  cached). The 2026-10-05 review's mechanism — period = work + 1.0 s — turns a 352 ms floor into a
  ~1.35 s poll, and a 3.6 s cold query into a visible freeze. **And the enrichment cache is not
  warmed by the poll loop**: the only `get_contacts`/`describe_contact` callers in `src/` are
  command handlers and `CalloutScheduler.tick`'s two per-callout calls, which enrich the few
  contacts about to be spoken, not all 52. BL-11's measured 12.6 ms poll work is itself the proof
  the poll does not enrich everything.
- **Why this is not a change request against this branch:** the `get_contacts` call and its cost are
  **pre-existing and unchanged in count** — `report_all` paid exactly this before BL-13, and BL-13
  does not add a call, widen the set enriched, or make any term more expensive. On the contrary, the
  path it replaced did *more* post-enrichment work (group resolution plus per-group full
  disclosure), and Stage 3 removes the report path's exposure to the unbounded `belief.groups`
  `EAGER` cohesion defect entirely, because the summary never walks a group roster. Demanding the
  fix here would mean redesigning a shared tool under a feature review.
- **Action:** **MONITOR, and escalate to the Architect** as its own body-layer item rather than back
  into this feature's loop. What makes it newly worth filing is that BL-13's entire purpose is to
  make the pilot ask *more often* and *more narrowly* — see finding 5.
- **Mitigation, for whoever picks it up** (all three are design decisions, not tweaks, which is why
  this is an escalation):
  1. **Let the report path opt out of semantic enrichment.** A flag on `get_contacts`/
     `_contact_facts` that skips `semantic_facts_for` and `terrain_divide_qualifier` removes 100 % of
     the measured cost for this path. The obstacle is `WorldEnrichmentCache`'s entry shape, which
     couples `world_position` and `semantic_facts` in one tuple, so a position-only computation
     needs a cache that can hold a half-populated entry without later callers mistaking it for a
     miss or a hit.
  2. **Filter before enriching.** Read `store.contacts` and compute the slot filters from
     `contact.last_position` + `relative_geometry`, enriching only survivors. Cuts `report left` at
     52 contacts from 52 enrichments to the 18 in-scope (2.9×), but changes which position the
     range/clock are computed from (flat vs terrain-aware), so it is a *correctness* decision about
     answer accuracy, not a perf tweak. It also does nothing for an unfiltered `report`.
  3. **Cache the never-cached term.** `terrain_divide_qualifier` is ownship-relative and so
     deliberately uncached (`enrichment.py:745`), but it is also the floor that survives a warm
     cache. Worth revisiting on its own.

### 5. The filters run after enrichment, so a narrow query costs exactly what the whole scene costs

- **Location:** `crew_console.py:2043-2070` — the `clock`/`wedge`/`band`/`descriptor` tests are all
  inside the loop body, after `get_contacts` has already enriched the contact.
- **Measured:** `report two o'clock` at 52 contacts puts **18** in scope; `report left` likewise
  narrows to a wedge. The post-filter work scales with the 18 (0.034 ms). The pre-filter work scales
  with the 52 (finding 4's figures). **The band/clock/relative slots cannot make a query cheaper —
  only shorter to say.**
- **Risk:** this is the behavioural half of finding 4, and it is what BL-13 changes. The feature's
  product argument is that short answers invite frequent narrow questions; the cost model says every
  narrow question is priced as `report_all`. A pilot who asks four times in a minute pays four full
  scene enrichments.
- **Action:** **MONITOR** — same escalation as finding 4, mitigation 2 is the one that addresses it.
- Also note: the ±1 h clock widening (`CALLOUT_GROUP_CLOCK_SPAN_HOURS`) puts more contacts in scope
  per query, which is intended. It is **not** a cost change, because the widening happens after
  enrichment and the post-filter term is 1 µs/contact.

### 6. Module-level derived tables are import-time only

- **Location:** `crew_console.py:451` (`_SECTOR_FOR_WORD`), `:486` (`_REPORT_BAND_LABELS`),
  `command_matcher.py:286` (`_REPORT_VERBS = report_verbs()`). All three are comprehensions or calls
  evaluated once at import, not per query. `ReportScope` is `frozen=True, slots=True`, so the one
  per-query dataclass allocation carries no `__dict__`.
- **Action:** none.

---

## Observations that are not findings

- **No per-request allocation worth naming.** Per query: one `ReportScope`, one `facts_list`, one
  `OutgoingSpeech`, and up to three candidate strings inside `_assemble`'s drop loop. Per transcript:
  five short `set`/`str` objects inside the parsers. Both measured above as whole-call costs.
- **The two pre-existing push-path defects named in the brief do not bear on any measurement here.**
  `belief.groups`' unbounded `EAGER` infantry cohesion would change how many contacts a *renderer*
  walks — but Stage 3's summary walks the in-scope facts and never a group roster, so the report
  path is no longer exposed to it. That is a side-effect of the leak fix, and worth saying in the
  defect's own ticket: closing it will not change the report path's cost either way.
- **`_render_report_lines`, `render_report` and `REPORT_MAX_GROUPS` are now unreachable dead code**,
  deliberately kept per Decision C so a revert is one call site. No cost; flagged only so the DoD
  pass knows it is intentional.
- **Band words unbenched on the user's voice** (the plan's own risk, `close`/`clock`) is a
  recognition-accuracy question, not a performance one. Out of scope for this pass.

---

## Verdict

**APPROVED — MONITOR.**

No required fixes. Everything BL-13 itself added is measured at **18.9 µs per transcript** and
**0.034 ms per query at the 2026-09-28 sortie's 52 contacts**, strictly linear to 2000 contacts
(0.97× per-contact over a 38× size increase), with the recognition branch landing **~500 µs faster**
than the phrase-table path it short-circuits. Nothing new reaches the per-poll path.

The one number worth anyone's attention — **63 ms/contact of semantic enrichment that this path now
computes and never reads, 3.6 s at 52 contacts on a cold cache, 352 ms on a warm one, synchronously
inside the poll body** — is a pre-existing cost that BL-13 neither adds to nor worsens, but whose
*waste* Stage 3 created and whose *frequency* the whole feature is designed to increase. It should be
filed as a body-layer item and taken to the Architect, because every fix for it changes a shared tool
or the position the answer's range is computed from. It must not be improvised into this branch.
