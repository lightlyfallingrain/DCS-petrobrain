### Goal

Make every recognised voice token that is not a routing token actually do something — the 20
`report_*` / `*_bearing_deg` tokens that currently fall through `CrewConsole.handle_f10_command`'s
defensive `else` and fail silently — and retire the "F10 command" framing from the layer that will
outlive the menu.

---

### What was measured, not assumed

Read before planning, and load-bearing for what follows:

- **`audio-adapter/src/vocabulary.py`**: 41 tokens (`LEGACY_F10_TOKENS` 17 + `VOICE_ONLY_TOKENS` 22
  + `ROUTING_TOKENS` 2). `handle_f10_command` dispatches 18; `wake_petrovich`/`cancel_nevermind`/
  `say_again` are handled above it. 20 reach body-layer and return `[]`.
- **`MatchResult.bearing_degrees` exists and is thrown away at the wire.**
  `audio-adapter/src/command_matcher.py` parses the numeric bearing correctly, but
  `transcript_queue.TranscriptEvent` carries seven fields and `bearing_degrees` is not one of them
  (`server.py:227`). So even a perfectly recognised "scan bearing three two zero" arrives at
  body-layer as a bare token with no number. This is the single largest piece of missing wiring.
- **`AttentionArea` already supports an arbitrary absolute wedge** (`wedge_deg: (center,
  half_width)`), so arbitrary-bearing areas were never blocked. Per the user's 2026-09-23 direction
  we are deliberately **not** using that capacity here — see Decision 3.
- **The eight compass scan tokens already do not steer gaze.** `logger._active_gaze` only honours
  `task.area.relative_sector`; a compass scan sets `area.sector`, so `_active_gaze` falls through to
  `FREE_SCAN_PLAN`. "Scan north" registers an attention area and speaks a readback, and Petrovich
  keeps free-scanning. That is pre-existing, is **not** fixed by this milestone, and is called out
  as a risk and a follow-on.
- **Contacts are never pruned.** `certainty_of` reaches `"lost"` past `LOST_THRESHOLD_S` (120 s,
  `belief/decay.py`) but the contact stays in `store.contacts` forever. A naive `report` would read
  out everything ever seen. Decay constants checked before designing: `OBSERVED_WINDOW_S` (16 s, =
  `SCAN_CYCLE_PERIOD_S`), `POSITION_HALF_LIFE_S` (30), `LOST_THRESHOLD_S` (120),
  `IDENTITY_HALF_LIFE_S` (600), `EVENT_COOLDOWN_S` (15), `CALLOUT_MAX_AGE_S` (10).
- **Command readbacks do not budget speech occupancy.** `CalloutScheduler.busy_until_sim` is set by
  `drain_events` and by `note_urgent`, never by an ordinary `_print`. A readback already queues
  behind, and is immediately queued-behind-by, routine callouts. Reports make this much worse
  because a report is long.

---

### Affected Modules / Files

**body-layer (the layer that survives the menu)**

- `body-layer/src/belief/crew_console.py` — rename `handle_f10_command` → `handle_command` and
  `_F10_SCAN_REASON` → `_SCAN_COMMAND_REASON`; add the three report families and their dispatch
  table entries; add bearing quantisation; carry `bearing_degrees` through confirm; declare
  `DISPATCHED_COMMAND_TOKENS`.
- `body-layer/src/belief/speech.py` — `render_report`/`render_clear`/`render_no_view` templates.
  Reuses `_contact_report_text` and `render_group_report`; **no second rendering path.**
- `body-layer/src/belief/callouts.py` — extract the facts-level grouping out of
  `group_candidates` so the report path and the callout path share it; add
  `CalloutScheduler.note_reply`.
- `body-layer/src/belief/voice_commands.py` — `PendingConfirmation` gains `bearing_degrees`
  (without it, a confirmed bearing command loses its number).
- `body-layer/src/logger.py` — `_poll_f10_commands`/`_poll_transcripts` call `handle_command` and
  thread `bearing_degrees`. **Do not touch the optic wiring in this file** (sibling agent owns it on
  `feature/binocular-optic`); the edits here are in `_poll_*` and the argparse help text only.
