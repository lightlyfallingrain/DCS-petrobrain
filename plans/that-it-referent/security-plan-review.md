## Security Plan Review: that-it-referent (BL-B102)

### Dependencies Checked

No new dependency proposed. The plan's own "Facts" section and `body-layer/CLAUDE.md`'s
"Tech stack" both confirm body-layer stays stdlib-only plus the existing transitive `pyproj`
(via the world-model seam, unchanged by this plan). `grep -niE 'dependenc|pip install|...'`
over `plan.md`/`explore-notes.md` returns nothing — the plan does not even need to disclaim a
dependency, because it introduces none. `body-layer/pyproject.toml` and
`audio-adapter`'s manifest are both unaffected.

### Scope note

This feature is deterministic application logic over already-trusted, already-flowing data:
voice transcripts through the existing `command_matcher`/`CrewConsole` pipeline, and belief
state already held in `ContactStore`. It does not call an LLM (no brain-layer escalation path
is touched — the plan is explicit that referent resolution happens on "existing contact-taking
command tokens only," before any fallthrough to brain escalation), so there is no new prompt-
injection surface: nothing here reads text into a place an LLM later treats as instructions.

### Design Findings

- **New mutable state (`ReferentMemory`) is time-windowed, not count-bounded** —
  `plans/that-it-referent/plan.md` "Affected Modules," `REFERENT_WINDOW_S` (15–180 s, tunable).
  Within the window, the number of recorded mentions is bounded only by how often `_print`
  is called with a non-empty `mentions` list. This is not an externally-triggerable flood: the
  only input path is the pilot's own voice and Petrovich's own speech cadence (rate-limited by
  `SPEECH_RATE_WPS`/`INTER_UTTERANCE_GAP_S` and the single-user LAN threat model this project
  scopes to). **Advisory only, not a blocker** — note it so a future count cap is considered if
  the mechanism is ever reused somewhere with a less-bounded input rate (e.g. the BL-10/SRS
  conversational-memory reuse the plan's "Second-order effect" section flags), but nothing in
  this plan's actual input path makes it exploitable today.
- **No new file paths, no new deserialization, no new network listener/endpoint, no new
  shell-out, no secrets.** The plan's own "Affected Modules / Files" list is confined to
  `belief/referent.py` (new, pure in-memory), `crew_console.py` (threading an existing kwarg
  pattern), and `vocabulary.py`/`command_matcher.py` (additive slot parsing, same shape as five
  existing slots). None of these categories are introduced or expanded.
- **The tunable constant (`REFERENT_WINDOW_S`) follows the existing `tuning.py` pattern**
  (`lo=15.0, hi=180.0, status="judgement"`), consistent with "Behaviour-affecting constants are
  tunable" in root `CLAUDE.md` — no bespoke parsing or input path introduced for it.

### Passed to Reviewer (not a security verdict)

- The resolver's "pick nearest, never ask" tie-break (Design, step 5) and the "last line wins"
  rule together mean a garbled or ambiguous transcript recognition could cause `"engage
  that"`/`"target it"` to resolve to a contact other than the one the pilot meant — a weapon-
  deployment consequence. This is a correctness/player-experience question (what the pilot
  experiences, not a security boundary), squarely Reviewer's territory per this role's scope
  section, not mine to verdict.

### Verdict

APPROVED

No required changes. No findings needed filing to a `ROADMAP/` backlog — the one advisory
item above is a forward-looking note attached to this plan's own review, not a standalone risk
that needs independent tracking or a risk-matrix decision from the user: it does not block this
feature and names no action the user needs to choose between.
