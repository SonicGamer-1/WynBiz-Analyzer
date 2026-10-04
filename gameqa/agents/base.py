"""Bot interface.

A bot sees only the observation dict and returns a raw action. Bots are
allowed to return garbage -- that is the chaos tester's whole job. The game
must survive it.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod


class Bot(ABC):
    name = "bot"

    def __init__(self):
        self.rng = random.Random(0)

    def reset(self, seed=0):
        self.rng = random.Random(seed)
        self._reset(seed)

    def _reset(self, seed):
        """Hook for subclass per-episode state."""

    @abstractmethod
    def act(self, obs):
        """Return the next action for `obs`. Any value is legal to return."""

    def describe(self):
        return self.__class__.__doc__ or self.name


def make_bot(name):
    from .chaos_tester import ChaosTester
    from .goal_seeker import GoalSeeker
    from .random_walker import RandomWalker

    registry = {
        RandomWalker.name: RandomWalker,
        GoalSeeker.name: GoalSeeker,
        ChaosTester.name: ChaosTester,
    }
    if name not in registry:
        raise KeyError("unknown bot %r; have %s" % (name, sorted(registry)))
    return registry[name]()


BOT_NAMES = ["random_walker", "goal_seeker", "chaos_tester"]
