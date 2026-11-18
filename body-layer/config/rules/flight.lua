-- Flying commands. Petrovich flies through the AI overlay (parked, mode
-- 2) -- plans/speech-rules/plan.md Stage 2/Stage 4, plans/flight-control/
-- plan.md. Every rule here (except "you/i have controls", category
-- "always" -- Q7: a silent no-op, the player toggles AI-overlay flight
-- mode himself) belongs to one of the "flight_control*" categories: the
-- gate refuses "unable, not flying" before any of these handlers ever
-- run when Petrovich has no controls, and -- for the categories that need
-- a particular held value -- holds (then retries) during the
-- takeover-settle window rather than refusing outright.
--
-- No rule checks whether its action worked: an action that fails ends the
-- handler, and Petrovich says "unable, <reason>" (README, "Actions").

when.speech("turn_heading_relative", "turn <direction:left|right> <degrees:angle>",
  "flight_control_heading",
  function(s)
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
when.speech("turn_heading", "<heading_deg:heading>", "flight_control",
  function(s)
    local r = flight.set_heading(s.heading_deg)
    say("Heading " .. digits(r.heading_deg) .. ".")
  end)

-- "Level flight" -- freezes heading, altitude and speed at their current
-- held values. `"flight_control_any"`: held while *none* of the three is
-- known yet, passes once any one of them is.
when.speech("level_flight", "level flight", "flight_control_any",
  function(s)
    flight.level_flight()
    say("Level flight.")
  end)

-- "Speed <value>" / "speed max" -- `speed_target` is a union slot (D14):
-- Lua resolves which branch was heard before calling either zero-arg
-- `set_speed_max` or the one-arg `set_speed`, the same "resolve the
-- directive in Lua, hand the action a plain number" idiom `turn_heading_
-- relative` above already uses.
when.speech("set_speed", "speed <speed_target:speed_target>", "flight_control",
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
when.speech("speed_step", "<verb:slow|speed> <direction:down|up>",
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

-- "alt[itude] <value> [radar/barometric]" -- the readback always names
-- the reference actually about to be pursued (the 700 m radar cap),
-- never the one the player said.
when.speech(
  "set_altitude",
  "<verb:alt|altitude> <altitude_m:quantity> [<reference:radar|barometric>]",
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
when.speech("altitude_step", "<direction:climb|descend> <amount_m:quantity>",
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

-- "hold alt[itude]" -- freezes the goal at the current held altitude.
-- Never names a reference in the readback (unlike `set_altitude`/
-- `altitude_step`), matching the pre-rules handler's own text exactly.
when.speech("hold_altitude", "hold <verb:altitude|alt>", "flight_control_altitude",
  function(s)
    local r = flight.hold_altitude()
    say("Holding " .. r.altitude_m .. " meters.")
  end)

-- "Level off" -- stops a turn and holds the current heading.
when.speech("level_off", "level off", "flight_control_heading",
  function(s)
    local r = flight.level_off()
    say("Heading " .. digits(r.heading_deg) .. ".")
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
when.speech("hvrt_translate_left", "left", "flight_control",
  function(s)
    flight.hvrt_translate_left()
    say("Left.")
  end)

when.speech("hvrt_translate_right", "right", "flight_control",
  function(s)
    flight.hvrt_translate_right()
    say("Right.")
  end)

when.speech("hvrt_translate_forward", "forward", "flight_control",
  function(s)
    flight.hvrt_translate_forward()
    say("Forward.")
  end)

when.speech("hvrt_translate_back", "back", "flight_control",
  function(s)
    flight.hvrt_translate_back()
    say("Back.")
  end)

when.speech("hvrt_hold", "hold", "flight_control",
  function(s)
    flight.hvrt_hold()
    say("Holding.")
  end)

when.speech("hvrt_step_up", "up", "flight_control",
  function(s)
    flight.hvrt_step_up()
    say("Up.")
  end)

when.speech("hvrt_step_down", "down", "flight_control",
  function(s)
    flight.hvrt_step_down()
    say("Down.")
  end)

-- "You have controls" / "I have controls" -- not the handover in
-- AI-overlay mode (that is a DCS key press the player makes); a silent
-- no-op (Q7: "say nothing, it's up to player to toggle AI overlay flight
-- mode"). Category "always": not limited by seat or flight state.
when.speech("you_have_controls", "you have controls", "always", function(s) end)
when.speech("i_have_controls", "i have controls", "always", function(s) end)
