# WynBiz-Analyzer

An AI agent swarm that plays a small grid game, finds real bugs, writes
reproducible bug reports, triages them with Cline, and then proves a fix
worked — without a human writing a single test case.

## What's in here

| Path | What it is |
|---|---|
| [`game-qa-swarm/`](game-qa-swarm/) | The **AI Game QA Swarm** — a headless, deterministic grid game with four planted bugs, three agent types, four rule-based detectors, a Streamlit dashboard (playable arcade, chatbot, file analyzer), and a fix-and-verify flow. See its [README](game-qa-swarm/README.md) for the full story. |

## Quick start

```bash
cd game-qa-swarm
pip install -r requirements.txt

python scripts/seed_bugs.py              # prove the 4 planted bugs reproduce
python -m gameqa.cli run --episodes 20   # let the swarm loose
streamlit run dashboard/app.py           # dashboard + playable arcade
```

# AI Game QA Swarm

An AI agent swarm that plays a small grid game, finds real bugs, writes
reproducible bug reports, triages them with Cline, and then proves a fix
worked — without a human writing a single test case.

Built as an 8-hour hackathon MVP. The core runtime has **zero hard
dependencies**: the game, agents, detectors, report store, swarm and CLI all
run on the Python standard library. Pillow, Streamlit and the Anthropic SDK
are optional and each one degrades gracefully when missing.

---

## The 60-second version

```bash
pip install -r requirements.txt

# 1. Prove the demo works before you trust it (finds all 4 planted bugs
#    from fixed, verified seeds)
python scripts/seed_bugs.py

# 2. Let the swarm loose: 20 episodes per bot type (60 total), 3 bots, 4 detectors
python -m gameqa.cli run --episodes 20 --triage

# 3. Look at what it found
python -m gameqa.cli list
python -m gameqa.cli show crash

# 4. Watch a bug happen, frame by frame
python -m gameqa.cli replay --seed 42 --actions "RIGHT,RIGHT,PICKUP"

# 5. Fix one bug (with Cline, or by hand), then prove it's fixed
python scripts/verify_fix.py --kind crash

# 6. Play the game interactively in your terminal!
python -m gameqa.cli play --map level_01

# 7. Production Dashboard & Playable Arcade (Canvas 60fps, Web Audio, Bot Spectator)
streamlit run dashboard/app.py
```

---

## What it actually does

```
                 ┌──────────────┐
   seed ────────▶│  GridGame    │  deterministic: (seed, actions) -> run
                 │  4 planted   │
                 │  bugs        │
                 └──────┬───────┘
                        │ obs / reward / done / info
        ┌───────────────┼───────────────────┐
        ▼               ▼                   ▼
 random_walker     goal_seeker        chaos_tester
        └───────────────┼───────────────────┘
                        │ every step is recorded
                        ▼
        ┌───────────────────────────────────┐
        │  4 rule-based detectors           │
        │  crash / softlock / map_hole /    │
        │  exploit                          │
        └───────────────┬───────────────────┘
                        │ Finding(kind, signature, detail)
                        ▼
        ┌───────────────────────────────────┐
        │  dedupe by signature -> BugReport │  repro = (seed, actions)
        │  + replay GIF  + Cline triage    │
        └───────────────┬───────────────────┘
                        ▼
              dashboard / cli / verify
```

### The four planted bugs

Each is gated behind a flag in `gameqa/game/bugs.py` and marked with a
`# BUG:` comment at its site in `gameqa/game/grid_game.py`, so a fix is a
small, legible diff.

| Bug | Kind | What's wrong | How it's caught |
|---|---|---|---|
| Key lost in pit | `softlock` | `DROP` on a pit destroys the key instead of refusing, so the door can never open | BFS reachability proof over the *intended* map |
| Walkable wall | `map_hole` | Off-by-one registers one wall tile as floor; the player walks through a pillar | Position checked against `MAP_RAW`, not the game's own walkable set |
| Coin duplication | `exploit` | The "already paid" guard is wiped on every move and coins are never marked taken | Hard arithmetic: `coins_collected > total_coins`, `score > max_legal_score` |
| Stale key flag | `crash` | `USE` trusts a flag `DROP` never clears, then indexes an empty inventory | Any exception escaping `step()` is a bug |

### Why the detectors are trustworthy

A detector that reads the game's own model of itself cannot notice the game
lying about that model — which is exactly what the map-hole bug does. So each
detector uses an **independent truth source**:

* **map_hole** compares against `MAP_RAW` (declared level data), never against
  `env.walkable`.
