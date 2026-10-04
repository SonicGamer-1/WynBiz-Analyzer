"""Softlock detector: the level can no longer be completed.

This is a reachability proof, not a step counter. A bot wandering in circles
is not a bug; a world state from which the goal is provably unreachable is.

The oracle: BFS over the *intended* map. The door counts as passable only if
it is already open, or if the key is still obtainable (carried, or sitting on
a tile the player can reach). If the key has been destroyed, the door can
never open and the goal is unreachable -> softlock.
"""
from __future__ import annotations

from ..game.pathing import goal_reachable
from .base import Detector, Finding


class SoftlockDetector(Detector):
    """Goal became provably unreachable from the current world state."""

    name = "softlock"
    kind = "softlock"

    def check(self, ctx):
        if ctx.obs_after is None or ctx.exception is not None:
            return None
        obs = ctx.obs_after
        if obs["done"] or obs["won"]:
            return None

        reachable = goal_reachable(
            pos=tuple(obs["pos"]),
            inventory=list(obs["inventory"]),
            key_pos=tuple(obs["key_pos"]) if obs["key_pos"] else None,
            door_pos=tuple(obs["door_pos"]),
            door_open=bool(obs["door_open"]),
            goal_pos=tuple(obs["goal_pos"]),
        )
        if reachable:
            return None

        reason = "key_destroyed" if obs["key_destroyed"] else "goal_unreachable"
        return Finding(
            kind=self.kind,
            signature="softlock|%s|%s" % (obs["map_id"], reason),
            summary="level cannot be completed: %s" % reason,
            severity_hint="critical",
            step_index=ctx.step_index,
            detail={
                "reason": reason,
                "key_destroyed": bool(obs["key_destroyed"]),
                "key_pos": list(obs["key_pos"]) if obs["key_pos"] else None,
                "inventory": list(obs["inventory"]),
                "door_open": bool(obs["door_open"]),
                "player_pos": list(obs["pos"]),
                "goal_pos": list(obs["goal_pos"]),
                "step": obs["step"],
                "last_action": str(ctx.action),
            },
        )
