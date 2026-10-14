---
name: project_constants_bind_by_value_at_import
description: body-layer binds module constants by value (`from belief.decay import OBSERVED_WINDOW_S`), so any config/override design that mutates module globals after import is silently broken — resolve at the declaration and read the path from the environment, never argparse.
metadata:
  type: project
---

Any design that makes Petrobrain's declared constants overridable must resolve the value **at the
declaration**, not by writing module globals afterwards.

**Why:** body-layer imports constants *by value*, not by module —
`from belief.decay import OBSERVED_WINDOW_S` in `belief/contacts.py`,
`from eyesight_view import DEFAULT_MAX_LINES as EYESIGHT_DEFAULT_MAX_LINES` in `logger.py`, and
dozens more. A later `setattr(module, NAME, value)` never reaches the importer, so a
"load config then patch the globals" layer appears to work (the defining module shows the new
value) while every consumer keeps the old one. It fails *silently*, which is the exact defect a
tuning layer exists to prevent.

The same fact kills a `--tuning PATH` CLI flag: constants resolve during **import**, and `argparse`
in `main()` runs after every import has completed, so the flag would be parsed too late to have any
effect — again silently. An environment variable read on the loader's first use (i.e. during
import) is correct by construction. A `--print-tuning`-style flag is fine, because it only reads an
already-resolved registry.

Corollary worth keeping: **derived constants must never become config keys.** body-layer has ~6
(`decay.OBSERVED_WINDOW_S = SCAN_CYCLE_PERIOD_S`, `gaze.SCAN_CYCLE_PERIOD_S`,
`optic_policy.OPTIC_RETRY_INTERVAL_S`, …). Their coupling to their inputs is already structural;
exposing them would let the two drift apart, and exposing the inputs instead keeps the derivation
as mechanism.

**How to apply:** when planning anything that makes an existing constant overridable, injectable or
environment-dependent, grep for `from <module> import <CONST>` before choosing the mechanism —
the binding style, not the elegance, decides the design. Full reasoning and the TOML/`tomllib`
choice that falls out of it: `plans/configurable-constants/plan.md` (X-T26).

See also [[project_three_projections_of_a_group_roster]] for the other case where body-layer's
import topology constrained a plan more than the feature did.
