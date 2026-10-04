"""Map-hole detector: the player is inside a wall or outside the map.

Compares the player's position against MAP_RAW -- the declared level data --
rather than against the game's own walkable set. The planted map-hole bug is
precisely a disagreement between those two, so trusting the game's set would
make this detector blind.
"""
from __future__ import annotations

from ..game.maps import in_bounds, is_wall_in_raw
from .base import Detector, Finding


class MapHoleDetector(Detector):
    """Player ended a step inside a wall tile or outside the map bounds."""

    name = "map_hole"
    kind = "map_hole"

    def check(self, ctx):
        if ctx.obs_after is None:
            return None
        pos = tuple(ctx.obs_after["pos"])

        if not in_bounds(pos):
            return Finding(
                kind=self.kind,
                signature="map_hole|out_of_bounds|%d|%d" % pos,
                summary="player left the map at %r" % (pos,),
                severity_hint="high",
                step_index=ctx.step_index,
                detail={"pos": list(pos), "reason": "out_of_bounds",
                        "last_action": str(ctx.action)},
            )

        if is_wall_in_raw(pos):
            return Finding(
                kind=self.kind,
                signature="map_hole|inside_wall|%d|%d" % pos,
                summary="player is inside a wall tile at %r" % (pos,),
                severity_hint="high",
                step_index=ctx.step_index,
                detail={"pos": list(pos), "reason": "inside_wall",
                        "raw_tile": "#",
                        "in_game_walkable": pos in ctx.env.walkable,
                        "last_action": str(ctx.action),
                        "came_from": list(ctx.obs_before["pos"])
                        if ctx.obs_before else None},
            )
        return None
