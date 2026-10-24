# Mi-24P `clickabledata.lua`/`command_defs.lua`/`devices.lua` -- exact forms, confirmed live

**Date:** 2026-10-23
**DCS version:** 2.9.30.28738 (`autoupdate.cfg`'s `"version"` field), read-only recon on the
Windows DCS machine, relayed via the main loop to the Implementer working
`plans/effector-sequences/plan.md` Stage 0b (`body-layer/tools/generate_effector_registry.py`).
**Theatre:** n/a (cockpit-only question).

### Why this note exists

`plans/effector-sequences/plan.md`'s "Generator tool" section and
`aircraft-layer/research/mi24p-command-surface.md` (generated 2026-09-11, build 2.9.29.27278)
both guessed at the exact Lua forms `devices.lua`/`command_defs.lua`/`clickabledata.lua` use --
reasonable guesses (dotted `devices.NAME = counter()`, a `cockpit_device_id`/`name`-keyed raw
table literal) but **wrong on several structural points**, confirmed only by reading the real
files. This note records what is actually there, build 2.9.30.28738, so the Stage 0b generator
is built against fact rather than inference, and so Stage 0c's real run (on the DCS machine) is
not the first time these forms are checked.

**749 `elements[` occurrences, same count as the 2026-09-11 dump** -- the module's clickable
surface has not grown between builds 2.9.29.27278 and 2.9.30.28738, only this recon's reading of
its *shape* has improved.

### Q0 -- files

Relative to `$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/`:

- `devices.lua` (81 lines)
- `command_defs.lua` (2196 lines)
- `clickable_defs.lua` (395 lines)
- `clickabledata.lua` (1205 lines)
- Per-system files that `dofile`/reference `command_defs.lua` but **define no command ids
  themselves**: `A036_commands.lua`, `FireExtinguishersInterface_commands.lua`,
  `Hydro_system_commands.lua`, `MiscSystems_commands.lua`, `Weap_syst_commands.lua`,
  `main_panel_commands.lua`, `Devices_commands/AUTOPILOT_commands.lua`. **The include direction
  is the reverse of what a casual reading suggests**: these per-system files `dofile`
  `command_defs.lua`, not the other way around, and none of them needs to be read for id
  resolution -- `generate_effector_registry.py` ignores them entirely.

All four main files are CRLF on every line; `devices.lua` has no final newline. Neither matters
to a parser that reads text via `Path.read_text()` (Python's universal-newline translation
handles CRLF transparently) and never relies on a trailing newline being present.

### Q1 -- `devices.lua`

```lua
local count = 0
local function counter()
	count = count + 1
	return count
end
devices = {}
devices["ELEC_INTERFACE"]			= counter()
```

All 73 entries are `devices["X"] = counter()` (tabs/spaces before `=`), ids assigned from 1 in
file order (`ELEC_INTERFACE = 1` ... `R60_INTERFACE = 73`). **There is no `devices.X = ...`
(dotted) declaration form, and no explicit numeric literal anywhere in this file** -- the plan's
and the 2026-09-11 note's dotted-assignment guess was wrong for the *declaration* (it is right for
the *reference*: `clickabledata.lua` and `clickable_defs.lua` both read devices back via
`devices.ASP_17V`-style dotted access, confirmed in the raw-literal example at Q5 below).

### Q2 -- `command_defs.lua`

Line 3: a global `start_command = 3000`. The file's own local `count`/`counter()` pair (separate
from `devices.lua`'s) increments from whatever `count` was last set to.

**49 resets**, each a column-0 `count = start_command` immediately before a table header:

```lua
count = start_command
elec_commands =
{
	ACGroundPower							= counter();
	ACGeneratorLeft							= counter(),
```

So the first entry in every reset table is `3001`. Of the 49: 48 are named `*_commands` tables in
this plain constructor shape; the 49th, `device_commands`, is built by a **loop** instead:

```lua
count = start_command
device_commands = {}
for cmd_num = 1,120 do
	device_commands["Button_"..cmd_num] = counter()
end
cb_start_cmd = device_commands.Button_31
cb_end_cmd = cb_start_cmd + 63
```

`cb_start_cmd`/`cb_end_cmd` are plain local derived values (no dot on the left-hand side), not
further command declarations -- irrelevant to id resolution. 1232 `counter()` calls total across
the file.

