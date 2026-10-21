# Configurable cockpit effector sequences

Why? Instead of hard coding switch positions and sequences, we should have configuration files that are read at startup and sequences run on triggers. While it costs initial effort, it makes future cockpit sequences and chanes to them a lot easier.

Suppose we have a foldel under body layer for effector-sequences/ and files there. Select format so that it's easy for human and code: .lua, .json, .md, or something else.
This is concept, not final truth. 

## General principle

| file-param | for |
| --- | --- |
| aircraft | Mi-24 |
| petrovich-role | copilot |
| run-on-trigger | <trigger-name> |

| string: condition (optional) | int: effector-id | float: set-value | string: petrovich-says (optional) | string: comment (optional) |
| --- | --- | --- | --- | --- |
| | <id> | <up-value> | "switch set" | "what this means" |
| if (<id2> = <up-value>) | <id3> | <value> | | "when 2 raedy do 3" |
| wait_s(5) | | | | |

All effector sequences follow the 1 second between effectors rule.
  - allowed exception is control axes, but that is not the use of these files


## Example and explanations


| file-param | for |
| --- | --- |
| aircraft | Mi-24 |
| petrovich-role | copilot |
| run-on-trigger | mission-start |

explanations:
- aircraft: only Mi-24 supported at the moment. (Mi-8 likely at some future point)
- petrovich-role: only copilot supported for now. If role does not match, sequence does not run.
  - future roles: 
    - pilot - can swap between pilot and copilot *in flight*, so rule execution must be determined by current seat occupied (opposite of current Player occupied seat).
    - wingman - fixed role - ignore all files not for wingman role (deferred to a lot later)
- run-on-trigger - what trigger executes this sequence. Triggers are a predefined set, enumeration in code (so that the list is easy to expand, but does require code change). 


| string: condition (optional) | int: effector-id | float: set-value | string: petrovich-says (optional) | string: comment (optional) |
| --- | --- | --- | --- | --- |
| | <ICS switch id> | <up-value> |  | intercom on |
| wait_s(10) | | | | give player some time |
| if (<oat> > 10) | <fan> | <on-value> | | "fan on" |
| if (<light-level> != day | <dome light switch> | <white> | | white dome light |
| | <canopy> | <close> | "ready for startup" | | 

The above are examples, not things that need to work now.

## Example 2 - takeoff


| file-param | for |
| --- | --- |
| aircraft | Mi-24 |
| petrovich-role | copilot |
| run-on-trigger | takeoff |



| string: condition (optional) | int: effector-id | float: set-value | string: petrovich-says (optional) | string: comment (optional) |
| --- | --- | --- | --- | --- |
| if (<dome light> != <off>) | <dome light> | <red> | | red dome light |
| | <missile power> | <on> | | powering up missile system |
| | <guidance unit power> | <on> | "guidance unit warming up" | |


# Triggers

At least the folowing
| trigger | when | single / every time it happens |
| --- | --- | --- |
| mission-start | mission start | single |
| taxi | speed > 10 km/h and AGL < 10 m | single |
| takeoff | AGL > 10 m | every time |
| guidance-unit-ready | guidance unit warmup completed | every time |
| land | AGL < 10 m and speed = 0 | every time |
| observ-on | player commands observ on | every time |
| observ-off | player comands observ off | every time |
| weapons-arm | player commands weapons armed or attack run starts | every time |
| weapons-safe | player commands weapons safe or disengage | every time |
| atgm-launch | atgm fired (by player or Petrovich) | every time |
| atgm-hit | atgm gone, hit or miss | every time |
| target-destroyed | current target destroyed | every time |


- the 10 m AGL is the value currently used. Bind to that value. It may change with override values, that is intentional.
- when trigger condition is met (= *transition* to met condition, not every tick when condition is true), execute defined sequence(s).
- one file allowed per combination (aircraft, petrovich-role, run-on-trigger) so we don't have to deal with files disagreing and order.
  - error on load if multiple files

