"""Chaos tester (gremlin).

Spams odd inputs -- None, "", "up", -1, 999, {}, object() -- and interleaves
them with a crude scripted routine: grab the key, drop it in a pit, walk to the
door, DROP, USE. A well-behaved game ignores the junk. This bot is what
surfaces the crash and the softlock, because both need a specific ordering --
PICKUP -> DROP -> USE at the door, and PICKUP -> DROP while standing on a pit --
that a pure random walker only hits by luck.

Both scripted targets come from documented game rules, not from knowledge of
the planted bugs: the map legend says items dropped in a pit are at risk, and
USE-at-door is the ordinary way to open it.
"""
from __future__ import annotations

from ..game.actions import MOVEMENT, Action, INVALID_INPUTS
from ..game.maps import pit_tiles
from ..game.pathing import door_approach, route
from .base import Bot

JUNK_RATE = 0.30

# The grief burst played once the gremlin reaches the door.
DOOR_BURST = [Action.DROP, Action.USE, Action.USE, Action.PICKUP, Action.DROP]


class ChaosTester(Bot):
    """Spams invalid input and scripted abuse sequences."""

    name = "chaos_tester"

    def _reset(self, seed):
        self._queue = []
        self._expected = None
        self._pits = set(pit_tiles())
        self._pit_done = False       # has a DROP actually landed on a pit?

    def _plan(self, obs):
        """State-driven priorities, not a phase machine.

        Junk input never moves the player, so it cannot desync the queue, but
        an enemy block can -- and a phase machine that advances at *planning*
        time then dead-ends once the key is gone. Every branch here is decided
        from the current observation, so a discarded plan just re-decides.
        """
        pos = tuple(obs["pos"])
        door = tuple(obs["door_pos"])

        # Both scripted abuses want the key, so fetch it whenever obtainable.
        if ("key" not in obs["inventory"] and not obs["key_destroyed"]
                and obs["key_pos"] is not None):
            leg = route(pos, tuple(obs["key_pos"]), door, door_passable=False)
            if leg is not None:
                return list(leg) + [Action.PICKUP]

        # The map legend says items dropped in a pit are at risk, so test that
        # rule with the key in hand. Re-routed until the DROP really lands on a
        # pit, then never attempted again: with the softlock bug fixed the key
        # survives the drop, and fetching it back to drop it again would loop
        # forever instead of grieving the door.
        if not self._pit_done and "key" in obs["inventory"]:
            best = None
            for pit in sorted(self._pits):
                leg = route(pos, pit, door, door_passable=False)
                if leg is not None and (best is None or len(leg) < len(best)):
                    best = leg
            if best is not None:
                return list(best) + [Action.DROP]

        # Grief the door: DROP, then USE on an empty inventory. This needs no
        # key, so it is still worth playing after the key has been destroyed.
        approach = door_approach(door)
        if approach is None:
            return []
        leg = route(pos, approach, door, door_passable=False)
        if leg is None:
            return []
        return list(leg) + list(DOOR_BURST)

    def act(self, obs):
        if self.rng.random() < JUNK_RATE:
            return self.rng.choice(INVALID_INPUTS)

        pos = tuple(obs["pos"])
        if not self._queue or pos != self._expected:
            self._queue = self._plan(obs)
            self._expected = pos
        if not self._queue:
            return self.rng.choice(list(MOVEMENT) + [Action.PICKUP, Action.DROP])

        action = self._queue.pop(0)
        if action == Action.DROP and pos in self._pits:
            self._pit_done = True
        if action in MOVEMENT:
            dx, dy = MOVEMENT[action]
            self._expected = (pos[0] + dx, pos[1] + dy)
        else:
            self._expected = pos
        return action