**Before line 625**: `Keys = { ... }` (lines 11-623), the global iCommand space, with **explicit
numeric values and no counter or reset** (`PlaneGear = 68`, etc.) as plain table-constructor
fields (`Keys = { PlaneGear = 68, ... }`), not `Keys.PlaneGear = 68` dotted assignments. **After
line 625, every table entry in every `*_commands` table is `= counter()`** -- no literal-int
entries anywhere past that point. `clickabledata.lua` never references `Keys`, so a parser that
only looks for `count = start_command`-preceded table blocks naturally never touches it.

**Parsing traps, confirmed:**

- Separators are mixed `;` and `,` within the same table, including on the very same block
  (`elec_commands` above ends its last entry with `,` not `;`).
- A table header can carry a trailing comment on the same line as its own `=`:
  `engine_commands = --OMG this sucks a lot` (then `{` on the next line);
  `fmproxy_commands = --kekeke` similarly. Comments must be stripped before any of this is parsed,
  not worked around with a comment-aware header regex.
- A blank line can sit between the reset marker and the table header (`timers_commands`,
  lines 2151-2153).
- `--hidden` single-line comments appear inside some table bodies.
- `command_defs.lua` has only *single-line* `--[[ WARNING SYSTEM ]]--` banner comments inside
  `Keys` -- no genuine multi-line block comment anywhere in this file. The trailing `--` after
  `]]` in that banner is not special: once the `--[[ ... ]]` block is stripped, the leftover `--`
  is picked up as an ordinary fresh line-comment on the next character, with nothing visible lost.
- Tables close with either `}` or `};`.

### Q3 -- `clickable_defs.lua`

