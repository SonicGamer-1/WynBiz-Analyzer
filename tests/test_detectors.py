"""Unit tests for the four detectors, dedupe signatures and report merging."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gameqa.detectors import make_detectors                    # noqa: E402
from gameqa.detectors.base import DetectContext                # noqa: E402
from gameqa.detectors.crash import CrashDetector               # noqa: E402
from gameqa.detectors.exploit import ExploitDetector           # noqa: E402
from gameqa.detectors.map_hole import MapHoleDetector          # noqa: E402
from gameqa.detectors.softlock import SoftlockDetector         # noqa: E402
from gameqa.game.bugs import reset_all                         # noqa: E402
from gameqa.game.grid_game import GridGame                     # noqa: E402
from gameqa.game.maps import MAP_HOLE_AT                       # noqa: E402
from gameqa.game.pathing import (                              # noqa: E402
    door_approach, goal_reachable, reachable_set,
)
from gameqa.reports.schema import BugReport                    # noqa: E402
from gameqa.reports.signature import kind_of, safe_filename    # noqa: E402


def _ctx(env, obs_before, obs_after, exception=None, tb="", action="WAIT",
         step_index=0):
    return DetectContext(
        env=env, obs_before=obs_before, action=action, obs_after=obs_after,
        reward=0.0, done=False, info={}, step_index=step_index,
        exception=exception, traceback_text=tb,
    )


# ------------------------------------------------------------------- crash

def test_crash_detector_fires_on_exception():
    env = GridGame()
    obs = env.reset(0)
    try:
        raise IndexError("list index out of range")
    except IndexError as exc:
        ctx = _ctx(env, obs, None, exception=exc, action="USE")
    finding = CrashDetector().check(ctx)
    assert finding is not None
    assert finding.kind == "crash"
    assert finding.severity_hint == "critical"
    assert finding.signature.startswith("crash|IndexError|")


def test_crash_detector_silent_without_exception():
    env = GridGame()
    obs = env.reset(0)
    assert CrashDetector().check(_ctx(env, obs, obs)) is None


def test_crash_signature_is_seed_independent():
    """Same fault site from different runs must merge into one report."""
    env = GridGame()
    signatures = set()
    for _ in range(3):
        obs = env.reset(0)
        try:
            raise IndexError("boom")
        except IndexError as exc:
            finding = CrashDetector().check(
                _ctx(env, obs, None, exception=exc, action="USE"))
        signatures.add(finding.signature)
    assert len(signatures) == 1


# --------------------------------------------------------------- map hole

def test_map_hole_fires_inside_a_wall():
    reset_all(True)
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["pos"] = (4, 7)          # a wall tile in MAP_RAW
    finding = MapHoleDetector().check(_ctx(env, before, after, action="RIGHT"))
    assert finding is not None
    assert finding.signature == "map_hole|inside_wall|4|7"


def test_map_hole_fires_out_of_bounds():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["pos"] = (-1, 3)
    finding = MapHoleDetector().check(_ctx(env, before, after, action="LEFT"))
    assert finding is not None
    assert "out_of_bounds" in finding.signature


def test_map_hole_silent_on_floor():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["pos"] = (2, 1)          # plain floor
    assert MapHoleDetector().check(_ctx(env, before, after)) is None


# ---------------------------------------------------------------- exploit

def test_exploit_fires_on_coin_overflow():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["coins_collected"] = env.total_coins + 1
    after["score"] = (env.total_coins + 1) * 10
    finding = ExploitDetector().check(_ctx(env, before, after, action="PICKUP"))
    assert finding is not None
    assert finding.signature.startswith("exploit|")


def test_exploit_fires_on_score_overflow():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["coins_collected"] = env.total_coins
    after["score"] = env.max_legal_score + 1
    finding = ExploitDetector().check(_ctx(env, before, after, action="PICKUP"))
    assert finding is not None
    assert finding.kind == "exploit"


def test_exploit_silent_on_legal_play():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["coins_collected"] = 2
    after["score"] = 20
    assert ExploitDetector().check(_ctx(env, before, after)) is None


# --------------------------------------------------------------- softlock

def test_softlock_fires_when_key_destroyed():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["key_destroyed"] = True
    after["key_pos"] = None
    after["inventory"] = []
    after["door_open"] = False
    after["done"] = False
    after["won"] = False
    finding = SoftlockDetector().check(_ctx(env, before, after, action="DROP"))
    assert finding is not None
    assert finding.severity_hint == "critical"
    assert "key_destroyed" in finding.signature


def test_softlock_silent_while_key_is_obtainable():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["key_destroyed"] = False
    after["key_pos"] = env.entities["key"]
    after["inventory"] = []
    after["door_open"] = False
    after["done"] = False
    after["won"] = False
    assert SoftlockDetector().check(_ctx(env, before, after)) is None


def test_softlock_silent_when_carrying_the_key():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["key_destroyed"] = False
    after["key_pos"] = None
    after["inventory"] = ["key"]
    after["door_open"] = False
    after["done"] = False
    after["won"] = False
    assert SoftlockDetector().check(_ctx(env, before, after)) is None


def test_softlock_silent_after_a_win():
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["done"] = True
    after["won"] = True
    after["key_destroyed"] = True
    assert SoftlockDetector().check(_ctx(env, before, after)) is None


def test_softlock_silent_once_the_door_is_open():
    """Regression: spending the key on the door is progress, not a softlock.

    After USE, the inventory is empty and key_pos is None, so an oracle that
    demands an obtainable key would report the level uncompletable one step
    before the player wins it.
    """
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["door_open"] = True
    after["inventory"] = []          # the key was spent on the door
    after["key_pos"] = None
    after["key_destroyed"] = False
    after["pos"] = env.entities["door"]
    after["done"] = False
    after["won"] = False
    assert SoftlockDetector().check(_ctx(env, before, after)) is None


def test_goal_reachable_honours_an_open_door():
    """The oracle must not require a key for a door that is already open."""
    env = GridGame()
    door = env.entities["door"]
    goal = env.entities["goal"]
    approach = door_approach(door)

    assert goal_reachable(pos=approach, inventory=[], key_pos=None,
                          door_pos=door, door_open=True, goal_pos=goal)
    # Same state with the door still shut and no key anywhere: genuinely stuck.
    assert not goal_reachable(pos=approach, inventory=[], key_pos=None,
                              door_pos=door, door_open=False, goal_pos=goal)


def test_softlock_silent_inside_the_map_hole():
    """Regression: standing in a wall is the map hole's finding, not a softlock.

    The map-hole bug lets the player onto (4, 7). An oracle that floods from
    that tile alone concludes nothing is reachable and reports a critical
    softlock on top of the map hole -- but the player can step straight back
    onto floor and still finish the level.
    """
    env = GridGame()
    before = env.reset(0)
    after = dict(before)
    after["pos"] = MAP_HOLE_AT           # inside a wall, key untouched
    after["key_destroyed"] = False
    after["key_pos"] = env.entities["key"]
    after["inventory"] = []
    after["door_open"] = False
    after["done"] = False
    after["won"] = False
    assert SoftlockDetector().check(_ctx(env, before, after)) is None
    # The map-hole detector still owns this exact state.
    assert MapHoleDetector().check(_ctx(env, before, after)) is not None


def test_reachable_set_escapes_an_off_map_start():
    """An off-map tile with walkable neighbours is not a prison."""
    env = GridGame()
    door = env.entities["door"]
    free = reachable_set(MAP_HOLE_AT, door, door_passable=False)
    assert MAP_HOLE_AT not in free       # the wall itself is not walkable
    assert env.entities["goal"] not in free   # goal is behind the locked door
    assert (3, 7) in free and (5, 7) in free  # but the floor either side is
    # Walled in with no exit at all: genuinely stuck, so it stays degenerate.
    assert reachable_set((0, 0), door, door_passable=False) == {(0, 0)}


# ------------------------------------------------------- signatures/merge

def test_safe_filename_is_stable_and_safe():
    signature = "crash|IndexError|grid_game.py:240:_do_use"
    assert safe_filename(signature) == safe_filename(signature)
    assert all(ch.isalnum() or ch in "._-" for ch in safe_filename(signature))
    assert kind_of(signature) == "crash"


def test_merge_keeps_the_shortest_repro():
    long_one = BugReport(signature="s", kind="crash", summary="x",
                         seed=1, actions=["A"] * 50, step_index=49)
    short_one = BugReport(signature="s", kind="crash", summary="x",
                          seed=2, actions=["A"] * 5, step_index=4)
    merged = long_one.merge(short_one)
    assert merged.occurrences == 2
    assert len(merged.actions) == 5
    assert merged.seed == 2


def test_merge_keeps_the_worse_severity():
    medium = BugReport(signature="s", kind="exploit", summary="x",
                       severity="medium", actions=["A"])
    critical = BugReport(signature="s", kind="exploit", summary="x",
                         severity="critical", actions=["A", "B"])
    assert medium.merge(critical).severity == "critical"


def test_all_detectors_have_distinct_kinds():
    kinds = [d.kind for d in make_detectors()]
    assert len(kinds) == len(set(kinds)) == 4


def test_report_round_trips_through_dict():
    report = BugReport(signature="s|1", kind="crash", summary="x",
                       actions=["UP", "DOWN"], detail={"a": 1})
    clone = BugReport.from_dict(report.to_dict())
    assert clone.to_dict() == report.to_dict()


def _run_all():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    failures = []
    for name, func in tests:
        try:
            func()
            print("  ok    %s" % name)
        except AssertionError as exc:
            failures.append(name)
            print("  FAIL  %s: %s" % (name, exc))
        except Exception as exc:                          # noqa: BLE001
            failures.append(name)
            print("  ERROR %s: %s: %s" % (name, type(exc).__name__, exc))
    print("")
    print("%d/%d passed" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())