# body-layer security audit — whole subproject

Dated: 2026-10-05. Mode 3 (full-subproject audit), against `main` at
`19143fa434b654d4ada9a51d91593f782320766c`. Scope: `body-layer/src` (53 files, ~25.8k lines),
plus the two cross-seam claims that could only be settled by reading the peer
(`aircraft-layer/src/collector/text_sender.py`, `audio-adapter/src/vocabulary.py`).

Threat model this audit is rated against, stated up front because it decides every severity below:
**single-player, single-user, LAN-only, under active development, not yet public.** body-layer binds
no socket (confirmed: no `HTTPServer`/`socket`/`bind` anywhere in `src/`) — it is a pure client of
aircraft-layer, audio-adapter and brain-layer. There is no remote attacker in this model. The real
harms are therefore, in order:

1. **Loss of provenance integrity** — Petrovich knowing or claiming something he could not perceive,
   or the system reporting success while silently running on a degraded input. This is the project's
   core invariant and it is where the findings are.
2. **Availability mid-flight** — a crash, a dead poll thread, or a disk filling up during a sortie.
3. **Privacy of artifacts the project will eventually publish** — logs and traces, once this goes
   open-source.

Everything else (authentication, injection, remote code execution, secret handling) is either
structurally absent or genuinely not a problem here, and §D says which and why, so this list stays
credible.

---

## A. Fix now

### A1 — The live LOS verdict can never reach a nameless object, so the building-aware gate is structurally unavailable for exactly the population most likely to be building-occluded

**Severity: HIGH** (integrity of a perception gate; no-omniscience invariant).

`src/perception/naked_eye_source.py:1066` `_resolve_los_by_unit_name` joins the
`GET /line_of_sight/latest` snapshot onto this poll's world objects **by `unit_name`**:

```python
name = obj.get("unit_name")
object_id = obj.get("object_id")
if not isinstance(name, str) or not isinstance(object_id, int):
    continue                      # line 1118 — no live verdict, silently
if name_counts[name] > 1:
    continue                      # line 1120 — no live verdict, silently
```

`unit_name` is **not a total key over the candidate population.** aircraft-layer's own schema says so
explicitly (`aircraft-layer/src/schema/world_objects.py:37-46`): it is `LoGetWorldObjects`'s
`UnitName` passed through unconverted, and it is *"`None` when the object carries no `UnitName`
(scenery/statics may not)"*. For every such candidate, `isinstance(name, str)` is `False`, the join
drops it, `WorldObjectCandidate.live_los_clear` stays `None`, and
`src/perception/visibility.py:785-790`'s gate 4 falls through to world-model's offline, **building-blind**
`line_of_sight_clear` with its 12 m terrain tolerance — permanently, for the whole sortie, not as an
outage.

**Why this is the highest-value finding and not a coverage statistic:** the capability X-B29 was built
for is the 9,861 rows in `aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md` §1
where *terrain was clear and a building blocked the sightline*. Statics and scenery are what buildings
**are**, and they are concentrated close in. So the objects for which a building-aware verdict matters
most are drawn from the same pool as the objects that can never receive one. The sortie note's own
"second, odd detail" in §3 — rows **missing** a verdict have a *lower* median true range (3,820 m)
than rows **with** one (6,750 m), the opposite of what truncation would produce — is exactly what this
mechanism predicts, and it is the only explanation offered so far that predicts the sign correctly.
The note excluded truncation and excluded the producer; this is the remaining candidate and it is
deterministic rather than timing-dependent.

Second, narrower leg of the same defect: `name_counts[name] > 1` drops **both** members of any
duplicate-name pair. Unit names are mission-author-controlled text, and the author is not constrained
by anything body-layer can see.

**Exploit/failure scenario (no attacker needed):** fly low over a village. Every building and scenery
object in the bubble is nameless, gets no verdict, and is gated by the SRTM grid with 12 m slack. A
`5p73 s-125 ln` parked behind one of those buildings — the exact case §1 names — is admitted,
clustered, classified and called out, because the fallback primitive does not know the building
exists. The pilot is told about a launcher Petrovich could not see. That is an omniscience violation
produced by a silent input degradation, which is the pairing this project's invariant exists to
prevent.

