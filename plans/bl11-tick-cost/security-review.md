# Security Deep Analysis: BL-11 (Stages 1, 2, 3b, 5)

Branch `feature/bl11-tick-cost`, tip `69073ca` (verified by `git rev-parse HEAD` after
fast-forwarding this worktree's own branch — the feature branch itself was checked out in
another agent's worktree and git refuses a second checkout).

Checks re-run here, against imports proved to resolve to this worktree's own `src`
(`run_log_paths`, `perception.object_model`, `belief.enrichment` all tracebacked through the
worktree's absolute path): **`pytest tests -q` → 1512 passed, 4 xfailed**, matching the
implementation log.

## Dependency Status

**No dependency change.** No addition to `body-layer/pyproject.toml`; the only new imports are
stdlib (`contextlib`, `functools.cache`, `math`, `sys`, `time`, `pathlib`). No CVE search was
warranted.

## Scope of the attack surface this branch touches

No network surface is added or widened. No new deserialisation, no subprocess, no `eval`/`exec`,
no `pickle`, no credential handling — a pattern scan of all nine changed `src` files returns only
pre-existing `token` identifiers (`brain_client.py:169` is a brain-response command token,
`logger.py:1343`/`:1378` are F10 command tokens, `object_model.py:53-61` is prose about word
tokenizers). None is a secret and none is in the diff.

One genuinely new surface: **a CLI argument now creates directories.** That is the whole of the
security-relevant delta, and findings 1–3 are about it.

## Code Findings

| # | File:Line | Pattern | Assessment | Action |
|---|---|---|---|---|
| 1 | `body-layer/src/logger.py:1751` (call outside the guard at `:1752-1760`) | degrade policy guards `OSError`, misses `ValueError` | **LOW** — confirmed by probe | Recommended, not required |
| 2 | `body-layer/src/logger.py:1948`, `:1974`, `:2017` (argparse `type=Path`) | `~` never expanded; `mkdir` now materialises it | **LOW** — latent, fix before public release | Recommended |
| 3 | `body-layer/src/logger.py:1753` | `mkdir(parents=True)` on an unbounded caller-supplied path | **INFORMATIONAL** — typo blast radius, not a vulnerability | Accept, stated below |
| 4 | `body-layer/src/detection_trace_writer.py:128`, `belief_truth_log.py:411` | a disabled writer leaves no in-band marker | **LOW** — analysis-integrity, not exploitability | Recommended |
| 5 | `body-layer/src/detection_trace_writer.py:125`, `belief_truth_log.py:408` | `contextlib.suppress(OSError)` around `close()` | **INFORMATIONAL** — correct as written | No action |

---

### 1. The Stage 5 degrade policy guards `OSError` and misses `ValueError` — LOW

`_per_run_log_paths.resolve` (`logger.py:1747-1760`) calls `per_run_log_path(path, stamp_at)`
**outside** its `try:` block, and the `except` clause is `OSError` only:

```python
stamped = per_run_log_path(path, stamp_at)     # ← outside the guard
try:
    stamped.parent.mkdir(parents=True, exist_ok=True)
except OSError as exc:
```

`per_run_log_path` ends in `path.with_name(...)`, which raises **`ValueError`** — not `OSError` —
for any path with an empty final component. Probed directly:

```
'.'   -> ValueError: PosixPath('.') has an empty name
'/'   -> ValueError: PosixPath('/') has an empty name
''    -> ValueError: PosixPath('.') has an empty name
```

**Failure scenario.** The pilot types `--detection-trace .` or `--detection-trace logs/trace`
with the filename elided. Instead of the stage's own policy ("an unwritable log should cost the
sortie its trace, not its crew" — that docstring, `logger.py:1742`), `main()` dies with an
unhandled traceback before the crew starts. The exact failure mode Stage 5 was written to remove,
reached through a different exception type.

This is not a *regression* in crash-vs-no-crash terms — before Stage 5 those paths would have
died at `path.open("a")` with `IsADirectoryError` instead. But the stage introduced a stated
degrade guarantee and this path escapes it.

Related, same function, no crash: `--detection-trace logs/` (trailing slash, meaning a directory)
produces `logs-20261006-143500` **as a file in the parent directory**, because `with_name`
rewrites the last component whatever it is. Surprising, harmless, no escape.

**Fix** — move the call inside and widen:

```python
try:
    stamped = per_run_log_path(path, stamp_at)
    stamped.parent.mkdir(parents=True, exist_ok=True)
except (OSError, ValueError) as exc:
```

`_resolve_speech_log_path`'s own `mkdir` (`logger.py:1697`) is unaffected — it operates on the
module constant, not on user input.

### 2. `~` is never expanded, and the new `mkdir` now materialises it as a directory — LOW

All three flags are `type=Path` (`logger.py:1948`, `:1974`, `:2017`), and `pathlib.Path` does not
expand `~`. There is no `expanduser` anywhere in `body-layer/src`, and no env-var or config-file
source for these paths — `os.environ`/`getenv` appear nowhere in the subproject — so argv is the
sole input, which is the right posture.

But the behaviour on a quoted or config-file-sourced `~` changed. Probed:

```
tilde          : ok, parent=~ exists=True
  created here : ['~']
```

**Failure scenario.** A stranger (this project is intended to go public open-source) copies
`--speech-log ~/dcs-speech.jsonl` from an older doc into a wrapper script that quotes its
arguments, or into a Windows shell that does not expand `~`. Before this branch that was a
per-write failure. Now it silently creates a directory literally named `~` in the current working
directory and writes into it — a directory most users will never find and some tools will mangle
when they do.

The branch has in fact just removed the only two `~` call sites in the repo
(`run-scripts/run-crew-text.sh`, `run-crew-text-debug-view.sh`, now `logs/dcs-*.jsonl`), so this
is latent rather than live — which is why it is a fix-before-public-release item rather than a
fix-now one.

**Fix** — one line at the argparse boundary, e.g. `type=lambda s: Path(s).expanduser()` on the
three flags, or `.expanduser()` inside `resolve` alongside finding 1's change.

### 3. The blast radius of a path typo, stated honestly — INFORMATIONAL, accept

`stamped.parent.mkdir(parents=True, exist_ok=True)` is unbounded: whatever argv says, including
an absolute path or `../../..`. Probed — `--detection-trace ../escaped/trace.jsonl` creates
`escaped/` outside the working directory; `a/b/c/d/e/f/trace.jsonl` creates six nested levels.

**This is not a vulnerability and should not be read as one.** Traversal is a meaningful concept
when a path is *built from* untrusted data; here the path *is* the operator's own expressed
intent, typed on their own command line, running as themselves. There is no attacker in this
threat model who can reach argv without already having a shell.

What a typo now costs, precisely, so the exposure is on the record:

- **Up to N empty directories** created at any location the running user can write.
- **Never a file overwrite.** `mkdir` with `exist_ok=True` suppresses `FileExistsError` only when
  the target is already a directory. A parent that is a *file* raises and is caught — probed:
  `parent is file : DEGRADED (FileExistsError: [Errno 17] File exists: 'afile')`, degrading that
  one log with a stderr line, exactly as designed.
- **Never a delete, never a permission change, never a privilege boundary crossed.**
- A **symlinked parent is followed** (probed: `link/` → writes land in `real/`). That is
  pre-existing `open(path, "a")` behaviour, not new, and the symlink must already exist inside the
  user's own tree.

No fix recommended. A guard here would reject the legitimate
`--detection-trace /big/disk/trace.jsonl` the module docstring explicitly supports
(`run_log_paths.py:57-58`).

### 4. A disabled log is indistinguishable from a short one to a later reader — LOW

Mechanism verified correct: `_fail` reports once on stderr and sets `_disabled`; subsequent
`write_poll`/`write_speech`/`flush` early-return. `DetectionTraceWriter.write_poll` clears
`collector.records` even when disabled (`detection_trace_writer.py:85-87`), so no unbounded
buffer growth. I traced the `None`-path case too: when `_per_run_log_paths` degrades
`detection_trace` to `None`, `trace_writer` is `None` and the `else: trace_collector.records.clear()`
branch (`logger.py:1231`) does the clearing — the collector is still built because
`eyesight_view` or `belief_truth_log_path` may be set, and it is still drained. **Nothing
downstream assumes a writer exists**; every call site is `is not None`-guarded
(`logger.py:1222`, `:1234`, `:1249`, `:1471`, `:1532`, `:1625`).

The gap is on the reading side. A disabled writer leaves a JSONL file that simply **stops**, with
no row saying so. The only record is a stderr line in terminal scrollback.

**Failure scenario.** Disk fills 20 minutes into a sortie. The detection trace stops at
`t_sim=1200`. A later triage run over that file — this project's primary diagnostic method; the
2026-10-05 performance review that produced this very milestone was built on exactly this
archaeology — reads "no candidates admitted after t=1200" and reasons about a perception defect
that does not exist. The discriminator is a stderr line that may well be gone.

`body-layer/RUN.md`'s new section does document the policy for a human who reads `RUN.md`, which
is real mitigation and is why this is LOW rather than MEDIUM. The automated reader
(`.claude/skills/sortie-log-triage`) has already been taught the *stamping* half — its description
on `main` now says to resolve the filenames and glob for the newest — but it is told nothing about
a writer that abandoned its file, which is the half that produces a wrong conclusion rather than a
missing one.

**Fix** — cheapest version, ~4 lines, zero risk: in each `close()`, inside the existing
`contextlib.suppress(OSError)`, attempt one final `{"event": "<log>_disabled", "reason": ...}`
row when `_disabled` is set. On `ENOSPC` it fails silently (no worse than today); on an
`EACCES`/path-went-bad failure it succeeds and the reader sees the marker in band. Optionally a
sentence in the triage skill: a trace that ends abruptly may be an abandoned writer.

### 5. `contextlib.suppress(OSError)` around `close()` — INFORMATIONAL, correct as written

Confirmed by reading the paths rather than trusting the docstring: `close()` calls `self.flush()`
**first**, and `flush()` either reports via `_fail` (healthy-but-failing writer) or early-returns
because `_fail` already reported (disabled writer). So in both writers, **every flush failure is
announced on stderr before the suppression is reached.** The guard cannot hide a data loss the
pilot was not already told about. `flush()`'s own reporting sits outside it, as the brief states.

The one residual case the suppression does swallow: `flush()` succeeds and the subsequent
`fd.close()` fails. On a local disk this is effectively unreachable; on NFS/SMB with close-time
writeback it is real, and would lose the final buffered rows silently (that is a `close()`-time error *after* a
successful flush — the disabled-writer case is already announced by `_fail`). It is log bytes in a debug
artifact on a shutdown path, so I am not asking for a change. If it were ever wanted, the minimal
form is `except OSError as exc:` with one stderr line instead of `suppress`.

**On discoverability, given `X-B33`.** `/invariant-check`'s swallowed-exception row cannot see
`contextlib.suppress` at all, so this suppression is invisible to the mechanical gate. For these
two sites specifically that is covered — both carry a `close()` docstring naming the reasoning,
and both are pinned by a named test pair (`test_close_does_not_raise_when_the_disk_is_full` and
`test_close_does_not_raise_on_a_healthy_writer`), so a reader grepping test names finds them.
That is sufficient here and is **not** a general substitute for fixing `X-B33`: the next
`contextlib.suppress` to land will not necessarily arrive with a docstring and two tests.

---

## Stated plainly: what is *not* a problem

Listed because an honest finding list needs its negatives, and because each of these was a real
question that had to be traced rather than assumed.

- **Stage 3b's 50 m cache-key quantisation cannot cause a provenance error.** This was the one
  with teeth, given the project's no-omniscience invariant. Two independent reasons it is safe:
  (a) the cache is keyed on `contact.id` (`enrichment.py:697`) and `_new_contact_id`
  (`contacts.py:1440-1442`) is a **monotonic counter, never reused within a process**, so one
  contact's enrichment can never be served for another contact — the only way quantisation could
  attribute a fact to something it was not computed for; (b) the error direction is *away* from
  knowledge. The cached `world_position` is up to ~70.7 m horizontally / ~86.6 m in 3D stale
  relative to the believed position, which makes Petrovich's nearest-feature reasoning slightly
  **coarser**, never better-informed than his perception justifies. It cannot manufacture
  knowledge of an unobserved thing. Omniscience is the invariant; staleness is the opposite
  failure and is already accepted here for the confidence numbers. The constant's own comment
  names the two consumers that can visibly shift (`_format_range_km` by one 0.1 km bucket,
  `terrain_divide_qualifier` flipping within ~70 m of a ridge) — both far inside a believed
  position's hundreds-of-metres uncertainty, and both already reviewed as a correctness trade.
- **`@cache` on `profile_for` is not an unbounded-growth primitive here.** I traced the key space
  rather than taking the reviewer's word. All eleven call sites pass either a DCS `object_type`
  from a perception source or a `classification_raw`; every assignment of `classification_raw`
  (`contacts.py:517`/`:605`, `percept.py:105`, `clustering.py:377`, `hybrid_source.py:263`,
  `naked_eye_source.py:763`/`:966`) originates in a perception source, and
  `belief/threat.py:165` uses a hand-written table. **No transcript, no voice-command text and no
  brain/Ollama output reaches it** — that was the vector worth ruling out, since a microphone-fed
  key space on an unbounded `@cache` would be a different judgement. The tables are module-level
  and never mutated and `ObjectTypeProfile` is `frozen=True`, so the cache cannot be poisoned
  through a returned value. The one technically-open edge: the key space is ultimately whatever
  the aircraft-layer LAN API returns, so an actor on that seam could grow the cache — but that
  actor already controls Petrovich's entire perception, which is a far worse outcome than memory
  growth, so the cache is not the thing to defend. `lru_cache(maxsize=4096)` would cost nothing if
  belt-and-braces is ever wanted; it is not needed.
- **Stage 1's `_wait_for_next_tick` has no security surface.** The no-voluntary-yield-under-
  sustained-overrun consequence is a local resource-pressure trade, deliberately taken, documented
  in the docstring, with `--poll-interval-s` named as the knob. A negative `--poll-interval-s`
  busy-spins, but it did so before this branch too (`stop_event.wait(-1)` returns immediately), so
  it is pre-existing and is a self-inflicted typo, not a finding.
- **Stage 2's hoist has no security surface** — pure geometry over already-trusted inputs, pinned
  by `test_group_salience_equivalence.py`'s 15 cases with the reference arithmetic now owned by the
  test file (round 2's fix) and a verified mutation counterfactual.
- **Run-stamped filenames cannot escape their directory.** The inserted component is
  `strftime("%Y%m%d-%H%M%S")` — digits and one hyphen, no separator, no user data — spliced via
  `with_name`, which only ever rewrites the final component. The second-resolution collision the
  module docstring admits degrades to the **old append** behaviour, which loses nothing and
  overwrites nothing; it is a legibility cost, not a destructive one.
- **Omitting `None` fields from trace rows** narrows what is written; it adds no parsing surface,
  and all three readers use `.get`.

## Pre-existing, noted and not blocking

`run-scripts/run-crew-text.sh:13` and `run-crew-text-debug-view.sh:18` end in unquoted `$@`,
which word-splits and globs the operator's own passthrough arguments. Pre-existing, not introduced
here, and the only input is the user's own terminal — but these two files were touched by this
branch, so `"$@"` is a free correction whenever one of them is next edited.

## Verdict

**APPROVED.**

Nothing here is exploitable and nothing blocks DoD. Findings 1, 2 and 4 are low-severity
robustness and analysis-integrity items on a debug-logging path, each with a concrete one-to-four
line fix. Finding 3 is an accepted consequence of the feature working as designed; finding 5 is
correct as written.

### If a change is wanted, it re-enters the loop

Per `AGENTS.md`, a Security change request goes Implementer → Reviewer → DoD, so these are posed
as a choice rather than imposed:

**Risk:** three low-severity gaps on the new filesystem path — the degrade policy escapable by
`ValueError` (1), an unexpanded `~` becoming a real directory (2), and a disabled log that reads
as an empty one (4).
**Probability:** low for 1 and 2 (operator typo; 2 is latent now that the `~` call sites are
gone), low for 4 (needs a full disk, which is precisely the scenario Stage 5 exists for).
**Impact:** low — a startup traceback instead of a graceful degrade, a stray `~/` directory, or
one wrong conclusion in a later log analysis. No data loss beyond debug artifacts, no
confidentiality or integrity impact on anything the pilot hears.
**Recommended action:** fold 1 and 2 into one small commit now (they touch the same five lines and
2 is the open-source-facing one); take 4 as a follow-up backlog item.

Options:
  (A) Ignore — accept all three, recorded here
  (B) Add to the backlog as a body-layer item — fix in a future session
  (C) Fix 1 and 2 now via Implementer → Reviewer, backlog 4
  (D) Stop — do not proceed to DoD until resolved

My recommendation is **(C)**, and **(B)** is entirely defensible: none of this blocks a sortie, and
the branch's actual purpose — the measured tick-cost reduction — is unaffected either way.
