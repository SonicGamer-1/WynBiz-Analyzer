"""One episode: environment + bot + detectors + a reproducible action trace.

Every action the bot sends is recorded, including the junk inputs from the
chaos tester, and every recording is *replayable*: `label_action` and
`parse_action_label` are exact inverses for anything a bot can produce.
"""
from __future__ import annotations

import traceback

from ..agents.base import make_bot
from ..detectors import make_detectors
from ..detectors.base import DetectContext
from ..game.actions import INVALID_INPUTS, Action, normalise
from ..game.grid_game import GridGame


def label_action(action):
    """Stable, JSON-safe, replayable label for any bot output."""
    if isinstance(action, Action):
        return action.value
    if isinstance(action, str):
        return "STR:%s" % action
    for i, candidate in enumerate(INVALID_INPUTS):
        if candidate is action:
            return "JUNK:%d" % i
    return "JUNK:%s" % type(action).__name__


def parse_action_label(label):
    """Inverse of label_action."""
    if not isinstance(label, str):
        return label
    if label.startswith("JUNK:"):
        rest = label[5:]
        if rest.isdigit():
            idx = int(rest)
            if 0 <= idx < len(INVALID_INPUTS):
                return INVALID_INPUTS[idx]
        return object()
    if label.startswith("STR:"):
        return label[4:]
    act = normalise(label)
    return act if act is not None else label


def run_episode(seed, bot_name, max_steps=300):
    """Play one episode and return a plain dict of results.

    Returns only picklable data so it can cross a process boundary.
    """
    env = GridGame()
    obs = env.reset(int(seed))
    bot = make_bot(bot_name)
    # Derive the bot's own rng seed from its name with a stable hash. Python's
    # built-in hash() is salted per process, which would silently make worker
    # processes disagree with the parent and break repro replay.
    offset = sum(ord(ch) for ch in str(bot_name)) * 977
    bot.reset(int(seed) + offset)
    detectors = make_detectors()

    actions = []
    findings = []
    seen = set()
    won = False
    score = 0.0
    crashed = False
    steps = 0

    for i in range(int(max_steps)):
        action = bot.act(obs)
        actions.append(label_action(action))
        steps = i + 1

        exc = None
        tb_text = ""
        try:
            obs_after, reward, done, info = env.step(action)
        except Exception as caught:                     # noqa: BLE001
            exc = caught
            tb_text = traceback.format_exc()
            obs_after = None
            reward = 0.0
            done = True
            info = {"reason": "exception"}

        ctx = DetectContext(
            env=env,
            obs_before=obs,
            action=label_action(action),
            obs_after=obs_after,
            reward=reward,
            done=done,
            info=info,
            step_index=i,
            exception=exc,
            traceback_text=tb_text,
            actions_so_far=list(actions),
        )
        for detector in detectors:
            finding = detector.check(ctx)
            if finding is None or finding.signature in seen:
                continue
            seen.add(finding.signature)
            payload = finding.to_dict()
            payload["actions"] = list(actions)
            findings.append(payload)

        if exc is not None:
            crashed = True
            break
        obs = obs_after
        won = bool(obs.get("won"))
        score = float(obs.get("score", 0.0))
        if done:
            break

    return {
        "seed": int(seed),
        "bot": bot_name,
        "map_id": env.map_id,
        "steps": steps,
        "won": won,
        "crashed": crashed,
        "score": score,
        "actions": actions,
        "findings": findings,
    }


def run_script(seed, actions, max_steps=None):
    """Step a fixed action list through the game with detectors attached.

    Used for pinned repros, the `replay` command and fix verification. Returns
    the same shape as run_episode, with bot == "script".
    """
    env = GridGame()
    obs = env.reset(int(seed))
    detectors = make_detectors()

    labels = []
    findings = []
    seen = set()
    won = False
    score = 0.0
    crashed = False
    steps = 0
    limit = len(actions) if max_steps is None else min(len(actions), max_steps)

    for i in range(limit):
        raw = actions[i]
        action = parse_action_label(raw) if isinstance(raw, str) else raw
        label = raw if isinstance(raw, str) else label_action(raw)
        labels.append(label)
        steps = i + 1

        exc = None
        tb_text = ""
        try:
            obs_after, reward, done, info = env.step(action)
        except Exception as caught:                     # noqa: BLE001
            exc = caught
            tb_text = traceback.format_exc()
            obs_after = None
            reward = 0.0
            done = True
            info = {"reason": "exception"}

        ctx = DetectContext(
            env=env, obs_before=obs, action=label, obs_after=obs_after,
            reward=reward, done=done, info=info, step_index=i, exception=exc,
            traceback_text=tb_text, actions_so_far=list(labels),
        )
        for detector in detectors:
            finding = detector.check(ctx)
            if finding is None or finding.signature in seen:
                continue
            seen.add(finding.signature)
            payload = finding.to_dict()
            payload["actions"] = list(labels)
            findings.append(payload)

        if exc is not None:
            crashed = True
            break
        obs = obs_after
        won = bool(obs.get("won"))
        score = float(obs.get("score", 0.0))
        if done:
            break

    return {
        "seed": int(seed),
        "bot": "script",
        "map_id": env.map_id,
        "steps": steps,
        "won": won,
        "crashed": crashed,
        "score": score,
        "actions": labels,
        "findings": findings,
    }


def signatures_of(result):
    return [f["signature"] for f in result["findings"]]