Plain global function definitions (no `require`/module wrapper); also sets module-level globals
`cursor_mode`, `direction`, `cyclic_by_default`, `anim_speed_default = 16` used as default-value
expressions inside `clickabledata.lua` calls (irrelevant to id resolution, never evaluated by the
generator). 22 distinct helper signatures, every one putting `device_` at positional index 1 and
the command(s) starting at index 2 (two command slots, indices 2-3, only for
`default_button_tumb` and `springloaded_3_pos_tumb`); `arg_` (the cockpit draw argument) always
comes immediately after the command(s). `crew` (actually `crew_member_access`, defaulting to `0`
= pilot when omitted or `nil` -- DCS's real default *is* 0, not an unassigned/undefined seat) is
always the **last** positional parameter when the signature has one at all; two helpers have none
(`default_square_button`, `stick_button`):

```
default_button(hint_,device_,command_,arg_,animation_speed_, crew)
default_spring_button(hint_,device_,command_,arg_,arg_val_,arg_lim_, turn_box_, crew)
default_square_button(hint_,device_,command_,arg_,turn_box_)
default_tumb_button(hint_,device_,command_,arg_,animation_speed_, crew_)
default_position_tumb(hint_, device_, command_, arg_, arg_val_, arg_lim_, turn_box_, crew)
default_1_position_tumb(hint_, device_, command_, arg_, animation_speed_, arg_val_, arg_lim_, crew)
default_2_position_tumb(hint_,device_,command_,arg_,animation_speed_, crew)
default_2_position_small_tumb(hint_,device_,command_,arg_,animation_speed_, crew)
default_2_position_flares_tumb(hint_,device_,command_,arg_,animation_speed_, crew)
default_3_position_tumb(hint_,device_,command_,arg_,cycled_,animation_speed_,inversed_,arg_value_,arg_limit_, crew)
triple_switch(hint_,device_,command_,arg_, crew)
multiposition_switch(hint_,device_,command_,arg_,count_,delta_,inversed_,min_,animation_speed_,cycled_, crew)
default_button_tumb(hint_,device_,command1_,command2_,arg_,animation_speed_, crew)
springloaded_2_pos_tumb(hint_,device_,command_,arg_,animation_speed_, crew)
springloaded_3_pos_tumb(hint_,device_,command1_,command2_,arg_,animation_speed_,val1_,val2_,val3_, crew)
default_animated_lever(hint_,device_,command_,arg_,animation_speed_,arg_lim_, crew)
default_axis(hint_,device_,command_,arg_, default_, gain_,updatable_,relative_,cycled_, attach_left_, attach_right_, crew)
default_axis_limited(hint_,device_,command_,arg_,default_,gain_,updatable_,relative_,arg_lim_, attach_left_, attach_right_, crew)
default_CB_button(hint_,device_,command_,arg_, crew)
default_blue_cover(hint_,device_,command_,arg_,animation_speed_, crew)
radio_wheel_1(hint_,device_,command1_,arg_, arg_value_, arg_lim_, slave_, crew)
stick_button(hint_,device_,command_,arg_)
```

**18 of these 22 are actually called** in `clickabledata.lua` (501 calls total): 205
`default_2_position_tumb`, 82 `default_button`, 40 `multiposition_switch`, 34 `default_blue_cover`,
33 `default_axis`, 25 `default_3_position_tumb`, 17 `default_square_button`, 10
`default_2_position_small_tumb`, 9 `default_position_tumb`, 9 `default_axis_limited`, 8
`default_animated_lever`, 8 `default_2_position_flares_tumb`, 5 `springloaded_3_pos_tumb`, 5
`radio_wheel_1`, 4 `triple_switch`, 3 `stick_button`, 2 `default_tumb_button`, 2
`default_spring_button`. Never called in this module: `default_CB_button`, `default_button_tumb`,
`springloaded_2_pos_tumb`, `default_1_position_tumb`.

`generate_effector_registry.py` bakes all 22 signatures into a static `_HELPER_SIGNATURES` table
rather than parsing `clickable_defs.lua` at runtime: the function *bodies* are mesh/sound triggers
irrelevant to id resolution, and the only thing the generator needs -- parameter order -- is fixed
and now known.

### Q4 -- `clickabledata.lua` top level

```lua
dofile(LockOn_Options.script_path.."clickable_defs.lua")
dofile(LockOn_Options.script_path.."command_defs.lua")
dofile(LockOn_Options.script_path.."devices.lua")
dofile(LockOn_Options.script_path.."sounds.lua")
-- dofile(LockOn_Options.script_path.."Hint_localizer.lua")  -- commented out
local gettext = require("i_18n")
_ = gettext.translate
cursor_mode = {...}
clickable_mode_initial_status = ...
use_pointer_name = true
direction = 1
cyclic_by_default = true
elements = {}
```

Nothing else at top level -- no loops, no function definitions, no other locals. Every statement
after line 23 is an `elements[...]` assignment or field patch.

### Q5 -- the 13 raw-table-literal elements

**Names (unchanged from the 2026-09-11 dump):** `COLLECTIVE-CORR-PTR`, `OP-COLL-THROTTLE-PTR`,
`CLOCK-LEFT-PTR`, `CLOCK-RIGHT-PTR`, `CLOCK-LEFT-OP-PTR`, `CLOCK-RIGHT-OP-PTR`,
`ILS-ADJUST-HANDLE-PTR`, `BRAKE-LEVEL-OP-PTR`, `RADAR-ALTIMETER-KNOB-PTR`, `STICK-PTT-PTR`,
`OP-STICK-PTT-PTR`, `TIMIR-LEFT-OP-PTR_2-9_5`, `TIMIR-LEFT-OP-PTR_8-38`.

**The field names the plan guessed (`cockpit_device_id`, `name`) are wrong.** The real shape,
example at line 1009:

```lua
elements["STICK-PTT-PTR"]	= {	
	class 				= {class_type.BTN, class_type.BTN},
	hint  				= _("Trigger Button, RADIO(LMB)/ICS(RMB)"),
	device 				= devices.SPU_8,
	action 				= {SPU_8_Mi24_commands.CMD_SPU8_TRIGGER_P, SPU_8_Mi24_commands.CMD_SPU8_TRIGGER_P},
	stop_action 		= {SPU_8_Mi24_commands.CMD_SPU8_TRIGGER_P, SPU_8_Mi24_commands.CMD_SPU8_TRIGGER_P},
	arg 				= {738, 738},
	arg_value			= {1.0, 0.5}, 
	arg_lim 			= {{0.0, 1.0}, {0.0, 0.5}},
	updatable			= true,
	use_release_message = {true},
	crew_member_access  = {0}
}
```

The correct field names: `device` (not `cockpit_device_id`), `hint` (not `name`), `action`
(the command reference(s), not a free-standing dotted ref), `arg` (a list when the element has
more than one action, as here: both LMB/RMB map to the same command with different `arg_value`s).
Each opens `elements["X"] = {` on one line and closes with a column-0 `}` -- no trailing comma on
the last field. **`devices.SPU_8` dotted access confirms the devices.lua declaration/reference
split noted at Q1**: declared with brackets, referenced with dots.

### Q6 -- `crew_member_access`, inline vs. post-assignment

The literal string `crew_member_access` appears 15 times total: 13 inside the raw literals above,
plus **2 as post-assignment patches** after an already-defined element:

```lua
elements["STICK-BRAKE-PTR"].crew_member_access  = {0}        -- line 222
elements["FIRE-SENSOR-CHANNEL-PTR1"].crew_member_access  = {0}  -- line 584
```

Positional-crew examples from ordinary helper calls:

```lua
default_2_position_tumb(_("Radio/ICS Switch"), devices.SPU_8, SPU_8_Mi24_commands.CMD_SPU8_O_ICS_RADIO, 660, nil, 1)
default_axis_limited(_("SPU-8 Radio Volume Knob"), devices.SPU_8, ..., 657, 0.0, 0.05, nil, nil, nil, nil, nil, 1)
```

**235 total post-assignment lines** (`elements["X"].field = ...`), breaking down by field:
`turn_box` 171, `sound` 27, `updatable` 18, `side` 11, `crew_member_access` 2, `arg_value` 2,
`arg_lim` 2, `use_OBB` 1, `animation_speed` 1. `generate_effector_registry.py` applies only the
`crew_member_access` patches (the only one of these fields in this registry's schema); every other
field is counted (so the completeness arithmetic in Q7 holds) but not otherwise acted on.

### Q7 -- the 749 count, decomposed

**749 = 501 helper calls + 13 raw-literal openers + 235 post-assignment patches.** This is a
decomposition, not a single number: 501 + 13 = 514 element *definitions*, and 235 separate
`elements["X"].field = ...` statements that mutate an already-defined element rather than creating
a new one. **No element name is defined twice, and no `elements["X"][...]` double-indexing form
appears anywhere.** `generate_effector_registry.py`'s completeness check is therefore two numbers,
not one: `heads (749) == definitions handled + definitions unhandled + post-assignment patches
(235)`, where "definitions" is 514 when every one of them resolves.

### Other hazards, confirmed

- **One element name carries a leading space**: `elements[" CONTROL-COVER-PRIORITY-PTR"]`. Kept
  verbatim by the generator -- no name normalisation.
- **Hints are always `_("...")` on the same line as the helper call, double-quoted, never string
  concatenation.** 207 of them contain parentheses and/or commas inside the string itself, e.g.
  `_("Radio Source Selector Switch, R-863/NF/R-828(Eucalypt)/JADRO-1A/ARC-15/ARC-U2")` -- a
  parser that tokenizes strings before counting parens/commas (as `generate_effector_registry.py`
  does) handles this correctly; a naive comma-split would not.
- **Every helper call fits on one line** once comments and strings are stripped and balanced.
- **Trailing commented-out arguments after the closing paren** occur, e.g. line 356:
  ``...elec_commands.Transformer115vMainBackup,	83)--, false, nil, false, 0.5, {0, 1})``.
  Harmless once comments are stripped *before* parsing the call -- the comment text disappears
  entirely, leaving a normally-closed call.