**Fix:**
1. **Record the join key and the join outcome in the trace.** `perception/detection_trace.py`'s
   `DetectionTrace` carries `object_type` (line 116) but **not** `unit_name`, so the hypothesis above
   cannot currently be confirmed from an existing trace file. Add `unit_name: str | None` and a
   `los_join: Literal["live", "no_name", "duplicate_name", "not_in_wedge", "stale", "no_feed", "malformed"]`.
   Then a one-line reduction over the next sortie settles A1 as fact or refutes it.
2. **Make the join key total, or state that it cannot be.** If the Hook cannot produce verdicts for
   nameless objects at all (mission scripting keys on `getName()`), then this is a permanent
   structural limit and the honest response is not to silently use a weaker primitive — see A2.

---

### A2 — Nothing downstream of gate 4 can tell which LOS primitive admitted a contact; the fallback is silent by construction

**Severity: HIGH** (provenance integrity). Re-rated from the pre-flight deep analysis's low/low, with
the flight evidence: **77 % of 14,703 admissions (11,268 rows) ran on the fallback.**

The admission path emits a single fixed provenance string regardless of which primitive decided:

- `src/perception/naked_eye_source.py:348` — `PROVENANCE_VISIBILITY_FILTER_ONLY = "world_objects/visibility_filter_only"`
- line 976 — `provenance=PROVENANCE_VISIBILITY_FILTER_ONLY` on **every** emitted naked-eye
  `Observation`, live-verdict or fallback.
- `src/perception/visibility.py:785-790` — the two branches of gate 4 return the identical
  `VisibilityResult`; the structure has no field for which branch ran.
- `src/belief/percept.py:93` / `src/belief/contacts.py:465` — `live_los_clear: bool | None` does cross
  the boundary, and `None` *is* the in-principle signal "no live verdict". But its only consumer is
  the engagement gate (`contacts.py:1357-1377`), it never reaches `belief/tools.py`'s
  `{facts, summary, phrasing_hints}` triple, never reaches `belief_truth_log.py`, and is never
  counted anywhere.

So the only observable for a 77 %-of-admissions degradation is a 3.55 GB `--detection-trace` file
that must have been switched on beforehand and reduced by hand afterwards. "The system reported
success" is literally true: nothing in the pipeline had anything to report.

**The specific observable that fixes this** — deliberately not "add more trace fields":

- **A per-poll counter pair on the poll loop, logged at a fixed cadence and on change of state:**
  `los_live_admissions` / `los_fallback_admissions` for the poll, plus a running sortie ratio. Emit
  one `logger.warning` the first time the sortie's fallback share crosses a threshold (50 % is a
  defensible first value) and once more if it crosses back. That is a single line in
  `aircraft_layer_debug`-grade output that answers the question without a 3.5 GB file.
- **One `kind: "los_coverage"` row per poll in `belief_truth_log.py`**, which is already the
  "everything on one timeline" file by the user's own 2026-09-25 direction. Cost is ~2k rows per
  sortie against the trace's 1.64 M.
- **`Contact.los_provenance: Literal["live", "offline_fallback", "none"]`** carried alongside
  `live_los_clear`, surfaced in `describe_contact`'s facts. This is the one that makes the degradation
  visible *to the brain layer and to the pilot-facing surface* rather than only to a post-flight
  reader, and it is the version that honours "code owns truth": a belief that rests on a weaker
  primitive should know that about itself.

**Not a boundary violation to add.** `live_los_clear` already crosses the `Percept` boundary with a
written justification (`belief/percept.py`'s docstring: a fact about physical space, not an identity
or position claim). "Which instrument established that fact" is strictly less revealing than the fact
itself.

---

