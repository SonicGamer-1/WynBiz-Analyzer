"""Crash detector: any exception escaping env.step() is a bug.

The signature is the exception type plus the innermost frame inside the game
package. That is what makes 40 identical crashes merge into one report while a
genuinely different crash site stays separate.
"""
from __future__ import annotations

import os
import traceback

from .base import Detector, Finding

_GAME_MARK = os.path.join("gameqa", "game")


def _fault_site(tb_text):
    """Innermost `gameqa/game/...` frame as file:line:func, else the last frame."""
    frames = []
    for line in tb_text.splitlines():
        line = line.strip()
        if line.startswith('File "'):
            frames.append(line)
    if not frames:
        return "unknown"
    chosen = None
    for frame in frames:
        if _GAME_MARK in frame.replace("/", os.sep) or "gameqa\\game" in frame \
                or "gameqa/game" in frame:
            chosen = frame
    if chosen is None:
        chosen = frames[-1]
    # File "path", line N, in func
    try:
        path_part, rest = chosen.split('", line ', 1)
        path = path_part.split('"', 1)[1]
        lineno, func = rest.split(", in ", 1)
        return "%s:%s:%s" % (os.path.basename(path), lineno.strip(), func.strip())
    except ValueError:
        return chosen


class CrashDetector(Detector):
    """An exception escaped env.step()."""

    name = "crash"
    kind = "crash"

    def check(self, ctx):
        if ctx.exception is None:
            return None
        exc = ctx.exception
        exc_type = type(exc).__name__
        tb_text = ctx.traceback_text or "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        site = _fault_site(tb_text)
        return Finding(
            kind=self.kind,
            signature="crash|%s|%s" % (exc_type, site),
            summary="%s at %s" % (exc_type, site),
            severity_hint="critical",
            step_index=ctx.step_index,
            detail={
                "exception_type": exc_type,
                "message": str(exc),
                "fault_site": site,
                "last_action": str(ctx.action),
                "traceback": tb_text[-4000:],
            },
        )