- **Trailing-parameter expressions vary widely**: `nil` (121 calls), table literals (18),
  fractions (`1/5`, `1/10`, `anim_speed_default / 5`), negative numbers, booleans. None of these
  are the device/command/arg/crew values this generator actually resolves (they are
  `animation_speed_`/`arg_val_`/`turn_box_`-class trailing parameters), so the generator never
  attempts to parse them -- it reads only the fixed-position device/command(s)/arg/crew slots per
  helper signature and ignores everything after.

### What this corrects in the earlier plan/research text

- `devices.lua` declares with `devices["NAME"] = counter()`, not `devices.NAME = counter()`
  (the dotted form is reference-only).
- `command_defs.lua`'s tables are plain Lua table constructors (`name = { field = counter(); }`),
  not `tablename.field = value` dotted top-level assignments -- except `device_commands`, which is
  the one table built by a `for` loop with string-concatenated keys.
- The raw-table-literal elements use `device`/`hint`/`action`/`arg` field names, not
  `cockpit_device_id`/`name`.
- Seat (`crew_member_access`) is a positional argument on almost every helper, not a bare
  always-present literal field -- and 2 of the 13 raw literals have it reassigned by a later
  post-assignment rather than set inline.
- 18 distinct helpers are in use, not 4 -- the original 2026-09-11 dump's "known gap" of 13
  raw-literal elements is confirmed unchanged in count, and its root cause (controls with more
  than one action) is now fully explained by the `action`/`arg` list fields shown at Q5, not
  merely inferred from the pattern of which elements were missing.
