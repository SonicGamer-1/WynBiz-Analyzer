"""Bug report schema.

A report is a plain JSON-serialisable record. `actions` plus `seed` is the
repro: replaying them through a fresh GridGame reproduces the failure exactly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def severity_rank(sev):
    try:
        return SEVERITY_ORDER.index(str(sev).lower())
    except ValueError:
        return len(SEVERITY_ORDER)


@dataclass
class BugReport:
    signature: str
    kind: str
    summary: str
    map_id: str = "level_01"
    seed: int = 0
    bot: str = ""
    actions: list = field(default_factory=list)
    step_index: int = -1
    severity: str = "medium"
    title: str = ""
    status: str = "open"
    occurrences: int = 1
    episodes: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    triage: dict = field(default_factory=dict)
    repro_path: str = ""
    gif_path: str = ""
    first_seen: str = field(default_factory=_now)
    last_seen: str = field(default_factory=_now)
    verified_fixed: bool = False

    # ------------------------------------------------------------ serialise

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    # -------------------------------------------------------------- merging

    def merge(self, other):
        """Fold a duplicate finding into this report.

        Keeps the *shortest* action list: a shorter repro is far easier to
        show on stage and faster to replay.
        """
        self.occurrences += other.occurrences
        for ep in other.episodes:
            if ep not in self.episodes:
                self.episodes.append(ep)
        if len(other.actions) < len(self.actions):
            self.actions = list(other.actions)
            self.seed = other.seed
            self.bot = other.bot
            self.step_index = other.step_index
            self.detail = dict(other.detail)
        if severity_rank(other.severity) < severity_rank(self.severity):
            self.severity = other.severity
        self.last_seen = other.last_seen
        return self

    # ---------------------------------------------------------------- repro

    def repro_text(self):
        lines = [
            "# Repro for %s" % (self.title or self.signature),
            "signature: %s" % self.signature,
            "kind:      %s" % self.kind,
            "severity:  %s" % self.severity,
            "map:       %s" % self.map_id,
            "seed:      %d" % self.seed,
            "bot:       %s" % self.bot,
            "step:      %d of %d" % (self.step_index, len(self.actions)),
            "",
            "# Replay with:",
            "#   python -m gameqa.cli replay --seed %d --actions \"%s\""
            % (self.seed, ",".join(self.actions)),
            "",
            "actions:",
        ]
        for i, action in enumerate(self.actions):
            marker = "   <== failure" if i == self.step_index else ""
            lines.append("  %3d  %s%s" % (i, action, marker))
        lines.append("")
        lines.append("detail:")
        lines.append(json.dumps(self.detail, indent=2, sort_keys=True))
        return "\n".join(lines)
