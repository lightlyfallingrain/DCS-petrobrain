# Petrobrain long term high level plans and goals

## Petrivich as copilot (first goal)

- First phase and most important
- Copilot's primary responsibility is contact detection and identification and ATGM guidance
  - Covered by existing roadmap and implementation (2026-09-27)
- Secondary role: fly the helicopter (to be implemented by Petrovich as pilot)
  - While controlling the aircraft, copilot cannot use optics

## Petrovich as pilot (second goal)

- Pilot's primary responsibility is flying the aircraft and navigation, per players request
  - Player sets desired state, Petrovich as pilot flies the aircraft
      - controlling aircraft pitch, bank, yaw, collective
  - heading, speed, altitude
  - pitch, bank angle
  - turn X deg left/right
  - turn to X o'clock
  - level flight
  - fly to waypoint
  - follow flight plan
  - use navaid to fly course (navaid = NBD)
  - heading to 9K113 heading
  - align for ATGM launch
    - aircraft boresight and 9K113 LOS aligned within X deg. X can be found from Mi-24 documentation.

- Secondary role: scan for contacts
  - Pilot should maintain awareness where contacts are, and therefore look around for them, but that is not his primary role
  - Pilot cannot use 9K113, that is copilot only instrument
  - Pilot can use binoculars, but only when not controlling the aircraft
    - not controlling aircraft = copilot has controls or autopilot has the helicopter in stable state so that no control inputs are required

## General 

- Flipping swithes in cockpit
  - when there is a need
  - when player requests
  - e.g. "weapons on" -> flip correct switches to turn weapons on
  - later stage goal
- Mi-24 is 1970's era aircraft, way before satnav. Therefore, realistically, ownship position is also belief, not fact. Belief derived from navigation instruments, VFR flying and dead reckoning.
  - This is a *much* later goal.

## Wingbrain (later goal)

- Control AI wingman
  - not known if possible in DCS, need investigation
  - could use DCS AI as much as possible to do the "flying" and simply command it what to do
  - heading, speed, alt
  - turns
  - attack runs (DCS AI attacks suck in Mi-24, can we make it better?)
  - simulating contact detection similar to Petrovich copilot, but could use more simplified approach
  - *radio communications* with other units in flight (player and possible other wingbrain units)
  - should do as much as possible with deterministic AI logic, as little as possible with LLM


