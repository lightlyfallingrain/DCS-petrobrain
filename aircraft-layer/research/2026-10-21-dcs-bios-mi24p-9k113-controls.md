# DCS-BIOS Mi-24P 9K113/weapons controls, and DCS-BIOS as a dependency

**Date:** 2026-10-21
**DCS version:** not verified locally this session — no DCS install reachable from this worktree.
DCS-BIOS's own arg/device/command numbers are positional and were read from its source, not from
a live DCS probe; treat every number below as "what DCS-BIOS's authors currently believe", not as
independently re-verified against the installed Mi-24P.
**Theatre:** n/a (cockpit-only question)

### Question

1. Is the READY/`READNS.` sight-readiness lamp readable as a cockpit draw argument via
   `GetDevice(0):get_argument_value(<arg>)`, the way DCS-BIOS reads every lamp? If so, which arg?
2. Is DCS-BIOS's number for `CPLR DISTR` (our guess: 761, device `ASP_17V`) corroborated?
3. Does DCS-BIOS cover the sight-head-angle readouts (874/876) or other 9K113 readouts?
4. (Added mid-task, user direction) Should Petrobrain depend on DCS-BIOS at runtime instead of its
   own Export.lua command-socket/telemetry path, for `BL-B66`/`BL-B80`/`BL-B67`?

**Source read:** `github.com/DCS-Skunkworks/dcs-bios`, commit `b5d0aa45a980909a6823562012f344cf7cfdd2a7`
(shallow clone, `HEAD` at fetch time 2026-10-21; commit date 2026-10-18, an unrelated Mosquito fix —
the shallow clone does not give true per-file history, so "last touched" for `Mi-24P.lua` specifically
could not be established beyond "present and loaded at this HEAD"). This is the DCS-Skunkworks
continuation of the original (now unmaintained) DCS-BIOS, per its own README.

---

### Findings — Q1: the READY lamp

**Still not corroborated as readable, and DCS-BIOS's own coverage gap is evidence (weak, not proof)
that no draw argument exists for it.**

- **Mechanism confirmed — evidence: documented (DCS-BIOS source).** Every DCS-BIOS lamp/switch/gauge
  output is driven by one call shape, in `Scripts/DCS-BIOS/lib/modules/Module.lua`:
  `local arg_value = dev0:get_argument_value(arg_number)`, run inside an "export hook" invoked once
  per DCS-BIOS export tick from `LuaExportAfterNextFrame`. `dev0` is `GetDevice(0)` — the
  whole-aircraft device that exposes *any* draw argument, not just ones "owned" by a particular
  device id. `defineIndicatorLight(id, arg, ...)` is sugar for a gated read: lamp is "on" when
  `arg_value` falls in `[min, max)` (default `< 0.3` = off-state excluded, i.e. lit above ~0.3).
  **No DCS-BIOS lamp anywhere in the Mi-24P module is read via `list_indication`** — that mechanism
  does not appear in the module at all. This matches our own probe's access pattern for 874/876 and
  confirms there is no second, alternate read path DCS-BIOS knows about that we have not tried.
- **DCS-BIOS has no entry for a sight-readiness/`READNS.` lamp — evidence: documented (absence in
  source), inference about *why* is ours.** Searching the full I9K113 ("sight") block
  (`Mi-24P.lua` lines 593–659) for every indicator light finds: `SHTV` tablo lights (917–930),
  `SCHO` lights incl. `OP_SCHO_RDY_L` (960, "SCHO READY Light", green — the *weapon/missile system*
  ready lamp, not the sight), `PK` lights L1–L14 (888–904), and `L166B WORK`/`FAIL` (868/869). None
  of these is the sight's own post-warm-up readiness lamp the procedure text calls `READNS.`.
  DCS-BIOS has mapped the Mi-24P exhaustively enough to cover minor tablo lights most players never
  touch, which makes a true gap less likely than usual — **but absence from a third-party survey is
  not proof of unreadability; it only shows nobody (including this well-resourced community project)
  has found an arg number for it.** If the lamp's state only reaches the player through a native
  function call (consistent with our own probe's `Ready_9k113` scene node carrying no value, and the
  previously-identified native-only `isGyroReady()`/`isLaunchPermission()` getters), then **no draw
  argument exists for it at all**, and neither DCS-BIOS nor any further `get_argument_value` probing
  from us would ever read it — this would not be a DCS-BIOS limitation, it would be a limitation of
  what the module's clickable-cockpit data exposes to Lua in general.
