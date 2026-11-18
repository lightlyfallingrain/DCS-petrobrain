-- Flying commands. Petrovich flies through the AI overlay (mode 2,
-- parked) or on the raw axes (mode 1, unparked) -- plans/speech-rules/
-- plan.md Stage 2/Stage 4, plans/flight-control/plan.md. Each
-- `flight.*` action dispatches by mode itself (Decision 21's `_by_mode`,
-- `rules.actions.py`); the wording and readbacks below are shared by
-- both modes unchanged. Every rule here except the two handover rules
-- (category "flight_handover", BL-16 mode 1 Decision 22) belongs to one
-- of the "flight_control*" categories: the gate refuses "unable, not
-- flying" before any of these handlers ever run when Petrovich has no
-- controls, and -- for the categories that need a particular held value
-- -- holds (then retries) during the takeover-settle window rather than
-- refusing outright.
--
-- No rule checks whether its action worked: an action that fails ends the
-- handler, and Petrovich says "unable, <reason>" (README, "Actions").

-- "turn left/right [NN]" -- with degrees, relative to the held heading
-- (unchanged); with no degrees (BL-16 mode 1 Decision 21), a continuous
-- turn: `flight.turn_continuous` raises "Unable, AI overlay." in mode 2
-- (there is no continuous-turn concept on the AI-pilot wheel) and starts
-- a turn-rate goal in mode 1.
when.speech("turn_heading_relative",
    "turn <direction:left|right> [<degrees:angle>]",
    "flight_control_heading",
  function(s)
    if s.degrees == nil then
      local sign = -1
      if s.direction == "right" then
        sign = 1
      end
      flight.turn_continuous(sign)
      if s.direction == "left" then
        say("Left.")
      else
        say("Right.")
      end
      return
    end
    local delta = s.degrees
    if s.direction == "left" then
      delta = -delta
    end
    flight.increment_heading(delta)
    say(s.degrees .. " " .. s.direction .. ".")
  end)

-- "Heading <deg>" -- the absolute form. The legacy compass-point form
-- ("heading north") is not ported: the shipped `heading` slot type is
-- three digits only (D7), with no compass-word alternative.
when.speech("turn_heading",
    "<verb:turn|fly> heading <heading_deg:heading>",
    "flight_control",
  function(s)
    local r = flight.set_heading(s.heading_deg)
    say("Heading " .. digits(r.heading_deg) .. ".")
  end)

-- "Level flight" / "level off" -- freezes heading, altitude and speed
-- at their current held values. `"flight_control_any"`: held while
-- *none* of the three is known yet, passes once any one of them is.
-- Stage P3+P4 (F-P8): "level off" is a second wording for this same
-- command, not a second meaning on `level_off` ("stop turn," below,
-- never touches an alignment) -- both wordings call this one action,
-- which speaks "Leveling off." instead of "Level flight." exactly when
-- it is aborting an "align for launch" dive (`r.leveling_off`, Q0's
-- "first level at current, then start recovery").
when.speech("level_flight",
    "level <form:flight|off>",
    "flight_control_any",
  function(s)
    local r = flight.level_flight()
    if r.leveling_off then
      say("Leveling off.")
    else
      say("Level flight.")
    end
  end)

