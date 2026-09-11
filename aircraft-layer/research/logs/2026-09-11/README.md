# Probe logs, 2026-09-11

Raw evidence for the command/detection investigation. Kept in-repo because
`win-mac-sync/` is gitignored and these are the primary record — several
conclusions in the dated research notes were overturned by re-reading them, so
the raw text matters more than usual here.

| file | probe | what it established |
|---|---|---|
| `probe-cmd.log` | `Export.probe-commands.lua` | `GetDevice`/`performClickableAction`/`get_argument_value` exist; ASP-17 write confirmed; 9K113 axes positional and linear |
| `probe-detect.log` | `Export.probe-detection.lua` | Petrovich's contacts are readable (`T-90A`, `BTR-60`); wheel options and `SEARCHING`/`TRACKING`/`WAITING` state readable |
| `probe-wheel.log` | `Export.probe-wheel.lua` | wheel drivable via `performClickableAction`; our sight command held 9/9 during his search |
| `probe-scan.log` | `Export.probe-scan.lua` | many runs, several void by probe bugs; the final run enumerates the full 8-contact list and confirms `SELECT TGT` → `TRACKING` |

`probe-scan.log` is append-only across ~8 runs; each begins with a `#####`
banner. The last run is the successful one. Earlier runs are kept deliberately —
the failures are what identified the `gmatch` empty-match bug and the
page-detection bug.
