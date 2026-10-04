"""Map layout and tile semantics.

MAP_RAW is the source of truth for the replay renderer and for the map-hole
detector: the detector compares where the player actually is against MAP_RAW,
not against the game's own walkable set. That is the whole point -- a detector
that trusts the game's own state cannot catch the game lying about its state.
"""
from __future__ import annotations

MAP_ID = "level_01"

# 12 wide x 10 tall. Legend:
#   #  wall        .  floor       ~  pit (walkable, items dropped here are at risk)
#   P  start       K  key         D  locked door     G  goal      C  coin
MAP_RAW = [
    "############",
    "#P.C.C..~..#",
    "#.#####.##.#",
    "#.#C..#..K.#",
    "#.#.#.#.##.#",
    "#.#C#.#.C..#",
    "#.#.#.####.#",
    "#...#....C##",
    "#####.##.DG#",
    "############",
]

HEIGHT = len(MAP_RAW)
WIDTH = len(MAP_RAW[0])

WALL = "#"
FLOOR = "."
PIT = "~"
START = "P"
KEY = "K"
DOOR = "D"
GOAL = "G"
COIN = "C"

# Tiles the game *intends* to let you stand on.
INTENDED_WALKABLE = {FLOOR, PIT, START, KEY, DOOR, GOAL, COIN}

# The planted map hole: a wall tile that the buggy walkable-set builder
# registers as floor. (4, 7) is the pillar separating the left chamber from
# the lower corridor, so walking through it is obvious on a replay.
MAP_HOLE_AT = (4, 7)

# Doors cost nothing to open but require the key. Kept as a constant so the
# exploit detector can reason about legal score deltas.
DOOR_OPEN_COST = 0
COIN_VALUE = 10
GOAL_VALUE = 100


def _assert_rectangular() -> None:
    for i, row in enumerate(MAP_RAW):
        if len(row) != WIDTH:
            raise ValueError(
                "MAP_RAW row %d is %d chars, expected %d" % (i, len(row), WIDTH)
            )


_assert_rectangular()


def in_bounds(pos) -> bool:
    x, y = pos
    return 0 <= x < WIDTH and 0 <= y < HEIGHT


def raw_tile(pos) -> str:
    """The tile character from MAP_RAW. Returns '#' for anything out of bounds."""
    x, y = pos
    if not in_bounds(pos):
        return WALL
    return MAP_RAW[y][x]


def is_wall_in_raw(pos) -> bool:
    return raw_tile(pos) == WALL


def parse_entities():
    """Extract start / key / door / goal / coin positions from MAP_RAW."""
    start = None
    key = None
    door = None
    goal = None
    coins = []
    for y, row in enumerate(MAP_RAW):
        for x, ch in enumerate(row):
            pos = (x, y)
            if ch == START:
                start = pos
            elif ch == KEY:
                key = pos
            elif ch == DOOR:
                door = pos
            elif ch == GOAL:
                goal = pos
            elif ch == COIN:
                coins.append(pos)
    if start is None or key is None or door is None or goal is None:
        raise ValueError("MAP_RAW must define P, K, D and G exactly once each")
    return {
        "start": start,
        "key": key,
        "door": door,
        "goal": goal,
        "coins": coins,
    }


def base_walkable():
    """The walkable set the game *should* build. Deterministic and sorted."""
    tiles = set()
    for y, row in enumerate(MAP_RAW):
        for x, ch in enumerate(row):
            if ch in INTENDED_WALKABLE:
                tiles.add((x, y))
    return tiles


def pit_tiles():
    """Pit tiles, in map order. The legend says items dropped here are at risk,
    so this is the documented hazard a QA bot is entitled to go and test."""
    return [(x, y)
            for y, row in enumerate(MAP_RAW)
            for x, ch in enumerate(row)
            if ch == PIT]


# ----------------------------------------------------------- campaign levels

LEVEL_02_RAW = [
    "############",
    "#P..~.C...K#",
    "###.#####.##",
    "#C..#...#..#",
    "#.###.~.##.#",
    "#...C.#..C.#",
    "#.#####.####",
    "#....~...C.#",
    "####.###.DG#",
    "############",
]

LEVEL_03_RAW = [
    "############",
    "#P.C...#C..#",
    "#.####.#.###",
    "#..K.#...#C#",
    "##.#.###.#.#",
    "#C.#...#...#",
    "#.####.###.#",
    "#....#.~.C.#",
    "####.###.DG#",
    "############",
]

CAMPAIGN_LEVELS = {
    "level_01": {
        "id": "level_01",
        "name": "The Forgotten Crypt",
        "theme": "dungeon",
        "raw": MAP_RAW,
        "description": "An ancient stone labyrinth with hidden dimensional anomalies and planted glitches.",
        "difficulty": "Normal",
        "par_steps": 28,
        "enemy_paths": [[(5, 7), (6, 7), (7, 7), (8, 7)]],
    },
    "level_02": {
        "id": "level_02",
        "name": "Inferno Bastion",
        "theme": "lava",
        "raw": LEVEL_02_RAW,
        "description": "Basalt corridors over magma chasms with patrolling fire elementals and secret coin vaults.",
        "difficulty": "Hard",
        "par_steps": 36,
        "enemy_paths": [[(3, 5), (4, 5), (5, 5)], [(1, 7), (2, 7), (3, 7)]],
    },
    "level_03": {
        "id": "level_03",
        "name": "Cyber Void Citadel",
        "theme": "cyber",
        "raw": LEVEL_03_RAW,
        "description": "A high-security neon cyber-grid vault guarded by high-speed surveillance drones.",
        "difficulty": "Expert",
        "par_steps": 42,
        "enemy_paths": [[(3, 1), (4, 1), (5, 1)], [(7, 5), (8, 5), (9, 5)]],
    },
}


def get_level(map_id: str = "level_01") -> dict:
    """Return level metadata and raw grid. Defaults to level_01."""
    return CAMPAIGN_LEVELS.get(map_id, CAMPAIGN_LEVELS["level_01"])


def parse_map_entities(raw_grid):
    """Extract start / key / door / goal / coin positions from any valid raw map."""
    start = None
    key = None
    door = None
    goal = None
    coins = []
    for y, row in enumerate(raw_grid):
        for x, ch in enumerate(row):
            pos = (x, y)
            if ch == START:
                start = pos
            elif ch == KEY:
                key = pos
            elif ch == DOOR:
                door = pos
            elif ch == GOAL:
                goal = pos
            elif ch == COIN:
                coins.append(pos)
    if start is None or key is None or door is None or goal is None:
        raise ValueError("Map must define P, K, D and G exactly once each")
    return {
        "start": start,
        "key": key,
        "door": door,
        "goal": goal,
        "coins": coins,
    }