-- "Speed <value>" / "speed max" -- `speed_target` is a union slot (D14):
-- Lua resolves which branch was heard before calling either zero-arg
-- `set_speed_max` or the one-arg `set_speed`, the same "resolve the
-- directive in Lua, hand the action a plain number" idiom `turn_heading_
-- relative` above already uses.
when.speech("set_speed",
    "speed <speed_target:speed_target>",
    "flight_control",
  function(s)
    if s.speed_target.kind == "max" then
      flight.set_speed_max()
      say("Speed max.")
      return
    end
    local r = flight.set_speed(s.speed_target.value)
    if r.is_max then
      say("Speed max.")
    else
      say("Speed " .. digits(r.speed_kmh) .. ".")
    end
  end)

-- "Slow down" / "speed up" -- one step from the AI's own held speed. The
-- pattern's own two word-sets admit the two invalid pairings too ("slow
-- up"/"speed down"); the handler rejects them explicitly rather than the
-- grammar trying to encode an exclusive-or no pattern element supports.
when.speech("speed_step",
    "<verb:slow|speed> <direction:down|up>",
    "flight_control_speed",
  function(s)
    local valid = (s.verb == "slow" and s.direction == "down")
      or (s.verb == "speed" and s.direction == "up")
    if not valid then
      say("say again -- no speed heard")
      return
    end
    local sign = 1
    if s.direction == "down" then
      sign = -1
    end
    local r = flight.step_speed(sign)
    if r.is_max then
      say("Speed max.")
    else
      say("Speed " .. digits(r.speed_kmh) .. ".")
    end
  end)

-- "altitude <value> [radar/barometric]" -- the readback always names
-- the reference actually about to be pursued (the 700 m radar cap),
-- never the one the player said. "alt" dropped (`[[BL-B129]]` D1, user
-- direction 2026-11-18: "altitude" is the word actually said) -- bench
-- evidence showed "hold alt" heard as "hold out" 2/4; "altitude" has no
-- such homophone collision.
when.speech(
    "set_altitude",
    "altitude <altitude_m:quantity> [<reference:radar|barometric>]",
    "flight_control",
  function(s)
    local ref_code = 0
    if s.reference == "radar" then
      ref_code = 1
    elseif s.reference == "barometric" then
      ref_code = 2
    end
    local r = flight.set_altitude(s.altitude_m, ref_code)
    if r.barometric then
      say(r.altitude_m .. " meters barometric.")
    else
      say(r.altitude_m .. " meters.")
    end
  end)

-- "climb/descend <m>" -- relative to the AI's own held altitude.
when.speech("altitude_step",
    "<direction:climb|descend> <amount_m:quantity>",
    "flight_control_altitude",
  function(s)
    local delta = s.amount_m
    if s.direction == "descend" then
      delta = -delta
    end
    local r = flight.step_altitude(delta)
    if r.barometric then
      say(r.altitude_m .. " meters barometric.")
    else
      say(r.altitude_m .. " meters.")
    end
  end)

-- "hold altitude" -- freezes the goal at the current held altitude.
-- Never names a reference in the readback (unlike `set_altitude`/
-- `altitude_step`), matching the pre-rules handler's own text exactly.
-- "alt" dropped (`[[BL-B129]]` D1) -- "hold alt" was heard as "hold out"
-- 2/4 on the bench; "altitude" is the word the user actually says.
when.speech("hold_altitude",
    "hold altitude",
    "flight_control_altitude",
  function(s)
    local r = flight.hold_altitude()
    say("Holding " .. r.altitude_m .. " meters.")
  end)

-- "Level off" -- stops a turn and holds the current heading.
when.speech("level_off",
    "stop turn",
    "flight_control_heading",
  function(s)
    local r = flight.level_off()
    say("Heading " .. digits(r.heading_deg) .. ".")
  end)

-- CBTM align/align-for-launch/break/break-away -- BL-16 mode 2 Stage
-- P3+P4 (`plans/flight-control/plan.md`, "Revised 2026-11-18 -- Stages
-- P3+P4 ready to build"). Category "flight_control": has-controls is
-- the whole precondition here, same as the HVRT rules below -- align/
-- align-for-launch answer "Unable, AI overlay." in mode 1 (permanent,
-- E-P20); break/break-away answer "Unable, not ready." in mode 1 for
-- now (temporary, until the mode-1 batch). Readbacks are the user's
-- own words (Stage P3 explore, answer 3): "Aligning.", "Aligning for
-- launch.", "Breaking left."/"Breaking right.", "Breaking away.".
when.speech("cbtm_align",
    "align",
    "flight_control",
  function(s)
    flight.cbtm_align()
    say("Aligning.")
  end)

when.speech("cbtm_align_for_launch",
    "align for launch",
    "flight_control",
  function(s)
    flight.cbtm_align_for_launch()
    say("Aligning for launch.")
  end)

when.speech("cbtm_break",
    "break turn <direction:left|right>",
    "flight_control",
  function(s)
    local sign = -1
    if s.direction == "right" then
      sign = 1
    end
    flight.cbtm_break(sign)
    if s.direction == "left" then
      say("Breaking left.")
    else
      say("Breaking right.")
    end
  end)

when.speech("cbtm_break_away",
    "break away",
    "flight_control",
  function(s)
    flight.cbtm_break_away()
    say("Breaking away.")
  end)

-- HVRT translate/hold/step -- bare single-word commands. The adapter
-- recognises these via its own exact, pre-rule `_HVRT_BARE_WORD_TOKENS`
-- shortcut (a measured fuzzy collision with `point`'s own verbs, see
-- that table's comment), not ordinary rule matching -- these patterns
-- exist so the rule still has one (for `PUT /rules`'s collision check
-- and the loader) and would still self-match if that shortcut were ever
-- bypassed. Category "flight_control": has-controls is the whole
-- category precondition here -- the hover-mode precondition
-- (`_ai_pilot_hvrt_ready`) stays the action's own finer check (D16/D18).
when.speech("hvrt_translate_left",
    "move left",
    "flight_control",
  function(s)
    flight.hvrt_translate_left()
    say("Left.")
  end)

when.speech("hvrt_translate_right",
    "move right",
    "flight_control",
  function(s)
    flight.hvrt_translate_right()
    say("Right.")
  end)

when.speech("hvrt_translate_forward",
    "move forward",
    "flight_control",
  function(s)
    flight.hvrt_translate_forward()
    say("Forward.")
  end)

when.speech("hvrt_translate_back",
    "move back",
    "flight_control",
  function(s)
    flight.hvrt_translate_back()
    say("Back.")
  end)

when.speech("hvrt_hold",
    "hold",
    "flight_control",
  function(s)
    flight.hvrt_hold()
    say("Holding.")
  end)

when.speech("hvrt_step_up",
    "move up",
    "flight_control",
  function(s)
    flight.hvrt_step_up()
    say("Up.")
  end)

when.speech("hvrt_step_down",
    "move down",
    "flight_control",
  function(s)
    flight.hvrt_step_down()
    say("Down.")
  end)

-- "You have controls" / "I have controls" -- BL-16 mode 1 Decision 22.
-- Category "flight_handover": always PASS, not limited by seat or
-- flight state -- what each means depends on state, which the action
-- itself reads (see that category's own docstring in rules/gates.py).
-- Refusals raise unable; "I have controls." is spoken only once Lua
-- confirms the take (the `says` argument, landed-confirmation contract).
-- In the AI overlay, "you have controls" is a silent no-op (the
-- 2026-11-17 answer -- Request Aircraft Control is that handover);
-- "I have controls" there answers "Unable, AI overlay." (U9).
when.speech("you_have_controls",
    "you have controls",
    "flight_handover", function(s)
  flight.take_controls("I have controls.")
end)
when.speech("i_have_controls",
    "i have controls",
    "flight_handover", function(s)
  local r = flight.release_controls()
  if r.acted then say("You have controls.") end
end)
