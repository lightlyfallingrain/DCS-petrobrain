# Mi-24P clickable value ranges: what each helper lets a control be set to

**Date:** 2026-10-23. **Source:** read-only recon of the installed module on the Windows DCS machine
(DCS 2.9.30.28738), relayed by the main loop. Files:
`$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/clickable_defs.lua` (395 lines) and
`clickabledata.lua` (1205 lines); the `class_type` enum is in
`Scripts/Aircrafts/_Common/Cockpit/clickable_common.lua:14`. Nothing was written under the
install.

**Why:** the user asked for `switch-reference.md` to show each control's settable values, *"be it
continuous or steps. Like 0/1, 0.0/0.5/1.0, 0.0-1.0"*. This note is the input for that change. It
complements `2026-10-23-mi24p-clickabledata-forms.md`, which covers parsing forms, not values.

**Reading rule.** `arg_lim` is the range a control's argument can take. `arg_value` is the
**step per click** (sign = direction), not a position. Settable values come from `arg_lim`, plus
`arg_value`'s magnitude for stepped controls. `class` says whether it is a button (`BTN`,
momentary), a switch (`TUMB`, latching), or a continuous lever/axis (`LEV`).

## Globals (clickable_defs.lua:10-12)

`direction = 1` and `cyclic_by_default = true` are referenced by no helper, so they have no
effect. `anim_speed_default = 16` affects animation only.

`class_type` enum: NULL=0 BTN=1 TUMB=2 SNGBTN=3 LEV=4 MOVABLE_LEV=5 MULTY_TUMB=6 BTN_FIX=7
TUMB_4SIDE=8.

## Helpers

| helper | class | arg_value | arg_lim | settable values |
|---|---|---|---|---|
| `default_button(hint,dev,cmd,arg,anim,crew)` | BTN | `{1}` | `{{0,1}}` | momentary 0/1 (`use_release_message`, `stop_action=cmd`) |
| `default_spring_button(..,arg,arg_val_,arg_lim_,turn_box_,crew)` | BTN | `arg_val_ or 1` | `arg_lim_ or {0,1}` | momentary, default 0/1 |
| `default_square_button` | wraps `default_button` (sound only; `turn_box_` ignored) | | | momentary 0/1 |
| `default_tumb_button` | wraps `default_button` (side only) | | | momentary 0/1 |
| `default_position_tumb(..,arg,arg_val_,arg_lim_,turn_box_,crew)` | TUMB, class_vr BTN_FIX | `arg_val_ or 1` | `arg_lim_ or {0,1}` | default 0/1 |
| `default_1_position_tumb(..,anim,arg_val_,arg_lim_,crew)` | TUMB | `arg_val_ or 1` | `arg_lim_ or {0,arg_val_}` | default 0/1 (not called) |
| `default_2_position_tumb(hint,dev,cmd,arg,anim,crew)` | {TUMB,TUMB} | `{1,-1}` | `{{0,1},{0,1}}`, cycle=true | 0/1 |
| `default_2_position_small_tumb` | wraps `default_2_position_tumb` (sound) | | | 0/1 |
| `default_2_position_flares_tumb` | wraps `default_2_position_tumb` (sound, BTN_FIX, side) | | | 0/1 |
| `default_3_position_tumb(..,arg,cycled_,anim,inversed_,arg_value_,arg_limit_,crew)` | {TUMB,TUMB} | `{-v,v}`, `v = arg_value_ or 1`, negated if `inversed_` | `arg_limit_ or {-1,1}`, cycle=`cycled_ or false` | default -1/0/1 |
| `triple_switch(hint,dev,cmd,arg,crew)` | {TUMB,TUMB}, 4 actions, class_vr TUMB_4SIDE | `{-0.1,0.1,0.2,0.3}` | `{{0,0.3},{0,0.3},{0,0.2},{0,0.3}}` | 0.0/0.1/0.2/0.3 |
| `multiposition_switch(..,arg,count_,delta_,inversed_,min_,anim,cycled_,crew)` | TUMB | `{-d,d}`, `d = delta_ or 0.5` (×−1 if `inversed_`) | `{min_, min_+d*(count_-1)}`, `min_ or 0`; `count_` required | `min_ + k*d`, k = 0..count_-1 (every real call uses d = 0.1) |
| `default_button_tumb(..,cmd1,cmd2,arg,anim,crew)` | {BTN,TUMB} | `{-1,1}` | `{{-1,0},{0,1}}` | -1 momentary, 0/1 latching (not called) |
| `springloaded_2_pos_tumb` | wraps `default_2_position_tumb`, class {BTN,BTN}, arg_value {1,1} | | | momentary (not called) |
| `springloaded_3_pos_tumb(..,cmd1,cmd2,arg,anim,val1_,val2_,val3_,crew)` | {BTN,BTN} | `{val1,val3}` | `{{val1,val2},{val2,val3}}`; defaults -1.0/0.0/1.0 | -1/0/1, springs back to 0 |
| `default_animated_lever(..,arg,anim,arg_lim_,crew)` | wraps `default_2_position_tumb`, then arg_value `{1,0}` | | **`arg_lim_` ignored**: a typo (`arg_lim__`) means the range stays `{{0,1},{0,1}}` | 0/1 |
| `default_axis(..,arg,default_,gain_,updatable_,relative_,cycled_,attach_l,attach_r,crew)` | LEV | `{default_ or 1}` | `{{0,1}}`, gain `gain_ or 0.1`, relative `relative_ or false`, cycle `cycled_ or false` | continuous 0.0–1.0 (a wheel notch moves by gain; wraps if cyclic) |
| `default_axis_limited(..,default_,gain_,updatable_,relative_,arg_lim_,..)` | wraps `default_axis`, non-cyclic, `use_OBB=false` | `default_ or 0` | `arg_lim_ or {0,1}` | continuous, default 0.0–1.0 |
| `default_CB_button` | wraps `default_2_position_tumb`, arg_value `{1,0}` | | | 0/1 (not called) |
| `default_blue_cover` | wraps `default_2_position_tumb` (sound, side) | | | 0/1 |
| `radio_wheel_1(..,cmd1,arg,arg_value_,arg_lim_,slave_,crew)` | {TUMB,TUMB}, relative | `arg_value_ or {-0.1,0.1}` | `arg_lim_ or {0,1}` | 0.0–1.0 in 0.1 steps, relative |
| `stick_button(hint,dev,cmd,arg)` | BTN | `{1}` | `{{0,1}}` | momentary 0/1 (no crew param) |

