"""Actions a bot can send to the game.

INVALID_INPUTS is what the chaos tester spams. A well-behaved game should
ignore them gracefully. If it raises instead, the crash detector fires.
"""
from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    USE = "USE"          # use the item in front of you (unlock a door)
    PICKUP = "PICKUP"    # pick up an item on your tile
    DROP = "DROP"        # drop the carried item on your tile
    WAIT = "WAIT"


MOVEMENT = {
    Action.UP: (0, -1),
    Action.DOWN: (0, 1),
    Action.LEFT: (-1, 0),
    Action.RIGHT: (1, 0),
}

# Deliberately nasty inputs for the chaos bot.
INVALID_INPUTS = [
    None,
    "",
    "up",            # wrong case
    "NORTH",         # unknown name
    -1,
    0,
    999,
    {},
    [],
    object(),
    Action.UP,
    Action.WAIT,
]


def normalise(action):
    """Best-effort coercion of a raw agent input into an Action.

    Anything unrecognised becomes None and must be treated as a no-op by the
    game. Crashing here is a bug in the game, not in the bot.
    """
    if isinstance(action, Action):
        return action
    if isinstance(action, str):
        try:
            return Action(action.strip().upper())
        except (ValueError, AttributeError):
            return None
    return None


ACTION_NAMES = [a.value for a in Action]
