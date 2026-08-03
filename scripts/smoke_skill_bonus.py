"""Verify skill_bonuses in serialized state after playing Magnifying Glass."""

import asyncio
import sys

import socketio

URL = "http://localhost:8910"


async def main() -> None:
    sio = socketio.AsyncClient()
    got: dict = {}

    @sio.on("state_update")
    async def _su(data):
        got.setdefault("states", []).append(data["state"])

    @sio.on("action_result")
    async def _ar(data):
        got.setdefault("results", []).append(data)

    @sio.on("room_update")
    async def _ru(data):
        got["room"] = data

    @sio.on("error")
    async def _err(data):
        got.setdefault("errors", []).append(data)

    await sio.connect(URL)

    for attempt in range(10):
        await sio.emit("create_room", {})
        await asyncio.sleep(0.4)
        await sio.emit("setup_game", {
            "scenario_id": "the_gathering",
            "investigator_id": "daisy_walker",
            "deck_preset": "daisy_walker_starter",
        })
        await asyncio.sleep(1.2)
        state = got["states"][-1]
        hand_ids = [c["id"] for c in state["hand"]]
        if "magnifying_glass_lv0" in hand_ids:
            break
        got["states"].clear()
    else:
        print("magnifying glass never in opening hand after 10 tries")
        sys.exit(1)

    # no bonuses before playing
    assert state["investigator"].get("skill_bonuses", {}) == {}, state["investigator"]
    print("✓ opening state: no skill_bonuses")

    # keep hand (close mulligan), then play magnifying glass
    await sio.emit("player_action", {"action": "MULLIGAN", "card_ids": []})
    await asyncio.sleep(0.6)
    await sio.emit("player_action", {"action": "PLAY", "card_id": "magnifying_glass_lv0"})
    await asyncio.sleep(0.8)
    res = got["results"][-1]
    assert res["success"], res
    # 行动者的最新状态在 action_result.state 里（state_update 广播会跳过行动者）
    state = res["state"]
    bonuses = state["investigator"].get("skill_bonuses", {})
    assert bonuses.get("intellect") == 1, bonuses
    print(f"✓ after playing magnifying glass: skill_bonuses={bonuses}")

    # investigate: outcome events should include asset_bonus
    await sio.emit("player_action", {"action": "INVESTIGATE", "committed_cards": []})
    await asyncio.sleep(1.0)
    res = got["results"][-1]
    outcome = next(
        (e for e in res.get("events", [])
         if e["event"] in ("SKILL_TEST_SUCCESSFUL", "SKILL_TEST_FAILED")),
        None,
    )
    assert outcome is not None, res.get("events")
    assert outcome.get("asset_bonus") == 1, outcome
    sources = outcome.get("skill_bonus_sources", [])
    assert any(s["reason"] == "magnifying_glass_bonus" for s in sources), sources
    print(f"✓ investigate outcome: modified_skill={outcome['modified_skill']} "
          f"asset_bonus={outcome['asset_bonus']} sources={sources}")

    await sio.disconnect()
    print("\n🎉 asset bonus display pipeline verified")


if __name__ == "__main__":
    asyncio.run(main())