- **Conclusion for Q1: the prior finding stands.** `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`
  §4's "READY lamp is not readable" is not overturned; DCS-BIOS's silence on it is a second,
  independent data point in the same direction (**evidence: inferred**, from an absence, not a
  positive test), not a new readable arg. **What would resolve it properly**: a brute-force scan —
  `for a = 1, 2000 do print(a, GetDevice(0):get_argument_value(a)) end` logged before and after a
  real ~5-minute warm-up, diffed for anything that flips from 0→1 around the warm-up boundary and
  nothing else (filtering out 874/876 motion noise). This is a probe we have not run and DCS-BIOS's
  source does not substitute for it.

### Findings — Q2: `761` / `CPLR DISTR`

**Corroborated as a real, mapped control — but what it *is* remains short of full confirmation.**

| DCS-BIOS identifier | device id | command | arg | type | description |
|---|---|---|---|---|---|
| `OP_USR_PW` | 16 (`ASP17`) | 3015 | **761** | toggle switch | "OPERATOR USR power" |
| `OP_USR_CHECK` | 16 (`ASP17`) | 3016 | **762** | toggle switch | "OPERATOR USR check" |

— **evidence: documented** (`Mi-24P.lua` lines 672–673).

- **Device agrees with the user's correction, not with the recon table's original pointer name.**
  `2026-10-17-9k113-procedures-direction.md` records the user rejecting 761 *conditionally* —
  *"761 is wrong, if it sits on ASP_17V"* — and the note's counter-argument was that device
  ownership (ASP-17 computer) is plausible for a weapons distributor regardless of seat. DCS-BIOS
  independently assigns 761 to device 16, which that note's own header table (§3) already equates
  to `ASP_17V`. **Two independent readings (the pointer-name guess and DCS-BIOS's own survey) now
  agree the argument sits on the ASP-17 device**, which raises confidence the number is real and
  correctly owned, without yet confirming what it *does*.
- **What is not confirmed: that "USR" means "coupler/distributor".** DCS-BIOS's own description is
  just "USR power" / "USR check" — it does not expand the acronym and gives no further hint. "USR"
  is not a term independently verified in this session against any Mi-24P systems manual; it could
  plausibly be a transliteration of a Russian subsystem abbreviation related to signal distribution,
  but that reading is **inferred, not documented** anywhere read this session. The project's own
  prior note already names 761 as "probable," not settled, and that status is unchanged by this
  finding — it is corroborated, not confirmed.
- **762 is real and sits next to 761 on the same panel**, which is relevant to the "OPER/TEST1/TEST2"
  part of the question: DCS-BIOS names it a plain toggle ("USR check"), not a 3-position
  TEST1/NEUTRAL/TEST2 selector. **A better match for a 3-position test selector already exists
  elsewhere in the module and was already partly identified in the prior research note**: `905`
  (`OP_SIGHT_CHECK`, device 7 `I9K113`, 3-position, "Sight CHECK2-NEUTR-CHECK1") and `903`
  (`OP_SIGHT_CHECK_BTN`, same device, toggle, "Sight WORK-CHECK"). **If "OPER/TEST1/TEST2" in the
  quickstart procedure refers to the sight's own check selector rather than the ASP-17's USR check,
  905/903 are the better-fitting args, not 762.** This is a disagreement worth flagging rather than
  silently resolving — both are real, mapped controls; which one the quickstart text means is a
  reading-of-a-manual question, not something this session can settle from DCS-BIOS alone.
- **The remaining Q2 sub-question, `L166V POWER`, is still unmapped.** No DCS-BIOS control in the
  Mi-24P module is named for an `L166V`-style device-power switch distinct from `OP_SIGHT_PW` (885).
  There are `OP_L166B_WORK_L` (868) and `OP_L166B_FAIL_L` (869) — indicator lights only, named
  `L166B` not `L166V`, and they are outputs, not a power switch. Consistent with the existing
  decision to drop `L166V POWER` from the buildable sequence rather than keep guessing at it.

### Findings — Q3: sight-head-angle readouts and other 9K113 readouts

- **874/876 are mapped, and as floats, not lamps — evidence: documented.**
  `Mi_24P:defineFloat("OP_SIGHT_AZI", 874, { -1, 1 }, "I9K113 Gauges", "OPERATOR Sight Azimuth")`
  and the elevation equivalent at 876, both on the generic float-gauge code path
  (`dev0:get_argument_value(arg_number)` directly, range `{-1,1}`). This matches our own probe's use
  of 874/876 exactly — same access pattern, same arg numbers, same range — and is independent
  corroboration that these two numbers and their semantics are correct.
- **Confirmed, additionally, which full set of 9K113 switches/lamps DCS-BIOS maps** (device 7
  `I9K113` unless noted): `OP_SIGHT_PW` 885 (matches our "Sight Power"), `OP_SIGHT_OBSERVE` 886
  (matches "OBSERV"), `OP_SIGHT_BACK_L` 884, `OP_SIGHT_DIAFR` 887, `OP_SIGHT_LOCK_ARU` 912,
  `OP_SIGHT_SSP` 913, `OP_SIGHT_GEN` 910, `OP_SIGHT_CHECK` 905 / `OP_SIGHT_CHECK_BTN` 903,
  `OP_SIGHT_PM_START` 911, `OP_BVK_SET` 899, `OP_SIGHT_HEAT` 890, `OP_SIGHT_ZOOM` 871,
  `OP_SIGHT_FILTER_ORG` 872, `OP_SIGHT_FILTER_LASER` 873, `OP_SIGHT_MISL_HEAT` 775 (named "Sight
  Doors" — matches our "905 gyro-door" context from the prior note), `OP_SIGHT_L_CHECK` 870 (3-pos,
  "Sight Lamps Check CHECK2-NEUTR-CHECK1" — matches the prior note's "L166V-SWITCH-PTR" guess
  closely enough that the pointer-name/physical-function match looks right even though the pointer
  name itself was flagged as possibly stale), plus the `SHTV`/`PK`/`L166B` lamp banks above. On
  device 6 `WEAP_SYS`: `OP_MISSL_PW` 773 (matches "MISSILE POWER"), `OP_SCHO_PW` 955 (matches "ЩО
  PWR"), `OP_SCHO_L_CHECK` 956 (matches the prior note's correction of the TEST-LAMPS button away
  from 870), `OP_MAIN_WPN_SAVE` 673 (matches "SAFETY SWITCHES ARMAMENT CIRCUITS" / our safety bar).
  **All seven of the arg numbers this project had already committed to (773, 885, 886, 955, 956,
  673, and 874/876) are independently corroborated by DCS-BIOS's own survey — none disagree.**
- **No 9K113 readout beyond 874/876 is mapped as a float/gauge.** No arg for missile-in-flight
  state, launch countdown, or anything resembling telemetry of a fired 9K113 round appears in the
  module — consistent with this being out of DCS-BIOS's and our own current scope (effector/launch
  telemetry would come from `LoGetWorldObjects`/weapon tracking, not cockpit draw args).

