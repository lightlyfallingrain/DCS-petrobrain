""" "That"/"it" referent resolution -- `[[BL-B102]]`, `plans/that-it-referent/
plan.md`. What a bare "it"/"that" (or a qualified "that AAA"/"that group")
in a player command refers to: the contact or group Petrovich was last
talking about, within a short window.

Kept out of `belief/crew_console.py` deliberately (root `CLAUDE.md`'s
"Behaviour as actions and params" shaping): resolving a referent is a pure
query over belief state, never a decision about *when* to speak or *what*
to do about the answer, so it lives beside the other state-param-shaped
query helpers rather than inside the console's own dispatch.

**Decision 4 (explore-notes, user: "time ok, but use belief if not
visible")**: a mentioned contact resolves within the window even if it has
since gone `"lost"` -- nothing here reads `certainty` at all. The caller's
own qualifier-filtering step (`qualifier_scope`, injected rather than
owned here -- see `resolve_referent`'s docstring) is the one place a
certainty-style drop could leak back in, and `CrewConsole._report_scope`'s
own `restrict_to_ids` mode is written to not do that; see its docstring.

**Decision 2's "last line wins" is a property of recording order, not of
`t_sim`.** Two mentions recorded in the same `_print` call (a report
naming two groups in one batch) share one `t_sim`; `ReferentMemory`
preserves the order they were recorded in, so an unqualified referent
immediately after such a batch takes the *last-listed* one, not an
arbitrary tie-break.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import tuning
from belief.speech import group_membership_state, render_unable

if TYPE_CHECKING:
    from belief.contacts import ContactStore

#: How long a mention stays resolvable by a bare/qualified pronoun
#: (Decision 4: "time ok"). The user's own figure, no measured sortie
#: data behind it yet -- `judgement` status, expect it to move once flown
#: (same posture `CONFIRM_WINDOW_S` carried before it had real use behind
#: it). A longer window keeps "where is it" working further from when
#: Petrovich last spoke; too long and a stale subject from several
#: exchanges ago starts winning a bare pronoun it should not.
REFERENT_WINDOW_S: float = tuning.real(
    "belief.referent.REFERENT_WINDOW_S", 60.0, lo=15.0, hi=180.0, status="judgement"
)


@dataclass(frozen=True, slots=True)
class Mention:
    """One contact or group Petrovich spoke about, at the moment he said
    it. `kind="group"` is resolved to one member contact id by
    `resolve_referent`'s own group-reduction step -- nothing downstream of
    that function ever sees a group id."""

    kind: Literal["contact", "group"]
    id: str
    t_sim: float


class ReferentMemory:
    """The short-window "what was just mentioned" ledger -- one per
    `CrewConsole` instance, reset implicitly by nothing (a mention past the
    window is simply never returned, see `recent`/`last`). Append-order is
    the single source of "which one is last" -- see module docstring."""

    def __init__(self) -> None:
        self._mentions: list[Mention] = []

    def record(self, mentions: Sequence[Mention], now_sim: float) -> None:
        """Appends `mentions` in the order given (the order they were
        spoken within one reply), then prunes anything now outside the
        window. A no-op for an empty sequence -- a line with no subject
        must not disturb what was last mentioned."""
        if not mentions:
            return
        self._mentions.extend(mentions)
        self._prune(now_sim)

    def _prune(self, now_sim: float) -> None:
        self._mentions = [
            mention
            for mention in self._mentions
            if now_sim - mention.t_sim <= REFERENT_WINDOW_S
        ]

    def recent(self, now_sim: float) -> list[Mention]:
        """Every mention still inside the window, oldest first (append
        order)."""
        self._prune(now_sim)
        return list(self._mentions)

    def last(self, now_sim: float) -> Mention | None:
        """The most recently recorded mention still inside the window, or
        `None` if nothing qualifies -- Decision 2's "the last line wins"."""
        recent = self.recent(now_sim)
        return recent[-1] if recent else None


def _fallback_member_id(
    store: ContactStore, member_contact_ids: Collection[str]
) -> str | None:
    """Any one member of a group that still resolves to a live `Contact`,
    used when `group_membership_state` cannot name a leading member --
    either because it returned `None` outright (fewer than two members
    still resolve) or because it resolved but found no engagement envelope
    to lead on. A group that has shrunk to one live contact is still a
    valid referent (Facts section, `group_membership_state`'s own
    docstring)."""
    for member_id in member_contact_ids:
        if store.contact(member_id) is not None:
            return member_id
    return None