### A3 — The consumer poll loop is not running at any specified rate; it is running at its own 1.0 s default plus the work, and `BL-B30`'s premise is wrong

**Severity: HIGH** (availability and calibration integrity, and it invalidates a filed backlog item's
diagnosis).

`body-layer/BACKLOG.md:948-968` (`BL-B30`) and the sortie note §2 both state the poll loop is
*"specified at 5 Hz — 0.2 s — and is observed at roughly 0.7 Hz, about seven times slower."*
**There is no 5 Hz specification in body-layer.** The grep is unambiguous:

- `src/logger.py:999` — `_DEFAULT_POLL_INTERVAL_S = 1.0`
- `src/logger.py:1679-1684` — `--poll-interval-s`, `default=_DEFAULT_POLL_INTERVAL_S`, help text
  *"seconds between poll ticks"*
- `src/logger.py:1192` and `:1552` — `stop_event.wait(poll_interval_s)` is the **last** statement of
  the loop body, so the interval is a sleep *after* the work, not a period. Actual period = work +
  1.0 s.

5 Hz is **aircraft-layer's export rate** (`aircraft-layer/CLAUDE.md`: `Export.lua`'s
`EXPORT_INTERVAL_S = 0.2`), not body-layer's consumption rate. With a 1.0 s default and ~0.44 s of
work, the expected period is ~1.44 s — which is precisely the 1.44 s median gap measured in the
detection trace and the 1.43 s median in the belief log. The loop is behaving exactly as written.

This is a security finding and not merely a correctness nitpick for two reasons:

1. **Everything timing-shaped in `belief/` was tuned against a tick rate the loop does not have.**
   `src/belief/decay.py`'s half-lives and certainty ladder, `events.py`'s `EVENT_COOLDOWN_S`,
   `perception/motion.py:91`'s *"objects arrive at 5 Hz"* decision, `gaze.py`'s `FOCUS_DWELL_S = 2.0`
   (now **less than one** poll period plus work, against a 2 s dwell — the scan cone can step past a
   dwell between consecutive polls), and `position_belief.py:124`'s own note that recovery time
   *"scaled as roughly `1 / poll_interval_s`"*. A gate calibrated at one rate and run at a seventh of
   it is a gate whose behaviour nobody has characterised. This is the same class as the elapsed-time
   inflation already recorded in agent memory (`project_elapsed_time_inflation_quadratic_dt_composition`).
2. **It is the mechanism behind the LOS consumer skipping publishes** (§2/§3 of the sortie note): the
   producer publishes at a metronomic 1.00 s and the consumer polls at ~1.44 s, so publishes are
   skipped structurally, not sporadically.

**Fix:** decide the rate deliberately and make the code say it. Either set
`_DEFAULT_POLL_INTERVAL_S = 0.2` and measure what the loop then actually costs, or keep 1.0 and
re-derive every constant above against it. Separately, make the loop a **fixed-period** loop
(`stop_event.wait(max(0.0, period - elapsed))`) rather than a fixed-delay one, so the rate is the
thing configured rather than an emergent sum, and log one warning when `elapsed > period` (the loop
falling behind is currently invisible).

