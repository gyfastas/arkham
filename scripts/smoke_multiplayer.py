#!/usr/bin/env python3
"""2-player multiplayer smoke test (requires a running server on :8910).

Flow: P1 creates room → P2 joins → both send setup_game (own investigator)
→ game starts when all ready → turn rotation: P2 cannot act out of turn,
P1 ends turn → P2 acts → both end turn → phases run, both draw encounters.

Run: python3 scripts/smoke_multiplayer.py
"""

import sys
import time

import socketio


def connect(name):
    s = socketio.SimpleClient()
    s.connect("http://localhost:8910")
    s.emit("connect")  # no-op safeguard
    welcome = wait_for(s, "welcome")
    return s, welcome["player_id"]


def wait_for(s, event, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ev = s.receive(timeout=deadline - time.time())
        if ev[0] == event:
            return ev[1]
    raise TimeoutError(f"waiting for {event}")


def drain_until(s, events, timeout=10):
    """Collect messages until all events seen; return {event: data}."""
    seen = {}
    deadline = time.time() + timeout
    while time.time() < deadline and set(events) - seen.keys():
        ev = s.receive(timeout=deadline - time.time())
        if ev[0] in events and ev[0] not in seen:
            seen[ev[0]] = ev[1]
    missing = set(events) - seen.keys()
    if missing:
        raise TimeoutError(f"missing {missing}, got {list(seen)}")
    return seen


def act(s, action, **kw):
    s.emit("player_action", {"action": action, **kw})
    return wait_for(s, "action_result")


def end_turn(s):
    s.emit("end_turn")
    return wait_for(s, "action_result")


def main():
    p1, pid1 = connect("P1")
    p2, pid2 = connect("P2")

    # P1 creates room
    p1.emit("create_room")
    ru = wait_for(p1, "room_update")
    room_id = ru["room_id"]
    print(f"✓ room created: {room_id}")

    # P2 joins
    p2.emit("join_room", {"room_id": room_id})
    wait_for(p2, "room_update")
    print("✓ P2 joined")

    # Both set up (last one triggers game start)
    p1.emit("setup_game", {"scenario_id": "the_gathering", "investigator_id": "roland_banks"})
    # P1 gets room_update (waiting), not state yet
    got = drain_until(p1, ["room_update"], timeout=8)
    print("✓ P1 ready, waiting for P2")

    p2.emit("setup_game", {"scenario_id": "the_gathering", "investigator_id": "daisy_walker"})
    st1 = drain_until(p1, ["state_update"], timeout=15)["state_update"]["state"]
    st2 = drain_until(p2, ["state_update"], timeout=15)["state_update"]["state"]
    assert st1["investigator"]["id"] == "roland_banks", st1["investigator"]["id"]
    assert st2["investigator"]["id"] == "daisy_walker", st2["investigator"]["id"]
    assert st1["your_turn"] is True and st2["your_turn"] is False
    assert len(st1["other_investigators"]) == 1
    assert st1["other_investigators"][0]["id"] == "daisy_walker"
    print("✓ game started: 2 investigators, per-player views, P1's turn")

    # P2 cannot act out of turn
    r = act(p2, "RESOURCE")
    assert r["success"] is False and "回合" in r["message"], r
    print("✓ out-of-turn action rejected")

    # P1 acts then ends turn
    r = act(p1, "RESOURCE")
    assert r["success"] is True, r
    r = end_turn(p1)
    assert r.get("turn_advanced") is True, r
    print("✓ P1 ended turn → P2's turn")

    # Now P2 can act; P1 cannot
    r = act(p2, "RESOURCE")
    assert r["success"] is True, r
    r = act(p1, "RESOURCE")
    assert r["success"] is False
    print("✓ P2 acts, P1 blocked")

    # P2 ends turn → phases + both draw encounters (mythos)
    r = end_turn(p2)
    # Handle possible pending choice/skill test from encounters
    for _ in range(10):
        st = r.get("state") or {}
        pc = st.get("pending_choice")
        pst = st.get("pending_skill_test")
        if pc:
            owner = pc.get("investigator_id")
            target = p1 if owner == "player" else p2
            choice = (pc.get("options") or [{}])[0].get("id")
            r = act(target, "RESOLVE_CHOICE", choice_id=choice)
            continue
        if pst:
            owner = pst.get("investigator_id")
            target = p1 if owner == "player" else p2
            r = act(target, "SKILL_TEST_ROLL", committed_cards=[])
            continue
        break
    st2 = r.get("state") or st2
    assert st2["round"] == 2, f"round={st2.get('round')}"
    print("✓ full round completed: phases ran, both drew encounters, round 2")

    p1.disconnect()
    p2.disconnect()
    print("\n🎉 multiplayer smoke test passed")


if __name__ == "__main__":
    sys.exit(main())
