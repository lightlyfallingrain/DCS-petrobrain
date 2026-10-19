# BL-B68 — Belief survives a DCS mission restart, because nothing resets it

- [~] **The collector holds every piece of belief state in plain dataclass fields with no lifecycle
  hook, so a DCS mission reload inside one service run carries the whole of the previous mission's
  belief into the next one.** #status/in-progress Diagnosed 2026-10-15 from the user's own test
  flight; full evidence in `plans/position-belief-runaway/debug-2026-10-15.md`.

  **Deferred by user direction, 2026-10-15:** *"defer mission end/start mechanics. We'll do them at
  some point, not now."* Filed so the diagnosis is not re-derived.

  **Scheduled 2026-10-19 as [[BL-15]] Stage 1 — fixed on `feature/bl15-mission-start`, DoD-passed
  2026-10-19, pending merge to `main`** (DoD acceptance testing with the user is the step
  remaining before that merge — see `plans/bl15-mission-start/dod-check.md`). Every item in the
  "Everything that carries over" table below is covered by `logger._reset_mission_state`/
  `reset_for_new_mission()` on each class named, confirmed by Reviewer against this table
  explicitly (`plans/bl15-mission-start/review.md` Batch 1). **This entry stays `[~]`/in-progress,
  not `[x]`, for two reasons: the merge itself has not happened yet, and the live sortie
  confirming the fix in the cockpit has not happened either** — the second is tracked on
  `[[BL-15]]` itself as `#needs-flight`, not duplicated here as a second debt marker. Mark `[x]`/
  `#status/done` once merged and that sortie clears.

  **How it presented.** The belief-truth tripwire fired on 18 contacts at ranges of ~532 km against
  a 10 km cap, with *small* position uncertainties (26–609 m) — belief confidently wrong, not vaguely
  wrong. The user's eyesight view showed every believed contact at the same bearing, −070°, 529–531 km.

  **What it actually was.** One log file held **three flights with the services never restarted**
  (`t_sim` resets twice in the detection trace, once in the belief-truth log). Splitting the
  belief-truth log at the reset:

  | segment | `t_sim` | rows | distinct contacts | tripwires |
  |---|---|---|---|---|
  | previous flight | 0.4 … 1,635.4 | 3,088 | 67 (ids 1–68) | **none** |
  | the flown mission | 0.0 … 140.1 | 871 | 22 (ids 5–72) | 18 |

  **Every tripwire contact in the new flight already existed before the reset; not one was new**, and
  contact ids continued (5…72) rather than restarting at 1. Stale contacts held believed positions
  that were correct *for the mission in which they formed* and ~532 km from the new ownship.

  **Perception was not at fault and neither was the tripwire.** The new mission's own far-away units
  were correctly rejected by the player bubble (`outcome: player_bubble`, `observation_id: null`) and
  never reached belief — which is what the user expected (*"the group far away should never even
  enter the belief layer"*). The tripwire caught a genuine stale-state defect and needs no change.

  ## Everything that carries over, not just contacts

  This is the part worth having written down, because **a reset that clears `ContactStore` alone
  would leave a second, quieter bug behind.** All of these are plain fields on
  `ConsolePerceptionRunner` (`body-layer/src/logger.py:323-463`) with no hook that clears them:

  | state | what goes stale |
  |---|---|
  | `store: ContactStore` | the confirmed defect; nests `GroupStore`, so group identity is stale too |
  | `tasks: TaskStore` | a pending `scan_area`/`watch_contact`/`attack_target` referencing a contact id that no longer means anything |
  | `attack_run_state` | **the most likely second bug** — an engaged attack run survives, holding a target contact id that is itself stale |
  | `optic_state: OpticState` | the binocular cycle's phase, and `BL-B64`'s new aim fields |
  | `scan_plan: ScanPlan` | a scan pattern set by an F10/voice command continues instead of resetting to `FREE_SCAN_PLAN` |
  | `mission_phase_tracker` | `BL-7`'s phase, computed against the previous mission's structure |
  | `enrichment: EnrichmentContext` | `WorldEnrichmentCache`, designed to persist across polls, never across missions |
  | `attitude_history` | the steadiness gate's rolling window, mixing the end of one mission with the start of the next |
  | `optic`, `_last_look_direction` | last-resolved optic and last look direction pushed to the Hook |
  | both sources' dedup maps | `_object_id_to_last_observation_id`, `_last_emitted_texts`, counters — and these feed the object-permanence shortcut, so they interact with the gap below |

  ## Open design questions, deliberately not answered

  - **Where does the reset belong** — body-layer detecting the discontinuity, or aircraft-layer
    signalling a new mission explicitly? The second is more honest if the export side can know it,
    but it is a cross-subproject change.
  - **Is "`t_sim` went backwards" a safe trigger?** It can plausibly fire on a pause, a time-accel
    change, or a reconnect to a running mission. **A reset firing wrongly mid-flight would wipe real
    belief, which is worse than the bug it fixes** — so the trigger needs more care than the symptom
    suggests.

  ## Workaround until it lands

  **Restart the body-layer service between missions.** The user was told this; it is why the
  `[[BL-B64]]` acceptance card carries the same note — otherwise stale contacts contaminate a sortie
  flown to judge perception.

  Related: `[[BL-B69]]` (the object-permanence distance gap, same investigation), `[[BL-14]]`
  (whose `attack_run_state` is the second-order risk above), `[[BL-B64]]` (whose acceptance sortie
  needs the workaround).
