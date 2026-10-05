---
name: name-the-acceptance-boundary-when-the-observable-is-an-absence
description: When a fix's observable is silence, a green fixture suite is especially weak; say so in the card and give the user the asked-vs-unprompted discriminator up front.
metadata:
  type: feedback
---

**When the thing a fix produces is an *absence*, a fixture pass is weaker evidence than usual, and
the acceptance card has to carry the discriminator or it will read as a failure.**

**Why:** `fix/callout-observability-gate` (2026-10-06) silences 17 unprompted callouts about clock
hours Petrovich cannot see — while a pilot `report` **deliberately still answers** about the same
rear hemisphere, because belief survives the aircraft turning away. A card that does not make that
split explicit guarantees the user scores a correct `report` answer about 7 o'clock as the bug
still being present. Separately, every test asserts `scheduler.tick(...) == []` against a hand-built
store, so the suite cannot tell "silent because the gate worked" from "silent because something
upstream stopped producing the event" — that distinction only exists in flight. This is the same
class as the F10-vocabulary defects: code doing exactly what it says, possibly against the wrong
subsystem or the wrong intent, which no fixture detects.

**How to apply:** for any silencing/suppression/gating fix, the card must state (1) that there is no
new sound to notice, (2) the one path that must *still* speak and how to provoke it, and (3) the
single question that resolves an ambiguous observation — here, *"did I just ask for it?"*. And in
the DoD report, name the gap plainly: a suite of `== []` assertions cannot distinguish a working
gate from a broken producer. Pairs with [[project_recurring_outcome_only_regression_test]], which is
the same weakness one layer down: asserting the outcome rather than the mechanism.
