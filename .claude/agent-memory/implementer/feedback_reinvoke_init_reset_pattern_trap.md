---
name: reinvoke-init-reset-pattern-trap
description: "re-invoking __init__() to reset a dataclass instance silently skips init=False fields with a plain `default` (not `default_factory`) -- found implementing BL-15's mission-start reset"
metadata:
  type: project
---

Body-layer's BL-15 Stage 1/2 (`plans/bl15-mission-start/plan.md`) established a
reset pattern used across five classes: `reset_for_new_mission()` re-invokes
`self.__init__(...)`, passing through only the fields that must survive, so
any field added later resets to the constructor's own default automatically.

**The trap, confirmed by direct repro, not just reading the dataclasses
docs:** for a dataclass field declared `field(default=X, init=False)` (a
*plain* default, not `default_factory`), Python's generated `__init__` does
**not** emit a `self.attr = X` assignment at all -- the default lives only as
a class-level attribute. Once something sets an *instance* attribute of the
same name (shadowing the class attribute), calling `__init__()` again never
resets it, because there is no statement in the generated `__init__` to do
so. `field(default_factory=X, init=False)` does **not** have this problem --
a factory field always gets a fresh `self.attr = X()` assignment inside
`__init__`, confirmed by the same repro.

```python
@dataclasses.dataclass
class Foo:
    y: int = dataclasses.field(default=2, init=False)       # TRAP
    z: list = dataclasses.field(default_factory=list, init=False)  # safe

f = Foo()
f.y = 999
f.z.append(1)
f.__init__()
# f.y == 999  (!) -- not reset
# f.z == []   -- reset, as expected
```

`logger.ConsolePerceptionRunner._last_look_direction`
(`field(default=None, init=False, repr=False)`) was exactly this shape. The
per-class completeness test (`test_mission_start_reset.py`, which poisons
every non-preserved field and asserts it resets to a fresh instance's
default) caught it immediately. Fix: one explicit
`self._last_look_direction = None` line *after* the `__init__` re-invocation,
documented in `reset_for_new_mission`'s own docstring.

**How to apply:** before trusting a "re-invoke `__init__`" reset pattern on
any class, check every `init=False` field declaration for a plain `default=`
(as opposed to `default_factory=`) -- that field needs its own explicit reset
line, the re-invoked `__init__` will not touch it. A completeness test that
poisons every field and checks it against a fresh instance's default (not a
hand-written list of "fields I remember to check") is what surfaces this
automatically; a reset test that only checks a few named fields would not
have caught it.