Call counts in clickabledata.lua: default_2_position_tumb ~211, default_button ~82,
multiposition_switch ~40, default_axis 34, default_blue_cover 34, default_3_position_tumb ~26,
default_square_button 17, default_axis_limited 10 (one commented out),
default_2_position_small_tumb 10, default_position_tumb 9, default_animated_lever 8,
default_2_position_flares_tumb 8, springloaded_3_pos_tumb 5, radio_wheel_1 5, triple_switch 4,
stick_button 3, default_tumb_button 2, default_spring_button 2. Four helpers are never called:
default_1_position_tumb, default_button_tumb, springloaded_2_pos_tumb, default_CB_button.

## Real calls (quoted from the arg number onward)

- `multiposition_switch` (arg, count, delta, inversed, min, anim, cycled[, crew]):
  `RED-LTG1-PTR … 148, 11, 0.1, false, 0.0, anim_speed_default, false` (0.0–1.0, 11 steps);
  `AC-HEATER2-MODE-PTR … 145, 4, 0.1, …`; `DEICER-KNOB-PTR … 114, 11, 0.1, false, 0, nil, false`;
  `WEAP-SELECT-KNOB-OP-PTR … 709, 5, 0.1, nil, nil, nil, nil, 1`; `R852-CHANNEL-PTR … 518, 4, 0.1`;
  `SHSCHO-KNOB-PTR 963, 9, 0.1 …`; `PK-WORK-CHECK-PTR 899, 5, 0.1 …`.
- `default_3_position_tumb`: `LTG-COCKPIT-PTR … 356`; `LTG-COCKPIT-OP-PTR … 682, nil,nil,nil,nil,nil, 1`;
  `LTG-CARGO-PTR … 355`; `TAXILIGHT-RETR-PTR … 208`; `NAVLIGHT-BRIGHT-DIM-OFF-PTR … 207`. None sets
  `inversed_` or `arg_value_`, so all are -1/0/1.
- `default_axis` (arg, default, gain, updatable, relative, cycled, …): `RRUD-LEFT-PTR … 5, 0, 0.05, true, true, false`;
  `RRUD-RIGHT-PTR … 4, 0, 0.05, …`; `ALTIMETER-KNOB-PTR … 18, 1, 0.6, false, true, nil, nil`;
  `ALTIMETER-KNOB-OP-PTR … 788, 1, 0.6, …, 1`; `SIGHT-OP-BRIGHTNESS-PTR … 136, 0, 0.05, false, false, false, …`.
- `default_axis_limited`: `CABIN-PRESS-VALVE-PTR … 516, 0, 0.1`; `PKP-INIT-PITCH-KNOB-PTR … 941, 0, 0.02`;
  `PKP-INIT-PITCH-KNOB-OP-PTR … 782, 0, 0.02, nil,nil,nil,nil,nil, 1`; `UKT-KNOB-PTR … 951, 0, 0.02`;
  `SPU8-VOLUME-PTR … 457, 0.0, 0.05`. None passes `arg_lim_`, so all are 0–1.
