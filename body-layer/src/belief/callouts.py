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

**Priority is an explicitly disposable placeholder.** `callout_priority`'s
first tuple element, `threat_band`, is a constant (`_DEFAULT_THREAT_BAND`)
-- no threat model is built here. The shape is chosen so a real threat band
slots in as that first element later without touching anything else (see
the plan's "Priority" section for the full rationale on each surviving
key: attention, then proximity, then recency).

**Aggregation groups in report space, not world space.**
`group_candidates` does **not** reuse `perception.clustering.
cluster_candidates` -- that module answers a different question (are two
*live candidates* optically resolvable apart, at the magnitude of one
target width) from the one a callout grouping asks (would two *reports*
sound the same to a listener, at the magnitude of the reporting
quantisation -- a 30-degree clock bucket, a rounded range word). It is
computed entirely from `belief.tools.describe_contact` facts, reusing
`belief.speech._unit_type_display`/`_format_range_km` so a report's own
displayed words are exactly what decide whether two reports would sound
the same -- deliberately not a second, parallel word-choice path.
`ClusterCandidate` also carries ground-truth positions that `belief/` must
not see (`belief/percept.py`'s structural no-omniscience boundary); this
module never imports `perception.clustering` for that reason, independent
of the "different question" argument above.

`CONTACT_CLASSIFICATION_CHANGED` events are never grouped -- aggregating a
specific identification into a generic count is exactly what would make a
BTR-70 disappear into "three infantry", which is the failure this design
explicitly guards against (plan, "What is lost, and what is not")."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final

from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.events import (
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_DETECTED,
    CONTACT_REACQUIRED,
    Event,
    EventKind,
)
from belief.speech import (
    _format_range_km,
    _unit_type_display,
    render_group_report,
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
    {CONTACT_DETECTED, CONTACT_REACQUIRED, CONTACT_CLASSIFICATION_CHANGED}
)

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
#: "the same direction" to a listener. See `group_candidates`'s docstring.
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


def _clock_diff(a: int, b: int) -> int:
    """Circular distance between two 1-12 clock positions, e.g.
    `_clock_diff(12, 1) == 1`, `_clock_diff(3, 9) == 6`."""
    diff = abs(a - b) % 12
    return min(diff, 12 - diff)


def _chain_by_clock(
    members: list[tuple[Event, int]],
) -> list[list[Event]]:
    """Single-link chaining of same-`(unit type word, range word)` members
    by clock position, capped at `CALLOUT_GROUP_MAX_SPAN_HOURS` total span
    (see module docstring's "Aggregation" note and the plan's "Aggregation"
    section). `members` is `(event, clock_position)` pairs already known to
    share a bucket.

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

    by_clock: dict[int, list[Event]] = {}
    for event, clock in members:
        by_clock.setdefault(clock, []).append(event)

    groups: list[list[Event]] = []
    current: list[Event] = []
    current_start_clock: int | None = None
    prev_clock: int | None = None
    for clock in order:
        for event in by_clock[clock]:
            if not current or prev_clock is None or current_start_clock is None:
                current = [event]
                current_start_clock = clock
                prev_clock = clock
                continue
            gap_from_prev = _clock_diff(prev_clock, clock)
            span_from_start = _clock_diff(current_start_clock, clock)
            if (
                gap_from_prev <= CALLOUT_GROUP_CLOCK_SPAN_HOURS
                and span_from_start <= CALLOUT_GROUP_MAX_SPAN_HOURS
            ):
                current.append(event)
                prev_clock = clock
            else:
                groups.append(current)
                current = [event]
                current_start_clock = clock
                prev_clock = clock
    if current:
        groups.append(current)
    return groups


def group_candidates(
    events: list[Event],
    store: ContactStore,
    now_sim: float,
    enrichment: EnrichmentContext | None,
) -> list[list[Event]]:
    """Partition `events` into groups that should be spoken as one line --
    see module docstring's "Aggregation" note for the merge rule and why it
    is computed here rather than reusing `perception.clustering`.

    `CONTACT_CLASSIFICATION_CHANGED` events are always singleton groups
    (never aggregated). An event whose contact has since vanished, or that
    carries no `relative_now` (no `EnrichmentContext` supplied -- clock/
    range are then undecidable, so grouping degrades to "no grouping", the
    plan's stated, accepted consequence), is also always a singleton
    group -- `CalloutScheduler.tick` discovers a vanished contact itself
    when it tries to render, this function only needs facts to bucket."""
    singles: list[Event] = []
    bucketed: dict[tuple[str, str], list[tuple[Event, int]]] = {}

    for event in events:
        if event.kind == CONTACT_CLASSIFICATION_CHANGED:
            singles.append(event)
            continue
        result = describe_contact(
            store, event.contact_id, now_sim, enrichment=enrichment
        )
        if result is None:
            singles.append(event)
            continue
        facts = result["facts"]
        relative_now = facts.get("relative_now")
        if not isinstance(relative_now, dict):
            singles.append(event)
            continue
        classification = facts["classification"]
        assert isinstance(classification, dict)
        unit_word = _unit_type_display(
            classification.get("value"), classification.get("level")
        )
        range_word = _format_range_km(relative_now["range_m"])
        clock = relative_now["clock_position"]
        assert isinstance(clock, int)
        bucketed.setdefault((unit_word, range_word), []).append((event, clock))

    groups: list[list[Event]] = [[event] for event in singles]
    for members in bucketed.values():
        groups.extend(_chain_by_clock(members))
    return groups


@dataclass
class CalloutScheduler:
    """Owns speech-time occupancy for one `CrewConsole` -- see module
    docstring. Held as one more `CrewConsole` field; `drain_events`
    delegates to `tick`, `_print` calls `note_urgent` on the
    `bypass_gate=True` path."""

    busy_until_sim: float = 0.0
    _consumed: set[str] = field(default_factory=set, repr=False)

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

    def _render_group(
        self,
        store: ContactStore,
        group: list[Event],
        now_sim: float,
        enrichment: EnrichmentContext | None,
    ) -> str | None:
        """Renders one candidate (a singleton or a multi-member group) and
        acknowledges every member event it actually spoke for. Returns
        `None` without acknowledging anything if any member's contact has
        vanished since grouping -- the caller then consumes every id in
        this candidate and tries the next one (plan, step 5: "If the render
        returns `None` ... consume and try the next candidate")."""
        if len(group) == 1:
            speech = route_event(store, group[0], now_sim, enrichment)
            if speech is None:
                return None
            return speech.text
        facts_list: list[dict[str, object]] = []
        for event in group:
            result = describe_contact(
                store, event.contact_id, now_sim, enrichment=enrichment
            )
            if result is None:
                return None
            facts_list.append(result["facts"])
        speech = render_group_report(facts_list)
        for event in group:
            acknowledge_event(store, event.id)
        return speech.text

    def tick(
        self,
        store: ContactStore,
        now_sim: float,
        enrichment: EnrichmentContext | None = None,
    ) -> list[str]:
        """Speak at most one thing, chosen fresh from current belief. See
        module docstring for the full algorithm; this is the plan's
        numbered steps 1-7 in one function."""
        if now_sim < self.busy_until_sim:
            return []

        live: list[Event] = []
        for event in store.unacknowledged_events:
            if event.kind not in _TEMPLATED_KINDS or event.id in self._consumed:
                continue
            if now_sim - event.t_sim > CALLOUT_MAX_AGE_S:
                self._consumed.add(event.id)
                continue
            live.append(event)

        if not live:
            return []

        groups = group_candidates(live, store, now_sim, enrichment)

        scored: list[tuple[tuple[int, int, float, float], list[Event]]] = []
        for group in groups:
            priorities: list[tuple[int, int, float, float]] = []
            vanished = False
            for event in group:
                result = describe_contact(
                    store, event.contact_id, now_sim, enrichment=enrichment
                )
                if result is None:
                    vanished = True
                    break
                priorities.append(callout_priority(result["facts"], event, now_sim))
            if vanished:
                for event in group:
                    self._consumed.add(event.id)
                continue
            scored.append((min(priorities), group))

        scored.sort(key=lambda item: item[0])

        for _, group in scored:
            text = self._render_group(store, group, now_sim, enrichment)
            if text is None:
                for event in group:
                    self._consumed.add(event.id)
                continue
            self.busy_until_sim = (
                now_sim + estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S
            )
            return [text]

        return []