### Licence

**GPL-3.0**, confirmed from the repository's own `LICENSE` file (full GPLv3 text) and the README's
own statement: *"Distributed under the `GPL 3.0` license."* (The README's badge image reads "MIT
License" — that is a stale/wrong shield graphic, contradicted by the README's own prose and the
actual `LICENSE` file two lines later; do not trust the badge over the file.) **Practical
implication for Architect, not a decision made here:** copying DCS-BIOS's *Lua code* verbatim would
pull GPL-3.0 obligations into this project. Copying its *factual tables* (which arg number maps to
which switch) is lower-risk — argument numbers are facts about DCS's own cockpit, not DCS-BIOS's
creative expression — but "citing a fact learned by reading GPL'd source" vs. "reproducing GPL'd
source's own documentation tables verbatim" is a licensing line Architect/the user should draw
explicitly if this project ever ships a derived table file, rather than this note assuming either
side of it.

---

### Section 4 (added mid-task): DCS-BIOS as a runtime dependency, instead of our own Export.lua path

**Scope:** could DCS-BIOS replace, in whole or part, `aircraft-layer`'s own Export.lua
command-socket + telemetry-push chain for `BL-B66`/`BL-B80`/`BL-B67`? Evidence below; recommendation
at the end.

#### Protocol — what DCS-BIOS actually carries, and at what rate

