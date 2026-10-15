# BL-B66 — The 9K113 sight, entry 2 of 3: effectors

- [ ] **BL-B66 — Make the real cockpit systems move: the warm-up sequence, OBSERV as an actual mode,
  the slew closed loop, and pinpoint-on-request. Everything that is visible to the pilot in the
  cockpit rather than only inside Petrovich's head.** #status/open
  **Specification: `docs/concept/9K113.md`** plus
  `docs/acceptance/2026-10-15-9k113-sight-direction.md` §5, §8.
  **Reconnaissance: `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`** — the full
  11-switch sequence, the 3–4 min and 10–15 s timings, and the device/command/argument numbers.

  Minted 2026-10-15 from the `[[BL-B64]]` split (user direction §5: *"We'll then add actually
  manipulating the systems in cockpit"*). Entry 2 of 3; `[[BL-B64]]` is perception, `[[BL-B67]]` is
  the attack run. **Sequenced after `BL-B64` and before `BL-B67`, by his explicit ordering.**

  ## The probe that is owed, and it belongs here rather than earlier

  **Run an `investigator` pass before this entry is planned, not before `BL-B64`.** The question:

  - Can `performClickableAction` actually move args **673 / 955 / 885 / 886 / 963** on **`WEAP_SYS`
    (device 6)** and **`I9K113` (device 7)**, and does the lamp state follow?
  - Does `list_indication` on `ccGunnersCPanel` (**index 8, never tried**) read the `READY` lamp?

  **Why it is not run yet.** The write channel is proven live only on **device 30** (the AI wheel)
  and **device 55** (SPU-8) — every argument number in the warm-up table is cross-referenced from a
  2026-09-11 probe of a *different device set*, and the numbers are **positional**, so an ED patch
  inserting a table entry shifts them. Regenerate before coding against them. This is the single
  largest risk in the 9K113 series and the whole reason perception was separated out ahead of it.

  ## What this entry contains, in dependency order

  1. **The cockpit-action channel.** A new `op` on `Export.lua`'s existing inbound command listener
     (`poll_command_socket`, which already dispatches `petrovich_search` and already calls
     `performClickableAction` live), plus 9K113 state args **874/876/886** pushed as telemetry with
     the change-epsilon pattern `push_spu8_state` established. Spans
     `aircraft-layer/dcs-export/Export.lua`, `src/collector/command_sender.py`, `src/api/server.py`,
     `src/schema/`, and `body-layer/src/aircraft_client.py`. **HTTP/JSON across the subproject
     boundary**, as aircraft-layer ↔ body-layer already does.
  2. **Warm-up and OBSERV as real modes.** The 3–4 min and 10–15 s timings are **two timers** — the
     research note is explicit that collapsing them is wrong — with the *"Guidance unit ready"* and
     *"Observ on/off"* callouts, and the constraint that OBSERV is not left on. **If the lamp probe
     comes back negative, readiness is a timer Petrobrain owns**: honest, and the manual itself
     presents the timing as elapsed-time gates.
  3. **The slew closed loop** — reading args 874/876 back and writing the AI axis (3060/3061).
     **876's degrees-per-unit is unmeasured**: the raw read is confirmed, the conversion is not, so
     elevation slew is not plannable to a degree today. Note that the AI axis (3060/3061) is
     *position* while the player axis (3025/3026) is *velocity* — do not generalise one from the
     other.
  4. **Pinpoint-on-request** — the surviving non-ATGM use.

  ## What this entry does *not* contain

  - **The ASP-17 crosshair-hold use case. It does not exist as work.** User direction §1:
    *"ASP-17 must not be manipulated directly. It shows the pilot where the 9K113 is pointing, but
    that's automatic, not manual."* The mark follows the sight's pointing by itself, so there is no
    action to build, no `AUTO/MAN` switch step (arg 553) and no PUVL selector step (arg 523) needed
    for it. It is a **consequence** of this entry, not a deliverable of it. The earlier plan treated
    it as one of two non-ATGM uses; that was wrong and is marked superseded in
    `plans/9k113-sight/plan.md`.
  - **The slew *rate limit*** — `plans/9k113-sight/plan.md` §15 recommends that live in `BL-B64`,
    because the 20 km cone consumes the pointing direction and an instantly-teleporting sight would
    be an omniscience leak. This entry owns the closed loop that checks where the sight *actually*
    went, which is the half that needs the unmeasured conversion. Open decision 6 in that plan.
  - **`[[BL-B65]]`** (the weapons safety circuit switch, arg 673) stays its own entry, as the
    specification requires, and gates `[[BL-B67]]`.

  ## Acceptance is unusually expensive, and that shapes the work

  **~3 minutes of warm-up before anything is testable**, plus a failure mode the specification does
  not model: a gyro toppled by an excessive-rate manoeuvre needs `GUID.UNIT POWER` cycled and
  **another 3–4 minutes**. A single mistake mid-test costs a full reset. **Budget acceptance in
  sorties, not in attempts, and build the flag-gated debug logging up front** rather than bolting it
  on after the first failed sortie.

  ## Second-order effect

  If built, this makes the cockpit-write channel a **general facility**: the SPU-8 and AI-wheel
  channels are each one-off, and a sequenced switch-action op would be the first reusable one, which
  `[[BL-B65]]` and anything else cockpit-side would inherit.

  Related: `[[BL-B64]]` (entry 1, perception — must land first), `[[BL-B67]]` (entry 3),
  `[[BL-B65]]` (gates entry 3), `[[BL-B63]]`/`AC-B3` (the selective fast lane — a dependency of
  `BL-B67`, not of this entry).
