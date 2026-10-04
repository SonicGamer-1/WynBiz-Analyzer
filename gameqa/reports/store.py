"""Artifact storage: runs, bug reports, repro files, replay GIFs.

All writes happen in the parent process; workers only return findings, so
there are never concurrent writes to the same file.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from .schema import BugReport, severity_rank
from .signature import safe_filename

DEFAULT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "artifacts",
)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(prefix="run"):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return "%s-%s-%d" % (prefix, stamp, os.getpid())


class BugStore:
    def __init__(self, root=None):
        self.root = root or DEFAULT_ROOT
        self.bugs_dir = os.path.join(self.root, "bugs")
        self.repro_dir = os.path.join(self.root, "repros")
        self.replay_dir = os.path.join(self.root, "replays")
        self.run_dir = os.path.join(self.root, "runs")
        self.cache_dir = os.path.join(self.root, "triage_cache")
        for d in (self.bugs_dir, self.repro_dir, self.replay_dir,
                  self.run_dir, self.cache_dir):
            os.makedirs(d, exist_ok=True)

    # ------------------------------------------------------------- reports

    def path_for(self, signature):
        return os.path.join(self.bugs_dir, safe_filename(signature) + ".json")

    def get(self, signature):
        path = self.path_for(signature)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return BugReport.from_dict(json.load(fh))

    def save(self, report):
        path = self.path_for(report.signature)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report.to_json())
        repro = os.path.join(self.repro_dir,
                             safe_filename(report.signature) + ".txt")
        with open(repro, "w", encoding="utf-8") as fh:
            fh.write(report.repro_text())
        report.repro_path = repro
        return path

    def record(self, finding, seed, bot, actions, episode_id, map_id="level_01"):
        """Merge a finding into the store and return the resulting report."""
        incoming = BugReport(
            signature=finding.signature,
            kind=finding.kind,
            summary=finding.summary,
            map_id=map_id,
            seed=int(seed),
            bot=bot,
            actions=[str(a) for a in actions],
            step_index=finding.step_index,
            severity=finding.severity_hint,
            title=finding.summary,
            occurrences=1,
            episodes=[episode_id],
            detail=dict(finding.detail),
            last_seen=_now(),
        )
        existing = self.get(incoming.signature)
        if existing is None:
            report = incoming
            report.first_seen = incoming.first_seen
        else:
            report = existing.merge(incoming)
        self.save(report)
        return report

    def all_reports(self):
        reports = []
        if not os.path.isdir(self.bugs_dir):
            return reports
        for name in sorted(os.listdir(self.bugs_dir)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.bugs_dir, name), "r",
                          encoding="utf-8") as fh:
                    reports.append(BugReport.from_dict(json.load(fh)))
            except (ValueError, OSError):
                continue
        reports.sort(key=lambda r: (severity_rank(r.severity), -r.occurrences))
        return reports

    def signatures(self):
        return [r.signature for r in self.all_reports()]

    def set_status(self, signature, status, verified_fixed=None):
        report = self.get(signature)
        if report is None:
            return None
        report.status = status
        if verified_fixed is not None:
            report.verified_fixed = bool(verified_fixed)
        self.save(report)
        return report

    def clear_reports(self):
        for d in (self.bugs_dir, self.repro_dir):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)

    # ---------------------------------------------------------------- runs

    def save_run(self, run_id, payload):
        path = os.path.join(self.run_dir, run_id + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        return path

    def latest_runs(self, limit=20):
        runs = []
        for name in sorted(os.listdir(self.run_dir), reverse=True):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.run_dir, name), "r",
                          encoding="utf-8") as fh:
                    runs.append(json.load(fh))
            except (ValueError, OSError):
                continue
            if len(runs) >= limit:
                break
        return runs

    # ------------------------------------------------------------- replays

    def gif_path(self, signature):
        return os.path.join(self.replay_dir, safe_filename(signature) + ".gif")
