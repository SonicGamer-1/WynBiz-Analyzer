"""Pinned, deterministic repros for the four planted bugs.

The random swarm is showmanship; these are the guarantee. Each repro is a
fixed (seed, action list) pair that MUST produce its detector's finding.
Running tests/test_planted_bugs.py before going on stage tells you the demo
will work.

Because enemies patrol and can block a step, a scripted route can desync on
some seeds. Rather than assume, `build_pinned()` searches seeds and keeps only
one that is *verified by actually running it*.
"""
from __future__ import annotations

from .game.actions import Action
from .game.bugs import PLANTED_BUGS, bug_enabled
from .game.maps import MAP_HOLE_AT, MAP_RAW, PIT, parse_entities
from .game.pathing import door_approach, route
from .swarm.runner import run_script

_ENT = parse_entities()
START = _ENT["start"]
KEY = _ENT["key"]
DOOR = _ENT["door"]
GOAL = _ENT["goal"]
COINS = _ENT["coins"]

PIT_TILE = next(
    (x, y)
    for y, row in enumerate(MAP_RAW)
    for x, ch in enumerate(row)
    if ch == PIT
)


def _labels(actions):
    return [a.value if isinstance(a, Action) else str(a) for a in actions]


def _leg(start, goal):
    leg = route(start, goal, DOOR, door_passable=False)
    if leg is None:
        raise AssertionError("no route %r -> %r" % (start, goal))
    return leg


# ---------------------------------------------------------------- builders

def build_softlock():
    """Pick up the key, carry it onto the pit, drop it. Key is gone forever."""
    actions = _leg(START, KEY) + [Action.PICKUP]
    actions += _leg(KEY, PIT_TILE) + [Action.DROP]
    return _labels(actions)


def build_map_hole():
    """Walk into the pillar that the buggy collision data says is floor."""
    approach = (MAP_HOLE_AT[0] - 1, MAP_HOLE_AT[1])
    actions = _leg(START, approach) + [Action.RIGHT]
    return _labels(actions)


def build_exploit():
    """Pick up a coin, step away, step back, repeat. Coins multiply."""
    coin = COINS[0]
    actions = _leg(START, coin) + [Action.PICKUP]
    for _ in range(len(COINS) + 2):
        actions += [Action.LEFT, Action.RIGHT, Action.PICKUP]
    return _labels(actions)


def build_crash():
    """Pick up the key, drop it at the door, then USE. Stale flag -> IndexError."""
    approach = door_approach(DOOR)
    if approach is None:
        raise AssertionError("door has no adjacent walkable tile")
    actions = _leg(START, KEY) + [Action.PICKUP]
    actions += _leg(KEY, approach) + [Action.DROP, Action.USE]
    return _labels(actions)


BUILDERS = {
    "softlock": build_softlock,
    "map_hole": build_map_hole,
    "exploit": build_exploit,
    "crash": build_crash,
}


# -------------------------------------------------------------- verification

def check(name, seed, actions=None):
    """Run a pinned repro and return the matching signature, or None."""
    if not bug_enabled(name):
        return None
    actions = actions if actions is not None else BUILDERS[name]()
    prefix = PLANTED_BUGS[name][1] + "|"
    result = run_script(seed, actions)
    for finding in result["findings"]:
        if finding["signature"].startswith(prefix):
            return finding["signature"]
    return None


def find_seed(name, actions=None, search=range(0, 500)):
    """First seed for which this repro is verified to fire."""
    actions = actions if actions is not None else BUILDERS[name]()
    for seed in search:
        if check(name, seed, actions):
            return seed
    return None


def build_pinned(search=range(0, 500)):
    """{bug name: {seed, actions, signature}} for every enabled planted bug."""
    pinned = {}
    for name in PLANTED_BUGS:
        if not bug_enabled(name):
            continue
        actions = BUILDERS[name]()
        seed = find_seed(name, actions, search)
        if seed is None:
            pinned[name] = {"seed": None, "actions": actions,
                            "signature": None, "verified": False}
            continue
        pinned[name] = {
            "seed": seed,
            "actions": actions,
            "signature": check(name, seed, actions),
            "verified": True,
        }
    return pinned
