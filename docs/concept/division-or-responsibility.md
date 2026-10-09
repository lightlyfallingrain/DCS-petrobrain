# Concept of division of responsibility into different layers/microservices

Layers:
- brain = LLM
- body = deterministic code
- aircraft = DCS I/O + API for exposing DCS data and possible commands to DCS
- memory = what has happended, what has been observed

Think microservice architechture. That tould naturally balance load on multiple processor cores or computers. DCS takes up all the GPU, a local LLM cannot run on the same computer. My MacBook Pro WM-M1 32GB RAM would be the computer running LLM with Ollama. My Windows computer (with DCS on it) has a lot of disk space, my Mac does not. LAN only, except possible cloud LLM.

## aircraft layer
- sensor / sensory input and output, i.e. data from DCS and commands to DCS
- world model query, data from world model (or maybe body layer, consider)
- aircraft manipulation
    - switches
    - sensors
        - which sensor to use, where to point it, etc
    - controls (defer)
        - pitch, bank, yaw control direct input, if possible
        - needs investigation on what is possible with DCS
    - aircraft speed, altitude (radar/barometric), heading (need to use either true or magnetic consistently, defer decision)
    - weapon system, if applicable (defer)
        - target acquisition, aiming, locking, firing, guiding

## brain layer
- LLM as the core brain, code that wraps interaction with LLM
    - potentially two different tiers of LLM, small fast local model and more capable model
        - model swap: either capable model is cloud model, or model swap in Ollama on request
            - if model swap in Ollama, only do that at briefing / when aircraft is on ground / explicit permission from player -> so that model swap delay does not cause brain-pause
- *what* we are doing and *why*
    - possible examples
        - flying to WP2 on route, because following mission flight plan.
        - scanning north-east for threats, because hostile territory is in that direction relative to current aircraft position
        - tracking target 2 o'clock on top of hill, because player requested
        - flying heading 320 degrees, 200 km/h, 100 m radar alt, because player instructed so (defer)
- high level reasoning of what to do and why
    - "why" is
        - mission briefing
        - player input
        - current world and aircraft state
        - current location
        - sensor input
        - knows units, friendly, enemy, neutral, unknown. Their positions and what they are doing. Threat levels they pose.
        - sensor input
        - memory of world and current mission
            - in campaign mission, also earlier campaign mission memory, if they provide useful detail
    - "what" is
        - scan, track, ignore, attack, report, etc
        - fly to waypoint, certain location, direction, etc
        - heading, altitude, speed, etc
        - what sensors to use and where to point them

## body layer
- deterministic code
- translates from brain to aircraft layer
    - example
        - brain: scan village 2 o'clock, 5 km
        - body:
            - 2 o'clock, 5 km -> 275 degrees, 5 km
            -> DCS coordinate x,y,z
            -> query world model
            -> determine scan points
            -> command aircraft layer to scan
            -> receive scan results from aircaft layer
            -> update mission memory
            -> report back to brain
    - example 2
        - brain: fly WP2, follow flight plan
        - body: heading to WP2, desired altitude, speed, terrain avoidance consideration
            -> command aircraft layer to achieve desired result
            -> observe DCS data to verify desired result, issue correcting commands if needed
- body must observe DCS data and use an inspect and adapt loop to measure if the desired outcome is achieved and issue corrective commands to reach it. This must be adaptive and allow time for DCS aircaft/world state to evolve, some things take time. (defer flight control until possible later stage, do this for sensors and detection)

## Speech / audio (SRS ICS)

- transport is SRS (SimpleRadio Standalone). Petrovich sits on the ICS (intercom) channel
    - player transmits on ICS -> Petrovich hears it
    - Petrovich transmits on ICS -> player hears it
    - same channel both directions, no separate mechanism for in/out
- an **audio adapter** owns the audio boundary. Proposed as its own thin component, sibling to the aircraft layer, not part of it
    - justification: aircraft layer's contract is "DCS I/O". SRS is a separate application with its own client/protocol, not DCS. Folding it into the aircraft layer would put two unrelated external processes behind one API
    - but it follows the same rule as the aircraft layer: **sanitized data out over a sensible API**, raw audio never leaves it
    - runs on the Windows box (where SRS and DCS are). Emits transcripts over LAN, accepts text to speak
- incoming audio path
    - PTT-down on ICS -> capture
    - **debounce**: ignore transmissions shorter than a sanity-check interval (accidental transmit-key clicks)
    - **silence/noise gate**: drop transmissions that are silence or noise rather than running STT on garbage
    - STT -> transcript text -> body layer
    - signal-level debounce and gating (duration, energy) live in the audio adapter, not body. Raw audio never crosses into body, and body should never see a transmission that was not real speech
    - any later *context-dependent* suppression — e.g. a tighter tolerance mid-engagement — is body's, acting on already-transcribed text. Not needed initially
