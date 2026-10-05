# SPU-8 intercom write path — can code set arg 664 (operator intercom power) from the pilot's seat?

**Date:** 2026-10-05
**DCS version:** 2.9.29.27278, static read this session (install at `/mnt/f/Games/DCS World/`,
read-only, reachable from this environment — not the Windows-only machine earlier sessions assumed;
no DCS process was running, so this is a file/binary read, not a live probe)
**Theatre:** n/a (module/cockpit question)

### Question

Audio-adapter Slice 2 (`audio-adapter/ROADMAP.md`) needs to set the co-pilot/operator ICS switch
(arg 664, `SPU-8 Intercom Power ON/OFF`, `crew_member_access = 1`) from code, with the player
occupying the **pilot** seat. Three sub-questions, per the dispatch brief:

1. Is there a way to write a clickable cockpit control from code at all, and from which context
   (Export, Hook/GUI, mission-scripting, or only device-internal code)?
2. Critically: does a write to an **operator-panel** control succeed when the player is **not**
   occupying that seat?
3. Recommend one write path to try first.

### This was mostly already answered — pointing to the existing note first

**Q1 is not new.** `aircraft-layer/research/2026-09-11-command-injection-surface.md` and its durable
output `aircraft-layer/research/mi24p-command-surface.md` already establish, live-confirmed on
2026-09-11, that `GetDevice(device_id):performClickableAction(cmd, value)` and
`GetDevice(device_id):SetCommand(cmd, value)` are callable from the **`Export.lua` state** and
actually move cockpit switches (`Brightness_PM`, arg 564, confirmed moved and restored) and slew the
9K113 sight (`SetCommand`, confirmed a position write, not a rate). Reads go through
`GetDevice(0):get_argument_value(<arg>)` — device 0 (mainpanel) only, confirmed live. The production
`aircraft-layer/dcs-export/Export.lua` already calls `GetDevice(30):performClickableAction(...)` for
the AI-wheel search trigger (BL-6), so this write path is not just probed, it is shipping.

**`audio-adapter/ROADMAP.md`'s framing — "whether `get_argument_value`'s counterpart can set an
argument from a Hook or Export context... is unverified" — undersells what's already settled.** The
mechanism (Export.lua, `GetDevice`, `performClickableAction`/`SetCommand`) is confirmed. What is
**genuinely still open**, and is the real content of Q2, is narrower than the roadmap text states:
**whether the write succeeds when the target control's `crew_member_access` does not match the
player's own seat.** Every existing confirmed-live write targeted either a pilot-seat control
(`Brightness_PM`, no `crew_member_access` field at all → defaults to `{0}`, pilot) or a command with
no clickable-element entry whatsoever (the 9K113 AI-axis commands, `ShowMenu`/wheel buttons — none
of these carry a `crew_member_access` value to test against). **No prior session tested a write
against a control explicitly flagged `crew_member_access = {1}`.** That gap is this session's actual
contribution.

### Findings

- **SPU-8 is one device (55, `SPU_8`) with two independent physical panels** — pilot's own
  (args 452-457, 376/377, 738) and the operator's (656-661, 664, 856) — not two devices and not a
  single shared control gated by occupancy. — **evidence: reproduced-locally** — **source:**
  `Mods/aircraft/Mi-24P/Cockpit/Scripts/clickabledata.lua:999-1050`, `devices.lua`.

