# Target detection visual measurements in non-perfect condition

Syria, "normal test mission" as base.

Note: as conditions for observation deteorite (weather, light, vegetation), the measurements become more imprecise. Do not treat there numbers as definite truth, but rather coarse measurements that show *trends*. Those trends are the important part, from those we can derive rules or formulas to drive the visibility logic in differnt environmental conditions and terrain states.

## Sun info
sunrise 05:18:29, 63.2 deg
sunset 19:15:17 296.4 deg
N 31deg 34 min 55 sec
E 40 deg 17 min 01 sec

## observations

Ownship: more or less at 200 m AGL. It varied between 100 - 300 m AGL depending on conditions and DCS AI Petrovich poor flying skills. This matter in very low observability because of slant range. All ranges here are 2D plane ranges measured on DCS map.

Target: single BTR-60, broadside aspect.

### dark/light

At time 05:00 = sunrise -18 min. This is dawn, sky lit by sun below horizon, ground very dark but not black. Can observe targets, but just barely.
9K113 has an orange filter that increases contrast in low light conditions, therefore it's detection capability in low light is far greater than eye or binoculars.
| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
|eye | 0.5 | 0.2 | - |
| binocular | 1.3 | 0.2 | - |
| 9K113 W | 5.0 (barely) | 1.0 | 0.5 |
| 9K113 N | 12.0 (barely) | 3.4 | 1.8 |


At time 04:50 = sunrise -28 min. This is pre-dawn, sky lighting up by sun below horizon, ground extremely dark, cannot see detail with eyes. 9K113 with orange filter still detects.
| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
|eye | - | - | - |
| binocular | - | - | - |
| 9K113 W | 2.5 (barely) | 0.9 | 0.5 |
| 9K113 N | 7.0 (barely) | 2.0 | 1.1 |
note: there's NVG in Mi-24, but it is completely useless for detection, it let's you see terrain so you don't fly into it


At time 05:20 = sunrise +2 min. Near daylight for detection. Still fairly low light for type identification. Class clear from silhuette, type detection needs more light and sun this low makes it mode difficult. Again 9K113 orange filter makes it near daylight performance.
| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
|eye | 1.8 | 0.8 | 0.25 |
any optic = almost daylight perf

--> in low light
  - 9K113 remains usefull into low light because it has orange filter that increases contrast. In real darkness, cannot see anything.
  - detection range drops, most notably for non-9K113
  - classification possbile by silhuette at close range
  - type id not possible, not enough light to see details

### rain

Time 08:00 = daylight
Overcast and rain 2 - DCS preset
| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
|eye | 1.2 | 0.3 | - |
| binocular | 1.8 | 0.6 | 0.35 |
| 9K113 W | 3.7 | 2.8 | 1.6 |
| 9K113 N | 3.7  | 1.1 | 0.6 |


Time 08:00 = daylight
Overcast and rain 3 - DCS preset
| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
|eye | 1.3 | 0.2 | - |
| binocular | 2.7 | 0.6 | 0.4 |
| 9K113 W | 5.5 barely| 2.6 | 1.6 |
| 9K113 N | 4.1 barely | 1.3 | 0.6 |

--> rain drastically reduces visibility through windsreen (to be tested: wipers. But the only cover a tiny segment at boresight)
  - it's the rain drops on the windscreen, makes everything blurry
  - 9K113 not affected by rain drops on glass -> not blurry. But visibility reduced by raindrops in air and meteorological horizontal visiblity

#### windscreen wipers

They do help, they remove the blur. However, wipers only clear area relative to boresight of
- left edge -10 deg
- right edge +10 deg
- bottom edge -17 deg
- top edge +3 deg

Not worth modeling at this stage. Info here if we ever model that.

### rain + sunrise/sunset

Time 05:00 = dawn before sunrise, see dark/light section
Overcast and rain 2 - DCS preset
| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
|eye | 0.65 | 0.1 | - |
| binocular | 1.0 | 0.3 | - |
| 9K113 W | 3.2 | 0.8 | 0.4 |
| 9K113 N | 4.0 barely  | 2.1 | 1.0 |


### snowfall

Note: exception to other flights:
  - Caucasus region.
  - 21 January 2016
  - Sun 22.0 deg, 154.7 deg.
  - Sunrise 09:02:34 118.5 deg
  - Sunset 18:17:14 241.6 deg
  - coords N 44 deg 02 min 43 sec, E 37 deg 47 min 58 sec

Time 12:00 = midday. 
Overcast and rain 2 - DCS preset. -10 deg C, so snow and white snowy ground.
| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
|eye | 2.1 | 0.4 | 0.2 |
| binocular | 5.0 | 2.2 | 0.8 |
| 9K113 W | 5.1 | 1.7 | 0.6 |
| 9K113 N | 7.0 | 4.1 | 2.0 |


### fog

To be measured, but limiting factor should be the meteorological visibility. The optics should be able to pick units, if the atmospheric conditions allow seeing that far.

Note: when inside fog/cloud, besides limited horizontal (and vertical) visibility, flying *towards the sun* creates a whiteout effect where sunlight scattering in fog/cloud shrouds everyhing in white glare. Next to no visibility at all. Setting up test scenario deterministically is difficult, so no prores measurements. Would at least need an azimuth estimate of how wide the white-out effect is.


## terrains

### forest

Syrian forest (or plantation, among trees generally) on flat land.

| instrument | detection km | class km | type km |
| --- | --- | --- | --- |
| any | - | - | - |

Any unit among trees can basically only be detected from straight above by and/or by heat signature. That targeting pod territory for likes of A10, not helicopter.
I know where the BTR-60 was, I used the map to see it's right below me and I flew circels with high bank angle to gaze down fairly vertically and still could not detect it.

### settlement

- Depends a lot on LOS with buildings. If hidden by building(s), can't see.
- When LOS exists, if close to/among building, it's still harder to detect, because of many blocky shapes to hide among. 

No clear way to model that statistically, we'll have to come up with something.



