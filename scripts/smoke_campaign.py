"""Smoke test: full campaign flow over Socket.IO.

Prereq: server running on :8910.

Flow: chaos bag info → campaign_new → setup ch.1 (expert bag=18 tokens)
→ resign (settlement) → campaign_state (xp settled) → campaign_upgrade
(xp insufficient error expected) → campaign_continue(advance) → setup ch.2.
"""

import asyncio

import socketio

URL = "http://localhost:8910"


async def main() -> None:
    sio = socketio.AsyncClient()
    got: dict = {}

    @sio.on("welcome")
    async def _w(data):
        got["welcome"] = data

    @sio.on("card_list")
    async def _cl(data):
        got["card_list"] = data

    @sio.on("campaign_state")
    async def _cs(data):
        got.setdefault("campaign_states", []).append(data)

    @sio.on("campaign_list")
    async def _clist(data):
        got["campaign_list"] = data

    @sio.on("chaos_bag_info")
    async def _cbi(data):
        got["bag"] = data

    @sio.on("state_update")
    async def _su(data):
        got.setdefault("states", []).append(data["state"])

    @sio.on("room_update")
    async def _ru(data):
        got["room"] = data

    @sio.on("error")
    async def _err(data):
        got.setdefault("errors", []).append(data)

    await sio.connect(URL)

    async def wait(key: str, timeout: float = 5.0):
        for _ in range(int(timeout * 10)):
            if key in got:
                return got[key]
            await asyncio.sleep(0.1)
        raise AssertionError(f"timeout waiting for {key}")

    # 1. chaos bag info (expert core = 18 tokens)
    await sio.emit("get_chaos_bag_info", {"campaign": "core", "difficulty": "expert"})
    bag = await wait("bag")
    assert bag["total"] == 18, bag
    assert bag["tokens"]["-8"] == 1
    print("✓ chaos bag info (expert=18 tokens)")

    # 2. card list for daisy (need a 30-card deck for campaign_new)
    await sio.emit("list_cards", {"investigator_id": "daisy_walker", "xp": 0})
    cl = await wait("card_list")
    presets = cl.get("presets") or []
    assert presets, "no presets"
    deck = list(presets[0]["cards"])
    assert len(deck) == 30, len(deck)
    print(f"✓ card list (preset {presets[0].get('id')}, 30 cards)")

    # 3. campaign_new
    await sio.emit("campaign_new", {
        "campaign_id": "core",
        "investigator_id": "daisy_walker",
        "difficulty": "expert",
        "deck_cards": deck,
    })
    camp = (await wait("campaign_states"))[-1]
    save_id = camp["save_id"]
    assert camp["xp"] == 0 and camp["scenario_index"] == 0
    assert camp["current_scenario_id"] == "the_gathering"
    print(f"✓ campaign_new (save_id={save_id})")

    # 4. start chapter 1
    await sio.emit("create_room", {})
    await wait("room")
    await sio.emit("setup_game", {
        "investigator_id": "daisy_walker",
        "save_id": save_id,
    })
    state = (await wait("states"))[-1]
    assert state, "empty state"
    print("✓ chapter 1 started (the_gathering, expert)")

    # 5. resign → settlement
    await sio.emit("player_action", {"action": "RESIGN"})
    await asyncio.sleep(1.0)
    await sio.emit("campaign_state", {})
    await asyncio.sleep(0.5)
    camp2 = got["campaign_states"][-1]
    assert camp2 is not None, "campaign_state None after game over"
    print(f"✓ resigned; settlement xp={camp2['xp']} xp_earned={camp2['xp_earned']} "
          f"trauma={camp2['trauma_physical']}/{camp2['trauma_mental']}")

    # 6. upgrade attempt (should fail if cost > xp; xp likely 0)
    if camp2["xp"] == 0:
        new_deck = list(deck)
        new_deck[0] = "magnifying_glass_lv1"  # cost 1 → insufficient
        await sio.emit("campaign_upgrade", {"save_id": save_id, "new_deck": new_deck})
        await asyncio.sleep(0.5)
        errs = got.get("errors", [])
        assert any(e.get("code") == "xp_insufficient" for e in errs), errs
        print("✓ upgrade correctly rejected (xp_insufficient)")
    else:
        new_deck = list(deck)
        removed = new_deck.pop()
        await sio.emit("campaign_upgrade", {"save_id": save_id, "new_deck": new_deck + [removed]})
        await asyncio.sleep(0.5)
        print("✓ no-op upgrade accepted")

    # 7. advance to chapter 2
    await sio.emit("campaign_continue", {"save_id": save_id, "advance": True})
    await asyncio.sleep(0.5)
    camp3 = got["campaign_states"][-1]
    assert camp3["scenario_index"] == 1, camp3["scenario_index"]
    assert camp3["current_scenario_id"] == "the_midnight_masks"
    print("✓ advanced to chapter 2 (the_midnight_masks)")

    # 8. campaign_list shows the save
    await sio.emit("campaign_list", {})
    saves = (await wait("campaign_list"))["campaigns"]
    entry = next(s for s in saves if s["save_id"] == save_id)
    assert entry["scenario_index"] == 1 and entry["difficulty"] == "expert"
    print(f"✓ campaign_list ({len(saves)} saves, ours at ch.2)")

    # 9. start chapter 2 in a fresh room
    await sio.emit("create_room", {})
    await asyncio.sleep(0.5)
    await sio.emit("setup_game", {
        "investigator_id": "daisy_walker",
        "save_id": save_id,
    })
    await asyncio.sleep(1.5)
    st2 = got["states"][-1]
    assert st2, "no state for chapter 2"
    print("✓ chapter 2 started")

    await sio.disconnect()
    print("\n🎉 campaign smoke test passed")


if __name__ == "__main__":
    asyncio.run(main())
