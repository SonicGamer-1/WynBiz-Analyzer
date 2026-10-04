"""Pre-flight check: prove the demo will work before you go on stage.

    python scripts/seed_bugs.py            # verify pinned repros only
    python scripts/seed_bugs.py --record   # also write them into the store

Searches for a seed at which each planted bug is *actually* reproduced by its
scripted repro, prints the seed and the finding signature, and exits non-zero
if any planted bug cannot be reproduced. A red run here means the demo is
broken; a green run means the four findings are guaranteed.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gameqa.cli import main as cli_main      # noqa: E402


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed-base", type=int, default=0)
    parser.add_argument("--search", type=int, default=200)
    parser.add_argument("--record", action="store_true",
                        help="write the verified repros into artifacts/bugs")
    parser.add_argument("--artifacts", default=None)
    parser.add_argument("--no-gifs", action="store_true")
    return parser


def run(argv=None):
    args = build_arg_parser().parse_args(argv)
    cli_argv = [
        "--artifacts", args.artifacts or "artifacts",
        "plant",
        "--seed-base", str(args.seed_base),
        "--search", str(args.search),
    ]
    if args.record:
        cli_argv.append("--record")
    if args.no_gifs:
        cli_argv.append("--no-gifs")
    return cli_main(cli_argv)


if __name__ == "__main__":
    sys.exit(run())
