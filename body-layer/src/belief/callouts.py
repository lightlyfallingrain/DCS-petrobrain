"""`CalloutScheduler` -- `plans/callout-scheduling/plan.md`, fixing the two
linked 2026-09-21 cones 2C sortie findings ("Callouts must not be
backlogged" / "Aggregate repetitive callouts").

**The decision moves to speech time.** `CrewConsole.drain_events` used to
render and acknowledge *every* currently-unacknowledged event on every poll,
handing the whole batch to `_print` at once -- so a callout's text was
frozen the instant `tick()` produced its event, and how long it sat before
being heard was whatever the downstream `AudioPlaybackSender` FIFO queue
happened to be doing. That is exactly the pilot's "12 o'clock when I had
already flown past it several seconds ago." `CalloutScheduler.tick` fixes
this by choosing **at most one** thing to say per call, re-rendering it from
*current* belief the instant it is chosen -- nothing is rendered until the
instant it is spoken, which is the whole fix: there is nothing to go stale,
because nothing exists ahead of being spoken.

**The candidate set is not a queue this module builds or owns.** It is
`store.unacknowledged_events`, filtered and re-read every call -- the belief
store itself is the backlog. `CalloutScheduler` holds only `busy_until_sim`
(a sim-time float) and `_consumed` (a `set[str]` of event ids deliberately
dropped as stale or vanished). No pre-rendered text is ever stored.

**Occupancy is modelled in sim time, never wall clock.** A real
playback-completion signal was rejected outright (see the plan's "Replay
determinism" section): it would have to come back from the Windows box
through `audio-adapter`, does not exist when `--speech-audio` is off, and is
unreproducible under replay -- `body-layer` replays recorded streams and sim
time is authoritative there, never wall clock.
`estimate_speech_duration_s` is a pure function of the rendered string, so
every piece of this module's state is a sim-time float or an id set derived
from events -- no `time.time()`, no thread, no I/O. Replaying the same
recorded stream therefore produces a byte-identical sequence of spoken
lines (`tests/test_callouts.py`'s replay-determinism test).

**Every spontaneous candidate passes an observability gate, and this is
the one place that is true (`plans/callout-observability-gate/debug.md`).**
`tick` asks `ContactStore.callout_observable` of each event candidate's
contact, and of each `Group`'s members, before it will consider speaking:
the no-omniscience invariant says Petrovich may not volunteer a position
and a classification for something his own cockpit mask puts out of sight.
`plans/sortie-2026-09-26-fixes/plan.md` Stage 1 placed that gate at
*emission* instead, inside `ContactStore.tick`'s fifth and sixth blocks,
which reached `CONTACT_MOTION_CHANGED` and `CONTACT_RANGE_CROSSED` and
nothing else -- so the 2026-10-05 sortie spoke 17 unprompted lines about
5, 6 and 7 o'clock, all of them `CONTACT_CLASSIFICATION_CHANGED` or
group-disclosure lines. (20 masked-hour lines in all; the other 3 were
answers to a `report` and belong to the pull path below, which is correct
as it stands -- the split is `plans/post-review-fixes/explore-notes.md`
§9.) Gating here instead of there is what makes it total: group
disclosure mints no `Event` at all, so no emission-site gate could ever
have covered it, and a per-kind list at emission is a list the next new
kind silently fails to join.

**This gate is for the *push* path only.** A pilot-initiated `report`
(`CrewConsole._handle_report`) must never be filtered by it -- belief
survives the aircraft turning away, and the pilot *asked*. That path
renders straight through `belief.speech` and never reaches `tick`, which
is what keeps the two answers separate; where no-omniscience bites on the
pull path it does so as an absence claim (`render_no_view`) or as
freshness phrasing, not as silence. See `plans/crew-query-path/plan.md`.
**`_handle_report` does legitimately answer about a masked hour** (3 of
the 2026-10-05 sortie's 20 such lines were exactly that, within 4.4 s of
a `report` command) and that is not a defect to fix here -- do not
"complete" this gate by wiring it to the pull path.

**Priority is an explicitly disposable placeholder.** `callout_priority`'s
first tuple element, `threat_band`, is a constant (`_DEFAULT_THREAT_BAND`)
-- no threat model is built here. The shape is chosen so a real threat band
slots in as that first element later without touching anything else (see
the plan's "Priority" section for the full rationale on each surviving
key: attention, then proximity, then recency).

**Group disclosure now speaks for its members (`plans/group-reporting/
plan.md` Stage 4).** `tick` reads `store.groups` directly, once per call,
alongside `store.unacknowledged_events` -- two candidate sources feeding
one shared priority sort (`callout_priority`/`group_priority`), no `Event`
kind minted for a group's own trigger. A `CONTACT_DETECTED`/`CONTACT_
REACQUIRED` event whose contact currently belongs to a group is filtered
out of the event candidate pool before scoring (never consumed -- it
surfaces instead as the group's own line changing, see `belief.groups`'
module docstring on why a membership change is always a live disclosure
trigger); every other kind still competes and speaks exactly as it does
today, grouped contact or not. `group_candidates` (the event-level,
report-space bucketer this replaces) is retired -- see below.

**`group_facts`/`render_group_report` are report-space bucketing, kept as
the residual path for contacts a real `belief.groups.Group` does not
cover** -- `CrewConsole._handle_report`'s own on-demand "report" command
(the `belief.crew_console` module), and any live candidate whose
`describe_contact` facts have no `relative_now` at all. This module no
longer calls either from `tick` itself: `group_candidates`, the function
that used to bucket *events* the same way, is deleted -- with grouped
detections filtered out before scoring and nothing else ever needing a
multi-`Event` report-space bucket, nothing calls it. `CONTACT_
CLASSIFICATION_CHANGED` events are never grouped by anything, upstream or
here -- aggregating a specific identification into a generic count is
exactly what would make a BTR-70 disappear into "three infantry", which is
the failure this design explicitly guards against (plan, "What is lost,
and what is not").

**Per-contact disclosure gating (`plans/group-reporting/plan.md` Stage 1)
still stands for ungrouped contacts.** `CalloutScheduler` suppresses a
scheduled `CONTACT_DETECTED`/`CONTACT_REACQUIRED` candidate whose rendered
text is byte-identical to the last one actually spoken for that same
contact (`_last_spoken_signature`, checked in `_render_event`'s singleton
branch before `route_event` is ever called, so a suppressed duplicate is
never acknowledged) -- a repeated detection/reacquisition cycle at the same
rounded range/clock no longer re-speaks the identical line. A grouped
contact's own detection never reaches this check at all (filtered out
before scoring, above); this gate now only ever sees a contact with no
group.

**Merge-echo `CONTACT_DETECTED` suppression (`plans/contact-report-flood/
plan.md` Stage 1).** When the naked-eye gaze sweep folds several already-
separate, already-identified contacts into one supercluster, continuity's
majority-overlap vote inherits one historical identity and abandons the
rest (`perception.naked_eye_source._build_observations`'s own module
docstring, point 6); those abandoned contacts decay to `lost` and the same
real objects later re-found under fresh ids, each earning an ordinary
first-sighting `CONTACT_DETECTED`. `_render_event`'s `CONTACT_DETECTED`
branch (never `CONTACT_REACQUIRED` -- see that branch's own comment for
why) checks whether any other, **strictly earlier-founded**, not-yet-
`lost` contact is spatially and class-plausibly the same real thing
(`belief.association_over_time.contacts_plausibly_same`, the already-
calibrated percept-vs-contact gate generalised to contact-vs-contact) and,
if so, suppresses the candidate the same one-shot way an expired or
stale-signature candidate already is (`tick`'s `for _, candidate in
scored` loop adds any `_render_event`-`None` result straight to
`_consumed` -- permanent for this scheduler instance, never retried on a
later call, though the event stays unacknowledged for a future brain's
`poll_events`).

**The strictly-earlier-founded condition (`other.first_seen_sim <
this_contact.first_seen_sim`) is load-bearing, not cosmetic -- found
missing against the real sortie-1004 snapshot, not in review.** Without
it, several genuinely distinct, genuinely simultaneous foundings that
happen to be mutually close (an ordinary real scene: several vehicles
entering view in the same scan poll) see *each other* as live,
plausibly-same peers the instant they are all founded, and every one of
them suppresses every other the first time any of them is attempted --
`tick()` tries every scored candidate in priority order until one
succeeds, but if all N already exist as of the first attempt, all N fail
identically. Confirmed directly against this module's own `CalloutScheduler.
tick` using the real believed positions of `plans/contact-report-flood/
debug.md`'s own named six-vehicle cluster (`CONTACT_3/4/5/7` all founded at
`t_sim=699.073`, pairwise `contacts_plausibly_same`): zero lines spoken for
the whole cluster, not "at most 2" -- worse than the flood this fix exists
to reduce, on the plan's own acceptance example. The merge-echo mechanism
this check targets always has the abandoned identity surviving from an
*earlier* poll than the re-founding it echoes; a same-poll peer is never
that, so excluding it costs nothing against the mechanism this check
targets while fixing the real regression.

**This necessarily also silences some genuine splits, and that is accepted,
not a defect to fix here.** A merge-echo re-founding and an honest "actually
that's two things" split look structurally identical at this layer: once a
merge overwrites every absorbed member's own `_object_id_to_last_
observation_id` entry to point at the survivor, a later re-split off that
survivor produces the exact same shape whether or not a merge ever touched
it. Nothing in this module -- or in `contacts_plausibly_same` -- can tell
the two apart, and no amount of local cleverness fixes that; it is a
consequence of the project's twice-reaffirmed decision not to track
per-member identity in clustering (see `plans/contact-report-flood/
plan.md`, "The honest cost of the chosen fix, stated plainly"). What is
lost is only the incremental "actually that's two things" spoken line --
the new contact's own record, classification and the survivor's
cardinality belief are untouched and still reachable via `report`/console.
**This does not close `BL-B24` or `plans/contact-duplication-ambiguity-
runaway/plan.md`** -- `ContactStore.ingest`'s own "2+ candidates -> always
a new contact" rule, the root policy question both leave open, is
unchanged by this suppression; only the audible symptom of its merge-
driven instance goes quiet.

**A group's own first disclosure can be redundant too (`plans/
redundant-group-disclosure/plan.md`), a second instance of the same
"the content already reached the pilot" idea above, one layer up.** A
group's `last_spoken_signature is None` branch used to always speak the
full roster the instant two-plus members first clustered, even when every
one of those members had already been announced individually -- real
sortie-1004 evidence, 2026-10-05: three ground contacts founded and
spoken individually at `t_sim=699.1`, one of them re-founded under a
fresh id at 714.5 and correctly silenced by the merge-echo suppression
above, and then at 730.9 a brand-new `Group` of those same contacts still
spoke "A couple of contacts, 1 o'clock, 2.5 kilometres" -- telling the
pilot, a second time, about things he had already been told about
individually. `_already_reported_member_ids` (below) answers "has this
member's own content already reached the pilot" for each current member
of a never-spoken group, counting a member reported either because its
own `CONTACT_DETECTED`/`CONTACT_REACQUIRED` was actually spoken, or
because it was itself merge-echo-suppressed by the mechanism directly
above -- and `belief.speech.render_group_disclosure`'s own first-
disclosure branch uses that set to decide full disclosure / a delta
naming only what is new / silence. See that function's own docstring for
the three-way split; see `_already_reported_member_ids`'s own docstring
for why this is computed here rather than stored on `Contact`/`Group`."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, TypeVar

from belief.association_over_time import contacts_plausibly_same
from belief.contacts import Contact, ContactStore
from belief.decay import certainty_of
from belief.enrichment import EnrichmentContext
from belief.events import (
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_DETECTED,
    CONTACT_ENGAGEMENT_CHANGED,
    CONTACT_MOTION_CHANGED,
    CONTACT_RANGE_CROSSED,
    CONTACT_REACQUIRED,
    Event,
    EventKind,
)
from belief.groups import Group
from belief.speech import (
    _format_range_km,
    _group_member_facts,
    _unit_type_display,
    group_membership_state,
    render_contact_report,
    render_group_disclosure,
    route_event,
)
from belief.tools import acknowledge_event, describe_contact

#: The event kinds `route_event`/`render_group_report` can actually turn
#: into speech -- every other kind (`CONTACT_LOST`, `CONTACT_ATTENTION_
#: CHANGED`, `CONTACT_CARDINALITY_CHANGED`) has no template and is skipped
#: outright here rather than re-rendered to `None` every poll, unlike the
#: pre-scheduler `drain_events`, which round-tripped every kind through
#: `route_event` regardless.
_TEMPLATED_KINDS: Final[frozenset[EventKind]] = frozenset(
    {
        CONTACT_DETECTED,
        CONTACT_REACQUIRED,
        CONTACT_CLASSIFICATION_CHANGED,
        CONTACT_MOTION_CHANGED,
        CONTACT_RANGE_CROSSED,
        CONTACT_ENGAGEMENT_CHANGED,
    }
)

#: `plans/watch-reporting/plan.md` Decision 1 -- report kinds that only ever
#: speak for a *watched* contact (`belief.attention.effective_attention` in
#: `("watch", "priority")`), gated here at the speech layer rather than at
#: emission: the underlying event fires and is logged for every contact
#: regardless (see `belief.events`'s own docstring for `CONTACT_MOTION_
#: CHANGED`), and whether it is ever *spoken* depends on attention at the
#: moment `tick` considers it -- so a contact watched after its event fired
#: still gets the callout. Never filtered by group membership either (see
#: module docstring's "Group disclosure now speaks for its members") --
#: these kinds render through `_contact_report_text`'s `event_clause`/`lead`
#: affixes (`belief.speech`), which `render_group_report`/`render_group_
#: disclosure` have no concept of, so folding one into a group's own line
#: would silently drop the very fact the event exists to report.
_WATCHED_ONLY_KINDS: Final[frozenset[EventKind]] = frozenset(
    {CONTACT_MOTION_CHANGED, CONTACT_RANGE_CROSSED, CONTACT_ENGAGEMENT_CHANGED}
)

#: Suppresses **all** watched-only speech about one contact, across kinds --
#: `belief.events.EVENT_COOLDOWN_S`'s sibling but a different mechanism (see
#: `plans/watch-reporting/plan.md` Decision 3's three-way comparison against
#: `EVENT_COOLDOWN_S`/`CLASSIFICATION_CONTRADICTION_LOCKOUT_S`, which this
#: docstring restates so the distinction lives next to the code, not only in
#: the plan). A watched-only event that loses to this gate is added to
#: `_consumed` and left unacknowledged -- **lost, not deferred**, the same
#: cost `CALLOUT_MAX_AGE_S` expiry already accepts for every other kind.
#: Uncalibrated placeholder, same debt class as `SPEECH_RATE_WPS` below.
WATCH_REPORT_MIN_GAP_S: Final[float] = 8.0

#: Shorter than both `EVENT_COOLDOWN_S` (15, `belief/events.py`) and
#: `SCAN_CYCLE_PERIOD_S` (16, `perception/gaze.py`) -- so an expired
#: candidate about something still present is regenerated by the next scan
#: cycle rather than lost for good. Expiring is not losing: an expired
#: candidate is added to `_consumed` and left unacknowledged (see
#: `CalloutScheduler.tick`), so a future brain's `poll_events` still sees
#: the original event.
CALLOUT_MAX_AGE_S: Final[float] = 10.0

#: A breath between lines, and slack absorbing a small under-estimate in
#: `estimate_speech_duration_s` -- see that function's own docstring.
INTER_UTTERANCE_GAP_S: Final[float] = 0.75

#: **Uncalibrated -- needs a live sortie.** ~150 words per minute, the plan's
#: one real guess (`plans/callout-scheduling/plan.md`, "Risks & Unknowns":
#: "Duration estimation drift is the only load-bearing guess"). Isolated
#: here, same "mechanism and calibration never share a commit" posture as
#: `perception/optics.py`'s own provenance comments, so retuning it later
#: never touches `estimate_speech_duration_s`'s mechanism.
SPEECH_RATE_WPS: Final[float] = 2.5

#: **Uncalibrated -- needs a live sortie.** Per-line synthesis/transport
#: overhead, roughly the measured `say` latency from `plans/
#: tts-voice-output/plan.md` Decision 2 -- see `SPEECH_RATE_WPS`'s own note
#: on why this is isolated as its own constant rather than folded into the
#: words-per-second term.
MIN_UTTERANCE_S: Final[float] = 0.6

#: The 30-degree clock bucket `belief.association_over_time` already treats
#: as one bucket -- two reports whose clock positions are this close read as
#: "the same direction" to a listener. See `group_facts`'s docstring.
CALLOUT_GROUP_CLOCK_SPAN_HOURS: Final[int] = 1

#: A chaining cap `perception/clustering.py` deliberately still lacks
#: (single-link clustering there has no bound on total chain span) -- cheap
#: to have here because a `(unit type word, range word)` bucket is tiny.
CALLOUT_GROUP_MAX_SPAN_HOURS: Final[int] = 2

#: The one line `docs/concept/threat-levels.md` will eventually replace,
#: once coalition inference lands (plan, "Second-order effect"). Every
#: candidate gets the same band today, so this key never actually
#: discriminates between candidates yet -- it exists so `callout_priority`'s
#: tuple shape does not have to change when it does.
_DEFAULT_THREAT_BAND: Final[int] = 0

#: `belief.attention._ATTENTION_RANK`'s ordering, restated here rather than
#: imported -- that name is module-private to `attention.py` (its own
#: docstring: "the one place that ordering is encoded"), and no other
#: module imports it. `callout_priority` needs the same ordering as a
#: ranking key, not as the source of truth for what "higher" means, so a
#: small local restatement (checked against `attention.py`'s table at
#: authorship) is preferable to widening that module's public surface for
#: one caller.
_ATTENTION_PRIORITY_RANK: Final[dict[str, int]] = {
    "ignore": 0,
    "normal": 1,
    "watch": 2,
    "priority": 3,
}


def estimate_speech_duration_s(text: str) -> float:
    """A pure function of `text` alone -- see module docstring's "Occupancy
    is modelled in sim time" note for why this must never consult a real
    playback-completion signal. `SPEECH_RATE_WPS`/`MIN_UTTERANCE_S` are both
    uncalibrated placeholders (their own docstrings say so)."""
    word_count = len(text.split())
    return MIN_UTTERANCE_S + word_count / SPEECH_RATE_WPS


def callout_priority(
    facts: dict[str, object], event: Event, now_sim: float
) -> tuple[int, int, float, float]:
    """`(threat_band, -attention_rank, range_m, -event.t_sim)` -- ascending
    sort order, so the *lowest* tuple is the best candidate. See module
    docstring's "Priority" section for why each surviving key is here:
    `threat_band` is `_DEFAULT_THREAT_BAND` today (a disposable placeholder,
    not a real assessment); `-attention_rank` ranks priority > watch >
    normal > ignore; `range_m` is nearer-first (what goes stale fastest);
    `-event.t_sim` is newer-first (what makes "backlogged" impossible by
    construction -- combined with `CALLOUT_MAX_AGE_S` expiry, an old
    candidate starving is the intended outcome, not a bug).

    `range_m` falls back to `math.inf` (sorts last, never first) when no
    `EnrichmentContext` was supplied -- `facts["relative_now"]` is then
    absent entirely, the module's own absent-not-null convention, and
    there is no proximity signal to rank on."""
    attention = facts.get("attention")
    default_rank = _ATTENTION_PRIORITY_RANK["normal"]
    rank = (
        _ATTENTION_PRIORITY_RANK.get(attention, default_rank)
        if isinstance(attention, str)
        else default_rank
    )
    relative_now = facts.get("relative_now")
    if isinstance(relative_now, dict):
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
    else:
        range_m = math.inf
    return (_DEFAULT_THREAT_BAND, -rank, range_m, -event.t_sim)


def group_priority(
    member_facts: Sequence[dict[str, object]], now_sim: float
) -> tuple[int, int, float, float]:
    """`callout_priority`'s group-level analogue (`plans/group-reporting/
    plan.md`'s Stage 4 design, section 3) -- same tuple shape, so a `Group`
    candidate and an `Event` candidate sort in one shared list. `-attention_
    rank` uses the *highest* rank among `member_facts` -- any one watched/
    prioritised member elevates the whole group's line, matching `belief.
    speech.render_group_disclosure`'s own trailing `", watched"` clause,
    which fires on the same "any member" test (user direction). `range_m`
    is the nearest member's, the same convention `render_group_disclosure`/
    `render_group_report` both already use. `-now_sim` stands in for
    `-event.t_sim`: a group candidate has no event and no age -- it is read
    fresh from `Group.last_spoken_signature` every tick (`belief.groups`'
    module docstring: groups need no expiry and no `_consumed` bookkeeping)
    -- so "now" is the only honest recency value, and every group candidate
    this tick ties on it, which is fine: ties only matter for stable
    ordering, not for staleness."""
    default_rank = _ATTENTION_PRIORITY_RANK["normal"]
    best_rank = default_rank
    nearest_range_m = math.inf
    for facts in member_facts:
        attention = facts.get("attention")
        rank = (
            _ATTENTION_PRIORITY_RANK.get(attention, default_rank)
            if isinstance(attention, str)
            else default_rank
        )
        best_rank = max(best_rank, rank)
        relative_now = facts.get("relative_now")
        if isinstance(relative_now, dict):
            range_m = relative_now["range_m"]
            assert isinstance(range_m, float)
            nearest_range_m = min(nearest_range_m, range_m)
    return (_DEFAULT_THREAT_BAND, -best_rank, nearest_range_m, -now_sim)


def report_priority(facts: dict[str, object]) -> tuple[int, int, float]:
    """`callout_priority`'s facts-only sibling, for ordering a report's
    groups (`plans/voice-command-completeness/plan.md` Decision 1b's
    "Group ordering and the cap"): `(threat_band, -attention_rank,
    range_m)` -- the same first three keys, `-event.t_sim` dropped since a
    report has no event and "what is newest" has no meaning for a query of
    current belief. Ascending sort order, so the lowest tuple sorts first,
    same convention as `callout_priority`."""
    attention = facts.get("attention")
    default_rank = _ATTENTION_PRIORITY_RANK["normal"]
    rank = (
        _ATTENTION_PRIORITY_RANK.get(attention, default_rank)
        if isinstance(attention, str)
        else default_rank
    )
    relative_now = facts.get("relative_now")
    if isinstance(relative_now, dict):
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
    else:
        range_m = math.inf
    return (_DEFAULT_THREAT_BAND, -rank, range_m)


def _clock_diff(a: int, b: int) -> int:
    """Circular distance between two 1-12 clock positions, e.g.
    `_clock_diff(12, 1) == 1`, `_clock_diff(3, 9) == 6`."""
    diff = abs(a - b) % 12
    return min(diff, 12 - diff)


_ChainItem = TypeVar("_ChainItem")

#: `CalloutScheduler.tick`'s one shared candidate type -- an `Event` (an
#: ungrouped contact's own lifecycle/classification candidate) or a
#: `belief.groups.Group` (a persisted associative belief's own disclosure
#: candidate, Stage 4). Scored into one list via `callout_priority`/
#: `group_priority`'s identically-shaped tuples; `isinstance(candidate,
#: Group)` at speak-time picks which render path applies.
_Candidate = Event | Group


def _chain_by_clock(
    members: list[tuple[_ChainItem, int]],
) -> list[list[_ChainItem]]:
    """Single-link chaining of same-`(unit type word, range word)` members
    by clock position, capped at `CALLOUT_GROUP_MAX_SPAN_HOURS` total span
    (see module docstring's "Aggregation" note and the plan's "Aggregation"
    section). `members` is `(item, clock_position)` pairs already known to
    share a bucket -- generic over `_ChainItem` (`plans/
    voice-command-completeness/plan.md` Stage 2 extracted `group_facts`,
    below, which chains raw `facts` dicts rather than `Event`s; this
    function never reads anything `Event`-specific, so widening it to any
    item type is a pure generalisation, not a behaviour change). `group_
    facts` is this function's only caller now -- `group_candidates`, the
    event-level wrapper that used to call it with `Event` members, was
    retired in `plans/group-reporting/plan.md`'s Stage 4 (module
    docstring's "Group disclosure now speaks for its members").

    Clock positions are circular (12 and 1 are adjacent), so this first
    finds the widest gap in the *sorted-by-value* set of distinct clock
    positions present and treats that gap as the cut point -- the same
    trick as reading a circular arrangement as a line, cut at its longest
    empty stretch. Members are then walked in that order, starting a new
    group whenever the next member is either more than
    `CALLOUT_GROUP_CLOCK_SPAN_HOURS` from the previous member or would push
    the running group's total span past `CALLOUT_GROUP_MAX_SPAN_HOURS`."""
    if not members:
        return []
    distinct_clocks = sorted({clock for _, clock in members})
    if len(distinct_clocks) == 1:
        order = distinct_clocks
    else:
        widest_gap = -1
        cut_index = 0
        for i in range(len(distinct_clocks)):
            next_clock = distinct_clocks[(i + 1) % len(distinct_clocks)]
            gap = (next_clock - distinct_clocks[i]) % 12
            if gap > widest_gap:
                widest_gap = gap
                cut_index = i
        order = distinct_clocks[cut_index + 1 :] + distinct_clocks[: cut_index + 1]

    by_clock: dict[int, list[_ChainItem]] = {}
    for item, clock in members:
        by_clock.setdefault(clock, []).append(item)

    groups: list[list[_ChainItem]] = []
    current: list[_ChainItem] = []
    current_start_clock: int | None = None
    prev_clock: int | None = None
    for clock in order:
        for item in by_clock[clock]:
            if not current or prev_clock is None or current_start_clock is None:
                current = [item]
                current_start_clock = clock
                prev_clock = clock
                continue
            gap_from_prev = _clock_diff(prev_clock, clock)
            span_from_start = _clock_diff(current_start_clock, clock)
            if (
                gap_from_prev <= CALLOUT_GROUP_CLOCK_SPAN_HOURS
                and span_from_start <= CALLOUT_GROUP_MAX_SPAN_HOURS
            ):
                current.append(item)
                prev_clock = clock
            else:
                groups.append(current)
                current = [item]
                current_start_clock = clock
                prev_clock = clock
    if current:
        groups.append(current)
    return groups


def group_facts(
    facts_list: list[dict[str, object]],
) -> list[list[dict[str, object]]]:
    """The bucket+chain merge rule (see module docstring's "Aggregation"
    note), originally lifted out of `group_candidates` (`plans/
    voice-command-completeness/plan.md` Stage 2) to a purely facts-level
    function -- the grouping decision has never needed anything but
    `belief.tools.describe_contact` facts; only the event->facts lookup
    that used to precede it was event-specific. `group_candidates` itself
    was retired in `plans/group-reporting/plan.md`'s Stage 4 (module
    docstring's "Group disclosure now speaks for its members") once a real
    `belief.groups.Group` took over the event-level case this function used
    to be called for; `crew_console.CrewConsole._handle_report`'s own
    residual bucketing of contacts with no `Group` (report has no events to
    look facts up from -- it already holds a facts list) is this function's
    sole caller now.

    A facts dict with no `relative_now` (no `EnrichmentContext` supplied,
    or -- for a report's own pre-filtered list -- unreachable in practice
    since the caller has already dropped those) is always a singleton
    group; grouping degrades to "no grouping" rather than guessing.

    Bucketed on the same reporting-word key `_format_range_km`/
    `_unit_type_display` would render, so a report's own spoken words are
    exactly what decides whether two contacts sound the same -- see module
    docstring's "`group_facts`/`render_group_report` are report-space
    bucketing" note."""
    singles: list[list[dict[str, object]]] = []
    bucketed: dict[tuple[str, str], list[tuple[dict[str, object], int]]] = {}

    for facts in facts_list:
        relative_now = facts.get("relative_now")
        if not isinstance(relative_now, dict):
            singles.append([facts])
            continue
        classification = facts["classification"]
        assert isinstance(classification, dict)
        unit_word = _unit_type_display(
            classification.get("value"), classification.get("level")
        )
        range_word = _format_range_km(relative_now["range_m"])
        clock = relative_now["clock_position"]
        assert isinstance(clock, int)
        bucketed.setdefault((unit_word, range_word), []).append((facts, clock))

    groups: list[list[dict[str, object]]] = list(singles)
    for members in bucketed.values():
        groups.extend(_chain_by_clock(members))
    return groups


def _is_merge_echo_of_earlier_contact(
    contact: Contact, store: ContactStore, now_sim: float
) -> bool:
    """Whether `contact` is a merge echo of some strictly-earlier-founded,
    not-`lost`, plausibly-same contact already in `store` -- the one
    condition shared, character for character, by `_render_event`'s own
    `CONTACT_DETECTED` suppression branch and
    `CalloutScheduler._already_reported_member_ids`'s branch 2 (`plans/
    redundant-group-disclosure/plan.md`, review item 1). Factored out here
    so the two call sites can never drift apart silently: `_render_event`
    asks this of its own candidate event's contact; `_already_reported_
    member_ids` asks it of a member reached by iterating a group's
    membership with no event in hand -- both questions are "does an
    earlier, live, plausibly-same contact already account for this one,"
    answered the same way regardless of which caller is asking."""
    return any(
        other.id != contact.id
        and other.first_seen_sim < contact.first_seen_sim
        and certainty_of(other, now_sim) != "lost"
        and contacts_plausibly_same(contact, other, now_sim)
        for other in store.contacts
    )


@dataclass
class CalloutScheduler:
    """Owns speech-time occupancy for one `CrewConsole` -- see module
    docstring. Held as one more `CrewConsole` field; `drain_events`
    delegates to `tick`, `_print` calls `note_urgent` on the
    `bypass_gate=True` path."""

    busy_until_sim: float = 0.0
    _consumed: set[str] = field(default_factory=set, repr=False)
    #: `plans/watch-reporting/plan.md` Decision 3's fifth suppression
    #: mechanism -- per-contact sim time a watched-only kind (`_WATCHED_
    #: ONLY_KINDS`) was last actually spoken, keyed by `contact_id`, read
    #: against `WATCH_REPORT_MIN_GAP_S` in `tick` below. Absent-not-null:
    #: no entry means "never spoken yet."
    _last_spoken_sim: dict[str, float] = field(default_factory=dict, repr=False)
    #: `plans/group-reporting/plan.md` Stage 1 -- per-contact rendered-
    #: signature gating for `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
    #: (see `_render_event`'s singleton branch): the exact text `render_
    #: contact_report` last actually produced for this contact, keyed by
    #: `contact_id`. A candidate whose freshly rendered text is
    #: byte-identical to this is suppressed -- a hold on a lockout-armed
    #: classification, or a re-detection at the same rounded range/clock,
    #: both read as "unchanged" under this check, since both produce the
    #: same rendered text. Absent-not-null: no entry means "never spoken
    #: yet," never `None`. Since Stage 4 (module docstring), a grouped
    #: contact's own `CONTACT_DETECTED`/`CONTACT_REACQUIRED` never reaches
    #: this check at all -- it only ever sees an ungrouped contact now.
    _last_spoken_signature: dict[str, str] = field(default_factory=dict, repr=False)

    def note_urgent(self, now_sim: float, text: str) -> None:
        """An urgent (`bypass_gate=True`) line just went out through a path
        this scheduler never chose -- `!inject-urgent`'s test harness, the
        only source of an `UrgentCall` today. `AudioPlaybackSender.
        interrupt` clears the routine queue and kills any in-flight
        playback on the real audio path, so this scheduler must reset its
        own occupancy to the urgent line's own duration rather than
        continuing to believe a routine line the audio layer has already
        destroyed is still playing (plan, "The urgent path")."""
        self.busy_until_sim = now_sim + estimate_speech_duration_s(text)

    def note_reply(self, now_sim: float, text: str) -> None:
        """A reply (a command readback or a report, anything spoken from
        `CrewConsole._print`'s non-urgent path) just claimed the channel --
        `plans/voice-command-completeness/plan.md` Decision 2's fix for a
        real latent defect: every command readback has been unbudgeted
        since readbacks existed, so a routine callout could queue
        immediately behind one instead of waiting for it to finish. Reports
        are what makes this audible (a report can be several groups long),
        but the fix belongs to every reply, not only reports.

        **Extends, never preempts** (`max`, not assignment) -- a reply is
        an answer, not an alarm; clobbering an in-flight callout's own
        budget to answer "report" would throw away a detection the pilot
        has not heard yet to save a couple of seconds, and `max()` also
        means a reply issued while a callout is still playing does not
        shorten that callout's own budget. Contrast `note_urgent` above,
        which *resets* rather than extends -- that path exists only because
        `AudioPlaybackSender.interrupt` has genuinely destroyed whatever was
        in flight, which a reply never does."""
        self.busy_until_sim = max(
            self.busy_until_sim,
            now_sim + estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S,
        )

    def _already_reported_member_ids(
        self, store: ContactStore, member_contact_ids: frozenset[str], now_sim: float
    ) -> frozenset[str]:
        """Which of a group's current `member_contact_ids` already had
        their own content reach the pilot, for `render_group_disclosure`'s
        `already_reported_contact_ids` gate (`plans/
        redundant-group-disclosure/plan.md`) -- computed here, not stored
        on `Contact` or `Group`, because the fact being asked is "what has
        this scheduler actually said," which only this scheduler's own
        `_last_spoken_signature` plus the store's contact graph can answer.

        A member counts as already reported two ways:

        1. **Its own `CONTACT_DETECTED`/`CONTACT_REACQUIRED` was actually
           spoken** -- `contact_id in self._last_spoken_signature`, the
           same dict `_render_event`'s singleton gate already reads.
        2. **It was itself merge-echo-suppressed** (module docstring's
           "Merge-echo `CONTACT_DETECTED` suppression") -- via the shared
           `_is_merge_echo_of_earlier_contact`, the same predicate
           `_render_event`'s `CONTACT_DETECTED` branch evaluates to decide
           whether to suppress that announcement in the first place, so
           the two can never drift apart silently. Per that predicate's
           own condition, this does not additionally require the earlier,
           plausibly-same contact to itself appear in
           `_last_spoken_signature` -- a contact that is not `lost` and
           strictly earlier-founded is, by the same reasoning the
           suppression itself relies on, the contact whose continuity the
           newer one is an echo of, not a second unreported thing."""
        reported: set[str] = set()
        for contact_id in member_contact_ids:
            contact = store.contact(contact_id)
            if contact is None:
                continue
            if contact_id in self._last_spoken_signature:
                reported.add(contact_id)
                continue
            if _is_merge_echo_of_earlier_contact(contact, store, now_sim):
                reported.add(contact_id)
        return frozenset(reported)

    def _render_event(
        self,
        store: ContactStore,
        event: Event,
        now_sim: float,
        enrichment: EnrichmentContext | None,
    ) -> str | None:
        """Renders one event candidate and acknowledges it. Returns `None`
        without acknowledging anything if its contact has vanished since
        scoring -- the caller then consumes this candidate's id and tries
        the next one (plan, step 5: "If the render returns `None` ...
        consume and try the next candidate").

        Takes a single `Event`, never a list -- `plans/group-reporting/
        plan.md`'s Stage 4 design retired `group_candidates`, the only
        source of a multi-`Event` candidate, so the multi-member branch
        this function used to have (`render_group_report` over several
        events) is dead code once nothing constructs that shape anymore;
        deleted here rather than left unreachable. Renamed from `_render_
        group` in the same change -- that name, for a `list[Event]`, would
        collide with `belief.groups.Group` now that this module scores
        real `Group` candidates too (see `tick` below)."""
        if event.kind in (CONTACT_DETECTED, CONTACT_REACQUIRED):
            # `plans/group-reporting/plan.md` Stage 1: suppress a
            # scheduled contact-report callout whose rendered text is
            # unchanged from the last one actually spoken for this
            # contact -- computed *before* calling `route_event` (which
            # auto-acknowledges on success), so a suppressed duplicate is
            # left unacknowledged, same "lost, not deferred" treatment
            # `tick` already gives an expired or vanished candidate. Only
            # ever reached for an ungrouped contact since Stage 4 -- a
            # grouped one is filtered out of `live` before this is called.
            candidate = render_contact_report(
                store, event.contact_id, now_sim, enrichment
            )
            if candidate is None:
                return None
            if self._last_spoken_signature.get(event.contact_id) == candidate.text:
                return None
        if event.kind == CONTACT_DETECTED:
            # `plans/contact-report-flood/plan.md` Stage 1 -- merge-echo
            # suppression. Scoped to `CONTACT_DETECTED` only, never
            # `CONTACT_REACQUIRED`: that kind only ever fires for a contact
            # id that already existed and had gone `lost`
            # (`belief.events.lifecycle_event_kind`), which is exactly "the
            # same guy is back" and must stay audible regardless of what
            # else is nearby. See module docstring's "Merge-echo
            # CONTACT_DETECTED suppression" section for the full rationale,
            # including why this also silences some genuine splits.
            this_contact = store.contact(event.contact_id)
            # Strictly earlier founding only (see
            # `_is_merge_echo_of_earlier_contact`'s docstring) -- a contact
            # founded in the very same poll is a simultaneous, independent
            # sighting, never a merge echo of an abandoned identity (the
            # mechanism this check exists for always has the abandoned
            # identity surviving from an *earlier* poll). Discovered
            # against the real sortie-1004 snapshot (`plans/
            # contact-report-flood/implementation.md`): without this,
            # several genuinely distinct, genuinely simultaneous foundings
            # that are mutually close (a common real scene -- several
            # vehicles entering view in the same scan poll) see each other
            # as live peers and mutually suppress, producing *zero* spoken
            # lines for the whole cluster -- worse than the flood this fix
            # exists to reduce, and a direct violation of this plan's own
            # "at most 2, not 6" acceptance bound on its own named
            # six-vehicle example.
            if this_contact is not None and _is_merge_echo_of_earlier_contact(
                this_contact, store, now_sim
            ):
                return None
        speech = route_event(store, event, now_sim, enrichment)
        if speech is None:
            return None
        if event.kind in (CONTACT_DETECTED, CONTACT_REACQUIRED):
            self._last_spoken_signature[event.contact_id] = speech.text
        return speech.text

    def tick(
        self,
        store: ContactStore,
        now_sim: float,
        enrichment: EnrichmentContext | None = None,
    ) -> list[str]:
        """Speak at most one thing, chosen fresh from current belief. See
        module docstring for the full algorithm; this is `plans/
        group-reporting/plan.md`'s Stage 4 design, section 4, "`tick`'s
        shape, end to end" -- two candidate sources (`store.
        unacknowledged_events`, `store.groups`) feeding one shared priority
        sort, no `Event` ever minted for a group's own trigger."""
        if now_sim < self.busy_until_sim:
            return []

        live: list[Event] = []
        for event in store.unacknowledged_events:
            if event.kind not in _TEMPLATED_KINDS or event.id in self._consumed:
                continue
            if (
                event.kind
                in (
                    CONTACT_DETECTED,
                    CONTACT_REACQUIRED,
                )
                and store.group_for_contact(event.contact_id) is not None
            ):
                # Spoken for by the group's own disclosure line instead --
                # skip without consuming, same "not yet" treatment
                # `_WATCHED_ONLY_KINDS`'s not-watched-yet case gets below
                # (Stage 4 design, section 1).
                continue
            if event.kind in _WATCHED_ONLY_KINDS:
                result = describe_contact(
                    store, event.contact_id, now_sim, enrichment=enrichment
                )
                if result is None or result["facts"].get("attention") not in (
                    "watch",
                    "priority",
                ):
                    # Not watched (yet) -- skip without consuming, so a
                    # contact watched later still gets this callout (see
                    # `_WATCHED_ONLY_KINDS`'s own docstring).
                    continue
                last_spoken = self._last_spoken_sim.get(event.contact_id)
                if (
                    last_spoken is not None
                    and now_sim - last_spoken < WATCH_REPORT_MIN_GAP_S
                ):
                    self._consumed.add(event.id)
                    continue
            if now_sim - event.t_sim > CALLOUT_MAX_AGE_S:
                self._consumed.add(event.id)
                continue
            # `plans/callout-observability-gate/debug.md` -- the
            # no-omniscience invariant applied to every spoken kind, not
            # only the two `plans/sortie-2026-09-26-fixes/plan.md` Stage 1
            # wired at emission. `CONTACT_CLASSIFICATION_CHANGED` passes
            # through neither gated block, and the 2026-10-05 sortie spoke
            # it at 6 and 7 o'clock -- body azimuths of 180 and 150
            # degrees, both past `_CO_PILOT_MASK.rear_cutoff_deg`'s 130.
            #
            # **Skipped without consuming -- deferred, not lost.** Unlike
            # `WATCH_REPORT_MIN_GAP_S` above, there is nothing stale about
            # a classification Petrovich simply cannot see *yet*: the
            # contact sliding back inside the mask makes the same line
            # correct, and the `CALLOUT_MAX_AGE_S` check immediately above
            # is what bounds the wait (it retires the candidate on a later
            # tick if the bearing never comes back). Placed *after* that
            # check for exactly that reason -- ahead of it, a permanently
            # astern contact's event would never be consumed at all.
            #
            # Deliberately gates every kind including `CONTACT_DETECTED`/
            # `CONTACT_REACQUIRED`, which this is close to a no-op for
            # (both perception channels already respect the mask at
            # founding time -- `naked_eye_source` via `check_visibility`,
            # `hybrid_source` via `association.FORWARD_HEMISPHERE_HALF_
            # WIDTH_DEG`'s narrower 90 degrees -- and `CALLOUT_OBSERVABILITY_
            # GRACE_S` equals `CALLOUT_MAX_AGE_S`). One total gate at the
            # one choke point beats a per-kind list that the next new kind
            # silently fails to join, which is the whole shape of this
            # defect.
            contact = store.contact(event.contact_id)
            if contact is not None and not store.callout_observable(contact, now_sim):
                continue
            live.append(event)

        scored: list[tuple[tuple[int, int, float, float], _Candidate]] = []
        for event in live:
            result = describe_contact(
                store, event.contact_id, now_sim, enrichment=enrichment
            )
            if result is None:
                self._consumed.add(event.id)
                continue
            scored.append((callout_priority(result["facts"], event, now_sim), event))

        for belief_group in store.groups:
            # `plans/callout-observability-gate/debug.md` -- the same
            # no-omniscience gate the event loop above applies, for the one
            # candidate source that mints no `Event` at all and so could
            # never have been reached by a gate placed at emission. The
            # 2026-10-05 sortie's *"A couple of contacts, 5 o'clock, 2.5
            # kilometres."* and *"Group, 5 o'clock, 4 kilometres."* are
            # both this path, at a 150-degree body azimuth.
            #
            # **Any one member observable is enough**, not all of them: a
            # group straddling the cutoff is a group Petrovich can
            # genuinely see, and the disclosure line renders its position
            # from the nearest member rather than per-member, so requiring
            # every member would silence a visibly-present group for the
            # sake of one straggler behind the doorframe.
            if not any(
                (member := store.contact(member_id)) is not None
                and store.callout_observable(member, now_sim)
                for member_id in belief_group.member_contact_ids
            ):
                continue
            member_facts = _group_member_facts(
                store, belief_group, now_sim, enrichment=enrichment
            )
            if member_facts is None:
                # Fewer than two members currently resolve -- self-corrects
                # on the next `GroupStore.reconcile`, nothing to do here.
                continue
            already_reported = self._already_reported_member_ids(
                store, belief_group.member_contact_ids, now_sim
            )
            speech = render_group_disclosure(
                store,
                belief_group,
                now_sim,
                enrichment,
                already_reported_contact_ids=already_reported,
            )
            if speech is None:
                continue
            # Compared by *content*, not the full rendered line -- a pure
            # range/clock drift must not count as "something changed"
            # (`plans/group-undermerging/debug.md`'s second finding: the
            # user flying away from an already-fully-reported group heard
            # its entire composition re-spoken every ~500 m of opening
            # range). `OutgoingSpeech.content_signature` is `None` only
            # for templates that never needed this distinction;
            # `render_group_disclosure` always sets it.
            content_signature = speech.content_signature
            assert content_signature is not None
            if content_signature == belief_group.last_spoken_signature:
                # Nothing changed since this group last spoke -- silent,
                # not a candidate this tick at all (Stage 4 design,
                # section 4, step 2).
                continue
            scored.append((group_priority(member_facts, now_sim), belief_group))

        if not scored:
            return []

        scored.sort(key=lambda item: item[0])

        for _, candidate in scored:
            text: str | None
            if isinstance(candidate, Group):
                # Re-render fresh at the instant of speaking, not the
                # scoring-time text -- the same "nothing exists ahead of
                # being spoken" invariant every other candidate gets
                # (Stage 4 design, section 4, step 4).
                already_reported = self._already_reported_member_ids(
                    store, candidate.member_contact_ids, now_sim
                )
                speech = render_group_disclosure(
                    store,
                    candidate,
                    now_sim,
                    enrichment,
                    already_reported_contact_ids=already_reported,
                )
                if speech is None:
                    continue
                content_signature = speech.content_signature
                assert content_signature is not None
                if content_signature == candidate.last_spoken_signature:
                    # Rare/defensive: belief moved between scoring and
                    # speaking within this one `tick()` call. Fall through
                    # to the next candidate exactly as a vanished event
                    # candidate does.
                    continue
                membership_state = group_membership_state(
                    store, candidate, now_sim, enrichment
                )
                # `membership_state` re-gathers the same member facts
                # `render_group_disclosure` just rendered against -- see
                # that function's own docstring for why this is the
                # existing double-gather pattern, not new duplication.
                # `None` here would mean the group dissolved between the
                # two calls; `speech` being non-`None` above makes that
                # impossible within one `tick()`, so the assert documents
                # the invariant rather than guessing past it.
                assert membership_state is not None
                member_contact_ids, leading_contact_id, differentiated = (
                    membership_state
                )
                store.mark_group_spoken(
                    candidate.id,
                    content_signature,
                    now_sim,
                    member_contact_ids=member_contact_ids,
                    leading_contact_id=leading_contact_id,
                    differentiated=differentiated,
                )
                for member_event in store.unacknowledged_events:
                    if (
                        member_event.kind in (CONTACT_DETECTED, CONTACT_REACQUIRED)
                        and member_event.contact_id in candidate.member_contact_ids
                    ):
                        acknowledge_event(store, member_event.id)
                text = speech.text
            else:
                text = self._render_event(store, candidate, now_sim, enrichment)
                if text is None:
                    self._consumed.add(candidate.id)
                    continue
                if candidate.kind in _WATCHED_ONLY_KINDS:
                    self._last_spoken_sim[candidate.contact_id] = now_sim
            self.busy_until_sim = (
                now_sim + estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S
            )
            return [text]

        return []
