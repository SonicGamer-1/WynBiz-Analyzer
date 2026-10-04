"""A tiny deterministic headless grid game with four planted bugs.

Contract:
    env.reset(seed) -> obs
    env.step(action) -> (obs, reward, done, info)
    env.render_state() -> str

Given the same seed and the same action list, a run replays exactly. That is
what makes a bug report's repro steps and GIF trustworthy rather than
decorative.

Every planted bug is marked with a `# BUG:` comment and gated by
gameqa.game.bugs.bug_enabled(name), so a fix is a small, legible diff.
"""
from __future__ import annotations

import random

from .actions import Action, MOVEMENT, normalise
from .bugs import bug_enabled
from . import maps
from .maps import (
    COIN_VALUE,
    DOOR,
    GOAL_VALUE,
    MAP_HOLE_AT,
    MAP_ID,
    PIT,
    base_walkable,
    in_bounds,
    parse_entities,
    raw_tile,
)

ENTITY_KEYS = ("start", "key", "door", "goal", "coins")


class GridGame:
    """12x10 grid: keys, doors, coins, patrolling enemies."""

    def __init__(self, map_id=MAP_ID):
        self.map_id = map_id
        self.level_meta = maps.get_level(map_id) if hasattr(maps, "get_level") else {}
        self.walkable = self._build_walkable()
        if self.map_id == MAP_ID:
            self.entities = parse_entities()
        else:
            self.entities = maps.parse_map_entities(self.level_meta["raw"])
        self.total_coins = len(self.entities["coins"])
        self.max_legal_score = self.total_coins * COIN_VALUE + GOAL_VALUE
        self.rng = random.Random(0)
        self.seed = 0
        self.health = 3
        self.max_health = 3
        self.combo = 0
        self.events = []
        self.reset(0)

    # ---------------------------------------------------------------- setup

    def _build_walkable(self):
        if self.map_id == MAP_ID:
            tiles = base_walkable()
            if bug_enabled("map_hole"):
                # BUG: off-by-one when seeding the walkable set -- this wall tile
                # gets registered as floor, so the player walks straight through
                # the pillar at MAP_HOLE_AT.
                tiles.add(MAP_HOLE_AT)
            return frozenset(tiles)
        raw = self.level_meta.get("raw", maps.MAP_RAW)
        tiles = set()
        for y, row in enumerate(raw):
            for x, ch in enumerate(row):
                if ch in maps.INTENDED_WALKABLE:
                    tiles.add((x, y))
        return frozenset(tiles)

    def _make_enemies(self):
        """Patrolling enemies.

        Patrol is driven by the step counter, and the seed only picks the
        starting phase, so enemies stay perfectly reproducible. They block
        movement like a wall and deal no damage, which keeps them out of the
        detectors' way.
        """
        paths = self.level_meta.get("enemy_paths") if hasattr(self, "level_meta") and self.level_meta else None
        if not paths:
            paths = [[(5, 7), (6, 7), (7, 7), (8, 7)]]
        enemies = []
        for path in paths:
            count = 2 if len(paths) == 1 else 1
            for j in range(count):
                phase = self.rng.randrange(len(path)) if path else 0
                enemies.append(
                    {"path": path, "idx": phase, "dir": 1 if j == 0 else -1}
                )
        return enemies

    def reset(self, seed=0):
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.pos = self.entities["start"]
        self.inventory = []
        self.door_open = False
        self.score = 0
        self.combo = 0
        self.health = self.max_health
        self.events = []
        self.coins_collected = 0
        self.step_count = 0
        self.won = False
        self.done = False
        self.key_destroyed = False
        self._holding_key = False       # see BUG: crash
        self._paid_for = set()          # see BUG: exploit
        self.coins = [
            {"id": i, "pos": pos, "taken": False}
            for i, pos in enumerate(self.entities["coins"])
        ]
        self.key_pos = self.entities["key"]
        self.enemies = self._make_enemies()
        self.last_action = None
        return self.observe()

    # ----------------------------------------------------------------- obs

    def observe(self):
        return {
            "map_id": self.map_id,
            "map_name": self.level_meta.get("name", self.map_id),
            "theme": self.level_meta.get("theme", "dungeon"),
            "pos": self.pos,
            "inventory": list(self.inventory),
            "key_pos": self.key_pos,
            "key_destroyed": self.key_destroyed,
            "door_pos": self.entities["door"],
            "door_open": self.door_open,
            "goal_pos": self.entities["goal"],
            "coins": [
                {"id": c["id"], "pos": c["pos"], "taken": c["taken"]}
                for c in self.coins
            ],
            "coins_collected": self.coins_collected,
            "score": self.score,
            "combo": self.combo,
            "health": self.health,
            "max_health": self.max_health,
            "enemies": [e["path"][e["idx"]] for e in self.enemies],
            "step": self.step_count,
            "won": self.won,
            "done": self.done,
            "walkable_size": len(self.walkable),
        }

    def get_hud_state(self):
        """Formatted HUD state for UI and arcade displays."""
        return {
            "map_id": self.map_id,
            "map_name": self.level_meta.get("name", "The Crypt"),
            "theme": self.level_meta.get("theme", "dungeon"),
            "score": self.score,
            "combo": self.combo,
            "health": self.health,
            "max_health": self.max_health,
            "coins": self.coins_collected,
            "total_coins": self.total_coins,
            "has_key": "key" in self.inventory,
            "door_open": self.door_open,
            "steps": self.step_count,
            "won": self.won,
            "done": self.done,
            "pos": self.pos,
        }


    # ------------------------------------------------------------ helpers

    def _coin_at(self, pos):
        for c in self.coins:
            if not c["taken"] and c["pos"] == pos:
                return c
        return None

    def _enemy_positions(self):
        return [e["path"][e["idx"]] for e in self.enemies]

    def _passable(self, pos):
        if pos not in self.walkable:
            return False
        if pos == self.entities["door"] and not self.door_open:
            return False
        if pos in self._enemy_positions():
            return False
        return True

    def _adjacent_door(self):
        door = self.entities["door"]
        dx, dy = self.pos
        for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            if (dx + ox, dy + oy) == door:
                return True
        return False

    def _advance_enemies(self):
        for e in self.enemies:
            nxt = e["idx"] + e["dir"]
            if nxt >= len(e["path"]) or nxt < 0:
                e["dir"] = -e["dir"]
                nxt = e["idx"] + e["dir"]
            e["idx"] = nxt

    # ------------------------------------------------------------- actions

    def _do_move(self, action):
        dx, dy = MOVEMENT[action]
        target = (self.pos[0] + dx, self.pos[1] + dy)
        if not self._passable(target):
            return 0.0
        self.pos = target
        if bug_enabled("exploit"):
            # BUG: coin duplication (part 2 of 2). The "already paid" guard is
            # wiped on every successful move, and coins are never marked as
            # taken, so returning to a coin tile pays it out again. Pick up ->
            # step away -> step back -> pick up == infinite coins.
            self._paid_for = set()
        if target == self.entities["goal"]:
            self.won = True
            self.done = True
            self.score += GOAL_VALUE
            return 1.0
        return -0.01

    def _do_pickup(self):
        coin = self._coin_at(self.pos)
        if coin is None:
            if self.key_pos == self.pos and "key" not in self.inventory:
                self.inventory.append("key")
                self.key_pos = None
                self._holding_key = True
                return 0.5
            return 0.0

        if bug_enabled("exploit"):
            # BUG: coin duplication. The coin is credited but never marked
            # taken, and the "already paid" guard holds only the current tile
            # and is reset by _do_move. Pick up -> step away -> step back
            # pays out the same coin again, forever.
            if self.pos in self._paid_for:
                return 0.0
            self._paid_for = {self.pos}
            self.coins_collected += 1
            self.score += COIN_VALUE
            return 0.5

        coin["taken"] = True
        self.coins_collected += 1
        self.score += COIN_VALUE
        return 0.5

    def _do_drop(self):
        if "key" not in self.inventory:
            return 0.0

        if bug_enabled("softlock") and raw_tile(self.pos) == PIT:
            # BUG: softlock. Dropping onto a pit silently *destroys* the item
            # instead of refusing the drop. The key leaves the world for good
            # and the door can never be opened again.
            self.inventory.remove("key")
            self.key_pos = None
            self.key_destroyed = True
            return -1.0

        if raw_tile(self.pos) == PIT:
            # Correct behaviour: you cannot place an item in a pit, so the
            # drop is refused and the player keeps the key.
            return 0.0

        self.inventory.remove("key")
        self.key_pos = self.pos
        # NOTE: the buggy USE path below trusts _holding_key, which this
        # drop forgets to clear. See BUG: crash.
        return -0.1

    def _do_use(self):
        if not self._adjacent_door():
            return 0.0
        if self.door_open:
            return 0.0

        if bug_enabled("crash"):
            # BUG: crash. USE trusts the stale _holding_key flag that DROP
            # never clears, then indexes inventory[0] without guarding an
            # empty inventory. PICKUP key -> DROP -> USE raises IndexError.
            if self._holding_key:
                held = self.inventory[0]
                if held == "key":
                    self.door_open = True
                    self.inventory.remove("key")
                    self._holding_key = False
                    return 1.0
            return 0.0

        if "key" in self.inventory:
            self.inventory.remove("key")
            self.key_pos = None
            self._holding_key = False
            self.door_open = True
            return 1.0
        return 0.0

    # ---------------------------------------------------------------- step

    def step(self, action):
        if self.done:
            return self.observe(), 0.0, True, {"reason": "already_done", "events": []}

        act = normalise(action)
        self.last_action = act
        self.step_count += 1
        reward = 0.0
        self.events = []
        sound = "step" if act in MOVEMENT else None
        info = {"action": act, "accepted": act is not None}

        if act is None:
            # Unknown input must be a no-op. Anything else is a game bug.
            info["reason"] = "invalid_input_ignored"
            self.events.append("invalid_input")
            sound = "error"
        elif act in MOVEMENT:
            prev_pos = self.pos
            reward = self._do_move(act)
            if self.pos != prev_pos:
                self.events.append("move")
                sound = "step"
                if self.won:
                    self.events.append("victory")
                    sound = "win"
            else:
                self.events.append("bump")
                sound = "bump"
        elif act == Action.PICKUP:
            prev_coins = self.coins_collected
            prev_held = "key" in self.inventory
            reward = self._do_pickup()
            if self.coins_collected > prev_coins:
                self.combo += 1
                self.events.append("coin")
                sound = "coin"
            elif "key" in self.inventory and not prev_held:
                self.events.append("key_pickup")
                sound = "key"
            else:
                sound = "fail"
        elif act == Action.DROP:
            reward = self._do_drop()
            if self.key_destroyed:
                self.events.append("key_destroyed")
                sound = "hazard"
            elif self.key_pos == self.pos:
                self.events.append("key_drop")
                sound = "drop"
            else:
                sound = "fail"
        elif act == Action.USE:
            prev_door = self.door_open
            reward = self._do_use()
            if self.door_open and not prev_door:
                self.events.append("door_open")
                sound = "door"
            else:
                sound = "fail"
        elif act == Action.WAIT:
            reward = -0.01
            sound = "wait"

        self._advance_enemies()
        info["events"] = list(self.events)
        info["sound"] = sound
        info["combo"] = self.combo
        info["health"] = self.health
        info["score"] = self.score
        info["pos"] = self.pos
        info["won"] = self.won
        return self.observe(), reward, self.done, info

    # -------------------------------------------------------------- render

    def render_state(self):
        """ASCII frame used by the replay GIF and the dashboard trace view."""
        raw = self.level_meta.get("raw", maps.MAP_RAW) if hasattr(self, "level_meta") and self.level_meta else maps.MAP_RAW
        height = len(raw)
        width = len(raw[0])
        grid = [list(row) for row in raw]
        for y in range(height):
            for x in range(width):
                if grid[y][x] in ("P", "C", "K"):
                    grid[y][x] = maps.FLOOR
        for c in self.coins:
            if not c["taken"]:
                x, y = c["pos"]
                grid[y][x] = "C"
        if not self.key_destroyed and self.key_pos is not None:
            x, y = self.key_pos
            grid[y][x] = "K"
        if self.door_open:
            x, y = self.entities["door"]
            grid[y][x] = maps.FLOOR
        for ex, ey in self._enemy_positions():
            if (ex, ey) != self.pos:
                grid[ey][ex] = "E"
        px, py = self.pos
        grid[py][px] = "W" if self.won else "@"
        return "\n".join("".join(row) for row in grid)

