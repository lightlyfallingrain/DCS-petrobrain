# Mission Start & Reset Patterns (BL-15)

- **A dataclass field declared `field(default=X, init=False)` (a plain `default`, not
  `default_factory`) is never reset by re-invoking `__init__` on an existing instance.** Python's
  generated `__init__` only emits a `self.attr = X` assignment for an `init=False` field when the
  default is a *factory* — a plain default lives only as a class-level attribute, so once an
  instance attribute of the same name is set (shadowing it), calling `__init__()` again has no
  statement that touches it back. `field(default_factory=X, init=False)` does not have this trap —
  it always gets a fresh assignment. This matters for any "reset by re-invoking `__init__`"
  pattern: check every `init=False` field for a plain default before trusting the pattern covers
  it; a completeness test that poisons every field via `dataclasses.fields()` and diffs against a
  fresh instance (rather than a hand-written list of fields to check) is what catches this
  automatically (`plans/bl15-mission-start/implementation.md`, `review.md`).
- **The "re-invoke `__init__` to reset" pattern only gives a genuine completeness guarantee for
  classes whose constructor can be called with no/preservable-only arguments.** A class needing
  live collaborators it cannot re-synthesize (a database connection, a theatre string, a network
  client) has to fall back to a hand-picked list of attributes to clear directly — and a new
  dedup/counter field added to that class later has no test that would catch its omission from
  that list. Worth stating explicitly which classes in a reset mechanism get the strong guarantee
  and which get the weaker one, rather than letting "there's a reset test for this class too" read
  as equivalent coverage (`plans/bl15-mission-start/review.md`).
- **A closure or function parameter that captures a mutable piece of state by value (a `theatre`
  string, an open writer, a connection) goes stale the moment that state can change at runtime
  without the closure being rebuilt.** Safe while the value is set once at process start; becomes
  a live hazard the instant a feature adds a runtime mechanism to change it (here: theatre
  switching, log re-roll). The fix pattern is uniform — read the live field off its owning object
  at call time (`runner.theatre`, not a captured `theatre: str` parameter) rather than capturing a
  value — and the hunt for every instance has to be a grep of every reader of the field/writer in
  question, not just the ones a dispatching brief happens to name
  (`plans/bl15-mission-start/implementation.md`, `review.md`).
- **When a degrade/refusal mode is added, check every way the system can *speak* — not just every
  way it can be *commanded*.** A gate placed only on command-dispatch entry points (the ones a
  human operates) leaves any autonomous/proactive output path (a scheduled callout, an async
  reply drain) silently ungated, and whether that currently matters can depend on an invariant
  elsewhere in the call graph that nobody wrote down — which fails silently (no crash, no test
  red, just the system speaking about state that should have been wiped) the moment a future
  change reaches the degrade mode by a different path than the one that currently makes it safe
  (`plans/bl15-mission-start/review.md`).