def _resolve_group_mention(
    store: ContactStore, group_id: str, now_sim: float
) -> str | None:
    """`Mention(kind="group")` -> one contact id (Design step 6): the
    group's own "most threatening member" (`belief.speech.
    group_membership_state`'s `leading_contact_id`, reused verbatim), or
    any still-resolvable member if that call cannot name one. `None` if no
    member resolves at all (the group itself is gone)."""
    group = next(
        (candidate for candidate in store.groups if candidate.id == group_id), None
    )
    if group is None:
        return None
    state = group_membership_state(store, group, now_sim)
    if state is not None:
        member_contact_ids, leading_contact_id, _differentiated = state
        if leading_contact_id is not None:
            return leading_contact_id
        return _fallback_member_id(store, member_contact_ids)
    # `group_membership_state` itself returned `None` (fewer than two
    # members still resolve) -- fall back over the group's own last-known
    # membership rather than giving up outright.
    return _fallback_member_id(store, group.member_contact_ids)


def resolve_referent(
    store: ContactStore,
    memory: ReferentMemory,
    now_sim: float,
    *,
    has_qualifier: bool,
    qualifier_scope: Callable[[Collection[str]], list[dict[str, object]]],
    active_attack_target_id: str | None,
) -> tuple[str | None, list[str]]:
    """The one resolver every referent-bearing command calls -- mirrors
    `CrewConsole._resolve_follow_target`'s/`_resolve_attack_target`'s own
    `(contact_id, failure_lines)` shape, so callers branch on it
    identically.

    `qualifier_scope` is the caller's own descriptor/clock/sector/
    relative/band filter (`CrewConsole._report_scope`'s `restrict_to_ids`
    mode in production), injected rather than owned here so this module
    stays a pure query over `Mention`s with no dependency on
    `crew_console.py`'s sector/clock tables -- called with exactly the
    mentioned ids still inside the window, never the whole store, and
    expected to return `get_contacts`-shaped fact dicts (each carrying at
    least `"id"` and, when geometry resolved, `"relative_now"`) for the
    ones that still match the qualifier. Not called at all when
    `has_qualifier` is `False`.

    Steps (Design, `plans/that-it-referent/plan.md`):
    1. Prune to the window (via `memory.recent`/`memory.last`). Empty ->
       `render_unable("NO_REFERENT")`.
    2. No qualifier -> the single last-mentioned `Mention` (Decision 2).
    3. A qualifier -> filter the recent mentions' ids through
       `qualifier_scope`, keeping only the `Mention`s whose id survived.
    4. Target-priority: if `active_attack_target_id` is itself among the
       surviving matches, it wins over any other match.
    5. More than one match left -> nearest wins, never ask (the same rule
       `_resolve_follow_target` already uses for its own tie-break).
    6. Group -> single-contact reduction (`_resolve_group_mention`)."""
    recent = memory.recent(now_sim)
    if not recent:
        return None, [render_unable("NO_REFERENT").text]

    matches: list[Mention]
    scoped_facts_by_id: dict[str, dict[str, object]] = {}
    if not has_qualifier:
        last = memory.last(now_sim)
        matches = [last] if last is not None else []
    else:
        ids = {mention.id for mention in recent}
        scoped_facts = qualifier_scope(ids)
        scoped_facts_by_id = {}
        for facts in scoped_facts:
            facts_id = facts.get("id")
            if isinstance(facts_id, str):
                scoped_facts_by_id[facts_id] = facts
        matches = [mention for mention in recent if mention.id in scoped_facts_by_id]

    if not matches:
        return None, [render_unable("NO_REFERENT").text]

    winner: Mention
    if active_attack_target_id is not None and any(
        mention.id == active_attack_target_id for mention in matches
    ):
        winner = next(
            mention for mention in matches if mention.id == active_attack_target_id
        )
    elif len(matches) == 1:
        winner = matches[0]
    elif scoped_facts_by_id:
        # Nearest wins, never ask -- `_resolve_follow_target`'s own
        # tie-break, reused rather than a second "ask" rule for referents.
        def _range_m(mention: Mention) -> float:
            facts = scoped_facts_by_id.get(mention.id)
            if facts is None:
                return float("inf")
            relative_now = facts.get("relative_now")
            if not isinstance(relative_now, dict):
                return float("inf")
            range_m = relative_now.get("range_m")
            return range_m if isinstance(range_m, float) else float("inf")

        winner = min(matches, key=_range_m)
    else:
        # Unqualified branch can never reach here (`matches` has at most
        # one entry there) -- kept as the honest fallback rather than an
        # assert, since a future caller shape could in principle reach it.
        winner = matches[-1]

    if winner.kind == "group":
        contact_id = _resolve_group_mention(store, winner.id, now_sim)
        if contact_id is None:
            return None, [render_unable("NO_REFERENT").text]
        return contact_id, []
    return winner.id, []