- `default_animated_lever` (arg, anim): `ROTOR-BRAKE-PTR … 745, 2`; `ENG-BRAKE-LEFT-PTR … 6, 2`;
  `ENG-BRAKE-RIGHT-PTR … 7, 2`; `LANDING-GEAR-PTR … 232, 4`; `LANDING-GEAR-LOCK-PTR … 228, 6`.
- `radio_wheel_1`: all five are the Jadro-1I frequency wheels (args 437, 436, 429, 428, 427), each
  `{-0.1, 0.1}, {0,1}` plus a slave-animation table, e.g.
  `JADRO-001-PTR … 437, {-0.1, 0.1}, {0,1},{434,{0.0,1.0}, 1.0,slave = {435,{0.0,1.0},1.0,master_lim = {0.9,1.0}}}`.
- `springloaded_3_pos_tumb`: `COLLECTIVE-GOV-PTR … READJUST_DOWN, READJUST_UP, 747`;
  `SAU-B-SWITCH-PTR … 253, nil,nil,nil,nil`; `SPUU-CONTROL-PTR … 277, …`;
  `FIRE-PYRO-CHANNEL-PTR … 486, …`; `ARC-U2-FRAME-PTR … 325, anim_speed_default * 1.5`. None passes
  val1–3, so all are -1/0/+1 and spring back to 0.

## Post-assignment patches that change values

Both patched elements are `default_2_position_tumb`s (asp_commands.Manual_Auto arg 553,
Sync_Async arg 554):

```
:717 elements["SIGHT-MAN-AUTO-PTR"].arg_value = {0.5,-0.5}
:718 elements["SIGHT-MAN-AUTO-PTR"].arg_lim = {{0,0.5},{0,0.5}}
:720 elements["SIGHT-SYNC-UNSYNC-PTR"].arg_value = {0.5,-0.5}
:721 elements["SIGHT-SYNC-UNSYNC-PTR"].arg_lim = {{0,0.5},{0,0.5}}
```

So these two are 0.0/0.5, not 0/1. A value table built from the helper alone gets them wrong.

## Raw table literals

| line | element | class | arg_value | arg_lim | values |
|---|---|---|---|---|---|
| :40 / :58 | COLLECTIVE-CORR-PTR / OP-COLL-THROTTLE-PTR | {LEV,LEV} | {0.0,0.0} | {{-1,1},{-1,1}}, gain {0.1,0.1} | continuous -1..1 |
| :253 / :295 | CLOCK-LEFT(-OP)-PTR | {BTN,BTN,LEV} | {1.0,-1.0,1.0} | {{0,1},{-1,0},{0,1}} | per action |
| :274 / :314 | CLOCK-RIGHT(-OP)-PTR | {BTN,LEV} | {1.0,0.05} | {{0,1},{-0.15,0.15}} | per action |
| :736 | ILS-ADJUST-HANDLE-PTR | {TUMB,LEV,0,0}, class_vr TUMB×4 | {-1,-0.1,1,0.1} | {{0.0,1.0}}×4 | per action |
| :760 | BRAKE-LEVEL-OP-PTR | {TUMB,LEV,0}, class_vr {BTN_FIX,MOVABLE_LEV,MOVABLE_LEV} | {0,0,0} | {{0,1}}×3 | per action |
| :967 | RADAR-ALTIMETER-KNOB-PTR | {BTN,LEV} | {1.0,0.05} | {{0,1},{0,1}} | per action |
| :1010 / :1038 | STICK-PTT-PTR / OP-STICK-PTT-PTR | {BTN,BTN} | {1.0,0.5} | {{0.0,1.0},{0.0,0.5}} | momentary; 1.0 radio, 0.5 intercom |
| :1167 / :1186 | TIMIR-LEFT-OP-PTR_* | {TUMB,LEV} | {0,0} | {{0,1},{0,1}} | per action |

No element uses SNGBTN, MULTY_TUMB or MOVABLE_LEV in its `class` field. `class_vr` values in use:
BTN_FIX and TUMB_4SIDE.

## Catches

1. `default_animated_lever`'s `arg_lim_` parameter does nothing (the `arg_lim__` typo); its range
   always comes from the wrapped `default_2_position_tumb`.
2. `default_2_position_tumb` is 0/1 unless post-patched. The two ASP-17 sight switches above are
   patched to 0/0.5.
3. Several raw literals have multiple actions with different classes (a button and a lever on one
   element). Their values are per action, not one range for the element.
