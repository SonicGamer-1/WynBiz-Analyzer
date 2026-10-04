"""Detector framework.

A detector is a pure rule: given everything that happened on one step, it
either returns a Finding or None. Findings carry a *signature* -- a stable,
seed-independent key used to merge duplicates, so 40 bots walking into the
same wall tile produce one bug report, not 40.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Finding:
    """One detector hit on one step."""

    __slots__ = (
        "kind",
        "signature",
        "summary",
        "severity_hint",
        "step_index",
        "detail",
    )

    def __init__(self, kind, signature, summary, severity_hint="medium",
                 step_index=-1, detail=None):
        self.kind = kind
        self.signature = signature
        self.summary = summary
        self.severity_hint = severity_hint
        self.step_index = step_index
        self.detail = detail or {}

    def to_dict(self):
        return {
            "kind": self.kind,
            "signature": self.signature,
            "summary": self.summary,
            "severity_hint": self.severity_hint,
            "step_index": self.step_index,
            "detail": self.detail,
        }


class DetectContext:
    """Everything a detector may look at for a single step."""

    __slots__ = (
        "env", "obs_before", "action", "obs_after", "reward", "done",
        "info", "step_index", "exception", "traceback_text", "actions_so_far",
        "max_score_seen", "frames",
    )

    def __init__(self, env, obs_before, action, obs_after, reward, done, info,
                 step_index, exception=None, traceback_text="",
                 actions_so_far=None, max_score_seen=0.0, frames=None):
        self.env = env
        self.obs_before = obs_before
        self.action = action
        self.obs_after = obs_after
        self.reward = reward
        self.done = done
        self.info = info or {}
        self.step_index = step_index
        self.exception = exception
        self.traceback_text = traceback_text
        self.actions_so_far = actions_so_far or []
        self.max_score_seen = max_score_seen
        self.frames = frames or []


class Detector(ABC):
    name = "detector"
    kind = "unknown"

    @abstractmethod
    def check(self, ctx):
        """Return a Finding or None."""

    def describe(self):
        return (self.__class__.__doc__ or self.name).strip().splitlines()[0]
