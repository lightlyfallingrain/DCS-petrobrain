"""Generic, tree-wide `DictKey_*` substitution pass.

Real-bytes validation (`mission-interpreter/research/
2026-09-12-miz-validation-against-real-sample.md`) found `DictKey_...`
references throughout the parsed `mission` tree -- not just the four
briefing/sortie fields the secondhand research note anticipated, but also
every trigger-action's user-facing text (`DictKey_ActionText_*`,
`DictKey_ActionRadioText_*`, `DictKey_ActionComment_*`). This module
implements the plan's corrected MI-1 scope: walk the *entire* parsed tree
and replace any string value matching `^DictKey_` via a lookup into
`l10n/DEFAULT/dictionary`'s parsed table, rather than a fixed list of known
fields.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_DICT_KEY_PREFIX = "DictKey_"


def resolve_dict_keys(node: Any, dictionary: dict[str, str]) -> Any:
    """Recursively walk `node` (as produced by `_vendor.dcs_lua.loads`),
    replacing any string value matching `^DictKey_` with its resolved text
    from `dictionary`.

    A `DictKey_...` string with no matching dictionary entry is left
    unchanged (and logged) rather than raised on -- the vocabulary of
    DictKey-bearing fields is not closed (see this module's docstring), so
    treating a miss as fatal would make the whole parse fragile against a
    field this session's one sample mission simply didn't happen to use.

    Returns a new structure; does not mutate `node` in place (dicts/lists
    from `_vendor.dcs_lua.loads` are ordinary mutable Python containers, but
    treating parse output as immutable-in/immutable-out keeps this pass
    safe to reuse or re-run without aliasing surprises).
    """
    if isinstance(node, dict):
        return {
            key: resolve_dict_keys(value, dictionary) for key, value in node.items()
        }
    if isinstance(node, list):
        return [resolve_dict_keys(item, dictionary) for item in node]
    if isinstance(node, str) and node.startswith(_DICT_KEY_PREFIX):
        resolved = dictionary.get(node)
        if resolved is None:
            logger.warning("DictKey %r has no entry in l10n/DEFAULT/dictionary", node)
            return node
        return resolved
    return node