* **softlock** is a real reachability proof (BFS over the intended map with the
  door's true state), not a "the bot stood still for N steps" counter. A bot
  wandering in circles is not a bug; a world state from which the goal is
  provably unreachable is.
* **exploit** is pure arithmetic against constants derived from the level data.
* **crash** treats any escaping exception as a bug and signs it by
  `ExceptionType|file:line:function`.

### Why the repros are trustworthy

The game is deterministic in `(seed, actions)`. Every action a bot sends is
recorded — including the chaos tester's junk inputs — through
`label_action` / `parse_action_label`, which are exact inverses. A replay GIF
is **re-simulated** from `(seed, actions)` rather than recorded during the run,
so it is always consistent with the repro file and can be regenerated after a
fix for a before/after comparison.

Findings are merged by a **seed-independent signature**, so 40 bots walking
into the same wall tile produce one bug report with `occurrences: 40`, not 40
reports. Merging keeps the *shortest* action list, because a shorter repro is
easier to show and faster to replay.

---

## Repo layout

```
game-qa-swarm/
├── gameqa/
│   ├── game/
│   │   ├── actions.py       Action enum + INVALID_INPUTS + normalise()
│   │   ├── bugs.py          the 4 planted-bug flags (the fix switches)
│   │   ├── maps.py          MAP_RAW: the source of truth for detectors
│   │   ├── grid_game.py     deterministic env; every bug marked `# BUG:`
│   │   └── pathing.py       BFS: routes for repros, reachability for softlock
│   ├── agents/
│   │   ├── base.py          Bot ABC + make_bot()
│   │   ├── random_walker.py uniform random legal actions
│   │   ├── goal_seeker.py   greedy BFS toward key -> door -> goal
│   │   └── chaos_tester.py  spams invalid inputs and illegal combos
│   ├── detectors/
│   │   ├── base.py          Finding / DetectContext / Detector
│   │   ├── crash.py         exception -> ExceptionType|file:line:func
│   │   ├── softlock.py      reachability proof
│   │   ├── map_hole.py      position vs MAP_RAW
│   │   └── exploit.py       arithmetic bounds on coins and score
│   ├── reports/
│   │   ├── schema.py        BugReport dataclass + merge + repro_text()
│   │   ├── signature.py     stable signatures + safe filenames
│   │   ├── store.py         artifacts/: bugs, repros, replays, runs, cache
│   │   └── triage.py        Cline triage, disk cache, heuristic fallback
│   ├── swarm/
│   │   ├── runner.py        run_episode() and run_script()
│   │   └── parallel.py      ProcessPoolExecutor fan-out + serial fallback
│   ├── replay/gif.py        re-simulate (seed, actions) -> ASCII frames -> GIF
│   ├── repros.py            pinned, machine-verified repros for all 4 bugs
│   └── cli.py               run / triage / list / show / replay / plant / verify
├── dashboard/
│   ├── app.py         Streamlit: runs, bugs, repros, GIF, re-verify
│   ├── arcade.py          playable Canvas arcade + bot spectator
│   ├── chat.py            SwarmAI chatbot over the bug store
│   └── file_analyzer.py   upload a .py game for an AI vulnerability report
├── scripts/
│   ├── seed_bugs.py         pre-flight: prove all 4 planted bugs reproduce
│   └── verify_fix.py        post-fix: prove one is gone and 3 still fire
├── tests/
│   ├── test_planted_bugs.py bugs are findable AND disappear when disabled
│   └── test_detectors.py    per-detector unit tests + merge/dedupe
├── requirements.txt         all optional; stdlib-only core
└── .env.example
```

Artifacts are written to `artifacts/` (gitignored):

```
artifacts/
├── bugs/<signature>.json     one merged BugReport per signature
├── repros/<signature>.txt    human-readable repro with the failing step marked
├── replays/<signature>.gif   re-simulated replay
├── runs/<run_id>.json        swarm summary (episodes, steps, wins, timing)
└── triage_cache/<sig>.json   Cline responses, so a network blip is invisible
```

---

## CLI reference

| Command | What it does |
|---|---|
| `run` | Run the swarm, merge findings into reports, render GIFs. `--triage` also runs Cline. `--disable crash exploit` simulates a fix. |
| `plant` | Search seeds for a verified repro of each planted bug. `--record` writes them into the store. Exits non-zero if any bug fails to reproduce. |
| `triage` | Triage stored reports. `--force` ignores the cache, `--offline` forces the heuristic. |
| `list` | Severity, occurrence count, fixed state and signature for every report. |
| `show <sig>` | Print one report's repro file (substring match works). |
| `replay` | Re-simulate `--seed` + `--actions`; print ASCII frames, or `--gif out.gif`. |
| `verify --kind K` | Prove `K` is gone **and** the other three are still detected. |

---

## The fix-and-verify flow

This is the part that makes the demo more than a bug-finding toy.

```bash
# BEFORE: 4 bugs, 4 kinds of finding
python -m gameqa.cli run --episodes 20

# FIX: ask Cline to fix one bug from its repro alone.
#   "Fix the bug described in artifacts/repros/<crash-signature>.txt.
#    The repro is deterministic: seed + action list. Do not touch the
#    detectors or the tests. Mark your change with a comment."
# Cline sees the repro, the traceback, the detector detail and the map data --
# never the `# BUG:` comments -- so the fix has to be earned.

# AFTER: prove it
python scripts/verify_fix.py --kind crash
```

`verify` passes only when **all three** hold:

1. The target bug's pinned repro produces no finding across a 200-seed search.
2. Every *other* planted bug's pinned repro **still** fires.
3. A fresh swarm run finds 0 occurrences of the target kind while still
   finding the other three kinds.

Condition 2 is the one that matters. Without it, "the crash no longer appears"
is worthless — a broken detector also produces zero findings. This is what
turns the success metric from *"the AI said it fixed it"* into *"the harness
proves the bug is gone and detection did not regress."*

`python scripts/verify_fix.py --simulate` runs the same verification for all
four bugs by flipping their flags off in turn, so you can prove the verify
harness itself works before relying on it live.

---

## Demo script (5 minutes)

| # | Do | Say |
|---|---|---|
| 1 | `python scripts/seed_bugs.py` | "Before I demo anything, I prove the four bugs are reproducible from fixed seeds. Green means the demo cannot flake." |
| 2 | `python -m gameqa.cli run --episodes 20 --triage` | "20 episodes per bot type (60 total) in a few seconds. Note the finding counts collapse into a handful of unique signatures — that's dedupe, not luck." |
| 3 | `streamlit run dashboard/app.py` | "Severity, occurrence count, the exact repro, Cline's triage, and a replay GIF. No human wrote a test case." |
| 4 | Pick the crash, show its repro | "`seed` plus this action list replays the failure exactly. The GIF is re-simulated from it, not screen-recorded." |
| 5 | Ask Cline to fix it from the repro alone | "It sees the repro, the traceback and the map data — never the `# BUG:` comments. The fix has to be earned." |
| 6 | `python scripts/verify_fix.py --kind crash` | "Passing means the crash is gone AND the other three bugs are still detected. Otherwise 'fixed' could just mean I broke a detector." |

Pre-warm the triage cache before you go on stage so a network blip is
invisible:

```bash
python -m gameqa.cli run --episodes 20 --triage
```

---

## Testing

```bash
python -m pytest tests/ -q          # if pytest is installed
python tests/test_planted_bugs.py   # no dependencies needed
python tests/test_detectors.py
```

`tests/test_planted_bugs.py` asserts both directions for every planted bug:

* the scripted repro **does** produce the finding, and
* with the bug disabled the same repro produces **no** finding.

Plus map integrity (`MAP_HOLE_AT` really is a wall, the door really is the only
route to the goal), the level really is completable with all bugs off, repros
are byte-identical when replayed, and the swarm finds all four kinds.

The test files run standalone with a tiny built-in runner, so a missing pytest
never blocks a pre-flight check.

---

## Design notes and honest limitations

**Determinism is load-bearing.** Everything downstream — repro files, replay
GIFs, fix verification — depends on `(seed, actions)` reproducing a run
exactly. Two consequences worth knowing:

* Bot RNG seeds are derived from the bot *name* with a stable sum, not
  Python's built-in `hash()`, which is salted per process and would silently
  make worker processes disagree with the parent.
* Replay GIFs are re-simulated, not recorded. Slower, but they can never drift
  from the repro they claim to illustrate.

**Scripted repros are machine-verified, not assumed.** Enemies patrol the
lower corridor and block movement like a wall, so a fixed action list can
desync on some seeds. `repros.find_seed()` therefore searches seeds and keeps
only one that actually reproduces the bug. Anything that claims a repro works
without running it is lying.

**Enemies block but do not kill.** They deal no damage and end nothing, which
keeps them out of the detectors' way. A damaging enemy would need its own
detector and its own notion of "legal", which was out of scope for 8 hours.

**Three levels, one campaign.** `MAP_RAW` is the 12x10 `level_01` ("The
Forgotten Crypt") that the swarm and detectors exercise. `maps.CAMPAIGN_LEVELS`
adds `level_02` ("Inferno Bastion") and `level_03` ("Cyber Void Citadel") for
the playable dashboard arcade, each with its own theme, difficulty, par step
count and enemy patrol paths. The detectors are map-agnostic (they read a
level's `raw` grid and constants), so a new level is a data change rather than
a detector change — but only `level_01` carries the planted bugs.

**Detectors are deliberately dumb.** Four hand-written rules with independent
truth sources. No ML, no tuning, no learned invariants. That is the point: on
stage you can read the rule that fired and agree with it in ten seconds. The
swarm supplies coverage; the detectors supply judgement.

**Triage is advisory.** Cline's title, severity and suspected cause are
recorded on the report and cached on disk. They never gate anything. The
`verify` flow is entirely deterministic and does not call the API, so the
success metric cannot depend on a model's opinion.

**Bots are simple on purpose.** A random walker, a greedy goal seeker and a
chaos tester find all four planted bugs within a few dozen episodes. A smarter
planner would find them faster but would make the demo less honest about how
much coverage cheap agents actually buy you.



