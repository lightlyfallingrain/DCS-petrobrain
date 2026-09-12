"""Raw `trigrules' `predicate`-string tree, parsed directly per Decision
1a (not through pydcs's `TriggerRule`/condition/action wrapper classes).

The real schema (`mission-interpreter/research/2026-09-12-miz-validation-
against-real-sample.md`): each rule carries a rule-kind `predicate`
(`triggerStart`/`triggerOnce`/`triggerContinious` [DCS's own spelling] /
`triggerFront`), a `rules[]` list of nested conditions (each a dict with
its own `predicate`, prefixed `c_`, or the boolean combinator
`predicate = "or"`), and an `actions[]` list (each a dict with its own
`predicate`, prefixed `a_`). 39 unique predicate strings were observed in
the one sample examined -- a closed, greppable vocabulary, but undocumented
by ED and possibly not exhaustive across DCS versions/authors.

This module does not re-parse `miz.tree.TriggerRule` (that dataclass
already carries `conditions`/`actions` as raw dicts) -- it provides the
predicate-inspection helpers `filter.crew_available` needs to reason about
whether a rule's actions could reveal a hidden/late-activated group's
existence, tolerating unrecognized predicates by treating them as
"unknown, do not assume safe" rather than failing the whole parse.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from miz.tree import TriggerRule

#: Rule-kind predicates confirmed against the real sample. A `TriggerRule`
#: whose `predicate` is not one of these is still parsed (the field is
#: preserved verbatim on the dataclass) but is flagged by
#: `is_recognized_rule_kind` as unrecognized, not silently treated as one
#: of these four.
KNOWN_RULE_KINDS: frozenset[str] = frozenset(
    {"triggerStart", "triggerOnce", "triggerContinious", "triggerFront"}
)

#: Condition/combinator predicates confirmed against the real sample
#: (prefixed `c_`, plus the `"or"` combinator). Not exhaustive -- see
#: module docstring.
_CONDITION_PREFIX = "c_"
_ACTION_PREFIX = "a_"
_OR_COMBINATOR = "or"

#: Action predicates that spawn or reveal a group -- the ones
#: `filter.crew_available` treats as a potential author-only-knowledge leak
#: if they reference a hidden/late-activated group. Extracted from the real
#: sample's `a_*` vocabulary; this list is deliberately conservative (only
#: predicates whose name unambiguously implies bringing something into
#: existence or visibility) rather than an exhaustive translation of all 39
#: observed predicates, since most (`a_out_text_delay`, `a_set_flag`, ...)
#: have nothing to do with unit existence at all.
GROUP_REVEALING_ACTION_PREDICATES: frozenset[str] = frozenset(
    {"a_activate_group", "a_spawn_group", "a_respawn_group"}
)


def is_recognized_rule_kind(predicate: str) -> bool:
    return predicate in KNOWN_RULE_KINDS


def is_condition_predicate(predicate: str) -> bool:
    return predicate.startswith(_CONDITION_PREFIX) or predicate == _OR_COMBINATOR


def is_action_predicate(predicate: str) -> bool:
    return predicate.startswith(_ACTION_PREFIX)


def action_predicate_of(action: Mapping[str, Any]) -> str:
    """The `predicate` field of one raw `actions[]` entry, or `""` if
    absent (malformed action, not expected in a real mission file but not
    worth raising over -- `filter.crew_available` treats an unrecognized/
    empty predicate as "not known to be safe" the same way)."""
    return str(action.get("predicate", ""))


def reveals_group(rule: TriggerRule, group_name: str) -> bool:
    """Whether `rule` has any action predicate in
    `GROUP_REVEALING_ACTION_PREDICATES` that references `group_name` by its
    `group`/`groupName` argument. Used only for research/debugging
    inspection of `trigrules` -- never to decide what reaches the
    crew-available tree (that decision is made purely from each group's own
    `hidden*`/`lateActivation` fields, per `filter.crew_available`'s
    deny-by-default posture)."""
    for action in rule.actions:
        if action_predicate_of(action) not in GROUP_REVEALING_ACTION_PREDICATES:
            continue
        referenced = action.get("group") or action.get("groupName")
        if referenced == group_name:
            return True
    return False