- **Exact command/arg mapping for the four controls named in the roadmap**, read directly from
  `clickabledata.lua` (device `SPU_8` = 55 throughout):

  | Arg | Element | Command | Cmd ID | `crew_member_access` |
  |---|---|---|---|---|
  | 456 | `SPU8-EXT-PTR` | `CMD_SPU8_P_ICS_RADIO` | 3004 | *(absent → default 0, pilot)* |
  | 457 | `SPU8-VOLUME-PTR` | `CMD_SPU8_P_MAIN_VOLUME` | 3001 | *(absent → default 0, pilot)* |
  | 376 | `SPU8-1-ON-OFF-PTR` | `CMD_SPU8_NETWORK_2` | 3018 | *(absent → default 0, pilot)* |
  | 377 | `SPU8-2-ON-OFF-PTR` | `CMD_SPU8_NETWORK_1` | 3017 | *(absent → default 0, pilot)* |
  | **664** | `SPU8-OP-PTR` | `CMD_SPU8_O_ICS` | **3015** | **`{1}` — operator, explicit** |

  — **evidence: reproduced-locally** — **source:** same file, lines quoted verbatim in the
  Reproducible Test below. Note the element-name/arg crossing on 376/377 (`SPU8-1-ON-OFF-PTR` holds
  `NETWORK_2`→376, `SPU8-2-ON-OFF-PTR` holds `NETWORK_1`→377) — this matches, not contradicts, the
  roadmap table's "376/377 NET-2/NET-1", it's just a naming quirk in ED's own file.

- **The write call for arg 664 is therefore:**
  ```lua
  GetDevice(55):performClickableAction(3015, 1)   -- SPU_8_Mi24_commands.CMD_SPU8_O_ICS
  ```
  with readback `GetDevice(0):get_argument_value(664)`. — **evidence: reproduced-locally**
  (command/arg numbers); **inferred** (that the call succeeds — see below).

- **`crew_member_access` is a real, natively-consumed field, not inert Lua metadata — but the
  evidence about *where* it's consumed points away from gating device-command dispatch.**
  `Mods/aircraft/Mi-24P/bin/{CockpitMi24,Mi24}.dll` contain **no** occurrence of the string
  `crew_member_access` at all. The shared engine binary `bin/CockpitBase.dll` (install root, not the
  module) **does** contain it, once, in a contiguous run of strings that is unmistakably the
  clickable-element table's own field-name list: `is_custom`, **`crew_member_access`**, `turn_box`,
  `box_min_max`, `"Cockpit: Clickable - Wrong connector name %s"`, `device`, `hint`, `use_OBB`,
  `updatable`, `cycle`, `children`, `attach_left`, `attach_right`, `clickable_common.lua`,
  `use_pointer_name`. That is the parser for the `elements[...]` table structure itself (the exact
  keys seen in `clickabledata.lua`), not a string anywhere near the `performClickableAction`/
  `SetCommand`/`GetDevice` cluster found in the 2026-09-11 session (`____self_device_handle`,
  `GetDevice`, `SetCommand`, `performClickableAction`, `listen_command`, `listen_event`, and the
  mangled `avDevice::performClickableAction(int, float, bool)` — a **device-command-id-and-value**
  signature with no element, seat, or table lookup in it). — **evidence: reproduced-locally**
  (both string searches) — **inferred** (the two clusters being unrelated code paths; binary strings
  cannot prove call-graph separation, only suggest it strongly).

- **Reading this as "the clickable-element registry (rendering/mouse-pick layer) owns
  `crew_member_access`; `avDevice::performClickableAction` dispatches directly on `(cmd_id, value)`
  with no reference to it" is the natural inference, and it predicts the write succeeds.** It is
  also consistent with what `crew_member_access` would need to do in a *single-player, one-human-seat*
  game anyway: decide which 3D clickable mesh regions respond to *this seat's mouse cursor* when a
  human is physically in the cockpit view, not decide whether the underlying device command can
  execute. Petrovich (the AI) operates the panels at seats the player isn't in through native
  code that has no "whose mouse is this" question to answer, and Export.lua's `GetDevice(...)` call
  has exactly the same property — it is not a click event with an owning camera/seat. — **evidence:
  inferred**, not proven. No file or binary read settles call-graph separation; only a live test does.