- `body-layer/tests/test_crew_console.py`, `test_callouts.py`, `test_speech.py`, `test_logger.py`.

**audio-adapter (wire addition only, no new tokens)**

- `audio-adapter/src/transcript_queue.py` — `TranscriptEvent` gains an eighth field,
  `bearing_degrees: int | None`, and its `to_dict` key.
- `audio-adapter/src/server.py` — pass `match.bearing_degrees` into the event.
- `audio-adapter/src/vocabulary.py` — **docstring only.** Add the note that the acted-on value is
  quantised onto the sector vocabulary and that the 5° slot is a recognition checksum, not
  precision, so a later reader does not "restore" precision that was never wanted. No token changes.
- `audio-adapter/tests/test_transcript_queue.py`, `test_server.py`.

**Unchanged, deliberately**

- `body-layer/src/belief/attention.py` — already holds everything needed. Read, not edited.
- `aircraft-layer/*` — `F10CommandQueue`/`F10CommandEvent`/`ALLOWED_COMMANDS`/`F10CommandReceiver`/
  `GET /f10_commands/poll`/`--f10-host`/`--f10-port`/`petrobrain-f10-commands-hook.lua`. See
  Decision 4.
- `body-layer/src/aircraft_client.py`'s `get_f10_commands` — it names a real F10 endpoint. Keep.

**Prose**

- `body-layer/CLAUDE.md`, `docs/concept/STATE_TRANSITIONS.md` — describe the surface as *commands*,
  noting F10 as one (legacy) transport among voice.
- `body-layer/ROADMAP.md` — new milestone row + the follow-ons this plan defers.
- `todo/todo.md` — the two deferred items named in Decisions 3 and 5.

---

### Decision 1 — Report semantics: reply from belief, never a look