**Do not fix `BL-B30` by chasing the suspected causes it names** (the world-model fallback's SQLite
query, `BL-B26`'s triple-gather, the trace writer, network latency) until the 1.0 s default is
accounted for. Those cost ~0.44 s combined on this evidence; the default costs 1.0 s.

---

### A4 — Both LOS gates fail open, and the admission one fails open into a *more permissive* primitive

**Severity: MEDIUM-HIGH** (this is the direct answer to the "which way does the gate fail" question;
A1/A2 are its two concrete instances).

Asked plainly: **does any path admit a contact with no verdict at all?** Yes — 77 % of admissions,
and nothing marks them. Both gates degrade in the permissive direction:

| gate | site | behaviour with no live verdict | direction |
|---|---|---|---|
| admission (gate 4) | `perception/visibility.py:785-790` | falls through to `line_of_sight_clear` — **building-blind, 12 m terrain slack** | **fails open, and into a weaker instrument** |
| engagement / threat masking | `belief/contacts.py:1357-1366` | `los_ok = True`, `los_masked_since_sim = None` | fails open |

The engagement one is **correct and well-argued** — its own comment makes the case (*"a watch is a
standing instruction to keep looking, not a subscription to continuous truth"*), and the masking-reset
is load-bearing in exactly the way the 2026-09-24 process rule documents. Fail-open there means
Petrovich keeps warning about a threat whose sightline may be blocked: he over-warns, which is the
right side to err on, and it is not an omniscience violation because the warning is about something
he already saw.

The admission one is a different thing wearing the same word. Fail-open there means **admitting a
contact that was never perceived**, judged by a primitive that cannot see buildings. Nothing in
`visibility.py` records that the weaker instrument was used, so there is no way for a later stage to
discount the belief — and 19 % of polls had zero live coverage, 211 distinct runs of them, the longest
20.7 s.

**Fix:** A2's `los_provenance` is the minimum. The stronger option, worth putting to the user rather
than deciding here, is to make the admission gate **fail closed** for candidates that *should* have had
a live verdict (inside the queried wedge, feed healthy, skew fresh) and fail open only where a verdict
is structurally impossible (A1's nameless objects, feed absent). That distinction needs A1's
`los_join` field to exist first, which is why A1 is ordered before it.

**Risk matrix, user decision required** (this is the one item in the audit that is a judgement call
rather than a defect):

```
Finding:  the naked-eye admission gate falls open into a building-blind primitive on 77% of
          admissions, with no record that it did
Location: body-layer/src/perception/visibility.py:785-790
Probability: high — measured, 11,268 of 14,703 admissions in one 70-minute sortie
Impact:   medium — Petrovich reports contacts he could not see, including SAM launchers behind
          buildings; it is the no-omniscience invariant, not a crash or a data breach
Recommended action: A2's observable now (cheap, unblocks everything else), A1's join fix next,
          then decide fail-open-vs-fail-closed with the join data in hand

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — observable first, then the join
  (D) Stop — do not proceed until resolved
```

---

### A5 — Unbounded, unrotated, cross-sortie-appending trace files

**Severity: MEDIUM** (availability mid-flight; integrity of the artifact).

Three writers, all `open("a")`, no size cap, no rotation, no per-sortie file:

- `src/detection_trace_writer.py:64` — `self._file = path.open("a", encoding="utf-8")`
- `src/belief_truth_log.py:261` — same
- `src/speech_log.py:55` — same, reopened per row

Measured: **3.55 GB in one 70-minute flight**, ~50 MB/min, and because it appends, the analyst of the
2026-10-05 sortie had to locate the new-schema region *by byte offset 2,448,471,603* — the head of the
file was a previous sortie. Two harms:

1. **Disk fill during a sortie.** At ~50 MB/min a long flight on a modest free-space margin fills the
   partition DCS is also writing to. When it does, the write raises `OSError` inside the poll loop and
   is swallowed by `logger.py:1541`'s broad `except Exception` → one `logger.exception` per poll, the
   trace silently stops being written, `connection.report_success()` is skipped, and the gaze push at
   the end of the cycle is skipped too. Nothing in the cockpit says anything.
2. **The artifact is not analysable without archaeology**, which directly raises the cost of every
   future investigation — including A1's and A2's.

**Fix:** stamp the path (`<path>.<utc-timestamp>.jsonl`) so each run gets its own file; refuse to
start if free space is below a floor (a `parser.error`, consistent with this subproject's existing
startup-error posture for `--theatre`/`--world-model-db`); and cap the file, closing the writer with
one explicit warning line when the cap is hit rather than discovering it as a disk-full exception. A
trace that stops with "trace cap reached, continuing without trace" is strictly better than one that
stops silently.

---

## B. Fix when the project goes public (or gains a second machine's worth of trust)

### B1 — The wire boundary type-checks but does not domain-check, and `slots["clock"]` can `KeyError` the poll cycle

**Severity: LOW** now, MEDIUM once anything untrusted can reach the LAN port.
**This is the second instance of a class already in agent memory** —
`project_wire_boundary_type_check_not_range_check` recorded it for `logger.py`'s transcript fields on
2026-09-25. Same shape, different field. Citing rather than re-filing.

`src/logger.py:1322-1349` validates every transcript field's **type** rigorously (including the
`isinstance(x, bool)` exclusions, which is the right level of care) and then passes `slots` through
untouched. On the consuming side, seven call sites index a **nine-key** dict with it:

- `src/belief/crew_console.py:518, 521, 530, 1121, 1368, 1572, 1693` — `_CLOCK_REPORT_LABELS[clock]`
- `_CLOCK_REPORT_LABELS` (`crew_console.py:395-405`) holds `{1,2,3,4,8,9,10,11,12}` — **5, 6 and 7 are
  deliberately absent**, the rear hours Petrovich cannot see.
- `crew_console.py:1405-1409` type-checks: `if not isinstance(clock, int): clock = None`. Nothing
  range-checks.

A peer sending `slots = {"clock": 6}` raises `KeyError: 6`. The dispatch is **outside**
`_poll_transcripts`'s own `try` (line 1317-1321 wraps only `get_transcripts`), so it escapes to the
poll loop's broad handler: one lost poll, logged, recovered next cycle. The transcript is already
drained so it does not repeat.

The correct peer cannot produce it — `audio-adapter/src/vocabulary.py:707` `parse_clock` restricts to
`FORWARD_CLOCK_POSITIONS = (8,9,10,11,12,1,2,3,4)` (line 79), the same nine. So this is reachable only
from a divergent, buggy, or hostile peer. What makes it worth recording is the *documented* trust
delegation: `crew_console.py:453-464`'s `_nearest_sector` docstring says outright that *"`degrees` is
assumed already a legal, 5-degree-multiple bearing (`audio_adapter.vocabulary.parse_bearing`'s own
checksum already rejected anything else upstream of this call)"* — a value-domain invariant that lives
in another process, reached over unauthenticated LAN JSON, with module independence forbidding the
import that would let one side check the other.

`bearing_degrees` is safe regardless (`_nearest_sector` is a `min()` over eight sectors, any int maps
somewhere) and `range_km` only reaches an f-string. `clock` is the only one that faults.

**Fix:** one guard at the seam —
`if clock is not None and clock not in _CLOCK_REPORT_LABELS: clock = None` — in `_handle_follow` and
in the confirm-describer, degrading to the existing "say again" path. Four lines, and it converts a
cross-process assumption into a local one.

### B2 — The speech log is a verbatim transcript of everything the microphone recognised, including speech never addressed to Petrovich

**Severity: LOW** now (single user, local disk), MEDIUM on publication.

`src/speech_log.py:55` writes one JSON row per recognised transcript, matched **and** unmatched —
which is the whole point of the file and is correct (its docstring makes the case: a fall-through was
previously unobservable, and a false fire is only findable by seeing what he acted on). The
consequence is that it is a log of household audio. The 2026-10-05 sortie's own rows include
`"Peace."`, `"All right."`, `"See you again."`, `"Can I sell it?"` and `"Yes."` — none of them
addressed to the aircraft.

This project is intended to go public open-source (recorded in auto-memory,
`project_public_open_source_intent`). The moment a user is asked to attach a speech log to a GitHub
issue, they are publishing unredacted transcripts of their room. No document currently asks them to —
a grep of `body-layer/RUN.md` and `body-layer/docs/` finds no log-sharing guidance at all — which
means the guidance will be written later, probably in a hurry, by someone debugging.

**Fix (cheap, do it before the repo is public, not after):** one paragraph in `RUN.md` stating what
each log contains and which are safe to share, and a `--speech-log-redact` mode that writes the seven
recognition fields and the disposition but replaces `transcript` with its length and token when the
disposition is `fallthrough`. That keeps every debugging use case named in `speech_log.py`'s docstring
(a fall-through is still visible as a fall-through) while dropping the content that is nobody's
business.

### B3 — Unbounded `response.read()` on every peer response

**Severity: LOW.** `src/aircraft_client.py:241, 260`, `src/belief/brain_client.py:253, 316`,
`src/belief/audio_client.py:71, 95, 112` all do a bare `response.read()` with no size limit. A
malfunctioning or hostile peer returns a multi-gigabyte body and the poll thread allocates it. The
`world_objects` poll runs every cycle, so this is the hot one.

Same class as the audio-adapter finding already in memory
(`project_audio_adapter_full_audit_2026_09_26`: no request-size cap, unguarded `Content-Length`) —
that was the server side, this is the client side, and the project now has it symmetric.

**Fix:** `response.read(MAX_RESPONSE_BYTES)` with a per-endpoint ceiling, raising the module's own
error type on a short read that is actually a truncation. One constant, three files.

### B4 — `assert` as a runtime guard in library code

**Severity: LOW.** `python -O` strips assertions, and nothing in this repo runs with `-O` today — so
this is a latent trap rather than a live one, and it is worth one line of record because the failure
would be silent rather than loud.

- `src/belief/tools.py:347, 397, 421, 515` — asserts on the *shape* of the brain-facing
  `{facts, summary, phrasing_hints}` payload. Under `-O` a shape drift stops raising and starts
  producing wrong facts.
- `src/belief/enrichment.py:490` — `assert terrain_info is not None` after a world-model query. Under
  `-O`, an unexpected `None` becomes an `AttributeError` somewhere further down instead.
- `src/belief/decay.py:174, 188` — module-level consistency asserts between constants. These are the
  *good* use: they fire at import, they document a relationship between calibration values, and
  losing them under `-O` costs nothing at runtime. No change wanted here.

**Fix:** convert the `tools.py` and `enrichment.py` ones to explicit raises. Leave `decay.py` alone.

### B5 — Untrusted display text reaches the terminal unescaped

**Severity: LOW, and thinner than it first looks.** `Observation.classification_raw` on the hybrid
channel is Petrovich's `list_indication` text, passed through unmodified
(`src/perception/hybrid_source.py:263`) into `Contact.last_class_raw` and from there into printed
lines and TTS. No sanitisation anywhere on that path.

The three sinks, and the honest read on each:

- **Terminal** (`crew_console.py:2308` `print(line, file=self.output)`) — ANSI escape sequences in DCS
  indication text would be interpreted by the user's terminal. Thin, because the controllable surface
  is thin: the indication strings are DCS-rendered UI class labels, not author-supplied names.
- **DCS overlay** (`aircraft_client.push_text_line` → `POST /text/push`) — **not** an injection
  surface, and worth stating positively since the cross-seam `net.dostring_in` bridge exists:
  `aircraft-layer/src/collector/text_sender.py:94` JSON-encodes and truncates
  (`json.dumps({"text": truncated})`). No string splicing into Lua. Consistent with
  `project_aircraft_layer_full_audit_2026_09_26` (all `dostring_in` call sites take fixed literals)
  and `project_dostring_in_numeric_splice_naN_clamp_gap` (X-B29 splices `%d` only).
- **TTS** (`audio_client.push_speech`) — `json.dumps`, safe.

**Fix:** strip C0/C1 control characters in `CrewConsole._print` before any sink. One line, closes the
category rather than the instance.

---

## C. Confirmed clean — checked, and specifically not a finding

Stated with the evidence, because a finding list that never clears anything stops being read.

- **No inbound network surface.** No `HTTPServer`, `socket`, `bind` or `listen` in `body-layer/src`.
  The "unauthenticated LAN JSON both ways" risk in the brief is real but lives in the *peers*
  (aircraft-layer, audio-adapter, brain-layer); on this side there is nothing to authenticate.
- **The no-omniscience boundary holds structurally.** `belief/percept.py`'s `percept_of` is the only
  reader of `Observation.derived_world_position`, and a grep of `src/belief/` for ground-truth fields
  finds no other crossing. The one sanctioned exception (`detection_trace_writer.py`) is read-only
  against `ContactStore` and passes nothing back. Two near-misses that are **not** violations:
  `enrichment.py:670`'s `true_bearing_deg` and `optic_policy.py:956`'s `true_bearing` both mean
  *true-north* bearing, not ground truth, and both are computed from `Contact.last_position` —
  a believed position. The naming is a trap for a future reader; the code is correct.
- **No prompt-injection path from speech or mission text to behaviour or voice.** This is the most
  load-bearing clear in the audit. `brain_client._reply_from_dict` (`brain_client.py:147-181`) is a
  structural parse that rejects anything whose `kind` is not one of four literals and anything whose
  string fields are not strings. `brain_reply.validate_brain_reply` then enforces D10: a `PICK` id
  must be one *this payload offered*, a `BECAUSE` clause must appear literally in the transcript **and**
  in the chosen candidate's `why` and **not** in any other's, a `CONFIRM` token must be in **both**
  `OFFERED_CONFIRM_VOCABULARY` (7 tokens) and `dispatched_command_tokens`, an `UNABLE` reason must be
  one of three. Everything else degrades to `ASK`/`UNABLE NO_MATCH`, never silence and never a guess.
  **No free model text is ever spoken or printed.** The worst a fully-compromised brain-layer can do
  is pick a wrong candidate from a list body-layer itself assembled, or fire one of seven no-slot
  tokens. That is a closed-vocabulary seam, correctly built, and it is the reason the obvious
  "recognised speech reaches a model that drives behaviour" risk does not land here.
  (The CONFIRM-vocabulary asymmetry recorded in `project_br1_stage2_ollama_trust_boundary` on
  2026-09-25 is closed — `brain_reply.py:184-192` now checks both sets.)
- **Degenerate-geometry guards are present and deliberate**, which is unusual and worth saying.
  `perception/motion.py:150-152` and `:179-192` both guard `range_m <= 0.0` before dividing, and the
  second returns `moving=None` with an explicit *"no honest verdict either way"* comment rather than a
  fabricated `False`. `clustering.py:207-218` returns `math.inf` for non-positive range with the
  conservative-merge reasoning written down. `estimation.py:91-93` maps the Box-Muller uniform onto
  `(0, 1]` *specifically* to keep `math.log` off zero, with the reason in a comment. `position_belief.py`
  wraps every `sqrt` in `max(0.0, …)`. I went looking for an unguarded divide-by-external-data and did
  not find one. The single unguarded division is `optic_policy.py:960`'s `height_delta / slant_m`,
  reachable only if a believed position coincides exactly with ownship in all three axes — not a
  realistic float outcome, and the cost would be one lost poll.
- **The LOS join's own field validation is thorough.** `_resolve_los_by_unit_name`
  (`naked_eye_source.py:1066-1135`) `isinstance`-checks `dcs_model_time_s`, `verdicts`-is-a-dict, each
  verdict-is-a-dict, and both `building_clear`/`terrain_clear`-are-`bool`, and drops to unresolved on
  any failure. A malformed feed cannot inject a verdict. It can only *suppress* verdicts — which is
  A1/A2's problem, not a validation gap.
- **No secrets, no credentials, no API keys, no `getenv`.** Grep for
  `password|secret|api_key|credential|bearer` over `src/` returns one false positive (a comment
  containing "token"). Consistent with the project's phase; flag immediately if a GIS/tile provider
  key ever appears.
- **No `eval`, `exec`, `pickle`, `yaml.load`, `subprocess`, `os.system`, or `__import__`** anywhere in
  `src/`. The only `shutil` use is `get_terminal_size` (`logger.py:944`). No deserialization surface
  beyond `json.loads` on peer responses.
- **No path traversal surface.** Every file path is a CLI argument the local user supplied
  (`--detection-trace`, `--speech-log`, `--world-model-db`) or a repo-relative data file
  (`belief/threat.py:86`, `perception/reporting_names.py:61`). No path is ever constructed from feed
  data. This is **unlike** the finding recorded for world-model on 2026-10-05
  (`project_mission_theatre_field_unsanitized_into_path_and_sqlite_uri`) — body-layer's `--theatre` is
  a startup argument validated against the store, not a path component built from a mission field.
- **Error suppression is deliberate, argued, and mostly logged.** The five broad handlers
  (`logger.py:1187`, `:1541`, `crew_console.py:906`, `:2010`, `:2313`) each carry a written
  justification, and the strongest one is right: `logger.py:1439-1446` explains that this runs on a
  daemon thread, so an escaping exception *"kills the thread without killing the process: the REPL
  keeps accepting input, the overlay keeps its last frame, and perception, belief and speech are
  simply dead from that moment on."* That is the correct trade and it is the fix for the exact
  unsupervised-daemon-thread gap recorded in `project_aircraft_layer_full_audit_2026_09_26`. Four of
  the five log with `exc_info`. The one that does not is `crew_console.py:2010`
  (`_log_transcript`'s `except Exception: return`), where an ENOSPC on the speech log is fully
  invisible — worth one `logger.warning`, not worth its own finding.
- **Bounded growth was re-checked and is still as accepted.** `ContactStore._contacts` has no delete
  path by design (a `lost` contact is memory Petrovich should keep) and `_observation_id_to_contact_id`
  is never pruned, both argued at `contacts.py:658-663` and `:1053-1066`, and the O(n²) clustering
  consumer is filtered rather than the store pruned (`BL-B23`). Consistent with
  `project_body_layer_bounded_growth_accepted_pattern` and
  `project_bl_b23_contact_store_pruning_security_approved`. Not re-flagged.

---

## D. One performance observation that belongs to A3

Not a security finding, but it is a measurable, sortie-length-dependent cost on the loop A3 is about,
and whoever instruments that loop should know where to look first.

`src/belief/enrichment.py:538-549` `_recent_percepts` does two avoidable things per call:

```python
observations = store.observations          # full dict COPY of the append-only log
for observation_id in reversed(contact.contributing_observation_ids):
    ...                                    # walks ALL of them, every time
```

`ContactStore.observations` (`contacts.py:680-683`) returns `dict(self._observations)` — a complete
copy of a log that grows monotonically all sortie. `_recent_percepts` is shared by
`_terrain_aware_world_position` (which wants **only the latest**) and `motion_when_seen` (which wants
**the two most recent distinct positions**, `enrichment.py:744-752`), and neither needs more than a
handful. Cost per call is O(total observations ever + this contact's observation count); both grow with
sortie length, which is the signature `BL-B30` describes (*"longer sorties make it worse"*).

Fix is small and local: add a `ContactStore.observation(observation_id) -> Observation | None` lookup
so no copy is made, and break out of the id walk once the caller's need is met. `position_belief.py:102`
already establishes that callers hold values, not live references into the store, so no boundary
changes.

---

## Verdict

**NEEDS FIXES.** A1–A3 are fix-now; A4 carries the one user decision; A5 is fix-now and cheap.

Nothing here is an exploitable vulnerability in the usual sense, and under this threat model nothing
could be — body-layer has no listener, no secrets, no deserialization, no shell, no path construction
from feed data, and a genuinely well-built closed-vocabulary seam to the model. What it has instead is
the failure this project cares about more: **a perception gate that degrades into a weaker instrument
on three quarters of its admissions and says nothing**, and a poll loop running at a rate nobody chose
while a backlog item attributes the shortfall to the wrong cause.

Fix A2 first even though A1 is the deeper defect. A2 is a counter and a log line; it makes A1
measurable, it makes A3's effect visible, and it is the observable whose absence is the reason a 77 %
degradation had to be discovered by reducing a 3.55 GB file after the fact.
