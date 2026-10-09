---
name: execute-the-published-recipe-before-trusting-it
description: A shell recipe written down in a convention doc is an untested claim; run it before citing or extending it — two published ID-minting recipes silently returned the wrong answer.
metadata:
  type: feedback
---

**A `grep`/`sort` recipe published in a convention document is an unverified claim. Run it against
the real tree before you cite it, extend it, or build a rule on top of it.**

**Why:** 2026-10-09, review round 4 of `obsidian-links-and-tags`. The round's headline finding was
that root `CLAUDE.md`'s ID table pointed at pointer files, so "read the highest existing ID" would
mint a colliding ID. The orchestrator's brief supplied the replacement command. Running it found
**the replacement was broken too, and so was the form already published in
`docs/DOC_CONVENTIONS.md`**:

| recipe | returns | real highest |
|---|---|---|
| `... \| sort -t B -k2 -n \| tail -1` on `body-layer/ROADMAP/` | `BL-B9` | `BL-B46` |
| `... \| sort -t W -k2 -n \| tail -1` on `world-model/ROADMAP/` | `WM-W9` | `WM-W12` |

`-t X` splits on the literal character `X`. `BL-` contains `B`; `WM-` contains `W`. Every affected
filename then shares an empty second field, `-n` scores them all 0, and the tie decays to a
lexicographic comparison where `B9 > B46`. **The second row had been the repo's own documented
recipe since the convention was written** — so minting the next `WM-W` item from it would have
produced the exact collision the invariant exists to forbid. `sort -V` is correct for every prefix.

Nothing about either recipe looks wrong on the page. Both read as obviously-fine idioms. The defect
is only reachable by execution, and the same `grep -oE '^[A-Z]+-W…'` prefix that made it *look*
rigorous is what hid it.

**How to apply:** when a task hands you a command, or a doc you are editing contains one, paste it
into a shell against the live tree and compare the output to an independently-derived answer (here:
`sed 's/.*-B//' | sort -n`). Same rule for a `grep -rl` find-the-set recipe — the `#needs-flight`
one in the same round returned 9 of 13 items **and exited 0**. A recipe that exits 0 on an
incomplete answer is the worst case, because the exit status reads as confirmation. Cheap: two
minutes. Related: [[feedback_verify_state_not_the_account_of_it]],
[[feedback_verify_mission_probe_pattern_claims]].
