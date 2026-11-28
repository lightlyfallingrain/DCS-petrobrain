"""`OwnWeaponTracker` -- `[[BL-B67]]` Stage 5 (`plans/bl-b67-atgm-run/
plan.md`, "Own-weapon channel, end to end"). Reads `GET /firing/latest`'s
`"own_weapons"` key (`aircraft-layer`'s `OwnWeaponLedger.snapshot`) each
poll and diffs it against what it has already seen, producing exactly one
poll's worth of events: a confirmed launch, a failed launch, whether the
tracked missile's flight just ended, and whether the feed itself is fresh.

**This is the no-omniscience boundary's own second instance, not a third
exception beside `detection_trace_writer.py`** (`body-layer/CLAUDE.md`'s
own invariant list) -- the crew perceives its own launch and impact
through the sight, and this module is where that perception is built.
The Hook's own `seq` counter is an opaque, per-shot identifier, never a
DCS object id, but it is still **never allowed to leave this module**:
`OwnWeaponEvents` carries only `belief.atgm_run.LaunchEvent`/`FailedLaunch`
(no `seq` field at all) plus two plain booleans. `belief/atgm_run.py`
declared those two event types first, as the input shape this module's
real producer would eventually fill (that module's own docstring) --
reusing them here, rather than declaring a second pair, is what keeps
`atgm_run.py`'s own shape unchanged now that a real producer exists.

**A new `seq` is a launch only if it is both a guided weapon and existed
at shot time.** The guided-missile filter (`category`/`guidance`) is
Stage 0's own confirmed values (`category == 1 and guidance == 8`,
`docs/acceptance/2026-11-27-bl-b67-stage0-probe-feedback.md` Q6) --
passed in by the caller (`body.py`, from `atgm.toml`) rather than
hardcoded here, so a second aircraft's own filter is a config change, not
a code change. An unguided new `seq` (S-8 rockets also raise
`S_EVENT_SHOT`) produces no event at all -- it is simply marked seen.

**Baseline, not launch.** Every `seq` already present the first poll this
tracker ever reads a snapshot (or the first poll after `reset_for_new_
mission`) is a baseline: marked seen, never reported as a launch. This
matters because the ledger itself retains an entry for
`OWN_WEAPON_RETENTION_S` after `gone_t` (aircraft-layer's own
`OwnWeaponLedger`), so a tracker that started mid-sortie (or after a
restart) could otherwise see a weapon from *before* it started watching
and misreport it as a fresh launch.

**Freshness is a plain age check against the caller-supplied `now_sim`,
mirroring `naked_eye_source.FIRING_MAX_AGE_S`'s own reasoning for the
same feed** -- this module does not import that constant (it has no
access to a `/world_objects/latest` poll to compare against the way
`naked_eye_source` does), so the caller passes the max-age bound in;
`body.py` passes the same `FIRING_MAX_AGE_S` both callers already share
one feed with."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from belief.atgm_run import FailedLaunch, LaunchEvent


@dataclass(frozen=True, slots=True)
class OwnWeaponEvents:
    """One poll's own-weapon events (plan: `OwnWeaponEvents(launch,
    failed_launch, missile_gone, own_feed_fresh, t_sim)`) -- `t_sim` is
    deliberately not carried here; the caller already has its own poll
    time and `belief.atgm_run.AtgmInputs.now_sim` is where it belongs."""

    launch: LaunchEvent | None = None
    failed_launch: FailedLaunch | None = None
    missile_gone: bool = False
    own_feed_fresh: bool = True


class OwnWeaponTracker:
    """Constructed once per runner, reset only at mission reset
    (`body-layer/CLAUDE.md`'s Co-moving Fields note on this class) --
    `poll()` is the only mutator and the only reader; nothing on this
    class is ever read by `belief/` directly (module docstring's own
    no-omniscience paragraph)."""

    def __init__(self, guided_category: int = 1, guided_guidance: int = 8) -> None:
        self._guided_category = guided_category
        self._guided_guidance = guided_guidance
        self._seen_seqs: set[int] = set()
        self._tracked_seq: int | None = None
        self._has_baseline = False

    def reset_for_new_mission(self) -> None:
        """A genuine DCS mission (re)start -- every `seq` this tracker has
        ever seen belongs to the mission that just ended (the aircraft-
        layer `OwnWeaponLedger` itself clears on the same `dcs_model_
        time_s` regression, but this tracker keeps its own seen-set
        independently, the same "no entry survives a mission boundary"
        posture every per-mission tracker in this codebase takes)."""
        self._seen_seqs = set()
        self._tracked_seq = None
        self._has_baseline = False

    def _is_guided(self, category: int | None, guidance: int | None) -> bool:
        return category == self._guided_category and guidance == self._guided_guidance

    def poll(
        self,
        firing_latest: Mapping[str, Any] | None,
        now_sim: float,
        max_age_s: float,
    ) -> OwnWeaponEvents:
        """One poll's own-weapon events, diffed against what this tracker
        has already seen. `firing_latest` is the raw `GET /firing/latest`
        dict (or `None` if the caller's own fetch failed/degraded this
        poll, the same independently-degradable-feed posture `naked_eye_
        source.py` already takes toward this endpoint) -- `own_feed_fresh`
        is `False` in that case, and the seen-set is left untouched (a
        transient fetch failure must not be mistaken for a mission
        restart's clean slate)."""
        if firing_latest is None:
            return OwnWeaponEvents(own_feed_fresh=False)

        feed_t_sim = firing_latest.get("dcs_model_time_s")
        if not isinstance(feed_t_sim, int | float):
            return OwnWeaponEvents(own_feed_fresh=False)
        fresh = abs(now_sim - feed_t_sim) <= max_age_s

        own_weapons = firing_latest.get("own_weapons")
        if not isinstance(own_weapons, dict):
            return OwnWeaponEvents(own_feed_fresh=fresh)

        current_seqs: dict[int, Mapping[str, Any]] = {}
        for seq_str, entry in own_weapons.items():
            if not isinstance(entry, dict):
                continue
            try:
                seq = int(seq_str)
            except (TypeError, ValueError):
                continue
            current_seqs[seq] = entry

        if not self._has_baseline:
            self._has_baseline = True
            self._seen_seqs = set(current_seqs.keys())
            return OwnWeaponEvents(own_feed_fresh=fresh)

        new_seqs = sorted(seq for seq in current_seqs if seq not in self._seen_seqs)
        self._seen_seqs.update(new_seqs)

        launch: LaunchEvent | None = None
        failed_launch: FailedLaunch | None = None
        launched_seq: int | None = None
        for seq in new_seqs:
            entry = current_seqs[seq]
            category = entry.get("category")
            guidance = entry.get("guidance")
            if not self._is_guided(
                category if isinstance(category, int) else None,
                guidance if isinstance(guidance, int) else None,
            ):
                continue
            type_name = entry.get("type_name")
            shot_t = entry.get("shot_t")
            shot_t_value = shot_t if isinstance(shot_t, int | float) else now_sim
            exists_at_shot = entry.get("exists_at_shot")
            if exists_at_shot is True:
                # The newest guided, existing-at-shot new `seq` this poll
                # becomes the tracked missile -- `new_seqs` is sorted
                # ascending, so the last match wins.
                launch = LaunchEvent(
                    t_sim=shot_t_value,
                    type_name=type_name if isinstance(type_name, str) else None,
                )
                launched_seq = seq
            elif failed_launch is None:
                failed_launch = FailedLaunch(
                    t_sim=shot_t_value,
                    type_name=type_name if isinstance(type_name, str) else None,
                )

        if launched_seq is not None:
            self._tracked_seq = launched_seq

        missile_gone = False
        if self._tracked_seq is not None:
            tracked_entry = current_seqs.get(self._tracked_seq)
            if tracked_entry is not None and tracked_entry.get("gone_t") is not None:
                missile_gone = True
                self._tracked_seq = None
            elif tracked_entry is None:
                # The ledger pruned it (past `OWN_WEAPON_RETENTION_S`)
                # without this tracker ever seeing its own `gone_t` --
                # should not happen at the retention window's own
                # generous size, but failing safe here means "stop
                # tracking", not "silently keep waiting forever".
                missile_gone = True
                self._tracked_seq = None

        return OwnWeaponEvents(
            launch=launch,
            failed_launch=failed_launch,
            missile_gone=missile_gone,
            own_feed_fresh=fresh,
        )
