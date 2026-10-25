# BL-B89 Stage 2 — pointing the 9K113 at a known place

Base: `main` at `406c1ce6` (`feature/9k113-scan-procedure`'s own tip; Stage 1 and `[[BL-B98]]`'s
fix merged into it). Supersedes Stage 2's one-paragraph sketch in `plan.md` — that section now
points here.

### Goal

Let the pilot aim the 9K113 at a named place by voice — an o'clock hour, a compass bearing, or
one of the sight's own sectors (left/right/ahead) — instead of only the idle search cycle Stage 1
built, and have Petrovich search that place, report what he finds (or doesn't), and resume
whatever he was doing before.

### What's already built — read before assuming any of this is new

- **The sight-vs-eyes split for guidance during an attack run already exists and needs no new
  code.** `optic_policy._apply_guidance`'s sight ceiling is re-derived from `state.home_phase`
  on *every* call: a sight-ranked `requested_optic` is silently capped to `BINOCULAR_OPTIC`
  whenever `home_phase is not OpticPhase.SIGHTING` (`optic_policy.py` lines ~2598-2609). This is
  exactly the explore-notes answer 5 rule ("during attack run, keep the sight on the target. If
  OBSERV off, eyes/binoculars on the target") — **already shipped, before this plan, for the
  attack-run case.** Stage 2 adds nothing here; see "Attack-run interaction" below for what that
  means for a *pointing* command issued mid-run.
- **`ScanPlan.fixed_look_at`** (`perception/gaze.py`) is the existing continuous-aim mechanism
  the attack-run's own gaze claim already uses (`body.py`'s `_scan_plan_for`) — a precedent for
  "aim at one exact direction, not a sector," reused by Stage 2's own point-aim rather than
  re-invented.
- **The confirm-band mechanism** (`belief.voice_commands.classify_yes_no`/`PendingConfirmation`/
  `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S`, `crew_console.handle_transcript`) already
  handles "ask, then act on yes" with a timeout and a late-answer grace period — reused for the
  OBSERV-off case below via one new, narrowly-scoped `PendingConfirmation` payload, not a new
  mechanism.
- **The once-per-poll drain pattern** (`drain_pending_positional_replies`, Voice-latency
  instrumentation) — a queued effect that waits for a later condition (there: the speech channel
  clearing) and is checked once per poll, dropped on `self.refused`, never forced out early. The
  deferred point request below is the same shape with a different condition.
- **Slotted voice commands already parse exactly the pieces this needs**: `parse_clock` (o'clock
  hour), `vocabulary.parse_sector_word` (the 8 compass words), `vocabulary.parse_relative_word`
  (`left`/`right`/`ahead`/`full`), `vocabulary.parse_range_km` (an optional distance) — all four
  already exist, are already slot-parsed (not enumerated phrases) for `follow`/`report`/
  `select_target`, and `command_matcher.py` already has the exact ordering precedent
  (`follow`'s/`report`'s/`select_target`'s own slot-resolution branches, tried before the generic
  phrase table, in that order, for the documented reason: a clock-only phrase would otherwise
  collide with another family under the plain word-sequence score).

### Vocabulary design

**Measured, not assumed — a naive approach collides badly.** Adding `look`/`sight`/`what is at`
as ordinary literal `PHRASES` entries (the shape every existing sector/bearing token uses) was
tried against the real matcher (`audio-adapter/src/command_matcher.py::match_transcript`, patched
in a scratch script, not committed) before writing this section:

| transcript | naive literal-phrase result | why it's wrong |
|---|---|---|
| `"look one o'clock"` | `report_clock_1` @ 0.67, **ambiguous=True** | no `look`-family phrase exists to compete, so it drifts onto `report`'s nearest phrase |
| `"sight two o'clock"` | `report_clock_2` @ 0.67, **ambiguous=True** | same failure |
| `"look two o'clock three kilometres"` | no match at all | the combinatorial clock × distance space cannot be enumerated, same reason `follow`/`report` are slot-parsed instead |
| `"what is at two o'clock"` | `point_place` @ 0.60 (borderline, the exact `MATCH_FLOOR`) | works, but by luck of the literal phrase overlapping, not by design |

This is the same failure `follow`/`report`/`select_target` were built to avoid (their own module
comments: "9 clock hours × ... is in the hundreds/thousands, far past what a closed grammar can
list"). **Decision: `look`/`sight`/`what is [at]` get a dedicated slot-resolution branch in
`command_matcher.py`, in the same place and the same shape as `follow`'s/`report`'s/
`select_target`'s — not a `PHRASES` entry.**

**One token, dispatched by which `where`-slot fired** — the user's own final word on this
("`look <o'clock>` collapses," see below) means the sector form and the point form are one
command, not two:

```
_POINT_VERBS = ("look", "sight")   # "what" handled separately, see below

def _parse_point_slots(text) -> dict | None:
    slots = {}
    relative = parse_relative_word(text)   # left / right / ahead / full
    if relative is not None:
        slots["relative"] = relative
    clock = parse_clock(text)
    if clock is not None:
        slots["clock"] = clock
    sector = parse_sector_word(text)        # compass word
    if sector is not None:
        slots["sector"] = sector
    distance = parse_range_km(text)
    if distance is not None:
        slots["distance_km"] = distance
    return slots if slots else None
```

tried in `match_transcript` at the same point `follow`/`report`/`select_target` are, before the
generic phrase table, with the same `_where_slot_count(...) > 1` guard (`clock`+`sector`+
`relative` together is a detected recognition error, same shape an illegal bearing already
returns — asks again rather than guessing).

**`"what"` is not added to `_POINT_VERBS`.** It already anchors via the *existing* literal phrase
`"what do you see"` (the `report`/`describe` zero-slot fallback) — `"what"` is not in
`_REPORT_VERBS` (`("report", "describe")`), so it never enters `report`'s own slot branch either.
Giving `_parse_point_slots` a second, `"what"`-anchored entry point (verb-anchor on `"what"`,
require a `where` slot to fire, fall through unchanged — including to `"what do you see"` — when
none does) reaches `"what is at two o'clock"` and `"what do you see"` correctly without disturbing
either existing path: the first produces a `where` slot and resolves to `point`; the second
produces none and falls through exactly as before. Order this branch anywhere relative to
`follow`/`report`/`select_target` — `"what"` doesn't collide with any of their verb sets.

**What this means for the vocabulary tables** (`audio-adapter/src/vocabulary.py`):
- Remove `"look ahead"`, `"look left"`, `"look right"` from `PHRASES["scan_ahead"/"scan_left"/
  "scan_right"]` — `look` is no longer an alias of `scan`.
- No new `PHRASES` entries for the point family itself (it's slot-resolved, like `follow`), but
  `"look"`/`"sight"` need to reach `VERB_ANCHOR_WORDS` (derived from `PHRASES`' first words) and
  `to_prompt()`'s whisper bias (the "prompt in sync by construction" rule) — add one minimal
  calibration phrase each (e.g. `"point": ("look", "sight")`, unused for matching, read only by
  the derivation and the prompt builder) rather than skip the bias.
- **This is a vocabulary change** — `/command-map` needs a redraw at merge (the coordinator's own
  note); flagging it here so the Implementer doesn't have to rediscover it.

**`look <sector>` vs `look <place>`: the fork collapses for o'clock/compass.** The open question
this plan started with — is `"look one o'clock"` Stage 1's 30°-wedge sector or Stage 2's exact
point, swept near-to-far? — turned out not to need an answer. A point-scan along the bearing line
(near-to-far, "two proper sweeps of the area," answer 3) *covers* the sector reading: anything a
30°-wedge sweep centred on that hour would have found, a near-to-far sweep along the hour's own
centre line also finds, provided the sweep itself has some lateral width (which it must anyway —
Stage 1's own wide-optic FOV is not a zero-width ray). So: **`relative` slot (`left`/`right`/
`ahead`/`full`) → Stage 1's commanded-sector shape** (no exact aim line, bias the sight's own
search cycle to that wedge, unchanged from Stage 1); **`clock` or `sector` (compass) slot → Stage
2's pointing shape** (exact aim line, near-to-far two-sweep, optional distance narrows the start).
One token, dispatch on which slot fired, no separate "is this a sector or a point" judgement call
anywhere in the code.

### `scan`/`look` split (explore-notes items 1-3)

- **`scan <where>` is unchanged.** Petrovich's own existing logic still decides which optic
  (eyes/binoculars/9K113) serves it — today's `scan_*` feeding both the naked-eye gaze claim and
  the sight's commanded sector (`_commanded_or_default_sector` reading `ScanPlan.commanded_sector`/
  `commanded_legs`) is correct as built and needs no change.
- **`look <where>`/`sight <where>`/`what is [at] <where>` are a new, explicit request for the
  9K113.** This is additive — a new command surface, not a rewire of `scan`'s own dispatch — so
  there is no risk of the two channels fighting over `ScanPlan`: `look` does not touch `ScanPlan`
  at all; it drives the sight directly (see "State" below), the same way the attack-run's own gaze
  claim already bypasses `ScanPlan` for the sight via `_apply_guidance`'s `requested_optic`.

### OBSERV gating for an explicit `look`

Because `look`/`sight`/`what is at` are an *explicit* request to use the 9K113, the command itself
is the pilot decision that satisfies `BL-B64`'s "OBSERV ON only on pilot command" — Petrovich is
not deciding to turn OBSERV on by himself, the pilot's own `look` command is the decision. So:

- **OBSERV already on**: dispatch the point/sector request immediately, same poll.
- **OBSERV off**: ask first, reusing the confirm band exactly as it already works elsewhere —
  see "OBSERV-off confirm flow" below. (explore-notes items 4-5, verbatim.)

### OBSERV-off confirm flow

**Reuse, not a new mechanism** — `PendingConfirmation` already carries a second,
mutually-exclusive payload beside its ordinary `token`/`slots` pair: `contact_pick`, for a
different kind of pending question ("only one candidate survived revalidation — confirm it, don't
silently act"). This plan adds a **third**, same shape: `observ_request: dict[str, int | str] |
None` — the point command's own parsed slots, carried across the confirm round trip, checked by
the affirm branch before falling to the ordinary `handle_command(pending.token, ...)` re-dispatch.

```
PendingConfirmation(
    token=None,               # not a command token to re-run as-is
    description="need observ",
    pending_since_sim=now_sim,
    observ_request=point_slots,
)
```

`render_confirm_request("need observ")` → `"Need observ, confirm?"` — the existing formatter,
unchanged, happens to produce exactly the user's own wording. No new speech-rendering code.

**On affirm** (`handle_transcript`'s existing pending-confirmation block, one new branch ordered
before the existing `contact_pick`/`token` checks):

```
if pending.observ_request is not None:
    lines = self._handle_observ_on()
    if self.sight_ready:   # _handle_observ_on didn't refuse (GUIDANCE_NOT_READY)
        self.pending_point_request = PendingPointRequest(
            slots=pending.observ_request, requested_sim=now_sim,
        )
    return lines
```

If the guidance unit itself isn't warmed up yet, `_handle_observ_on()` already returns
`render_unable("GUIDANCE_NOT_READY")` unchanged (`"Unable, guidance unit not ready."`) — the look
is simply dropped, no new unable reason needed, and no `pending_point_request` is queued (nothing
to wait for).

**`"observ on"` spoken during the confirm window counts as the "yes," not a second,
independent dispatch.** `classify_yes_no`'s own rule 2 ("a resolved command token is never an
answer") would otherwise swallow it — `"observ on"` resolves to the real `observ_on` token,
`matched_command=True`, so ordinarily it falls through *past* the confirm check to be evaluated on
its own merits, which would dispatch `_handle_observ_on()` a second, independent way while the
`pending_point_request`-worthy confirmation is simply dropped (cleared unconditionally the moment
any transcript arrives inside the window, answered or not). **Fix, scoped to this one pending-
confirmation kind only** (not a change to `classify_yes_no` itself, which stays exactly as its four
review rounds left it, for every other confirm use): in the pending-confirmation block, when
`pending.observ_request is not None`, also treat `token == "observ_on"` as confirmed, in addition
to `classify_yes_no`'s own "affirm" outcome:

```
if pending.observ_request is not None and (answer == "affirm" or token == "observ_on"):
    ...  # the branch above
```

This calls `_handle_observ_on()` exactly once either way (via this branch, never falling through
to the ordinary dispatch afterward — the function returns from inside the pending-confirmation
block regardless of which condition fired it).

**"no" cancels the look, silently** — `answer == "negative"` already returns `[]` unconditionally
for every confirm kind; inherited unchanged, no new wording. (Flagged as a Decision below only
because the user's own instruction didn't say whether a cancelled look should get an
acknowledgement — the existing silent-drop is the default, consistent with every other confirm's
negative branch.)

**No answer / timeout — inherited unchanged.** `CONFIRM_WINDOW_S` (15 s) elapses, the pending
confirmation (and with it the point request) is silently dropped, `_confirmation_expired_sim` is
set, and `CONFIRM_LATE_ANSWER_GRACE_S` (20 s) catches a delayed yes/no with "Say again?" rather
than misreading it as a fresh, unrelated command. No new timeout constant for this half.

**A second timeout *is* new**: once OBSERV is confirmed on and `pending_point_request` is queued,
waiting for the sight to actually be usable. See "What 'ready' means" below.

### What "ready" means — flagged, not assumed

The user's own words were "use sight when observ ready (lamp lit)." Two different things in this
codebase could be meant, and they are not the same wait:

1. **`self.sight_ready`** (`CrewConsole`, synced from `sight_effector.sight_ready`) — the
   guidance-unit *power-up* lamp. This is checked **synchronously, inside `_handle_observ_on`
   itself**, before OBSERV is even allowed to transition — if it's false, `_handle_observ_on`
   already refuses with `GUIDANCE_NOT_READY` and nothing is queued (see above). By the time the
   affirm branch above queues a `pending_point_request` at all, this lamp was already lit.
2. **`home_phase is OpticPhase.SIGHTING`** (actually, **does nothing** on its own) — entering
   OBSERV only sets `observ_transition`; `decide()`'s own phase cycle moves `home_phase` into
   `SIGHTING` at its *next* phase boundary (one poll, ordinarily), per `_handle_observ_on`'s own
   docstring. This is the wait that's actually still outstanding once the affirm branch returns.

**Recommendation: the drain condition is (2), not a second check of (1).** The lamp was already
checked at the door; what the pointing request is actually waiting for is the phase cycle catching
up, which is normally one poll and never more than a few. **Flagged because the user's wording
("lamp lit") names (1), and if a re-check of (1) was intended instead of (2), the two are not
interchangeable** — (1) could already be true for several polls before (2) catches up, so waiting
on (1) alone would try to point a sight phase that isn't `SIGHTING` yet.

### State — a new deferred-action queue, and the "pointed" OpticState question

**`CrewConsole.pending_point_request: PendingPointRequest | None`**, drained once per poll
(`drain_pending_point_request(now_sim)`, called from `body.py` alongside `drain_events`/
`drain_brain`/`drain_pending_positional_replies` — the same place, same pattern):

```
@dataclass(frozen=True)
class PendingPointRequest:
    slots: dict[str, int | str]
    requested_sim: float

def drain_pending_point_request(self, now_sim: float) -> list[str]:
    if self.refused or self.pending_point_request is None:
        return []
    if self.home_phase is not OpticPhase.SIGHTING:
        if now_sim - self.pending_point_request.requested_sim > POINT_READY_TIMEOUT_S:
            self.pending_point_request = None
            return [render_unable("GUIDANCE_NOT_READY").text]  # or a dedicated reason, see Decisions
        return []
    slots = self.pending_point_request.slots
    self.pending_point_request = None
    return self._start_point(slots, now_sim)   # the actual dispatch, see "Sight state" below
```

`POINT_READY_TIMEOUT_S` is a new tunable (`tuning.py`, a few seconds — the ordinary wait is one
poll; this is a backstop against something else intervening, e.g. a violated `sight_steady`
triggering `_force_observ_off` between the affirm and the next poll boundary).

**The actual aim/sweep mechanism — `OpticState`'s own "pointed, not searching" field — is left for
the Implementer to design against this plan's Co-moving Fields table below, not pinned to exact
field names here.** What *is* decided: it is **not** `ScanPlan.fixed_look_at` (that's the
naked-eye/binocular gaze claim, a different channel from the sight's own `OpticState`/
`decide_optic` cycle `look`/`sector` scanning uses) — the shape to follow is `OpticState`'s own
existing `sight_search_leg`/`look_azimuth_deg`/`look_elevation_deg` plus a new marker that this is
a *commanded* point, not the idle cycle, so `_decide_sighting`'s dispatch can tell them apart (the
same way `home_phase`/`phase` already distinguish idle search from a chosen-target look).

### The sweep itself

- **No distance given → near to far** (answer 2, unchanged from the explore notes' earlier
  settlement). Reuses `sight_look_optic`'s existing wide-then-narrow-at-a-target shape, applied to
  the commanded aim line instead of a detected contact's believed bearing — orient with
  `SIGHT_WIDE_OPTIC` first (find/orient, consistent with every other "wide orients, narrow
  classifies" rule this feature already encodes), then `SIGHT_NARROW_OPTIC` to identify/range.
- **A distance given → the sweep starts narrowed around that range** rather than sweeping the
  whole reach from 1.5 km out — exact narrowing left to the Implementer (a band around the stated
  distance, tunable width).
- **Two proper sweeps of the area** (answer 3) — a tunable sweep count (`POINT_SWEEP_COUNT`,
  default 2), not hardcoded, consistent with root `CLAUDE.md`'s tuning rule and this feature's own
  established posture (Stage 1's band edges are already tunable).
- **Nothing found after both sweeps**: `"<where> clear."` (answer 3) and **resume whatever the
  previous action was** — the idle search cycle at whatever leg it was on, a standing `scan_area`
  task, or a watch, per the same "resume, don't restart" principle `[[BL-B98]]` just fixed for the
  glance-away case. `<where>` renders the same way the sector/clock/bearing labels already do
  elsewhere in `crew_console.py` (`_RELATIVE_SCAN_LABELS`/`_SECTOR_SCAN_LABELS`/
  `_CLOCK_REPORT_LABELS` — reused, not a new label table).
- **Something found**: report through the normal callout path (unchanged — `choose_sighting_look`/
  the existing classification-driven callout mechanism), then **go back to scanning** — target
  count makes no difference (answer 4), so this is not a new "stay and track" behaviour, just the
  ordinary report-then-resume the idle cycle already does for any other sight look.
- **Readback on command**: a short acknowledgement naming the place (e.g. `"Two o'clock."`),
  mirroring `scan`'s own existing readback shape (`render_scan_readback`/`_describe_token_for_
  confirm`'s "a plain human phrase for the command" convention) — reuse, not new wording design.

### Attack-run interaction

**Already correct, structurally, before this plan.** `_apply_guidance`'s sight-ceiling re-check
(see "What's already built" above) means: if an attack run is engaged, its own `requested_optic`
governs the sight regardless of any standing `look`/point request — a sight-ranked request is
capped to binoculars whenever `home_phase is not SIGHTING`, and the attack run's own gaze claim
(answer 5) already wins the sight when `OpticPhase.SIGHTING` applies. **What this plan decides is
only what happens to a `look` command issued *while* a run is engaged**, which the existing
mechanism does not itself answer (it governs what the sight does once a decision is made, not
whether a new `look` command is accepted at all).

**Recommendation: refuse, don't queue.** `"unable, attack run"` (a new `render_unable` reason,
e.g. `ATTACK_RUN_ENGAGED`) — the same "say again vs unable" shape as `ON_GROUND`/
`GUIDANCE_NOT_READY`: the command is heard and understood, it just cannot be actioned right now,
because the sight is already committed to the run's own target and nothing a `look` command could
ask for would be allowed to displace it anyway (`_apply_guidance` would silently override it the
very next poll even if queued). Queuing it for after the run ends is possible but adds a second
deferred-queue shape (alongside `pending_point_request`'s OBSERV-wait) for a case the user has not
asked for — flag below.

### Supersession — a new command replaces a pending-or-running look

User direction, verbatim (explore-notes item 6): *"new command replaces if it is look or scan
command. Effector sequences and commands to trigger tham can fire."*

| command class | effect on a pending/running `look` |
|---|---|
| `look_*`, `scan_*` (any sector/clock/bearing/point) | **replaces** — clears `pending_point_request` or the active point-aim, starts the new one |
| `observ_on`, `observ_off`, `weapons_armed`, `weapons_safe` (effector-trigger commands) | **run normally, no dispatch-level cancel** — `observ_off` ends the look as a *side effect* of `[[BL-B98]]`'s own rule (aim resets to boresight, `home_phase` leaves `SIGHTING`), not because this plan taught it to; see below |
| `report`, `describe`, `where_is_it` | **run without cancelling** — pure queries, no task state changes |
| `mark_here`, `mark_target` | **run without cancelling** — same reasoning, they write mission memory, not the sight's task |
| `cancel_task`, `cancel_scan`, `cancel_watch` | **cancel the look** — these are explicitly destructive of standing state, and a point request/active point is exactly that kind of standing state |
| `watch_nearest`, `follow`, `select_target`, `engage`, `disengage`, `drop_target`, `step` | **task-changing → replace/cancel** — consistent with answer 5's own attack-run priority; `engage` in particular hands the sight to `_apply_guidance` regardless (see above), so a standing point request would be moot even if left queued |

**One case flagged, not defaulted**: `silence` is neither destructive of task state nor a query —
it only gates `_print`'s own output. **Recommendation: `silence` does not cancel a pending/running
look** (consistent with it leaving `scan_area`/`watch_contact` tasks alone today) — the look
continues to run and resume as normal, just without the spoken readback/report while silenced
(the existing silence gate already suppresses speech regardless of its source).

**`observ_off` during a *running* point (not just a pending one)**: checked against `[[BL-B98]]`'s
own rule directly — `body.py`'s `run_once` OBSERV-observed-off branch nulls the aim fields
unconditionally on the `home_phase` on→off edge, which already fires regardless of whether
`home_phase` got there via the idle search cycle or a commanded point (the branch doesn't
distinguish the two, by construction). So a running point is torn down correctly with **no new
code** — this plan's own "pointed, not searching" marker just needs to be included wherever
`[[BL-B98]]`'s reset `replace()` call already resets the other sighting fields, which is this
plan's own Co-moving Fields concern below, not a new mechanism.

---

## Co-moving Fields

Trigger: a new "pointed, not searching" marker on `OpticState`, co-moving with `sight_search_leg`/
`look_azimuth_deg`/`look_elevation_deg`/`home_phase`, at least one of which (`home_phase`) is
externally written (pilot command) and at least one (the idle-cycle fields) is internally decided.
**Build the actual table by grepping every `OpticState(`/`replace(state` construction site once
the field is named** (per root `CLAUDE.md`'s "build the table by grepping every construction
site, not by enumerating transitions from the phase narrative") — Stage 1's own table already
names the two fresh-construction sites (`GLASSING`/`SEARCHING` entry in `body.py`) that must carry
the new field forward; this plan adds the following transitions to check against it:

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| "pointed" marker | internal (`_start_point`) | `look`/point command accepted (OBSERV already on) | marker set, `look_azimuth_deg`/`look_elevation_deg` set to the commanded aim line, `sight_search_leg` untouched (irrelevant while pointed) |
| "pointed" marker | internal (`drain_pending_point_request`) | OBSERV-wait clears, deferred point starts | same as above — the deferred and immediate paths must produce an identical post-state, or a test covering only one will miss the other |
| "pointed" marker | internal | both sweeps complete, nothing found | marker cleared, resumes the idle cycle at whatever leg/task it was on before — **not** reset to `wide_near` unconditionally, the same "resume, don't restart" principle `[[BL-B98]]` fixed |
| "pointed" marker | internal | something found | marker cleared after the report, same resume rule |
| "pointed" marker | external (`home_phase` on→off, any cause) | OBSERV off | marker cleared, aim nulled to boresight — **already covered by `[[BL-B98]]`'s existing `replace()` call**, provided the new field is added to that same call rather than left out of it |
| "pointed" marker | external (a new `look`/`scan` command) | supersession (see table above) | marker cleared or replaced by the new request's own marker, never left stale alongside a new aim |
| `pending_point_request` | internal/external mix (confirm affirm, poll drain, supersession) | any of the above | at most one of `pending_point_request` (waiting on OBSERV) and the "pointed" marker (actually pointing) is set at a time — they are sequential phases of one request, never concurrent |

---

### Tests

- **Vocabulary/matcher** (`audio-adapter/tests/test_command_matcher.py`): `"look two o'clock"`,
  `"sight two o'clock, three kilometres"`, `"what is at two o'clock"` all resolve to the point
  token with the expected slots; `"what do you see"` still resolves to `report_all` unchanged;
  `"look left"`/`"look right"`/`"look ahead"` resolve to the point token with `relative` set and
  no longer alias `scan_left`/`scan_right`/`scan_ahead`; `"scan left"` is unaffected; a
  two-where-slot transcript (`"look left two o'clock"`) is a detected error (`token=None,
  verb_anchored=True`), not a guess.
- **OBSERV-off confirm flow** (`test_crew_console.py`): OBSERV off → `look` → `"Need observ,
  confirm?"` → `"yes"`/`"confirm"`/`"observ on"` each independently drive the same affirm branch,
  exactly once (`_handle_observ_on` called once, not twice, for the `"observ on"` case); `"no"`
  drops it silently; the existing `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S` timeout tests
  extended to cover this pending-confirmation kind rather than duplicated.
- **Deferred point drain**: queued after affirm, `home_phase` not yet `SIGHTING` → still pending;
  `home_phase` reaches `SIGHTING` → drains and starts the point same poll; `POINT_READY_TIMEOUT_S`
  elapses first → dropped with the fallback unable line.
- **Supersession**: a second `look`/`scan` command while one is pending-on-OBSERV or actively
  pointing replaces it cleanly (no stale aim, no double-queued request); `observ_on`/
  `weapons_armed` while pointing leave the active point running; `cancel_scan`/`select_target`
  cancel it; `observ_off` while actively pointing tears the aim down to boresight via the existing
  `[[BL-B98]]` test shape, extended to a pointed `OpticState` rather than only an idle-cycle one.
- **Sweep**: near-to-far with no distance; narrowed-around-distance when one is given; two
  sweeps then `"<where> clear"` and resume (asserted against whatever the previous state was —
  idle leg, standing `scan_area`, or watch — not reset to a fixed leg); a found contact reports
  then resumes, independent of how many targets were present.
- **Attack-run interaction**: `look` issued while an attack run is engaged → `"unable, attack
  run"`, no `pending_point_request` queued, no change to the run's own sight claim.

### Risks & Unknowns

- **The "ready" ambiguity (above) is the single largest risk of a wrong first cut.** If the
  Implementer builds against reading (1) (`self.sight_ready`) instead of (2) (`home_phase is
  SIGHTING`), the failure is subtle — it will often *look* correct in a quick test (the lamp and
  the phase usually line up within one poll) and only diverge under a slow effector sequence or a
  near-simultaneous OBSERV-off/on.
- **Two deferred-queue shapes now exist on `CrewConsole`** (`_pending_positional_replies`,
  `pending_point_request`) plus the ordinary `_pending_confirmation` — worth a `grep` sanity check
  that `drain_pending_point_request` is wired into `body.py`'s poll loop alongside the other two
  drains and not forgotten, the same class of gap `[[BL-B98]]` itself was.
- **The point-vs-sector collapse (relative word → Stage 1 sector, clock/compass → Stage 2 point)**
  is this plan's own judgement call, not something the user was asked to confirm directly — it
  follows from their "the fork likely collapses" framing, but flagged below for an explicit
  sign-off before implementation rather than assumed settled.
- **Vocabulary removal is a live-mapping change**: any sortie muscle-memory for "look left" meaning
  a naked-eye/binocular sector scan (if the pilot has been using it that way) now gets the 9K113
  instead. Worth a one-line callout in the eventual acceptance card.

### Second-order effect

Gives `[[BL-B66]]` (the 9K113 effector entry) a second standing-state shape to carry through its
own slew-rate model — not just the idle search cycle's phases, but a commanded point with its own
start/sweep/resume lifecycle. The "pointed, not searching" marker this stage adds should be named
with that in mind (the same state `[[BL-B66]]`'s own warm-up/OBSERV/slew co-moving fields will
need to reference), rather than as a private detail of this stage alone.

### Decisions Requiring User Input

- **"Ready" means `home_phase is SIGHTING`, not a re-check of `self.sight_ready`** — recommended
  above; please confirm, since the user's own wording ("lamp lit") names the other one and the two
  are not interchangeable (see "What 'ready' means").
- **A `look` issued during an engaged attack run is refused (`"unable, attack run"`), not
  queued for after the run.** Recommended because `_apply_guidance` would silently override a
  queued point the moment the run claims the sight anyway, making a queue pointless busywork;
  please confirm this is acceptable rather than, say, queuing it to run once the run ends/is
  disengaged.
- **`silence` does not cancel a pending/running look** — recommended for consistency with its
  existing scope (task state), but not explicitly covered by the user's own supersession rule;
  please confirm.
- **A cancelled-by-"no" look gets no acknowledgement (silent drop)** — consistent with every other
  confirm's negative branch; flagging only because the user's own instruction didn't say either
  way.
- **The sector/point collapse for `look <o'clock>`/`look <compass>`** (above) — recommended, but
  worth an explicit yes before the Implementer builds one mechanism instead of two.
