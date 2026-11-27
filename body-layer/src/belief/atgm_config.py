"""Loads the per-aircraft ATGM data file (`config/sequences/<aircraft-dir>/
atgm.toml`) -- `[[BL-B67]]` Stage 5/6 (`plans/bl-b67-atgm-run/plan.md`,
Affected Modules: "aircraft data... because it is aircraft-specific like
effectors.toml"). Pure, startup-time loading, mirroring `effector_registry.
load_polled_config`'s own shape: a bad or missing file is never fatal (D5's
own posture, restated for this file) -- `load_atgm_config` always returns a
usable `AtgmConfig`, falling back to this module's own code defaults
(unconfirmed-guess values, pre-existing before this file existed) for
whichever part of the TOML is missing or malformed, and collects every
finding rather than raising.

**Why this lives beside, not inside, `effector_registry.py`**: this file
has no `source_element`/raw-dump join at all -- it is plain aircraft data
(a guided-weapon filter, a knob-step map, an object-name exclusion set),
not a cockpit-control registry entry. A shared loader would force this
module's three unrelated tables through a schema built for one."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from belief.effector_registry import DEFAULT_SEQUENCES_DIR, RegistryError

#: Stage 0 sortie Q6 (`docs/acceptance/2026-11-27-bl-b67-stage0-probe-
#: feedback.md`): "guided filter category == 1 and guidance == 8" --
#: the code default `load_atgm_config` falls back to when `atgm.toml`
#: is missing/malformed/absent its own `[guided_filter]` table.
DEFAULT_GUIDED_CATEGORY: Final[int] = 1
DEFAULT_GUIDED_GUIDANCE: Final[int] = 8

#: Q3 (re-probed and confirmed same day): "step n fires Stations[n]" --
#: a 1:1 identity mapping, the code default for `knob_steps`.
DEFAULT_KNOB_STEPS: Final[Mapping[int, int]] = {n: n for n in range(1, 9)}

#: Q2 (exclusion only), confirmed live, Stage 0 sortie.
DEFAULT_OWN_WEAPON_OBJECT_NAMES: Final[frozenset[str]] = frozenset(
    {"Ataka_9M120", "AT_6", "C_8CM", "C_8"}
)


@dataclass(frozen=True, slots=True)
class AtgmConfig:
    """The resolved ATGM data (plan's own three affected-modules items) --
    `knob_steps` is knob step -> payload station index; `own_weapon_
    object_names` is the exclusion set `naked_eye_source` drops before a
    candidate can become a contact."""

    guided_category: int = DEFAULT_GUIDED_CATEGORY
    guided_guidance: int = DEFAULT_GUIDED_GUIDANCE
    knob_steps: Mapping[int, int] = field(
        default_factory=lambda: dict(DEFAULT_KNOB_STEPS)
    )
    own_weapon_object_names: frozenset[str] = field(
        default_factory=lambda: DEFAULT_OWN_WEAPON_OBJECT_NAMES
    )

    def station_for_step(self, step: int) -> int:
        """The payload station index for knob step `step` -- `step`
        itself when `knob_steps` has no entry for it (the identity
        default, never a guess at some *other* mapping)."""
        return self.knob_steps.get(step, step)


def load_atgm_config(
    path: Path,
) -> tuple[AtgmConfig, list[RegistryError]]:
    """Returns `(config, errors)` -- `config` is always usable (module
    docstring); `errors` is empty on a clean load, a missing file, or an
    empty file, and non-empty (but still paired with a usable, code-
    default-filled `config`) on anything else that went wrong."""
    if not path.exists():
        return AtgmConfig(), []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return AtgmConfig(), [
            RegistryError(
                scope="polled-file", name=None, reason=f"cannot read {path}: {exc}"
            )
        ]
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return AtgmConfig(), [
            RegistryError(
                scope="polled-file",
                name=None,
                reason=f"cannot parse {path} as TOML: {exc}",
            )
        ]

    errors: list[RegistryError] = []
    guided_category = DEFAULT_GUIDED_CATEGORY
    guided_guidance = DEFAULT_GUIDED_GUIDANCE
    guided_filter = doc.get("guided_filter")
    if isinstance(guided_filter, dict):
        category = guided_filter.get("category")
        guidance = guided_filter.get("guidance")
        if isinstance(category, int) and not isinstance(category, bool):
            guided_category = category
        elif category is not None:
            errors.append(_entry_error("guided_filter.category", "must be an integer"))
        if isinstance(guidance, int) and not isinstance(guidance, bool):
            guided_guidance = guidance
        elif guidance is not None:
            errors.append(_entry_error("guided_filter.guidance", "must be an integer"))
    elif guided_filter is not None:
        errors.append(_entry_error("guided_filter", "must be a table"))

    knob_steps: dict[int, int] = dict(DEFAULT_KNOB_STEPS)
    knob_steps_raw = doc.get("knob_steps")
    if isinstance(knob_steps_raw, dict):
        parsed: dict[int, int] = {}
        bad = False
        for key, value in knob_steps_raw.items():
            try:
                step = int(key)
            except (TypeError, ValueError):
                bad = True
                break
            if not isinstance(value, int) or isinstance(value, bool):
                bad = True
                break
            parsed[step] = value
        if bad:
            errors.append(
                _entry_error(
                    "knob_steps", "every key/value must be an integer step/station"
                )
            )
        else:
            knob_steps = parsed
    elif knob_steps_raw is not None:
        errors.append(_entry_error("knob_steps", "must be a table"))

    own_weapon_object_names = DEFAULT_OWN_WEAPON_OBJECT_NAMES
    exclusion = doc.get("exclusion")
    if isinstance(exclusion, dict):
        names = exclusion.get("own_weapon_object_names")
        if isinstance(names, list) and all(isinstance(n, str) for n in names):
            own_weapon_object_names = frozenset(names)
        elif names is not None:
            errors.append(
                _entry_error(
                    "exclusion.own_weapon_object_names",
                    "must be a list of strings",
                )
            )
    elif exclusion is not None:
        errors.append(_entry_error("exclusion", "must be a table"))

    return (
        AtgmConfig(
            guided_category=guided_category,
            guided_guidance=guided_guidance,
            knob_steps=knob_steps,
            own_weapon_object_names=own_weapon_object_names,
        ),
        errors,
    )


def _entry_error(name: str, reason: str) -> RegistryError:
    return RegistryError(scope="entry", name=name, reason=reason)


def default_atgm_config_path(
    aircraft_dir: str, sequences_dir: Path = DEFAULT_SEQUENCES_DIR
) -> Path:
    """`config/sequences/<aircraft-dir>/atgm.toml` -- the one path
    `body.py`'s startup wiring needs, mirroring `effector_registry`'s own
    per-aircraft path convention (`aircraft_dir_name`)."""
    return sequences_dir / aircraft_dir / "atgm.toml"


__all__ = [
    "AtgmConfig",
    "default_atgm_config_path",
    "load_atgm_config",
]
