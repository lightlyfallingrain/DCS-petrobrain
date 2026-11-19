# Wingbrain - concept

Goal: control DCS AI wingmen - how they fly and what they do.

## Prerequisites

### flight parameter control

*Goal: find a way to control wingman speed, heading, altitude dynamically via lua.*

We must find a way to control wingman
- speed
- heading
- altitude
Either by writing some parameter that DCS AI then flies or likely by using a dynamic waypoint to set these parameters.
If dynamic waypoint, then something like this:
- insert steering waypoint as next waypoint
- set it 1.5 km away in desired heading -> heading control
- set desired altitude and speed
- when waypoint closer than some limit (800m?) reset it to 1.5 km away
- when desired params change (or there is need to correct AI wingman drifting, update the waypoint

### attack control

*Goal: find a way to set target and engage it from lua.*

We need to find a way to specify which target AI engages and command engagement.
- if possible, what weapon to use

I have no idea how this can be done, needs investigation.

## Goals

1 - control winman flight (heading, altitude, speed)
2 - control wingman attacks (target selection, command attack)
3 - commands from player
4 - radio interface and radio communication
5 - wingbrain perception, detection, belief - simplified versions of what Petrovich does
    - until 5 is build, simply use belief from player aircraft Petrovich


### Flight control

Default behaviour for DCS AI wingmen is they fly formation with flight lead (player). Keep that initially. Only control flight patameters when necessary. At some later stage, if ever, we may build taking control of wingmen flight parameters immediately after takeoff.
If using the dynamic waypoint solution, that may mess up with the flight plan route. In first phase, ignore that, let it happen. We'll fix it at some point.

Flight control modes:
- fly heading, alt, speed
- fly to a point
    - hold there (orbit or hover) or turn and fly to next waypoint

### Attack control

We need to be able to specify which unit(s) AI wingman is to engage. Preferably by setting a certain unit by DCS id or something like that. It is ok to break no-omniscience rule to accomplish this.
We need to get AI to engage that target. If possible control *how* AI engages it, but likely that is outside what we can do from lua.

## Commands from player

Wingbrain gets commands not from ICS, but radio. Therefore audio capture needs to listen to full radio trigger (VOIP) press and record. 
Attach metadata to recording that tells
- ICS/RADIO
- if radio, then frequency of radio channel. SPU-8 selector tells us which radio is selected (R-8xx) and from that radio we get active channel and from that the frequence that channel is set to.
In audio-adapter route RADIO commands to wingbrain, ICS commands to Petrovich.
Before radio interface is built, simply ignore the frequency and send all commands to wingbrain(s).

Stage 1:
- simple player commands:
    - "speed <value>"
    - "heading <value>"
    - "altitude <value>"
Stage 2:
- attack commands:
    - "set target <unit> <where>" - in similar way as setting target to Petrovich
        - target is wingbrain internal state
    - "engage" - in similar way as command to Petrovich
        - AI wingman to engage set target

## Radio interface

Radio interface will need to be it's own layer. It acts as the medium for all intra-flight communications.
Wingbrain will simulate radio, not use the DCS radio.

Each flight member will be on a specific frequency (possibly multiple simultanous frequencies in future).
In player aircraft player control radio settings. Read the set values from aircfart: SPU-8 radio selector, R-8?? active channel and it's frequency.
For wingbrains, frequency is internal state. They share the same R-8xx channels and frequencies as player aircraft.
Initially winbrains start on R-863 channel 0.
Wingbrain changes channel on player command only. "Set radio channel <value> [shorthand-for-R-863/shorthand-for-R-828]"
Wingbrain listens on the channel (frequency) they are on. Other frequencies are not heard.
Wingbrain transmits on the channel (frequency) they are on.

Radio interface will simulate radio channels.
When someone (player, wingbrain) transmits, those who are on the same frequency will hear it.
Each wingbrain probably need to register with radio layer what frequency they are on. Then radio layer will relay trasmissions to listeners of that frequency.
Wingbrains will transmit on radio to talk to flight lead (player). Very much like Petrovich does.

Radio transmission will need a payload of two kinds: spoken text and data payload.
- For wingbrain transmits spoken text will be TTS'd and played via audio adapter if and only if player is listening on the transmission frequency
- Data payload is so that each wingbrain does not need to handle spoken text transmission, but instead acts on the data payload. -> spoken text is for player's benefit only.
Example:
Player: "2, turn right 30" on R-863 channel 0
Audio adapter STT's command, sends to radio layer. Radio layer (or some layer) extracts command data set from speech text: { from: 1, to: 2, command: "heading_increment", value: 30 }
If wingman number 2 is on R-863 channel 0, then he hears that transmission.
Wingman 2 will readback (=radio transmission as well) and act. Transmission { speech: "2, turn right 30", data: { from: 2, to: 1, command: "acknowledge"}}

Wingmen have their number in flight: 1, 2, 3, 4. They respond to radio transmissions by their number. "flight,..." means all wingbrains.
Player: "2, fly heading 320" -> message is intended for number two only. Two responds by readback "2, heading 320" and acts on it.
On commands to "flight" each wingbrain responds with their number, 2,3,4. Only first response does full readback, rest just answer with their number.
- Player: "flight, speed 100" -> "2, speed 100" > 2s silence on frequency > "3" > 2s silence on frequnecy > "4"
- if a unit does not answer within some seconds (busy, destroyed, returning to base, not on frequency), the next one will. 

Plain command "flight" will have each flight member respond with their number: "2", "3", "4".

Wingbrains can talk to player and to other wingbrains on the frequence when needed.
Petrovich can transmit on radio. Use case: player command on ICS to send unit location, mark, some known location or unit to flight. Petrovich then transmits that on radio (SPU-8 is pilot controlled, copilot can only transmit on whatever channel is active). That transmission would (as all) include text to speak so that player hears it and data section that wingbrains would act on. Readback from wingbrains as normal.
- this is real use case, but a later stage thing to build

## Wingbrain perception, detection and belief

Simplified version of Petrovich. Goal: sane detection kinda similar to Petrovich, but with emphasis on performance.
Stage 1: simply share Petrovich's belief from player aircraft. This is required for commands from player stage.
Stage 2: scanning and detection, but simplified and more based on statistical propabilities than eyesight simulation, dwell times, etc. The goal is to have sane detection for wingbrains, statistically similar to what Petrovich detects, but with much less CPU. Wingbrains will hold their own belief.
Stage 3: LOS. LOS is still important. If wingman is close to player (say within 500m) simply share (cached) LOS from player aircraft. If wingman if further away, do a LOS for units wingbrain would statistically detect and drop those he can't see. Cache LOS for a while, so we don't do it all the time.
Stage 4: belief transfer between wingbrains and/or Petrovich/player. Using radio, transmit a unit/group location. Receivers will add/update to belief. Only transmit on request: player request to transmit or winman commanded to act on a target he does not know > asks for target data > Petrovich will transmit target data.


## General concepts

Winbrain is to be a sub-module of Petrobrain. It will be a simplified version of Petrovich for Player. Focus is performance and simulation detail is allowed to be sacrificed. Especially detection behaviour is to be more statistical based to improve performance.

DCS missions have Player as flight lead (exceptions exist, but are out of scope initially) and 0-3 wingmen. Typical case is one wingman.
Wingbrain should be it's own service/thread. One parallel thread/instance per wingman. You can challenge this if it's not a good idea.
When mission start, detect how many members there are in player's flight. Start a wingbrain to control each of them. On mission end, stop wingbrains.
If flight of one, only player, wingbrain is not needed, radio layer is not needed.
Wingbrains will share mission interpreter's mission understaning. Briefing data is common to whole flight.
All communication/commands with wingbrains happen via radio.

Wingmen are usually of same unit type as player, but that is not necessary. However, mixing types is out of scope for now.

How existing Petrobrain code and modules can be reused needs planning. Prefer to use existing code/modules instead of duplicating or writing new. If needed refactor existing code to modulirize it so that wingbrain can simply call it or parts of it. Avoid code duplication, but at the same time wingbrain code is intended to be simpler and faster than Petrovich, at least for perception.

Wingbrain behaviour is to be controlled by lua rules and triggers, as BL-17 has built the framework.

