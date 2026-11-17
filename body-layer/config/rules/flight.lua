-- Flying commands. Petrovich flies through the AI overlay (parked, mode
-- 2) -- plans/speech-rules/plan.md Stage 2, plans/flight-control/plan.md.
-- "flight_control" (Stage 3b, D16): the category gate refuses "unable,
-- not flying" before this handler ever runs when Petrovich has no
-- controls, and holds (then retries) during the takeover-settle window.
when.speech("turn_heading_relative", "turn <direction:left|right> <degrees:angle>",
  "flight_control",
  function(s)
    local delta = s.degrees
    if s.direction == "left" then
      delta = -delta
    end
    local r = flight.increment_heading(delta)
    if not r.ok then
      say(unable(r.reason))
      return
    end
    say(s.degrees .. " " .. s.direction .. ".")
  end)
