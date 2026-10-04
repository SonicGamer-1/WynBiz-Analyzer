"""Planted bugs.

Every planted bug is behind a flag here and marked with a `# BUG:` comment at
its site in grid_game.py. Fixing a bug during the demo means flipping the flag
off (or, better, letting Cline delete the buggy branch).

`verify_fix.py` re-runs the swarm with a flag off and asserts that bug's
signature disappears while the other three are still found.
"""
from __future__ import annotations

# name            -> (flag, signature kind, short description)
PLANTED_BUGS = {
    "softlock": (
        "BUG_SOFTLOCK_KEY_LOST_IN_PIT",
        "softlock",
        "DROP on a pit tile destroys the key instead of refusing, "
        "so the door can never be opened.",
    ),
    "map_hole": (
        "BUG_MAP_HOLE_WALKABLE_WALL",
        "map_hole",
        "Off-by-one when building the walkable set registers one wall "
        "tile as floor, so the player can walk through a wall.",
    ),
    "exploit": (
        "BUG_COIN_DUPLICATION",
        "exploit",
        "Coin identity is keyed by tile instead of by coin id, so "
        "pick up / step away / step back duplicates a coin.",
    ),
    "crash": (
        "BUG_CRASH_USE_DROP_USE",
        "crash",
        "USE reads inventory[0] without guarding an empty inventory; "
        "USE, DROP, USE on the door tile raises IndexError.",
    ),
}

BUG_FLAGS = {name: True for name in PLANTED_BUGS}


def bug_enabled(name: str) -> bool:
    return bool(BUG_FLAGS.get(name, False))


def disable(name: str) -> None:
    BUG_FLAGS[name] = False


def enable(name: str) -> None:
    BUG_FLAGS[name] = True


def reset_all(value: bool = True) -> None:
    for name in PLANTED_BUGS:
        BUG_FLAGS[name] = value


def signature_for(name: str) -> str:
    return PLANTED_BUGS[name][1]


def describe(name: str) -> str:
    return PLANTED_BUGS[name][2]
