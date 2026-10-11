# Attacking target

This describes player - Petrovich interaction when attacking a  target.

## Selecting target

Player: "[set|select] target <what> <where>"

### target selection logic

- units that match <what> and <where>
  - <what> can be classification or type
- if multiple units match
  - pick watched unit over not watched
  - pick closest
- report selected target: "target <what> <where>"

#### select left/right/near/far

Player: "step [count] left/right/near|closer|close/far|further|away"

-> select next (or N th next, N = count) unit matching to <what> in direction specified, stay within the unit group
- report selected target: "target <what> <where>"

This allow easy changing of target if detection logic picked the wrong one.

### deselect target

Player: "drop target" -> deselect target
Also normal "cancel/stop" path for cancelling tasks deselects.

## Attack run

### commanding attack run

Player: "engage/attack/attack-run <what> <where>"
- first perform target selection from <what> and <where> using the target selection logic above, then immediately start attack run behaviour

Player: "engange/attack target"/"attack run"
- start attack run on the selected target

### attack run behaviour

Petrovich guides the pilot to align with the target by perdiodic callouts about target location

See 'Brain layer — exploration notes (2026-09-24)' for earlier description of behaviour.

    This is part of that exploration description, lifted here for easy reference. Read the whole description from the file.

        Petrovich then guides the pilot onto the target by frequent callouts, whose register changes
        as the run develops:

        phase	what he says
        far	"10 o'clock, 2 km, edge of forest" · "11 o'clock, 2 km" · "12 o'clock, 1.5 km"
        close, boresight-relative	"10 degrees left, 15 degrees down, edge of forest" · "5 degrees left, 10 degrees down, 1 km" · "at nose, 5 degrees down, 800 m"
        lined up	"lined up, 700 m"
        after	"hit" / "missed, aim higher" · "target smoking / on fire / destroyed"
        re-attack	"target not hit, attack again?" → yes: keep the run and the watch · no: stop the run, keep the watch
        The user's own note on the lined-up call: "with rockets/gun attack run is almost never exactly
        boresight, it has to take trajectory into account, that's pilots job." So "lined up" means
        aligned in azimuth on the target, not the weapon will hit — ballistics stay with the pilot,
        deliberately.

#### 9K113 attack run (deferred)

When using anti-tank missiles, the co-pilot is responsible for missile guidance by keeping 9K113 fixed on target for the duration of the attack.
Otherwise as above, but:
- copilot keeps 9K113 fixed on target
- when starting attack, select a missile pylon that has missile (missile selector to pylon, light will illuminate if missile present)
- when missile is launched, stop callouts.
- when missile is on flight, keep 9K113 fixed on target
- when missile impacts, report hit or miss
- after impact or terminated attack run (missile has been launced), reset the missile guindance unit transmitter (there's a button to press).
- if target is destoyed and there is enough distance to safely attack another target in target group, switch no next target in list and point 9K113 at it. Let the pilot know and decide whether to push attack or turn away. If another attack not possible/safe, end attack run.


### ending attack run

Player: "disengage"/"stop attack"/"abort" -> stop attack run

If target is destroyed (on fire is enough), attack run stops automatically (9K113 exception stated above).