- **Output (telemetry) — evidence: documented (source).** DCS-BIOS exports a custom binary stream
  (sync word `0x55 0x55 0x55 0x55` + address/count/data, from `BIOSStateMachine.lua`), sent two ways
  simultaneously, both configured in `Scripts/DCS-BIOS/BIOSConfig.lua`:
  - **UDP multicast**, default `239.255.50.10:5010` (send), with a receive port `7778` for commands
    on the same UDP connection.
  - **TCP**, default port `7778`, full-state-on-connect then incremental diffs.
  - **Rate: `export_rate = 30`, "export count by second ... supported range: [1;30]"**, driven from
    `LuaExportAfterNextFrame` with its own internal throttle (`bytes_in_transit` / elapsed
    `LoGetModelTime()`). **This would comfortably carry 874/876 at up to 30 Hz** — both are already
    mapped as ordinary float controls (see Q3), so *if* DCS-BIOS were adopted for telemetry, the
    sight-angle readback would come along for free at a rate at or above our own Export.lua's
    current polling cadence. 30 Hz is a hard ceiling DCS-BIOS imposes on itself, though — if
    `BL-B63`'s rate loop ever needs a tighter tick than that, DCS-BIOS's own export path would be
    the limiting factor, not DCS.
- **Input (commands) — evidence: documented (source), with one load-bearing limitation.** Commands
  are a plain text line protocol: `"<IDENTIFIER> <value>\n"`, parsed by
  `BIOSStateMachine:processInputLine` (`cmd, args = line:match("^([^ ]+) (.*)")`), dispatched to the
  named control's `inputProcessor`. For a toggle switch that processor does exactly
  `GetDevice(device_id):performClickableAction(command, 1)` after reading current state via
  `GetDevice(0):get_argument_value(arg_number)` — i.e. **DCS-BIOS commands are always routed through
  a *named Control* that some Lua file (the Mi-24P module) chose to define**, each wrapping one
  specific `performClickableAction` call. **There is no generic "send device X, command Y, value Z"
  passthrough.** This matters directly for the two things we would most want to write:
  - Switches on devices 6 (`WEAP_SYS`) and 7 (`I9K113`), including all of `BL-B66`'s targets (773,
    761, 885, 955, 886, 673) — **all already have named DCS-BIOS controls** (confirmed above), so
    DCS-BIOS's command protocol could drive every one of them today, by sending e.g.
    `"OP_MISSL_PW TOGGLE\n"`.
  - **The player slew axis (3025/3026, device 7) has no DCS-BIOS control at all.** Grepping every
    use of commands 3025/3026 in the whole Mi-24P module turns up only unrelated controls on other
    devices (wheel brake, operator fan, AC voltmeter knob, SAU correction, Jadro test, SPU-8) — none
    on device 7. This is the expected shape of the gap: DCS-BIOS's module authors build controls
    from the aircraft's *clickable* cockpit elements, and the slew axis (a raw `SetCommand`
    continuous axis with "no clickable element," per the Architect's own framing of the question) is
    exactly the kind of control that process would never surface. **DCS-BIOS could not drive the
    `BL-B80` slew loop without someone first adding a bespoke control for it to the Mi-24P module —
    which is new DCS-BIOS-side code we don't control, not a capability we'd simply be unlocking.**

#### Coexistence with our existing Export.lua chain

