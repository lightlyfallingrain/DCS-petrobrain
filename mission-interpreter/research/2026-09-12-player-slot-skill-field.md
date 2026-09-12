# Player-Slot Marker: `skill` Field on `unit[]` Entries

**Date:** 2026-09-12
**DCS version:** not stated in sample (mission `["version"] = 23`, a format-revision number — see prior note)
**Theatre:** Afghanistan (`Mission 02-Bagram.miz`, same sample as the prior MI-0/MI-1 validation note)

### Question
MI-3 needs to populate an `ownship` field in `MissionUnderstanding` by "trivial passthrough" from the parsed mission tree. That's only trivial if there's a reliable, structurally-identifiable marker distinguishing a player-flyable unit from an AI-only one. The community convention (pydcs, general ME knowledge) is a `skill` field with values `"Client"`/`"Player"` for human slots vs. `"Average"`/`"Good"`/`"High"`/`"Excellent"` for AI — unverified against real bytes in this project until now. `tree.py`'s `Unit` dataclass currently has no `skill` field.

### Findings

All findings are **evidence: reproduced-locally** (grep/Read against the real sample's extracted `mission` table) unless otherwise labeled.

- **Every `unit[]` entry does carry a `skill` field.** 44 occurrences of `["skill"]` in this file. Distinct values observed: `"Average"` (23), `"High"` (20), `"Player"` (1). **`"Client"` does not appear anywhere in this sample.**
- **The single `skill = "Player"` unit is exactly the player's own aircraft.** At `unitId = 90`, `type = "Mi-24P"`, `name = "Player (Восток-2)"`, inside a group named `"Player (Восток-2)"` (`groupId = 38`), under `mission.coalition.red.country[1].helicopter.group[1]`. This confirms the community convention directly: `skill = "Player"` marks the human-flyable slot, and it correctly identifies a flyable Mi-24P.
- **The unit's own `name` field also happens to say "Player"**, but this is mission-author-supplied text (Russian campaign, literal string `"Player (Восток-2)"`), not a schema guarantee — a parser must not rely on the string `"Player"` appearing in `name`. `skill` is the structural field; `name` here is coincidental/cosmetic.
- **No other field reliably signals "player slot" — checked and ruled out:**
  - `callsign` — present on 12 numeric-valued units and several table-valued ones (30 total occurrences across the file); the player unit's `callsign = 134` is just one more numeric value in that range, not a distinguishing marker.
  - `onboard_num` — 21 occurrences, present on many non-player aircraft units too.
  - `AddPropAircraft` — 20 occurrences, present on every Mi-24P-type unit (player and AI alike), not player-specific.
  - `uncontrolled` (group-level, sibling of `task`) — `false` on the player's group but also `false` on 3 other groups in this file, so it does not uniquely identify the player group either.
  - No `unitId` cross-reference elsewhere in the tree (e.g. no separate "playerUnitId" pointer at the mission root) was found.
  - Conclusion: **`skill` on the `unit` entry is the only structural marker found in this sample.**
- **Group/unit category context confirms the slot is a flyable aircraft**, consistent with the prior note's established path `mission.coalition.<side>.country[N].<category>.group[].units[]` (`<category> = "helicopter"` here).
- **Count in this sample: exactly one `Player`-skill unit, zero `Client`-skill units.** This is a single-player campaign mission, consistent with needing only one player slot.

### Reproducible Test
```
unzip -p "mission-interpreter/research/samples/<file>.miz" mission > /tmp/mission.lua
grep -o '\["skill"\] = "[A-Za-z ]*"' /tmp/mission.lua | sort | uniq -c
grep -n '\["skill"\] = "Player"\|\["skill"\] = "Client"' /tmp/mission.lua   # then Read surrounding unit/group block
grep -c '\["callsign"\]\|\["onboard_num"\]\|\["AddPropAircraft"\]\|\["uncontrolled"\]' /tmp/mission.lua  # sanity-check these aren't player-exclusive
```
(Scratch file kept outside the repo, per the existing sample-handling discipline — third-party campaign content, never committed, never quoted at length.)

### Possible Approaches
- MI-3's ownship-detection logic should walk all `unit[]` entries across all coalitions/countries/categories and select the one(s) with `skill in {"Player", "Client"}` — do **not** key off `name` string content, callsign ranges, or `uncontrolled`, none of which are reliable per the findings above.
- `tree.py`'s `Unit` dataclass should gain a `skill: str` field (plain passthrough string) so this logic has something to read; no new parsing complexity needed beyond that.
- Because a mission could in principle contain more than one player-skill unit (see Unresolved), ownship-detection should collect **all** matches and only fail/flag-for-review if the count isn't exactly 1 for a single-player mission context, rather than blindly taking "the first match" — cheap to build now, saves a silent-wrong-answer failure mode later for a multiplayer sample.

### Unresolved
- **Client vs. Player distinction**, from general/secondhand DCS Mission Editor knowledge (not re-verified via live forum/wiki fetch this session — **evidence: forum-claim-unverified**): `"Client"` marks a slot human-flyable in multiplayer (also usable when flown solo), while `"Player"` marks a slot restricted to single-player-only (locks exclusively, not selectable as an MP client slot). If that distinction is accurate, MI-3 should treat both as "this is a player slot" for ownship purposes (mission type — SP vs MP — decides which variant appears, not whether it's a player slot at all). This sample only exercises `"Player"`; a multiplayer sample would be needed to reproduce `"Client"` against real bytes and confirm the distinction holds structurally rather than just by ED convention.
- **Guarantee of exactly one player-skill unit is not established in general.** This sample shows exactly one (`Player`, count 1; `Client`, count 0) — consistent with a single-player campaign — but nothing here proves DCS enforces "at least one" or "at most one" `Player`/`Client` unit mission-wide. A multiplayer mission with multiple client slots, or a purely-AI mission stub, would need a second sample to check. Flag this as an open generalization question for MI-3: the ownship-selection step should handle 0 matches (error/flag) and >1 matches (ambiguous — needs another signal, e.g. player-selected slot at mission start, which is runtime info not present in the static `.miz`) explicitly rather than assuming exactly 1.

### Cross-reference
Builds on group/unit container path and schema established in `mission-interpreter/research/2026-09-12-miz-validation-against-real-sample.md` (same sample file). That note did not examine unit-level fields beyond `unit_id`/`name`/`type`/`x`/`y`; this note extends it with the `skill` field specifically.
