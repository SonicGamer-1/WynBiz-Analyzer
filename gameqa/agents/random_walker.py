"""Random walker: uniform-ish random legal actions, biased toward movement."""
from __future__ import annotations

from ..game.actions import Action
from .base import Bot

MOVES = [Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT]

# Weighted action table. DROP is rare but present: that is what eventually
# loses the key in the pit.
TABLE = (
    [(a, 19) for a in MOVES]
    + [(Action.PICKUP, 10), (Action.WAIT, 5), (Action.USE, 5), (Action.DROP, 4)]
)


def _weighted(rng, table):
    total = sum(w for _, w in table)
    pick = rng.randrange(total)
    acc = 0
    for action, weight in table:
        acc += weight
        if pick < acc:
            return action
    return table[-1][0]


class RandomWalker(Bot):
    """Wanders without a plan. Good at finding map holes and dup loops."""

    name = "random_walker"

    def _reset(self, seed):
        self._last = None

    def act(self, obs):
        action = _weighted(self.rng, TABLE)
        # Avoid pure repetition so walks cover more ground.
        tries = 0
        while action == self._last and tries < 3:
            action = _weighted(self.rng, TABLE)
            tries += 1
        self._last = action
        return action