- **Evidence: documented, and favourable.** `BIOSConfig.lua`'s installer explicitly chains rather
  than overwrites: on load it captures whatever `LuaExportStart` / `LuaExportStop` /
  `LuaExportBeforeNextFrame` / `LuaExportAfterNextFrame` already exist as `PrevExport.*`, defines its
  own versions, and calls `call_function_safe(PrevExport.LuaExportStart)` etc. at the end of each of
  its own handlers. **This is precisely the hook-chaining pattern our own `aircraft-layer/dcs-export/*.lua`
  hooks already use for each other.** The README's own install instructions describe the two load
  orders explicitly: if no `Export.lua` exists, DCS-BIOS supplies one; if one exists, the user adds
  one `dofile(...)` line to the end of it. **Whichever file runs its chain-capture line second wins
  the "calls the other's handlers" position** — so if our own Export.lua defined
  `LuaExportAfterNextFrame` before DCS-BIOS's `BIOS.lua` is `dofile`'d, DCS-BIOS would capture and
  chain to *our* handler; if DCS-BIOS's `dofile` line runs first, we would need to chain to *its*
  captured `PrevExport.LuaExportAfterNextFrame` the same way it does. No conflict was found in the
  mechanism itself, only an install-order detail to get right once.

#### Install burden for a stranger (this project intends to be public)

- **Evidence: documented (README "Getting Started"/"Installation"), moderate but real burden.**
  Download a release zip, extract, copy a `DCS-BIOS` folder into `Saved Games\DCS[.openbeta]\Scripts`,
  and either let it supply `Export.lua` or add one line to an existing one. This is a second
  third-party install step beyond whatever this project already asks a stranger to set up (its own
  `dcs-export/*.lua` files), with its own release cadence and its own version-compatibility promises
  to track.
