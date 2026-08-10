"""Dream-Gate (Level 0) — Neutral Location. Bonded (Gate Box).
梦之门与其他每个已揭示地点互相连接。除卢克·罗宾逊外的敌人和调查员
不能进入梦之门。
强制 - 调查阶段结束时：将梦之门置于一旁，移出游戏。（若卢克·罗宾逊
在此，将他移动到任意已揭示地点。）

简化说明：
- "与每个已揭示地点互相连接"：引擎的地点连接是静态卡面数据，不支持
  动态连接（引擎缺口），未接线。
- "仅卢克·罗宾逊可进入"由会话层在移动时过滤（引擎移动不咨询卡牌）。
- 阶段结束置于一旁：从 state.locations 移除并记入
  scenario.vars["set_aside_locations"]；在梦之门的调查员移动到第一个
  其他已揭示地点（官方为卢克选择任意已揭示地点——自动选第一个）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DreamGate(CardImplementation):
    card_id = "dream_gate_lv0"

    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.FORCED)
    def set_aside(self, ctx):
        """调查阶段结束时：梦之门置于一旁，移出游戏。"""
        game_state = ctx.game_state
        gate = game_state.locations.get("dream_gate_lv0")
        if gate is None:
            return

        # 在梦之门的调查员移动到任意已揭示地点（自动选第一个）
        fallback = None
        for loc_id, loc in game_state.locations.items():
            if loc_id != "dream_gate_lv0" and loc.revealed:
                fallback = loc_id
                break
        for inv in game_state.investigators.values():
            if inv.location_id == "dream_gate_lv0" and fallback is not None:
                inv.location_id = fallback
                ctx.extra.setdefault("dream_gate_moved", []).append(
                    inv.investigator_id)

        game_state.locations.pop("dream_gate_lv0")
        game_state.scenario.vars.setdefault(
            "set_aside_locations", []).append("dream_gate_lv0")
        ctx.extra["dream_gate_set_aside"] = True
        game_state.log_effect("🌀 梦之门：置于一旁，移出游戏")
