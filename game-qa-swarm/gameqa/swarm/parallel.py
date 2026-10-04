"""Parallel swarm fan-out.

Workers receive (seed, bot_name, max_steps, bug_flags) and build their own
environment internally, so nothing unpicklable crosses the boundary and the
planted-bug flags stay consistent even on Windows, where processes are
spawned rather than forked.

All file writes happen in the parent, so there are never concurrent writes.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

from ..agents.base import BOT_NAMES
from ..game.bugs import BUG_FLAGS
from ..reports.store import new_run_id
from .runner import run_episode


def _apply_flags(flags):
    BUG_FLAGS.clear()
    BUG_FLAGS.update(flags)


def _worker(job):
    seed, bot_name, max_steps, flags = job
    _apply_flags(flags)
    return run_episode(seed, bot_name, max_steps)


def build_jobs(episodes_per_bot, bots, max_steps, seed_base, flags):
    jobs = []
    seed = int(seed_base)
    for bot_name in bots:
        for _ in range(int(episodes_per_bot)):
            jobs.append((seed, bot_name, int(max_steps), dict(flags)))
            seed += 1
    return jobs


def run_swarm(episodes_per_bot=20, bots=None, max_steps=300, workers=None,
              seed_base=1000, bug_flags=None, progress=None):
    """Run the swarm and return an aggregate, picklable result dict."""
    bots = list(bots or BOT_NAMES)
    flags = dict(bug_flags if bug_flags is not None else BUG_FLAGS)
    jobs = build_jobs(episodes_per_bot, bots, max_steps, seed_base, flags)

    if workers is None:
        workers = max(1, min(len(jobs), (os.cpu_count() or 2)))
    workers = int(workers)

    started = time.time()
    results = []
    if workers > 1 and len(jobs) > 1:
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for index, result in enumerate(pool.map(_worker, jobs,
                                                        chunksize=4)):
                    results.append(result)
                    if progress:
                        progress(index + 1, len(jobs))
        except (OSError, RuntimeError, ImportError):
            # Fall back to serial rather than failing on stage.
            results = []
            _apply_flags(flags)
            for index, job in enumerate(jobs):
                results.append(run_episode(job[0], job[1], job[2]))
                if progress:
                    progress(index + 1, len(jobs))
    else:
        _apply_flags(flags)
        for index, job in enumerate(jobs):
            results.append(run_episode(job[0], job[1], job[2]))
            if progress:
                progress(index + 1, len(jobs))

    duration = time.time() - started

    findings = []
    signature_counts = {}
    per_bot = {}
    for result in results:
        stats = per_bot.setdefault(
            result["bot"],
            {"episodes": 0, "steps": 0, "wins": 0, "crashes": 0,
             "episodes_with_findings": 0},
        )
        stats["episodes"] += 1
        stats["steps"] += result["steps"]
        stats["wins"] += 1 if result["won"] else 0
        stats["crashes"] += 1 if result["crashed"] else 0
        if result["findings"]:
            stats["episodes_with_findings"] += 1
        for finding in result["findings"]:
            enriched = dict(finding)
            enriched["seed"] = result["seed"]
            enriched["bot"] = result["bot"]
            enriched["map_id"] = result["map_id"]
            findings.append(enriched)
            signature_counts[finding["signature"]] = (
                signature_counts.get(finding["signature"], 0) + 1
            )

    return {
        "run_id": new_run_id(),
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_s": round(duration, 3),
        "workers": workers,
        "max_steps": int(max_steps),
        "seed_base": int(seed_base),
        "bug_flags": flags,
        "episodes": len(results),
        "steps": sum(r["steps"] for r in results),
        "wins": sum(1 for r in results if r["won"]),
        "crashes": sum(1 for r in results if r["crashed"]),
        "episodes_with_findings": sum(1 for r in results if r["findings"]),
        "unique_signatures": len(signature_counts),
        "signature_counts": signature_counts,
        "per_bot": per_bot,
        "findings": findings,
    }
