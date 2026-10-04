"""BFS helpers: shortest paths for repro generation, reachability for the
softlock detector.

The detector reasons about the *intended* map (maps.base_walkable), not the
game's own walkable set. A detector that trusts the game's model of itself
cannot notice the game lying about that model -- which is exactly what the
map-hole bug does.
"""
from __future__ import annotations

from collections import deque

from .actions import Action
from .maps import base_walkable, in_bounds

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))
_STEP_FOR_DELTA = {
    (0, -1): Action.UP,
    (0, 1): Action.DOWN,
    (-1, 0): Action.LEFT,
    (1, 0): Action.RIGHT,
}


def _free_tiles(door_pos, door_passable):
    tiles = set(base_walkable())
    if not door_passable:
        tiles.discard(door_pos)
    return tiles


def reachable_set(start, door_pos, door_passable):
    """All tiles reachable from `start` under the given door state.

    A start tile that is not walkable in the intended map means the game has
    already let the player somewhere it should not have. That is the map-hole
    bug, and the map-hole detector owns it -- such a tile is not a prison,
    because the player can still step off it onto any adjacent floor, so the
    flood is seeded from those neighbours. Seeding from `start` alone would
    make every off-map position look uncompletable and double-report the map
    hole as a critical softlock.
    """
    if not in_bounds(start):
        return set()
    tiles = _free_tiles(door_pos, door_passable)
    if start in tiles:
        seeds = [start]
    else:
        seeds = [(start[0] + dx, start[1] + dy) for dx, dy in NEIGHBOURS]
        seeds = [s for s in seeds if s in tiles]
        if not seeds:
            return {start}         # no way off the tile: genuinely stuck
    seen = set(seeds)
    queue = deque(seeds)
    while queue:
        x, y = queue.popleft()
        for dx, dy in NEIGHBOURS:
            nxt = (x + dx, y + dy)
            if nxt in tiles and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def bfs_path(start, goal, door_pos, door_passable):
    """Shortest tile path start->goal inclusive, or None."""
    tiles = _free_tiles(door_pos, door_passable)
    if start == goal:
        return [start]
    if goal not in tiles:
        return None
    prev = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        x, y = cur
        for dx, dy in NEIGHBOURS:
            nxt = (x + dx, y + dy)
            if nxt in tiles and nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    if goal not in prev:
        return None
    chain = [goal]
    while chain[-1] is not None:
        chain.append(prev[chain[-1]])
    chain.reverse()          # [None, start, ..., goal]
    return chain[1:]


def path_to_actions(path):
    """Convert a tile path into a list of movement Actions."""
    actions = []
    for cur, nxt in zip(path, path[1:]):
        delta = (nxt[0] - cur[0], nxt[1] - cur[1])
        act = _STEP_FOR_DELTA.get(delta)
        if act is None:
            raise ValueError("non-adjacent step in path: %r -> %r" % (cur, nxt))
        actions.append(act)
    return actions


def route(start, goal, door_pos, door_passable=False):
    """Movement actions from start to goal, or None if unreachable."""
    path = bfs_path(start, goal, door_pos, door_passable)
    if path is None:
        return None
    return path_to_actions(path)


def door_approach(door_pos, blocked=()):
    """A walkable tile orthogonally adjacent to the door (USE range)."""
    x, y = door_pos
    tiles = base_walkable()
    for dx, dy in NEIGHBOURS:
        cand = (x + dx, y + dy)
        if cand in tiles and cand not in blocked:
            return cand
    return None


def goal_reachable(pos, inventory, key_pos, door_pos, door_open, goal_pos):
    """Can the player still finish the level from this state?

    This is the softlock oracle. It is a real reachability proof, not a step
    counter, so it does not fire on a bot that is merely wandering.

    An *open* door needs no key, so it must be checked first: after the player
    spends the key on the door, inventory is empty and key_pos is None, and
    demanding an obtainable key at that point would report a softlock on a
    level that is one step from being won.
    """
    if door_open:
        return goal_pos in reachable_set(pos, door_pos, door_passable=True)

    free = reachable_set(pos, door_pos, door_passable=False)
    if goal_pos in free:
        return True
    key_available = ("key" in inventory) or (key_pos is not None and key_pos in free)
    if not key_available:
        return False
    with_door = reachable_set(pos, door_pos, door_passable=True)
    return goal_pos in with_door
