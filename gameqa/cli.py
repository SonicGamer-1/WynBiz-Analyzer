"""Command line entry point: `python -m gameqa.cli <subcommand>`.

Subcommands
    run       run the swarm, record bug reports, render replay GIFs
    triage    run Cline AI triage over reports (or pre-warm the cache)
    list      list recorded bug reports
    show      print one report's repro file
    replay    re-simulate a (seed, actions) pair, print frames or write a GIF
    plant     write pinned, deterministic repros for the four planted bugs
    verify    re-run the swarm and prove a signature is gone
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .game.actions import Action
from .game.bugs import BUG_FLAGS, PLANTED_BUGS
from .replay.gif import has_pillow, make_gif, simulate
from .reports.store import BugStore
from .reports.triage import Triager
from .swarm.parallel import run_swarm


def _print(text=""):
    sys.stdout.write(str(text) + "\n")


def _parse_actions(text):
    return [part.strip() for part in text.split(",") if part.strip()]


def _record_findings(store, swarm, make_gifs=True, gif_tail=60):
    """Merge every finding into the store. Returns the touched reports."""
    reports = {}
    for finding in swarm["findings"]:
        report = store.record(
            finding=__finding_obj(finding),
            seed=finding["seed"],
            bot=finding["bot"],
            actions=finding["actions"],
            episode_id="%s/seed%d/%s" % (swarm["run_id"], finding["seed"],
                                         finding["bot"]),
            map_id=finding.get("map_id", "level_01"),
        )
        reports[report.signature] = report
    if make_gifs and has_pillow():
        for signature, report in reports.items():
            path = store.gif_path(signature)
            if make_gif(report.seed, report.actions, path, tail=gif_tail):
                report.gif_path = path
                store.save(report)
    return list(reports.values())


def __finding_obj(payload):
    from .detectors.base import Finding

    return Finding(
        kind=payload["kind"],
        signature=payload["signature"],
        summary=payload["summary"],
        severity_hint=payload.get("severity_hint", "medium"),
        step_index=payload.get("step_index", -1),
        detail=payload.get("detail", {}),
    )


# ------------------------------------------------------------------ commands

def cmd_run(args):
    store = BugStore(args.artifacts)
    flags = dict(BUG_FLAGS)
    for name in args.disable or []:
        if name not in flags:
            _print("warning: unknown bug %r" % name)
        flags[name] = False

    if args.clean:
        store.clear_reports()

    def progress(done, total):
        if not args.quiet and (done % 25 == 0 or done == total):
            _print("  %d/%d episodes" % (done, total))

    _print("running swarm: %d episodes/bot x %d bots, %d steps max, %d workers"
           % (args.episodes, 3, args.max_steps, args.workers or os.cpu_count() or 2))
    swarm = run_swarm(
        episodes_per_bot=args.episodes,
        max_steps=args.max_steps,
        workers=args.workers,
        seed_base=args.seed_base,
        bug_flags=flags,
        progress=progress,
    )
    store.save_run(swarm["run_id"],
                   {k: v for k, v in swarm.items() if k != "findings"})

    reports = _record_findings(store, swarm, make_gifs=not args.no_gifs)

    if args.triage:
        triager = Triager(store, offline=args.offline)
        for report in reports:
            triager.apply(report, force=args.force_triage)

    _print("")
    _print("run %s  %.2fs  episodes=%d steps=%d wins=%d crashes=%d"
           % (swarm["run_id"], swarm["duration_s"], swarm["episodes"],
              swarm["steps"], swarm["wins"], swarm["crashes"]))
    _print("findings=%d  unique signatures=%d"
           % (len(swarm["findings"]), swarm["unique_signatures"]))
    kinds = {}
    for signature, count in swarm["signature_counts"].items():
        kinds[signature.split("|", 1)[0]] = (
            kinds.get(signature.split("|", 1)[0], 0) + count)
    for kind in sorted(kinds):
        _print("  %-10s %d" % (kind, kinds[kind]))
    _print("")
    for report in sorted(reports, key=lambda r: -r.occurrences):
        _print("  [%s] %s  x%d  (%s)"
               % (report.severity, report.title or report.signature,
                  report.occurrences, report.signature))
    if not has_pillow() and not args.no_gifs:
        _print("")
        _print("note: Pillow is not installed, so no GIFs were rendered.")
    return 0


def cmd_triage(args):
    store = BugStore(args.artifacts)
    triager = Triager(store, offline=args.offline)
    reports = store.all_reports()
    if args.signature:
        reports = [r for r in reports if r.signature == args.signature]
    if not reports:
        _print("no reports to triage; run `python -m gameqa.cli run` first")
        return 1
    for report in reports:
        triager.apply(report, force=args.force)
        payload = report.triage
        _print("[%s] %s" % (payload.get("source", "?"), report.signature))
        _print("    title:   %s" % report.title)
        _print("    severity:%s" % report.severity)
        _print("    cause:   %s" % payload.get("suspected_cause", ""))
        _print("    area:    %s" % payload.get("suggested_fix_area", ""))
    return 0


def cmd_list(args):
    store = BugStore(args.artifacts)
    reports = store.all_reports()
    if not reports:
        _print("no bug reports recorded yet")
        return 0
    _print("%-9s %-6s %-5s %s" % ("SEVERITY", "OCCURS", "FIXED", "SIGNATURE"))
    for report in reports:
        _print("%-9s %-6d %-5s %s"
               % (report.severity, report.occurrences,
                  "yes" if report.verified_fixed else "no",
                  report.signature))
        _print("           %s" % (report.title or report.summary))
    return 0


def cmd_show(args):
    store = BugStore(args.artifacts)
    report = store.get(args.signature)
    if report is None:
        for candidate in store.all_reports():
            if args.signature in candidate.signature:
                report = candidate
                break
    if report is None:
        _print("no report matching %r" % args.signature)
        return 1
    _print(report.repro_text())
    if report.triage:
        _print("")
        _print("triage (%s):" % report.triage.get("source", "?"))
        _print(json.dumps(report.triage, indent=2, sort_keys=True))
    return 0


def cmd_replay(args):
    actions = _parse_actions(args.actions)
    frames = simulate(args.seed, actions, max_steps=args.max_steps)
    for index, frame in enumerate(frames):
        _print("--- step %d ---" % index)
        _print(frame)
    if args.gif:
        if not has_pillow():
            _print("Pillow is not installed; cannot write a GIF")
            return 1
        written = make_gif(args.seed, actions, args.gif, fps=args.fps)
        _print("wrote %s" % (written or "<failed>"))
    return 0


def cmd_play(args):
    """Play the game interactively in your terminal with colored ANSI graphics."""
    from .game.grid_game import GridGame
    from .game import maps

    level_meta = maps.get_level(args.map)
    env = GridGame(map_id=args.map)
    env.reset(seed=args.seed)

    # ANSI styles
    BOLD = "\033[1m"
    RESET = "\033[0m"
    GOLD = "\033[93m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"

    TILE_RENDER = {
        "#": GRAY + "🧱" + RESET,
        ".": "  ",
        "~": "\033[44m  " + RESET,
        "C": GOLD + "🪙" + RESET,
        "K": MAGENTA + "🗝️" + RESET,
        "D": "\033[33m🚪" + RESET,
        "G": GREEN + "🌀" + RESET,
        "E": RED + "👾" + RESET,
        "@": CYAN + "🤺" + RESET,
        "W": GOLD + "👑" + RESET,
    }

    message = "Welcome to " + level_meta.get("name", "The Crypt") + "! Use W/A/S/D to move."

    def render_board():
        _print("\n" + "=" * 40)
        _print(BOLD + GOLD + "=== " + level_meta.get("name", "Dungeon").upper() + " ===" + RESET)
        hearts = "❤️ " * max(0, env.health)
        key_str = GREEN + "HELD" + RESET if "key" in env.inventory else (RED + "DESTROYED" + RESET if env.key_destroyed else "WORLD")
        door_str = GREEN + "OPEN" + RESET if env.door_open else RED + "LOCKED" + RESET
        _print("Health: %s  Score: %s%d%s  Coins: %s%d/%d%s  Key: %s  Door: %s"
               % (hearts, GOLD, env.score, RESET, GOLD, env.coins_collected, env.total_coins, RESET, key_str, door_str))
        _print("Step: %d  Par: %d  Combo: x%d" % (env.step_count, level_meta.get("par_steps", 28), env.combo))
        _print("─" * 36)

        ascii_frame = env.render_state()
        for line in ascii_frame.split("\n"):
            rendered_line = "".join(TILE_RENDER.get(ch, ch * 2) for ch in line)
            _print("  " + rendered_line)
        _print("─" * 36)
        _print("Event: " + message)
        _print(GRAY + "Controls: [W/A/S/D] Move | [E/SPACE] Pickup | [F] Use Key | [X] Drop | [.] Wait | [Q] Quit" + RESET)

    def get_key():
        try:
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                arrow_map = {b"H": "W", b"P": "S", b"K": "A", b"M": "D"}
                return arrow_map.get(ch2, "")
            return ch.decode("utf-8", errors="ignore").upper()
        except Exception:
            try:
                line = input("Action (W/A/S/D/E/F/X/./Q): ").strip().upper()
                return line[0] if line else "."
            except (EOFError, KeyboardInterrupt):
                return "Q"

    while not env.done:
        render_board()
        key = get_key()
        if key == "Q":
            _print("Quit game.")
            return 0
        act = None
        if key in ("W", "UP"):
            act = "UP"
        elif key in ("S", "DOWN"):
            act = "DOWN"
        elif key in ("A", "LEFT"):
            act = "LEFT"
        elif key in ("D", "RIGHT"):
            act = "RIGHT"
        elif key in ("E", "P", " "):
            act = "PICKUP"
        elif key in ("F", "U"):
            act = "USE"
        elif key in ("X", "DROP"):
            act = "DROP"
        elif key in (".", "\r", "\n", "WAIT"):
            act = "WAIT"
        elif key == "R":
            env.reset(seed=args.seed)
            message = "Game reset!"
            continue

        if act:
            obs, reward, done, info = env.step(act)
            events = info.get("events", [])
            if "victory" in events:
                message = GOLD + BOLD + "🏆 VICTORY! You escaped in %d steps with %d points!" % (env.step_count, env.score) + RESET
            elif "coin" in events:
                message = GOLD + "🪙 Coin collected! (+10 pts) Combo: x%d" % env.combo + RESET
            elif "key_pickup" in events:
                message = MAGENTA + "🗝️ Golden key acquired!" + RESET
            elif "key_destroyed" in events:
                message = RED + BOLD + "💀 GLITCH! Key destroyed in bottomless pit! (Softlock)" + RESET
            elif "door_open" in events:
                message = GREEN + "🚪 Iron door unlocked!" + RESET
            elif "bump" in events:
                message = GRAY + "Bumped into obstacle." + RESET
            elif act == "UP" and env.pos == (4, 7) and args.map == "level_01":
                message = RED + BOLD + "🕳️ GLITCH! You walked through a solid pillar at (4,7)! (Map Hole)" + RESET
            else:
                message = "Action: " + act

    render_board()
    if env.won:
        _print(GREEN + BOLD + "\nCongratulations! You cleared " + level_meta.get("name", "the dungeon") + "!" + RESET)
    return 0



def cmd_plant(args):
    from .detectors.base import Finding            # noqa: F401
    from .repros import build_pinned
    from .swarm.runner import run_script

    store = BugStore(args.artifacts)
    pinned = build_pinned(search=range(args.seed_base,
                                       args.seed_base + args.search))
    failed = []
    for name in sorted(pinned):
        entry = pinned[name]
        if not entry["verified"]:
            failed.append(name)
            _print("  FAIL  %-9s no seed in range produced the finding" % name)
            continue
        _print("  ok    %-9s seed=%-5d steps=%-4d %s"
               % (name, entry["seed"], len(entry["actions"]),
                  entry["signature"]))
        if not args.record:
            continue
        result = run_script(entry["seed"], entry["actions"])
        for payload in result["findings"]:
            if payload["signature"] != entry["signature"]:
                continue
            report = store.record(
                finding=__finding_obj(payload),
                seed=entry["seed"],
                bot="pinned_repro",
                actions=entry["actions"],
                episode_id="pinned/%s" % name,
            )
            if has_pillow() and not args.no_gifs:
                path = store.gif_path(report.signature)
                if make_gif(report.seed, report.actions, path, tail=40):
                    report.gif_path = path
                    store.save(report)
    if failed:
        _print("")
        _print("planted bugs not reproduced: %s" % ", ".join(failed))
        return 1
    return 0


def cmd_verify(args):
    """Prove a bug is gone AND that the other detectors still fire.

    Without the second half, "the bug is gone" could just mean a detector
    broke. This is what makes the success metric defensible on stage.
    """
    from .repros import BUILDERS, check, find_seed

    kinds = {name: value[1] for name, value in PLANTED_BUGS.items()}
    target_kind = args.kind
    if target_kind not in set(kinds.values()):
        _print("unknown kind %r; expected one of %s"
               % (target_kind, sorted(set(kinds.values()))))
        return 2
    target_name = next(n for n, k in kinds.items() if k == target_kind)

    store = BugStore(args.artifacts)
    flags = dict(BUG_FLAGS)
    expected_others = sorted(
        {kinds[n] for n in kinds if n != target_name and flags.get(n)}
    )
    search = range(args.seed_base, args.seed_base + args.search)
    ok = True

    _print("verifying '%s' is gone and the other detectors still fire" % target_kind)
    _print("")

    # 1. the target's pinned repro must no longer produce its finding.
    # Search many seeds rather than trusting one: a scripted route can be
    # blocked by a patrolling enemy and desync, which would look like a fix
    # that never happened. find_seed uses the *current* source, so it returns
    # None exactly when the bug is genuinely gone.
    actions = BUILDERS[target_name]()
    seed = find_seed(target_name, actions, search)
    still = check(target_name, seed, actions) if seed is not None else None
    if still:
        _print("  FAIL  pinned repro for %s still fails at seed %d: %s"
               % (target_name, seed, still))
        ok = False
    else:
        _print("  ok    pinned repro for %s produces no '%s' finding in %d seeds"
               % (target_name, target_kind, len(search)))

    # 2. every other enabled bug's pinned repro must STILL fail
    for name in sorted(kinds):
        if name == target_name or not flags.get(name):
            continue
        other_actions = BUILDERS[name]()
        seed = find_seed(name, other_actions, search)
        signature = check(name, seed, other_actions) if seed is not None else None
        if signature:
            _print("  ok    %s detector still fires (%s)" % (name, signature))
        else:
            _print("  FAIL  %s detector no longer fires: a detector broke, "
                   "not the game" % name)
            ok = False

    # 3. full swarm rerun
    _print("")
    _print("re-running swarm (%d episodes/bot)..." % args.episodes)
    swarm = run_swarm(episodes_per_bot=args.episodes, max_steps=args.max_steps,
                      workers=args.workers, seed_base=args.swarm_seed_base,
                      bug_flags=flags)
    counts = swarm["signature_counts"]

    def hits(kind):
        return sum(c for sig, c in counts.items()
                   if sig.split("|", 1)[0] == kind)

    target_hits = hits(target_kind)
    if target_hits == 0:
        _print("  ok    swarm: 0 occurrences of '%s' in %d episodes"
               % (target_kind, swarm["episodes"]))
    else:
        _print("  FAIL  swarm: '%s' still found %d time(s)"
               % (target_kind, target_hits))
        ok = False

    for kind in expected_others:
        found = hits(kind)
        if found:
            _print("  ok    swarm: '%s' still found %d time(s)" % (kind, found))
        else:
            _print("  FAIL  swarm: '%s' no longer found: detection regressed"
                   % kind)
            ok = False

    store.save_run(swarm["run_id"],
                   {k: v for k, v in swarm.items() if k != "findings"})

    if ok:
        report = store.get(args.signature) if args.signature else None
        if report is None:
            report = next((r for r in store.all_reports()
                           if r.kind == target_kind), None)
        if report is not None:
            store.set_status(report.signature, "fixed", verified_fixed=True)
            _print("")
            _print("marked %s as fixed and re-verified" % report.signature)

    _print("")
    _print("VERIFY: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# -------------------------------------------------------------------- parser

def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m gameqa.cli",
        description="AI playtesting swarm for a tiny buggy grid game.",
    )
    parser.add_argument("--artifacts", default=None,
                        help="artifacts directory (default: ./artifacts)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("run", help="run the swarm and record bug reports")
    p.add_argument("--episodes", type=int, default=20,
                   help="episodes per bot type (default 20)")
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--seed-base", type=int, default=1000)
    p.add_argument("--disable", nargs="*", default=[],
                   choices=sorted(PLANTED_BUGS), help="simulate a fix")
    p.add_argument("--clean", action="store_true",
                   help="delete existing reports first")
    p.add_argument("--no-gifs", action="store_true")
    p.add_argument("--triage", action="store_true",
                   help="run LLM triage on the new reports")
    p.add_argument("--force-triage", action="store_true")
    p.add_argument("--offline", action="store_true",
                   help="use heuristic triage, never call the API")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("triage", help="run Cline AI triage over stored reports")
    p.add_argument("--signature", default=None)
    p.add_argument("--force", action="store_true", help="ignore the cache")
    p.add_argument("--offline", action="store_true")
    p.set_defaults(func=cmd_triage)

    p = sub.add_parser("list", help="list stored bug reports")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="print one report's repro file")
    p.add_argument("signature")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("replay", help="re-simulate a (seed, actions) pair")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--actions", required=True, help="comma separated")
    p.add_argument("--max-steps", type=int, default=None)
    p.add_argument("--gif", default=None, help="write a GIF to this path")
    p.add_argument("--fps", type=int, default=8)
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("plant", help="verify and record the planted-bug repros")
    p.add_argument("--seed-base", type=int, default=0)
    p.add_argument("--search", type=int, default=200,
                   help="how many seeds to search")
    p.add_argument("--record", action="store_true",
                   help="write the repros into the bug store")
    p.add_argument("--no-gifs", action="store_true")
    p.set_defaults(func=cmd_plant)

    p = sub.add_parser("verify", help="prove a bug is gone, detectors intact")
    p.add_argument("--kind", required=True,
                   choices=sorted({v[1] for v in PLANTED_BUGS.values()}))
    p.add_argument("--signature", default=None)
    p.add_argument("--episodes", type=int, default=20)
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--seed-base", type=int, default=0)
    p.add_argument("--search", type=int, default=200)
    p.add_argument("--swarm-seed-base", type=int, default=5000)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("play", help="play the game interactively in your terminal")
    p.add_argument("--map", default="level_01", choices=["level_01", "level_02", "level_03"],
                   help="campaign map to play")
    p.add_argument("--seed", type=int, default=0, help="enemy starting seed")
    p.set_defaults(func=cmd_play)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