- **This generalizes the existing finding, not reverses it.** The 2026-09-11 session's closing
  statement — "very likely yes, the exact commands are enumerated... but it has not been
  demonstrated from Export.lua" — was about the write mechanism in general and was then settled for
  pilot-seat/no-access-flag controls. The *cross-seat* case it did not test is exactly `arg 664`, and
  remains exactly as open as that statement implies, just narrower in scope now.

### Reproducible Test

Static, re-runnable on any machine with the install mounted (no DCS session needed):

```sh
sed -n '999,1050p' "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/clickabledata.lua"
grep -n "crew_member_access" "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/clickabledata.lua"
grep -n "helperai_commands\s*=" "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/command_defs.lua" -A 25

# crew_member_access native-consumption check
strings -n 6 "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/bin/CockpitMi24.dll" | grep -i crew_member_access   # -> empty
strings -n 6 "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/bin/Mi24.dll"       | grep -i crew_member_access   # -> empty
strings -t d -n 4 "$DCS_INSTALL_PATH/bin/CockpitBase.dll" | grep -n -B15 -A5 crew_member_access
```

**Live probe, the one thing that actually settles Q2** — see
`docs/acceptance/2026-10-05-spu8-intercom-probe.md` for the exact steps and what to bring back.

### Possible Approaches

- **If the write succeeds regardless of seat (the predicted outcome):** this is the cleanest path —
  collector gains a small effector in `collector/command_sender.py`'s existing shape
  (`GetDevice(55):performClickableAction(3015, value)`), reached the same way the AI-wheel search
  trigger already is, with `GetDevice(0):get_argument_value(664)` for readback/verification. No new
  architectural surface — this is the same mechanism BL-6 already shipped, just a different device.
- **If the write silently no-ops for the cross-seat control** (the one way this could still fail
  despite the inference above — e.g. if some other, unfound code path *does* check seat ownership
  before invoking the device, just not via the `crew_member_access` string): fall back exactly as
  the roadmap already names — treat arg 664 as a **read-only precondition** and have the automatic
  "wait 5s then set co-pilot ICS switch ON" behaviour instead simply assume/require it starts ON (most
  missions probably default it there) and tell the player to flip it if the read shows it off, rather
  than writing it. This degrades gracefully: the roadmap's actual gating logic is the *conjunction*
  of 456 (pilot's own switch, definitely writable) and 664, so a read-only 664 still lets the pilot's
  own switch meaningfully gate the channel; only the "Petrovich always starts reachable" convenience
  behaviour would be lost.
- **If writes work for pilot-seat controls but the probe can't get a clean read on 664 specifically**
  (e.g. some other switch is wired to gate it): re-run the probe with `get_argument_value` on nearby
  operator-panel args (656-661) to see if *any* operator-seat control is writable, which would
  isolate whether 664 itself is special-cased rather than the operator panel generally.

### Unresolved

- **The actual question (Q2): does `GetDevice(55):performClickableAction(3015, 1)` move arg 664**
  **when the player is in the pilot seat?** Everything above is either already-confirmed mechanism
  or a structural inference from binary string adjacency — neither is a live result. This needs the
  probe.
- **Whether any other, unfound code path checks seat ownership before a device command executes.**
  The binary string-adjacency argument is suggestive, not exhaustive — `strings` cannot see which
  function actually reads a given string (per the established methodological finding in
  `2026-09-20-dcs-install-detection-deep-read.md` finding 12, "absence is not evidence" also cuts
  the other way: presence-near-other-strings is not proof of co-location in the call graph either).
- **Whether `CMD_SPU8_O_ICS` (3015) is itself gated by some other switch** (power bus, master arm
  equivalent) that would make a "no change" result ambiguous between "seat-gated" and "precondition
  not met" — same method fault the 2026-09-11 probe runs hit repeatedly with the 9K113 sight (gyro
  spin-up, sight doors). The probe card asks for 456/457/376/377 readback across travel specifically
  so a 664 failure isn't read in isolation.