`report` is a **read of current belief and nothing else** (user, 2026-09-23: *"report is always
about current belief. Scan tells to go look."*). No `AttentionArea`, no `PendingIntent`, no gaze
change, no `aircraft_client` call. It is the first command in this codebase that is purely a query,
and that is the property to protect: a reader later tempted to "make report also look" is breaking
the user's own distinction.

**Source of facts.** `belief.tools.get_contacts(store, now_sim, enrichment=self.enrichment)`, then:

1. drop `facts["certainty"] == "lost"` — contacts are never pruned, so without this the report grows
   monotonically over a sortie. `"estimated"` stays: a remembered contact is still belief, and
   dropping it would make Petrovich forget things he has not given up on.
2. drop contacts with no `relative_now` (no enrichment ⇒ no direction or range to report). With
   `self.enrichment is None` the whole family answers `"no world-model connection configured"`, the
   same graceful-degradation line `_handle_scan` already uses.
3. apply the family filter (Decision 1a).
4. group and render (Decision 1b).

**1a — the three filters**, all read `facts["relative_now"]`, which already carries both
`clock_position` (ownship-relative hour) and `bearing_deg` (true):

| family | filter |
|---|---|
| `report_all` | none |
| `report_clock_<p>` | `relative_now["clock_position"] == p` |
| `report_bearing_<compass>` | `angular_delta_deg(relative_now["bearing_deg"], _SECTOR_CENTER_DEG[sector]) <= 45` — the same 90° wedge `AttentionArea.sector` means, so "report north" and "scan north" name the same patch of sky |
| `report_bearing_deg` | quantised to the nearest compass sector, then exactly the row above (Decision 3) |

The clock filter is an exact hour match, not a tolerance: `_clock_position` already quantises 30°
buckets, and adding a second tolerance on top of a quantisation produces overlap the speaker did not
ask for.

**1b — rendering reuses the callout path, it does not fork it.** `belief.callouts.group_candidates`
today takes `Event`s, looks up facts, buckets by `(unit word, range word)` and chains by clock. The
grouping decision is entirely facts-level; only the event lookup is not. So:

- extract `group_facts(facts_list) -> list[list[dict]]` in `callouts.py` holding the bucket+chain
  logic verbatim;
- `group_candidates` becomes the thin event→facts→`group_facts`→events wrapper it already
  essentially is.

This is the one new abstraction in the plan, and it removes a real duplication (the alternative is a
second bucketing rule for reports that would drift from the callout rule and make the same two
contacts read as one group in a callout and two in a report).

Then, per group: `len == 1` → `speech._contact_report_text(facts)` (byte-identical to today's
single-contact wording, semantic fragment included); `len > 1` → `speech.render_group_report`.

**Group ordering and the cap.** Order by a facts-only sibling of `callout_priority` —
`(threat_band, -attention_rank, range_m)`, dropping the `-event.t_sim` term which has no meaning for
a query. Render **at most `REPORT_MAX_GROUPS = 3`** groups, joined into **one** utterance, with a
trailing `" And more."` when truncated.

One utterance, not one line per group, is the whole point: `plans/callout-scheduling/` removed the
backlog by never having more than one thing in flight, and a report that pushes six lines through
`_print` in a loop re-introduces exactly that — a queue of pre-rendered text going stale while it
waits. Three groups is the cap because a crew member answering "report" gives the near, the
important, and one more; the constant is isolated and trivially retunable after a sortie.

---

### Decision 2 — "Clear", and the one case where "clear" would be a lie

The empty answer is **"Clear."** (user, 2026-09-23), with the direction named for a directional
report:

| case | spoken |
|---|---|
| `report_all`, nothing to report | `Clear.` |
| `report_clock_3`, nothing there | `Three o'clock, clear.` |
| `report_bearing_n` (or a quantised numeric), nothing there | `North, clear.` |

**The carve-out: a direction he cannot see is not clear.** `perception.cockpit_mask`'s Mi-24P mask
has `rear_cutoff_deg = 130.0` — beyond 130° off the nose nothing is visible at all. The clock family
is safe by construction (`FORWARD_CLOCK_POSITIONS` is 8–4, i.e. ±120°, and `vocabulary.py`'s own
note says the omitted hours were omitted for exactly this reason). The compass and numeric families
are **not** safe: with the nose south, "report north" asks about the rear hemisphere, and answering
"North, clear" claims a look that is physically impossible. That is the no-omniscience invariant
inverted — omniscience's mirror image, asserting absence from nothing.

So: compute the requested direction's **relative** bearing against ownship heading; if
`>= rear_cutoff_deg`, answer `Can't see north.` rather than `North, clear.` A contact that *is*
believed to sit there is still reported normally — belief survives the aircraft turning away; only
the *absence* claim is withheld.

`belief` importing `perception.cockpit_mask` is direction-legal (belief already imports
`perception.geometry`/`perception.gaze`). Read `rear_cutoff_deg` off the existing mask object; do
not restate `130.0`.

**Replies claim occupancy; they do not preempt.** Add:

```python
def note_reply(self, now_sim: float, text: str) -> None:
    self.busy_until_sim = max(
        self.busy_until_sim,
        now_sim + estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S,
    )
```

and call it from `CrewConsole._print` on the non-urgent path (the urgent path keeps `note_urgent`,
which *resets* rather than extends, because `AudioPlaybackSender.interrupt` really has destroyed
what was in flight).

Why extend rather than preempt: a report is an answer, not an alarm. Clobbering an in-flight
contact callout to start answering "report" throws away a detection the pilot has not heard yet, to
save two seconds. `max()` also means a reply issued while a callout is still playing does not
shorten that callout's budget.

This additionally fixes the latent defect noted above — **every** command readback has been
unbudgeted since readbacks existed, so routine callouts have been queuing immediately behind them.
Fixing it here is in scope because reports are what make it audible.

Per the poll-loop order (`drain_events` → `_poll_f10_commands` → `_poll_transcripts`), a callout
chosen in the same poll as a report still goes first. That is one callout of latency, bounded and
acceptable; making replies jump the queue would need reordering the loop and is not worth it.

---

### Decision 3 — `scan_bearing_deg` / `report_bearing_deg`: quantise to the nearest **compass sector**

Per the user's 2026-09-23 direction (*"o'clock direction is enough, no need for x degrees
granularity now"*), the acted-on value is quantised. Of the two candidates offered, **compass point,
not o'clock** — on frame grounds, and the reasoning is not a preference:

- A spoken bearing is **absolute** ("scan bearing 320" means 320 true, and must not swing when the
  nose swings). O'clock is **ownship-relative**. Quantising an absolute bearing onto an
  ownship-relative bucket would freeze a heading-dependent answer at command time and then be wrong
  the moment the aircraft turns — or, if carried as `relative_sector`, would follow the nose, which
  is the opposite of what the pilot said.
- `AttentionArea.sector` is already the absolute vocabulary, already exercised by
  `scan_bearing_n..nw` and `report_bearing_n..nw`.

So the numeric tokens **reduce to tokens that already work**:
`scan_bearing_deg(320)` ≡ `scan_bearing_nw`, `report_bearing_deg(005)` ≡ `report_bearing_n`. One
`_nearest_sector(degrees) -> Sector` helper (22.5° half-buckets), no new geometry, no
`AttentionArea` change, no `wedge_deg` use. This is the cheapest correct answer available and it is
cheap precisely because the frame matches.

**The 5° slot stays, and it is not precision.** `vocabulary.py`'s `parse_bearing` constrains
bearings to multiples of five so that roughly four in five mishearings land on an illegal value and
come back as a *detected* error rather than a confident wrong heading. Quantising the acted-on value
afterwards does not weaken that one bit — the checksum runs at recognition time, the quantisation at
act time, and they are independent. Say this in `vocabulary.py`'s own docstring so nobody later
"restores" a precision that was never wanted.

**The readback names the sector, not the number** — `"Scanning northwest."` for "scan bearing 317",
not `"Scanning bearing 317."` Agreed with the user's instinct and worth stating why: the readback's
job is to expose a misunderstanding, and a readback that repeats the spoken number while acting on
something coarser hides the only discrepancy worth hearing. The cost is that a genuine mis-recognition
inside the same 45° bucket ("320" heard as "330") now reads back identically — but that was already
true of the acted-on behaviour, and the readback was never going to catch it once the bucket is the
unit of action.

**Wire work this requires** (the real cost of these two tokens, and why they get their own stage):

1. `TranscriptEvent` + `to_dict` gain `bearing_degrees: int | None`; `server.py` populates it from
   `match.bearing_degrees`.
2. `logger._poll_transcripts` reads the key and passes it on.
3. `CrewConsole.handle_transcript` and `handle_command` gain `bearing_degrees: int | None = None`.
4. `PendingConfirmation` gains `bearing_degrees` — **without this, a bearing command that lands in
   the confirm band loses its number on "affirm"** and would act on a token with no heading.
5. `_describe_token_for_confirm` must say the quantised sector for the confirm prompt
   (`"scan northwest, confirm?"`), for the same reason the readback does.
6. `!voice` harness gains an optional trailing degrees argument.

---

### Decision 4 — the rename: rename the concept, not the transport

Scoped honestly, three tiers:

**Cheap — body-layer internals, no wire, no deploy. Do now.**
`handle_f10_command` → `handle_command`; `_F10_SCAN_REASON` → `_SCAN_COMMAND_REASON` (a
`PendingIntent.reason` string, read by nothing but logs/traces); the `--f10-commands` argparse
*help text*; every docstring in `crew_console.py`/`logger.py` that calls these "F10 commands".
`handle_command` is the right name because it is already the shared dispatcher for three input
surfaces (F10, voice, and the confirm band), and the F10 one is the one being retired.

**Wire/deploy cost — aircraft-layer. Do not do now.**
`F10CommandQueue`, `F10CommandEvent`, `F10CommandReceiver`, `ALLOWED_COMMANDS`,
`GET /f10_commands/poll`, `--f10-host`/`--f10-port`, and `petrobrain-f10-commands-hook.lua`'s UDP
vocabulary. Renaming the endpoint means a coordinated redeploy of the collector (Windows) and the
logger (Mac) plus a Hook-script copy, with a stale-copy failure mode that looks like "commands
stopped working" — the exact class of failure the sortie cards keep warning about. And these names
are *accurate*: they describe the F10 radio-menu transport specifically, which is real and still
running. The user said the menu may go stale; churning the name of code scheduled for deletion buys
nothing. **Leave them, and delete them wholesale when the menu goes.**

**Prose — cheap, do now.** `body-layer/CLAUDE.md`, `docs/concept/STATE_TRANSITIONS.md`,
`body-layer/ROADMAP.md`. Frame the surface as *commands* with F10 as one legacy transport. Leave
`plans/f10-crew-commands/` and `plans/f10-command-vocabulary/` alone — they are dated decision logs,
and rewriting history to match current naming is how a decision log stops being one.

`body-layer/src/aircraft_client.py`'s `get_f10_commands` stays: it names a real F10 endpoint.

---

### Decision 5 — `scan <clock>`: recommended, but **not this milestone**

The user is right that o'clock granularity closes the report/scan asymmetry naturally. Deferring it
anyway, for three reasons:

1. **It is new vocabulary, and therefore unbenched** — nine tokens with no recordings, the same cost
   that kept `cancel_scan`/`cancel_watch` off voice until 2026-09-23. Cheapest when the corpus is
   next re-recorded, not now.
2. **This milestone's whole point is the opposite direction** — making already-recognised tokens
   stop being no-ops. Adding tokens mid-flight dilutes the one thing the user will check.
3. **It is the only genuinely new geometry in the picture.** A single o'clock hour is not
   expressible as a `RelativeSector` today: `perception.gaze._SECTOR_LEGS` maps
   `ahead→(12,)`, `left→(11,10,9)`, `right→(1,2,3)`, `full→8 legs`, and `ScanPlan.commanded_sector`
   is typed `RelativeSector | None`. The clean generalisation is to let `ScanPlan` carry legs
   directly (an o'clock command is a one-leg plan, exactly like `ahead` already is) rather than
   widening the `RelativeSector` literal and rippling through
   `_RELATIVE_SECTOR_WEDGE_DEG`/`belief.attention`'s re-export/the label tables.

That same generalisation is what would also fix the measured gap that compass scans never reach
gaze — `_active_gaze` could convert an absolute `area.sector` into relative o'clock legs per tick
using current heading. Do both together as one follow-on milestone; separately they are two partial
fixes to the same seam. Backlog both in `todo/todo.md`.

---

### Implementation Plan

**Stage 1 — rename and dispatcher plumbing. No behaviour change.**
`handle_f10_command` → `handle_command`; `_F10_SCAN_REASON` → `_SCAN_COMMAND_REASON`; update
`logger._poll_f10_commands`/`_act_on_voice_decision`/`handle_transcript` call sites, docstrings, and
the flag's help text. Replace the silent `else: return []` with a `logger.warning` naming the token
— the failure mode the user hit was silence, and even after this milestone an unknown token should
say so somewhere. Declare `DISPATCHED_COMMAND_TOKENS: frozenset[str]` in `crew_console.py` (the
canonical "what has behaviour" set) with a test asserting `handle_command` returns a non-empty
result — or a deliberate documented no-op — for every member. Tests stay green throughout.

**Stage 2 — the report families. This is the stage the user notices first.**
`group_facts` extraction in `callouts.py`; `note_reply` + the `_print` call; `speech.render_report`/
`render_clear`/`render_no_view`; `_handle_report(filter)` in `crew_console.py`; dispatch entries for
`report_all`, the nine `report_clock_*`, and the eight `report_bearing_<compass>`. Flyable on its
own: 18 of the 20 dead tokens come alive here, and the F10 menu is untouched.

**Stage 3 — the numeric bearing slot.**
The six wire/plumbing items in Decision 3, plus `_nearest_sector`, plus the two numeric tokens'
dispatch. Requires an `audio-adapter` redeploy (Mac-side only — the adapter runs on the Mac; the
Windows capture process is unaffected because the field is added server-side). Independently
flyable: nothing in stages 1–2 depends on it.

**Stage 4 — prose and roadmap.**
`body-layer/CLAUDE.md`, `docs/concept/STATE_TRANSITIONS.md`, `body-layer/ROADMAP.md` milestone row,
`todo/todo.md` entries for the two deferred items (o'clock scan vocabulary; absolute-sector gaze).

Verification per subproject after every stage that touches it: `ruff format` + `ruff check` +
`mypy --strict` + `pytest`, in **both** `body-layer` and `audio-adapter` for Stage 3.

---

### Risks & Unknowns

- **Compass scans still do not drive gaze** (measured, above). `scan north` — and now
  `scan bearing 320` — register an attention area and speak a readback while Petrovich keeps
  free-scanning. A pilot who hears "Scanning northwest" and gets free-scan behaviour will read this
  milestone as broken. Deferred to the follow-on in Decision 5, but it must be **said in the sortie
  card**, not discovered in the air.
- **`REPORT_MAX_GROUPS = 3` and the three-group join are guesses.** Uncalibrated, like
  `SPEECH_RATE_WPS` and `MIN_UTTERANCE_S` next door. A report of three groups could be a long
  utterance the pilot cannot interrupt (barge-in does not exist). `stop` still cuts it.
- **`note_reply` changes existing timing.** Callouts will now wait behind readbacks they previously
  queued immediately behind. This is the intended fix, but it is a behaviour change on a path the
  user has already flown, and if `estimate_speech_duration_s` over-estimates, callouts get quieter
  than before.
- **Quantisation is invisible in the transcript.** "Scan bearing 317" becomes a northwest scan; the
  readback says so, the recorded transcript says 317. Anyone reading a log without this plan will
  think a bug ate the number. Mitigated by the `vocabulary.py` docstring note and by logging the
  quantisation at debug level.
- **Vocabulary sync has three hand-maintained copies** (`audio-adapter/src/vocabulary.py`,
  `aircraft-layer`'s `ALLOWED_COMMANDS`, `crew_console.py`'s dispatch tables) and no mechanism can
  be added without violating module independence. **Sync owner: whoever edits
  `audio-adapter/src/vocabulary.py` owns updating `crew_console.DISPATCHED_COMMAND_TOKENS` in the
  same change.** Each module's docstring names the others. No new token is introduced by this plan,
  which is the only reason that is tolerable here.
- **Nothing added here is benched** in the recognition corpus sense — but nothing added here is a
  new *token* either. The 20 tokens being wired up were all in the corpus from the start. The
  unbenched risk stays confined to `cancel_scan`/`cancel_watch` (already flagged) and to the
  deferred o'clock scan family.
- **`"estimated"` contacts in a report.** A contact last seen 90 s ago is still reported with a
  current clock/range derived from a stale position. `_contact_report_text` has no certainty hedge
  today. Flagged, not fixed — adding a hedge is a wording milestone of its own.

---

### Second-order effect

Making `_print` the single point where speech occupancy is claimed — for replies, callouts and
urgent calls alike — is the seam BL-10's real barge-in and any future duck/resume behaviour needs;
without it there is no one place that knows the channel is busy. It narrows a later milestone in a
good way. Less comfortably, folding numeric bearings onto the eight compass sectors means the
absolute-direction vocabulary is now 8-valued end to end, so the follow-on that makes compass scans
drive gaze inherits a 45° quantisation it cannot undo without revisiting this decision.

---

### Decisions Requiring User Input

1. **Wording of the rear-hemisphere answer.** `Can't see north.` is the proposal. It is a new class
   of reply — an honest refusal — and the register matters more than the words.
2. **Whether the compass-scan gaze gap blocks this milestone.** The user's rule was *"if we have the
   machinery for a command to work, it must work."* `scan north` arguably *works* (area, task,
   readback) and always has; what it does not do is move his eyes. Recommendation: ship this
   milestone, take the gaze fix as the immediately-following one together with `scan <clock>`. If
   the user reads "works" as "moves his eyes", that follow-on is really Stage 5 of this plan and the
   milestone should be scoped accordingly.
3. **`REPORT_MAX_GROUPS = 3`.** Worth one sortie's judgment: is a three-group answer useful or too
   long to sit through.