- incoming routing gate (transcript -> action), decided by body
    - deterministic parse succeeds ("scan 2 o'clock", "watch that", "say again") -> body acts directly, no brain call
    - deterministic parse fails or is ambiguous, or the player asked a genuine question or wants judgement -> pass to brain, with whatever body already extracted from the transcript
    - brain either decides the action or asks the player for clarification
- outgoing routing gate (what Petrovich says), same split
    - **deterministic / templated**, body writes the text itself
        - command readbacks — "scanning 2 o'clock"
        - contact reports — "enemy, 2 o'clock, 3 km, group of 3 tanks, 2 IFVs and infantry, crossroad east of <village>"
        - urgent reactive calls — "missile launch, 9 o'clock, break right"
    - **brain-level**, body supplies facts, brain writes the text
        - judgement and advice — "commander, SAM threat in the target area, suggest terrain cover east of target"
        - anything conversational, or anything answering a question the templates do not cover
- outgoing audio path
    - chosen text -> TTS -> injected into SRS on ICS
    - TTS lives in the audio adapter, same as STT. Body and brain deal in text only
- latency note: the deterministic paths exist largely so common interactions do not wait on an LLM. A readback should be near-instant; an advisory may take a beat
- the text-only version of all of this (typed input standing in for STT, printed text standing in for TTS) is the thing to build first. The routing, parsing, templating and readback logic is not audio work and should not wait for audio

## Memory layer
- active mission memory
    - mission briefing
    - player instructions and intent
    - observations during mission
    - memory decay system, as time passes, certainty of locations and units becomes more uncertain (as units may move)
    - after mission, memory serves as basis for a debriefing document (defer)
    - active mission memory resets after mission (so that playing the same mission again is from clean-slate mission memory)
- campaign memory
    - when in a campaign mission, remember debriefings from earlier campaign missions
        - but not this mission file or mission files further in campaign, if it is being played again
    - note that DCS world state is not persistent nor necessarily continuos between campaign missions, each mission is it's own indivudial sandbox created by the campaign creator. Continuity is entirely dependent on the campaign creator.
- world memory
    - non-mission specific obervations about the world, per terrain module
- player memory
    - observations about player gameplay and communications, about interaction with player
    - objective is to learn how to improve interaction with player in order to achieve mission results
    - note that player style may vary a lot depending on terrain, aircraft, mission, weather, etc
- aircraft memory
    - per aircraft type
    - observations about operating that aircraft, what should pilot/co-pilot remember/learn about operating this aircraft type
        - environemnt conditions play a factor

## Inputs and outputs (summarized, above description may have more)
Brain
    - input: position, world around, aircraft state, known contacts, memory
    - output: actions
        - scan, track, ignore, report, attack, etc
        - communicate. Communication is a key feature, but not yet properly defined. Will be defined and specified in another document, later.
        - aircraft state manipulations (defer)
            - heading, alt, speed
            - individual system actions, body layer will translate to cockpit switch/instrument actions
    - maintains:
        - state, what we are doing and why
        - memory, what has happeded
        - goal: from mission briefing and player communicated intent

Body
    - "pilot body" operating cockpit instruments, swithces, buttons, systems so that action from brain is translated to actions on aircraft
    - monitoring of desired result vs achieved state and corrective actions to reach desired state

Aircraft
- inputs:
    - data that we can read from DCS during a live mission
        - "sensor" data from aircraft sensors (radar, MI-24 observation scope, RWR, etc)
            - can be approximated from DCS contacts list, filter by who can "see" what instrument can "see" -> approximation of sensor detecting
        - "sensory" data, what a pilot/copilot could see/feel in cockpit
            - aircraft pitch, bank, yaw, heading, speed, alt, current motion, etc
            - switch positions, indicator light on/off, instrument readings, etc
    - commands API that body can call to issue aircraft commands and manipulations
- outputs:
    - sanitized data over sensor and sensory API
        - offer data in standard format, sensible API, can ask for specific data, not everything at once
    - keep the most recent data in memory
        - would it be beneficial to offer API of delta since last query or given state?

## investigation
- what data is available from DCS, runtime?
    - existing solutions to get data?
    - reverse engineering investigations?
- what can DCS be commanded to do?
    - aircraft swithces, sensors
    - aircraft pithc, bak, yaw
    - heading, alt, speed
    - fly to waypoint, fly to any point, attack, what else?
    - existing solutions and reverse engineering?