- **Version coupling is symmetric with our own risk, not worse — but doubled.** DCS-BIOS's arg
  numbers are positional and drift with ED patches exactly like ours do (confirmed by this session's
  own cross-checking exercise). Depending on it does not remove that risk category; it adds a
  **second** project's patch-tracking cadence that our installation would be hostage to — if
  DCS-BIOS lags a DCS patch, our pipeline breaks on their schedule, not ours, with no path to fix it
  ourselves except patching their Lua locally (GPL-permitted, but now we're maintaining a fork).
- **Maintenance currency — evidence: weak/inferred, from a shallow clone.** The DCS-Skunkworks fork
  is presented in its own README as an actively maintained continuation of an abandoned original,
  with a release process, contributing guide, Discord, and ~50 aircraft modules including several
  recent DCS modules (AH-64D, F-15E). The one commit visible in this session's shallow clone
  (2026-10-18, a Mosquito fix) shows *a* commit landed three days before this investigation, which
  is weak evidence of recent activity but not a real maintenance history for `Mi-24P.lua`
  specifically — a full, unshallow clone with `git log -- .../Mi-24P.lua` would answer that properly
  and was not run here (would need to fetch full history, not attempted this session).

#### What DCS-BIOS would not cover — we would still build these ourselves regardless of the decision

- The player slew axis (see above) — no clickable control exists for DCS-BIOS to wrap.
- Everything our own `dcs-export/*.lua` hooks already do that has nothing to do with cockpit draw
  arguments: `LoGetWorldObjects`, line-of-sight probes, firing/damage events, F10 command injection,
  mission telemetry. DCS-BIOS is strictly a cockpit-clickable-data exporter; it has no opinion on
  world state.
- Any lamp/readout DCS-BIOS has not mapped — which, per Q1, includes the one lamp (`READNS.`) this
  whole investigation was first asked to resolve. **Adopting DCS-BIOS would not have answered the
  highest-value question in this report.**

#### Middle options

1. **Full runtime dependency**: drop our command-socket/telemetry Export.lua hooks for the switches
   DCS-BIOS already covers, speak its UDP/TCP line protocol instead. Gains the device-6/7 switch set
   for free; gains nothing for the slew axis, world-state probes, or the READY lamp; adds a second
   install step and a second patch-tracking dependency for the whole project, not just this feature.
2. **Reference-only**: keep our own Export.lua path entirely, but treat DCS-BIOS's Mi-24P module as
   a standing cross-check source — re-diff our arg/device/command table against theirs after every
   DCS patch, the way this session just did once by hand. No install burden, no licensing exposure
   beyond reading facts out of GPL'd source (already done), no coexistence risk. Does not get us
   30 Hz telemetry or any new read path; the READY-lamp question still needs our own brute-force
   probe regardless.
3. **Borrow the read approach, not the dependency**: nothing to borrow beyond what we already do —
   DCS-BIOS's lamp-read mechanism (`GetDevice(0):get_argument_value(arg)` in an export hook) is
   exactly our own existing mechanism, confirmed identical in Q1. There is no technique here we
   don't already have; "borrowing the approach" is a no-op.

#### Recommendation

**Reference-only (option 2), not a runtime dependency — recommendation, not a conclusion; the
decision to add a dependency is the user's.** Main reason: the one problem this report was
originally commissioned to solve — whether the READY lamp is observable at all — is not solved by
DCS-BIOS either, because the lamp has no mapped draw argument in its survey. Adopting DCS-BIOS as a
dependency would buy telemetry for switches we can already read and write ourselves today (every
arg this project has committed to for `BL-B66` is already working through our own Export.lua), at
the cost of a second install step and a second project's patch cadence for a public, stranger-facing
pipeline — and it would do nothing for the slew axis, which has no DCS-BIOS control and would need
bespoke module code either way. The cross-check value (confirming 773/885/886/955/956/673/874/876
all agree) is real and was obtained for free in this session without installing anything — that
value is fully captured by treating DCS-BIOS as a reference to re-diff against after DCS patches,
without taking on the dependency itself.

---

### Reproducible Test

Not run live against DCS this session (no install reachable). Two tests this report recommends to
whoever next has DCS access:

1. **READY-lamp brute-force scan** (resolves Q1 properly): from the pilot's seat with the sight
   switch sequence run correctly and a full ~5 minute wait, log
   `for a = 1, 2000 do v = GetDevice(0):get_argument_value(a); if v ~= 0 then table.insert(nonzero, a) end end`
   once before power-up and once after confirmed warm-up, diff the two sets, and exclude 874/876
   (which move from slew activity, not warm-up).
2. **Full, unshallow DCS-BIOS clone** if maintenance currency for `Mi-24P.lua` specifically becomes
   load-bearing to a future decision: `git clone https://github.com/DCS-Skunkworks/dcs-bios.git` (no
   `--depth`), then `git log --format='%ad %s' --date=short -- Scripts/DCS-BIOS/lib/modules/aircraft_modules/Mi-24P.lua`.

### Possible Approaches

See "Middle options" and "Recommendation" above for the dependency question. For the 761/762 vs.
905/903 "OPER/TEST1/TEST2" disagreement (Q2), the cheapest resolution is the same kind of
read-not-write live pass the prior research note already proposed for 761 generally: throw each
candidate switch by hand while logging `get_argument_value` for all four (761, 762, 903, 905) and
read off which one the quickstart procedure's "OPER/TEST1/TEST2" step actually corresponds to by its
visible cockpit effect.

### Unresolved

- **Q1, fully**: whether `READNS.` has *any* draw argument at all. DCS-BIOS's silence narrows this
  but does not close it — only the brute-force scan above does.
- **Q2**: whether "USR" in DCS-BIOS's `OP_USR_PW`/`OP_USR_CHECK` names is in fact our "CPLR DISTR"
  function, versus some other ASP-17 subsystem that happens to share a device. Device-level agreement
  is two independent signals, not a positive functional test.
- **Q2**: which of 762 vs. 905/903 corresponds to "OPER/TEST1/TEST2" in the quickstart procedure —
  flagged as a real disagreement between two equally-plausible, independently-real controls.
- **DCS-BIOS `Mi-24P.lua` maintenance currency specifically** — not established beyond "present and
  loaded at a 2026-10-18 HEAD"; the shallow clone used this session cannot show per-file history.
- **Whether DCS-BIOS's 30 Hz export ceiling would actually bind** on any future `BL-B63`/`BL-B80`
  rate-loop tick rate — not measured, because the dependency question was evaluated on protocol
  capability, not against a concrete target loop rate that does not exist yet.
