# BL-B67 — The 9K113 sight, entry 3 of 3: the ATGM attack run

- [ ] **BL-B67 — The ATGM attack run on the 9K113: azimuth-only guidance, in-range/out-of-range,
  the launch callout, impact, and resetting the guidance transmitter.** #status/open
  **Specification: `docs/concept/9K113.md`** plus
  `docs/acceptance/2026-10-15-9k113-sight-direction.md` §5.
  **Missile data: `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`, "Addendum,
  2026-10-15"** — the user supplied the sources himself and the speed/range gap is closed.

  Minted 2026-10-15 from the `[[BL-B64]]` split (user direction §5: *"Only then can we add the ATGM
  attack run"*). **Entry 3 of 3, and deliberately last.** Kept thin on purpose — this is not
  designed yet, and should not be until entries 1 and 2 have landed.

  ## Hard preconditions, all of them outside this entry

  - **`[[BL-B64]]`** — there is no 9K113 optic without it. From the `BL-14` explore: *"ATGM guidance
    is with 9K113 only, there is no naked eye channel for ATGM guidance."*
  - **`[[BL-B66]]`** — the whole of the effector axis. The run arms a circuit, selects a pylon and
    slews a real sight.
  - **`[[BL-B65]]`** — the weapons safety circuit switch (arg 673), which the specification requires
    be its own item before the run.
  - **`[[BL-B63]]`** — *"this is where the selective fast lane stops being optional."* The run slews
    the **sight** to track a moving unit, a second inspect-and-adapt loop against a 1.0 s poll, and
    the user named 9K113 missile guidance as that fast lane's second consumer explicitly.
    (`AC-B3` is not a prerequisite — the dependency runs the other way; see its own entry.)

  ## What reuses `[[BL-14]]`, and what differs

  **Most of it reuses `BL-14`** — the register rules from
  `docs/acceptance/2026-10-14-attack-run-guidance-direction.md`: o'clock outside the ±15° sector,
  qualitative *"come left"* / *"a bit right"* inside it, one *"lined up"* then silence, the
  `", obstructed"` qualifier composing onto any tier-1 utterance, change-driven cadence, one voice
  with the inter-utterance gap, and **one contact is the target** (mechanically forced here too —
  one crosshair cannot point at two units).

  Where it differs:

  - **Azimuth only**, which removes `BL-14`'s vertical half entirely, so its aligned conjunction
    becomes a single gate. A real departure from what shipped; flag it rather than inheriting it
    silently.
  - **The target is tracked, not held.** `BL-14` guides the *aircraft*; this also slews the *sight*.
  - **New utterances with no `BL-14` analogue**: *"in range"* / *"out of range"* (once each), the
    launch callout, *"impact"* (with hit/miss if detectable), and the transmitter reset 1 s later
    (arg 882, `LAlt+R`).
  - **A 400 m minimum range** that both missile families share and that `BL-14` has no concept of.

  ## Target selection is now harder than the first plan assumed

  **User direction §2 establishes there is no elevation readout on the sight at all** — only an
  azimuth arc. `BL-14` uses the vertical axis as a *discrimination* aid for picking the right unit;
  the 9K113 crewman cannot read one. So **ATGM target selection cannot discriminate vertically the
  way `BL-14` does, and selection has to come from somewhere else.** That has to be solved in this
  entry rather than assumed away, and it is the main reason this entry is not thin by accident.

  Note also that `[[BL-B62]]`'s relative-direction channel names **this** entry as its candidate
  consumer — *"a tracking task, not a describing one"* — and should be built on from the start rather
  than retrofitted. That needs a non-zero `RELATIVE_DIRECTION_SIGMA_DEG` (`BL-14` ships it at `0.0`,
  defensible for a commanded bounded manoeuvre and not for routine output) and replaces `BL-14`'s
  two-file grep fence with a considered rule rather than deleting a test.

  ## The missile data gap is closed; two open decisions remain the user's

  From the 2026-10-15 addendum: **Shturm 345 m/s, 400–5,000 m; Ataka 400 m/s average (550 peak),
  400–6,000 m**, so flight time is computable (~14.5 s to 5 km, ~15 s to 6 km). The earlier interim
  — speak the missile word, suppress the time and the range callouts — **loses its premise** and was
  correct only while the numbers were unknown.

  - **The missile word is a loadout read, not a constant.** *"Hind can carry **either** 9K114 Shturm
    **or** 9M120 Ataka."* "Shturm" is right *today* only because DCS has not shipped the Ataka
    family; derive from the loaded store and fall back to generic `"missile"`.
  - **Speed and max range belong in `X-T26`'s configurable set as two per-family profiles**, not as
    inline numbers — the ~40% speed difference is large enough to be audible in a spoken flight time.
  - **One caution that keeps the original reasoning alive:** these are Wikipedia figures, not DCS's
    own weapons tables. An unverified community number must not be encoded as fact, so **DCS's
    shipped `db_weapons*.lua` remains the authoritative read** — a file read, not a flight — before
    any of these numbers reaches a callout the pilot trusts.
  - Two decisions carried from `plans/9k113-sight/plan.md` (its Decisions 4 and 5) are this entry's
    to settle, not `BL-B64`'s: **which missile word to speak**, and **the flight-time callout's
    interim**.

  **Readback note (`[[BL-B90]]` Stage 4, 2026-10-24):** arg 962 (launch permission lamp) and arg 673
  (the weapons safety bar) are no longer read continuously by anything after Stage 4 —
  `push_cockpit_switch_state` is gone, and `GuidanceUnitState.launch_perm_observed`/
  `weapon_safety_observed` currently have no reader. This entry chooses, for each, whether it goes
  into `body-layer/config/sequences/mi-24p/polled.toml` (continuous, if the run needs to react to a
  state change on its own) or is read at need via a trigger's own one-shot read (if it is only ever
  checked at a specific moment, e.g. "launch permission at the moment of firing").

  ## 2026-10-26 update — explore run, behaviour settled

  `/explore` ran 2026-10-26: `plans/bl-b67-atgm-run/explore-notes.md` (the user's words, verbatim)
  **now governs where it differs from this entry.** In short:

  - **"Target selection is now harder" is struck** (*"Elevation - drop"*): `BL-14`'s `select`/`step`
    never used elevation, so the missing elevation readout costs selection nothing.
  - **Missile data: Wikipedia figures accepted** (*"Wikipedia is good enough approximation"*) — the
    `db_weapons*.lua` read is no longer owed.
  - **`RELATIVE_DIRECTION_SIGMA_DEG` stays `0.0`** for this run. Always a single unit, never a
    cluster — so the aim point must be one unit's position, not a cluster centroid.
  - **Launch** = pilot's launch button **and** loadout −1 (both; jettison is not a launch).
    **Impact** = the launched missile's object leaving the DCS object list, any cause.
    Damage reporting is a later stage. The missiles are radio-guided.
  - `engage … missiles` = ATGM run. After impact: keep tracking, select next missile. Last one gone:
    *"No more missiles"*, keep tracking for guns/rockets. Silence in flight; no range warnings at
    launch. End of run: missile selector OFF, OBSERV stays on. Selector touched only for an ATGM run.
  - **Mi-24P quirk:** cannon selected on the pilot's selector and OBSERV ON are mutually exclusive.
    What Petrovich does on a refusal is **deferred**.
  - **`[[BL-B63]]` is no longer a precondition** — `[[BL-B66]]`'s 2026-10-21 note dropped it once the
    AI-axis per-frame writes moved into Lua; the list above predates that.

  Still owed before a plan: args from the user (pylon selector, launch button, extra readers),
  desk recon (loadout read, launched-missile id), and `[[BL-B80]]` Flight A.

  Related: `[[BL-B64]]`, `[[BL-B66]]`, `[[BL-B65]]`, `[[BL-B63]]`, `[[BL-B62]]`, `[[BL-14]]`,
  `[[BL-B90]]`.
