"""Goal seeker: BFS-planned bot that goes for coins, then the key, then the
door, then the goal. Replans whenever its plan runs out or the world moves
under it (an enemy blocking a corridor, a dropped key, an opened door).

Two deliberate design choices, both of which matter for the demo:

  * Coins are tracked by what *this bot* has already picked up, not by
    `obs["coins"][i]["taken"]`. The game can lie about `taken` -- the coin
    duplication bug does exactly that -- and a bot that believed it would
    re-walk the whole coin sweep on every replan, burn its step budget, and
    never reach the key. Planning against your own history keeps the bot
    competent even when the world state is untrustworthy.

  * Once the sweep is done, if the game *still* reports a coin as present, the
    bot walks back and takes it again. A player who sees a collected item
    reappear investigates. That single probe is what surfaces the duplication
    exploit on the intended path, without the bot being written to cheat.

Planning is incremental -- coins, then one probe, then key/door/goal -- and
`_claimed` and `_probed` only ever grow, so every replan makes forward progress
instead of restarting from scratch. The probe is armed as a *target* rather
than a flag, so an enemy blocking a step mid-walk re-routes it instead of
silently cancelling it; it is only retired once its PICKUP has been issued.
"""
from __future__ import annotations

from ..game.actions import Action
from ..game.pathing import door_approach, route
from .base import Bot


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class GoalSeeker(Bot):
    """Competent player. Finds bugs that only show up on the intended path."""

    name = "goal_seeker"

    def _reset(self, seed):
        self._queue = []
        self._expected = None
        self._claimed = set()      # coin tiles this bot has picked up
        self._probe_target = None  # ghost coin it is walking back to
        self._probed = False       # has the probe's PICKUP been issued?

    # ---------------------------------------------------------------- plan

    @staticmethod
    def _untaken(obs):
        return [tuple(c["pos"]) for c in obs["coins"] if not c["taken"]]

    @staticmethod
    def _coin_here(obs, pos):
        return any(tuple(c["pos"]) == pos and not c["taken"]
                   for c in obs["coins"])

    def _plan_coins(self, obs, door, cur):
        """Sweep every coin this bot has not already collected, nearest first."""
        actions = []
        targets = [p for p in self._untaken(obs) if p not in self._claimed]
        while targets:
            nxt = min(targets, key=lambda t: _manhattan(t, cur))
            targets.remove(nxt)
            leg = route(cur, nxt, door, door_passable=False)
            if leg is None:
                continue
            actions.extend(leg)
            actions.append(Action.PICKUP)
            cur = nxt
        return actions, cur

    def _plan_probe(self, obs, door, cur):
        """Walk back to the ghost coin this bot already took and take it again,
        to see what the game does."""
        pos = self._probe_target
        if pos is None or self._coin_here(obs, pos) is False:
            return [], cur
        leg = route(cur, pos, door, door_passable=False)
        if leg is None:
            return [], cur
        return list(leg) + [Action.PICKUP], pos

    @staticmethod
    def _plan_finish(obs, door, cur):
        """Key -> door -> goal."""
        actions = []
        need_key = "key" not in obs["inventory"] and not obs["door_open"]
        if need_key and not obs["key_destroyed"] and obs["key_pos"] is not None:
            key_tile = tuple(obs["key_pos"])
            leg = route(cur, key_tile, door, door_passable=False)
            if leg is not None:
                actions.extend(leg)
                actions.append(Action.PICKUP)
                cur = key_tile

        if not obs["door_open"]:
            approach = door_approach(door)
            if approach is not None:
                leg = route(cur, approach, door, door_passable=False)
                if leg is not None:
                    actions.extend(leg)
                    actions.append(Action.USE)
                    cur = approach

        leg = route(cur, tuple(obs["goal_pos"]), door, door_passable=True)
        if leg is not None:
            actions.extend(leg)
        return actions

    def _plan(self, obs):
        cur = tuple(obs["pos"])
        door = tuple(obs["door_pos"])

        actions, cur = self._plan_coins(obs, door, cur)
        if actions:
            return actions

        # Arm the probe once, then keep re-routing to it until its PICKUP is
        # actually issued. An enemy can block a step mid-walk, which discards
        # the queue; if the probe were marked done at *planning* time, one
        # block would cancel it for good and the exploit would go unnoticed.
        if self._probe_target is None and not self._probed and self._untaken(obs):
            self._probe_target = self._untaken(obs)[0]
        if self._probe_target is not None:
            actions, cur = self._plan_probe(obs, door, cur)
            if actions:
                return actions
            self._probe_target = None    # gone or unreachable: stop trying

        return self._plan_finish(obs, door, cur)

    # ----------------------------------------------------------------- act

    def act(self, obs):
        pos = tuple(obs["pos"])
        if not self._queue or pos != self._expected:
            self._queue = self._plan(obs)
            self._expected = pos
        if not self._queue:
            return Action.WAIT

        action = self._queue.pop(0)
        # Record coin pickups as they are *issued*, not as they are planned:
        # a plan can be discarded mid-way when an enemy blocks a step, and a
        # coin the bot never reached must stay targetable.
        if action == Action.PICKUP:
            if self._coin_here(obs, pos):
                self._claimed.add(pos)
            if pos == self._probe_target:
                self._probed = True
                self._probe_target = None
        self._expected = self._advance(pos, action)
        return action

    @staticmethod
    def _advance(pos, action):
        from ..game.actions import MOVEMENT

        if action in MOVEMENT:
            dx, dy = MOVEMENT[action]
            return (pos[0] + dx, pos[1] + dy)
        return pos
