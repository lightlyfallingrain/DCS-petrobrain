---
name: bl11-perf-stages
description: BL-11 Stages 1/2/3b/5 — hoist-vs-scene speedup ratios, the None-omission test collision, and the grep-test wording trap.
metadata:
  type: project
---

`BL-11` Stages 1, 2, 3b, 5 landed on `feature/bl11-tick-cost` (2026-10-06).
Four things that cost real time and are not derivable from the diff.

**A measured speedup from a research note is scene-dependent, and saying so
beats matching it.** Stage 2's note measured `group_salient_ids` at 215 ms /
8.1× at n=440. The synthetic scene in the equivalence test gives 24.8 ms /
5.0×. Not a worse fix — cost is O(*resolvable*²), and that scene resolves 145
of 440 candidates (~10 k pairs) against the sortie's ~96 k. **When a
reproduction's absolute numbers are an order out, check the loop's actual
iteration count before doubting the fix.** Report both figures; a flight
measurement that comes back at 5× is then not read as a regression.

**Omitting `None` fields from a JSONL row collides with tests that assert
explicit nulls, and the test is usually right.** `_entry_to_dict`'s blanket
omission broke `test_writer_leaves_contact_id_null_when_never_admitted`.
The resolution was *not* to edit the test: `observation_id`/`contact_id` are
join keys, where an absent key reads as *unknown* rather than the definite
*never admitted* a `null` states. Narrowing the rule to exempt the join keys
kept nearly all the byte saving (the motion/LOS annotations are almost all of
the `None`s anyway). **Generalise: before omitting nulls from a record format,
separate "optional annotation" from "deliberately-null answer".**

**A grep test over `src/` for a stale claim fails on its own correction.**
`test_no_stale_five_hertz_claims_remain_in_src` fired on the comment that
*explains* the 5 Hz claim was wrong. Spell the forbidden string out in words
in prose that has to discuss it, and say in the comment why — otherwise the
next reader "fixes" the wording back and breaks the build.

**Overrun policy is a decision a deadline-sleep loop must state.**
`logger._wait_for_next_tick` drops missed ticks (re-bases the deadline on the
clock now) rather than advancing by one interval, which would accumulate debt
and run the loop back-to-back until repaid. Justified by the loop's nature:
every poll reads the *latest* telemetry, so a skipped tick has no backlog.

See also [[feedback_worktree_branch_behind_main]] — this worktree was created
four commits behind `main`, i.e. before the research note this milestone is
built on existed.
