"""Each planted bug MUST be found from a fixed, verified repro.

Run this before going on stage:

    python tests/test_planted_bugs.py
    python -m pytest tests/ -q

The random swarm is showmanship; these pinned repros are the guarantee. They
also assert the *inverse*: with a bug disabled, its repro must stop producing
the finding -- exactly what `cli.py verify` checks after a Cline fix.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gameqa.game.bugs import PLANTED_BUGS, disable, enable, reset_all  # noqa: E402
from gameqa.game.grid_game import GridGame                             # noqa: E402
from gameqa.game.maps import MAP_HOLE_AT, is_wall_in_raw               # noqa: E402
from gameqa.game.pathing import goal_reachable                         # noqa: E402
from gameqa.repros import BUILDERS, find_seed                          # noqa: E402
from gameqa.swarm.runner import run_script                             # noqa: E402

SEARCH = range(0, 120)


def _signature_of(name, seed, actions):
    prefix = PLANTED_BUGS[name][1] + "|"
    result = run_script(seed, actions)
    return next((f["signature"] for f in result["findings"]
                 if f["signature"].startswith(prefix)), None)


# ------------------------------------------------------- bugs are findable

def test_softlock_is_found():
    reset_all(True)
    actions = BUILDERS["softlock"]()
    seed = find_seed("softlock", actions, SEARCH)
    assert seed is not None, "softlock repro never fired"
    signature = _signature_of("softlock", seed, actions)
    assert signature and signature.startswith("softlock|")
    assert "key_destroyed" in signature


def test_map_hole_is_found():
    reset_all(True)
    actions = BUILDERS["map_hole"]()
    seed = find_seed("map_hole", actions, SEARCH)
    assert seed is not None, "map hole repro never fired"
    signature = _signature_of("map_hole", seed, actions)
    assert signature and signature.startswith("map_hole|")
    assert "%d|%d" % MAP_HOLE_AT in signature


def test_exploit_is_found():
    reset_all(True)
    actions = BUILDERS["exploit"]()
    seed = find_seed("exploit", actions, SEARCH)
    assert seed is not None, "exploit repro never fired"
    signature = _signature_of("exploit", seed, actions)
    assert signature and signature.startswith("exploit|")


def test_crash_is_found():
    reset_all(True)
    actions = BUILDERS["crash"]()
    seed = find_seed("crash", actions, SEARCH)
    assert seed is not None, "crash repro never fired"
    result = run_script(seed, actions)
    assert result["crashed"], "crash repro did not raise"
    signature = _signature_of("crash", seed, actions)
    assert signature and signature.startswith("crash|")
    assert "IndexError" in signature


# --------------------------------------------- bugs disappear when disabled

def test_disabling_a_bug_clears_its_finding():
    for name in PLANTED_BUGS:
        reset_all(True)
        actions = BUILDERS[name]()
        seed = find_seed(name, actions, SEARCH)
        assert seed is not None, "%s repro never fired" % name
        try:
            disable(name)
            assert _signature_of(name, seed, actions) is None, (
                "%s still fires with its bug disabled" % name)
        finally:
            enable(name)
    reset_all(True)


def test_repros_are_replayable():
    """A repro run twice gives identical findings."""
    reset_all(True)
    for name in PLANTED_BUGS:
        actions = BUILDERS[name]()
        seed = find_seed(name, actions, SEARCH)
        assert seed is not None
        first = run_script(seed, actions)
        second = run_script(seed, actions)
        assert first["findings"] == second["findings"], (
            "%s repro is not deterministic" % name)
        assert first["actions"] == second["actions"]
    reset_all(True)


# ------------------------------------------------------------ map integrity

def test_map_hole_tile_really_is_a_wall():
    assert is_wall_in_raw(MAP_HOLE_AT), (
        "MAP_HOLE_AT must be a wall in MAP_RAW or the detector is meaningless")


def test_door_is_the_only_way_to_the_goal():
    """Without the key the goal must be unreachable, otherwise the softlock
    detector has nothing to prove."""
    env = GridGame()
    env.reset(0)
    ent = env.entities
    assert not goal_reachable(
        pos=ent["start"], inventory=[], key_pos=None,
        door_pos=ent["door"], door_open=False, goal_pos=ent["goal"],
    )
    assert goal_reachable(
        pos=ent["start"], inventory=[], key_pos=ent["key"],
        door_pos=ent["door"], door_open=False, goal_pos=ent["goal"],
    )
    assert goal_reachable(
        pos=ent["start"], inventory=["key"], key_pos=None,
        door_pos=ent["door"], door_open=False, goal_pos=ent["goal"],
    )


def _winning_script():
    from gameqa.game.actions import Action
    from gameqa.game.pathing import door_approach, route

    env = GridGame()
    ent = env.entities
    approach = door_approach(ent["door"])
    actions = list(route(ent["start"], ent["key"], ent["door"]) or [])
    actions.append(Action.PICKUP)
    actions += list(route(ent["key"], approach, ent["door"]) or [])
    actions.append(Action.USE)
    actions += list(route(approach, ent["goal"], ent["door"], True) or [])
    return actions


def test_level_is_completable_with_no_bugs():
    """The fixed game must actually be beatable, or 'the bug is gone' is empty.

    Patrolling enemies can block a step and desync a scripted route, so this
    searches a few seeds rather than assuming seed 0 works.
    """
    reset_all(False)
    try:
        actions = _winning_script()
        assert actions, "could not build a winning script"
        won = False
        for seed in range(0, 60):
            result = run_script(seed, actions)
            if result["won"]:
                assert result["score"] <= GridGame().max_legal_score
                won = True
                break
        assert won, "level not completable with all bugs disabled"
    finally:
        reset_all(True)


# -------------------------------------------------------------- swarm smoke

def test_swarm_finds_all_four_kinds():
    from gameqa.swarm.parallel import run_swarm

    reset_all(True)
    swarm = run_swarm(episodes_per_bot=12, max_steps=250, workers=1,
                      seed_base=7000)
    kinds = {sig.split("|", 1)[0] for sig in swarm["signature_counts"]}
    missing = {v[1] for v in PLANTED_BUGS.values()} - kinds
    assert not missing, "swarm missed %s; pinned repros still cover them" % missing


# ------------------------------------------------------------------ runner

def _run_all():
    tests = [(name, obj) for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
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
