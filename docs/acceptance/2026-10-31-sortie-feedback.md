# 2026-10-31 sortie feedback

## Voice commands: too many "confirm?" requests

User, verbatim:

> *"One other thing: I get many "confirm?" requests for my audio commands. The bar for "confirm?" is
> too high. The commands have mostly been correct and having to confirm a command many times per
> missio is very annoying. This needs a quick fix now."*

> *"recent speech logs are in windows, not here"*

Context at capture: `body-layer/src/belief/voice_commands.classify_response` acts at STT confidence
≥ `ACT_FLOOR` (0.60), ≥ `ACT_FLOOR_CANCEL` (0.80) for the six state-destroying tokens
(`CANCEL_TOKENS`), confirms down to `CONFIRM_FLOOR` (0.35), and always confirms an ambiguous match.
The only speech logs on the Mac (≤ 2026-10-17, 49 rows) show confirms at 0.55 ("describe.",
"silence.") and 0.65 ("violence." → silence, a cancel-class token). Recent logs are on Windows.

Handling: the user asked for a quick fix now, so this goes straight to a fix (`fix/voice-confirm-bar`)
rather than an explore round: lower the act bar, make the three floors tunable so they can be
adjusted from flight without a code change. Values refined once the Windows speech logs are read.
