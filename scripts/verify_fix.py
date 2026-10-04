"""Verify a fix: the bug is gone AND every other detector still fires.

    python scripts/verify_fix.py --kind crash
    python scripts/verify_fix.py --simulate          # dry-run all four
    python scripts/verify_fix.py --all               # after a real fix sweep

Why both halves matter: "the crash no longer appears" is worthless on its own,
because a broken detector also produces zero findings. This script asserts the
target signature is gone while the other three planted bugs are still found by
both their pinned repros and a fresh swarm run.

`--simulate` needs no code change at all: it flips each planted-bug flag off in
turn and runs the same verification, so you can prove the verify harness works
before you rely on it on stage.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gameqa.cli import build_parser, cmd_verify          # noqa: E402
from gameqa.game.bugs import PLANTED_BUGS, disable, enable, reset_all  # noqa: E402


def _verify_args(kind, artifacts, episodes, workers, seed_base, search,
                 swarm_seed_base):
    parser = build_parser()
    argv = [
        "--artifacts", artifacts,
        "verify",
        "--kind", kind,
        "--episodes", str(episodes),
        "--workers", str(workers),
        "--seed-base", str(seed_base),
        "--search", str(search),
        "--swarm-seed-base", str(swarm_seed_base),
    ]
    return parser.parse_args(argv)


def verify_one(kind, args):
    return cmd_verify(_verify_args(
        kind, args.artifacts, args.episodes, args.workers,
        args.seed_base, args.search, args.swarm_seed_base,
    ))


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", default=None,
                        choices=sorted({v[1] for v in PLANTED_BUGS.values()}))
    parser.add_argument("--all", action="store_true",
                        help="verify every planted bug kind in turn")
    parser.add_argument("--simulate", action="store_true",
                        help="flip each bug flag off instead of trusting a fix")
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed-base", type=int, default=0)
    parser.add_argument("--search", type=int, default=200)
    parser.add_argument("--swarm-seed-base", type=int, default=5000)
    args = parser.parse_args(argv)

    kinds = sorted({v[1] for v in PLANTED_BUGS.values()})
    if args.simulate:
        args.all = True

    if not args.all and not args.kind:
        parser.error("choose --kind KIND, --all, or --simulate")

    targets = kinds if args.all else [args.kind]
    results = {}
    for kind in targets:
        name = next(n for n, v in PLANTED_BUGS.items() if v[1] == kind)
        if args.simulate:
            disable(name)
            print("=== simulating a fix for %s (%s) ===" % (name, kind))
        else:
            print("=== verifying %s (%s) ===" % (name, kind))
        try:
            results[kind] = verify_one(kind, args)
        finally:
            if args.simulate:
                enable(name)
        print("")

    print("=" * 62)
    print("kind        result")
    for kind in targets:
        print("%-11s %s" % (kind, "PASS" if results[kind] == 0 else "FAIL"))
    failed = [k for k, v in results.items() if v != 0]
    if args.simulate:
        reset_all(True)
    print("")
    print("OVERALL: %s" % ("PASS" if not failed else "FAIL (%s)" % ", ".join(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(run())
