---
name: dcs-log-recon
description: Parse aircraft_layer_debug.log (or any Export.lua-style debug log) for a named probe's samples -- dedupe repeated payloads, count occurrences, extract multi-line entries. Use when investigating what a live DCS probe (list_indication, LoGetWorldObjects, get_param_handle, etc.) actually returned across a flight, instead of writing an ad hoc python heredoc each time.
---

# DCS Log Recon

Standardizes the log-parsing pattern from PB-1's live-spike sessions: `Export.lua`'s
`debug_log()`/`debug_dump()` calls write timestamp-prefixed, sometimes multi-line entries into
`Saved Games\DCS\Logs\aircraft_layer_debug.log`, synced back to `win-mac-sync/from-windows/`.
Answering "did this probe's value ever change across the flight" by hand (ad hoc `grep -c`,
inline `python3 -` heredocs with regex) is slow and error-prone to rewrite each session.

## Usage

```
python3 .claude/skills/dcs-log-recon/scripts/parse_dcs_log.py <log_path> "<probe_label>"
```

`<probe_label>` is the substring identifying the probe in its `debug_log` call, e.g.
`"list_indication(6)"`, `"LoGetWorldObjects()"`, `"get_param_handle(\"FlexSight_Distance\")"`.
The script anchors on the first line containing that label, captures every following line up to
(not including) the next timestamped line as that sample's full payload, then dedupes samples by
their content (stripping only the timestamp and the probe's own `#<N>` sample counter, so
otherwise-identical payloads compare equal regardless of when or which sample number they were).

Output: total sample count, distinct-body count, then each distinct body with its occurrence
count and one example (long bodies truncated at 500 chars).

Options:
- `--first N` — only consider the first N matches (useful for a quick early-flight check)
- `--show-samples N` — print up to N full examples per distinct body, not just one (useful when
  you want to see whether e.g. a timestamp or minor field varies within an otherwise-identical
  group)

## Example

```
python3 .claude/skills/dcs-log-recon/scripts/parse_dcs_log.py \
  win-mac-sync/from-windows/dcs-logs/aircraft_layer_debug.log \
  "list_indication(6)"
```

Reveals every distinct thing the probe returned across the flight (e.g. "empty", "crosshair
populated but no target", "Ural truck", "SA-3 launcher") and how often each occurred, in one
pass instead of a hand-rolled regex per session.

## Notes

- Works on any Export.lua-style debug log using the `HH:MM:SS <message>` line format this
  project's `Export.lua` files use (see `aircraft-layer/dcs-export/Export.lua`'s `debug_log`
  helper) -- not DCS-specific beyond that convention.
- Read-only against the log file; never modifies it.
