"""Tony's Quarry (Level 0) — Neutral Enemy, Signature Weakness (Tony Morgan).
生成 - 离托尼·摩尔根最远的地点。冷漠。
强制 - 在托尼的猎物入场后：在其上放置1个毁灭标记。然后放置1资源在其上，
作为赏金。

官方数值（arkhamdb 06012，玩家卡 JSON 通道不含 enemy_* 字段，需会话/数据
层接线；测试以 make_enemy_data 注入）：战斗4 / 生命3 / 躲避1 / 伤害1 / 恐惧2。

简化说明：
- 抽到（CARD_DRAWN）时视为生成：从手牌移除，生成在离持有者连接距离最远
  的地点（BFS，与 smite_the_wicked_lv0 同一算法）；毁灭与赏金在生成时
  一并放置（官方"入场后"强制效果紧邻生成，合并结算）。
- 赏金以 uses["bounty"] 计数（与 tonys_38_long_colt_lv0 共读）。
- "冷漠"关键词与猎物/移动行为依赖敌人 AI 通道，引擎缺口。
"""

from collections import deque

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class TonysQuarry(CardImplementation):
    card_id = "tonys_quarry_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def spawn_on_draw(self, ctx):
        if ctx.extra.get("card_id") != "tonys_quarry_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "tonys_quarry_lv0" in inv.hand:
            inv.hand.remove("tonys_quarry_lv0")

        # 生成在离持有者最远的地点
        target_loc = self._farthest_location(ctx.game_state, inv.location_id)

        inst_id = ctx.game_state.next_instance_id()
        enemy = CardInstance(
            instance_id=inst_id,
            card_id="tonys_quarry_lv0",
            owner_id=inv.investigator_id,  # 承受者（猎物/归属判定用）
            controller_id="scenario",
            attached_to=target_loc,
        )
        ctx.game_state.cards_in_play[inst_id] = enemy
        loc_state = ctx.game_state.get_location(target_loc)
        if loc_state is not None and inst_id not in loc_state.enemies:
            loc_state.enemies.append(inst_id)

        # 强制 - 入场后：1毁灭 + 1赏金
        enemy.doom += 1
        enemy.uses["bounty"] = enemy.uses.get("bounty", 0) + 1

        ctx.game_state.log_effect(
            f"🎯 托尼的猎物：生成于【{target_loc}】，放置1毁灭与1赏金")
        ctx.extra["tonys_quarry_spawned"] = inst_id

    @staticmethod
    def _farthest_location(game_state, start_location_id) -> str:
        """BFS 计算连接距离最远的地点；无连接信息时取任一其他地点。"""
        locations = game_state.locations
        if not locations:
            return start_location_id
        if start_location_id not in locations:
            return next(iter(locations))

        dist = {start_location_id: 0}
        queue = deque([start_location_id])
        while queue:
            current = queue.popleft()
            loc = locations.get(current)
            if loc is None:
                continue
            for nxt in getattr(loc, "connections", []) or []:
                if nxt in locations and nxt not in dist:
                    dist[nxt] = dist[current] + 1
                    queue.append(nxt)

        if len(dist) <= 1:
            for loc_id in locations:
                if loc_id != start_location_id:
                    return loc_id
            return start_location_id
        return max(dist, key=lambda k: dist[k])
