---
name: reference-grep-device-name-not-label-for-russian-initialisms
description: when a Mi-24P system is known only by its Russian initialism (SAU, SPUU, DISS, ...), grep effectors-raw's device_name field directly -- an English-word label search will miss it
metadata:
  type: reference
---

Found 2026-11-28 investigating the pedal-stops/SPUU-52 question
(`aircraft-layer/research/2026-11-28-mi24p-pedal-stops.md`): a first-pass grep of
`body-layer/config/effectors-raw/mi-24p.toml` for English synonyms of "adjustable stops" ("stop",
"limit", "restrict", "adjust", "gauge", "knob") found nothing, even though the control (device 19,
`SPUU_52`) was right there in the file — because ED's own source comment (which the registry's
`label` field is generator-derived from) used the system's Russian initialism transliterated to
Latin ("SPUU"), not an English translation. The element `SPUU-CONTROL-PTR` even appeared in an
earlier `springloaded_3_pos_tumb` shape sweep in the same session and was misread as unrelated,
because the eye was scanning for "SAU"/"stop", not "SPUU".

**The fix: when a real Mi-24P system is known by a Russian name/initialism (СПУУ-52, ДИСС, САУ-В24,
...), grep `device_name` values directly** (`grep "^device_name" effectors-raw/mi-24p.toml | sort
-u` lists all ~49, or `grep -i "spuu\|sau\|diss\|..."` against that smaller list) **before**
searching `label` text for English synonyms. The label is a translation layer and can miss or
garble the system's identity; the device name is often a closer transliteration of the source and
is a much smaller haystack to eyeball once narrowed.

See [[project_spuu52_pedal_stops_identified]] for what this unblocked.
