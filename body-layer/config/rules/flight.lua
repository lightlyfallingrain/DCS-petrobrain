-- Flying commands. Petrovich flies through the AI overlay (parked, mode
-- 2) -- plans/speech-rules/plan.md Stage 2, plans/flight-control/plan.md.
when.speech("turn_heading_relative", "turn <direction:left|right> <degrees:angle>",
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
