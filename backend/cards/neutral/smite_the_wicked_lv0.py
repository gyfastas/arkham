"""Smite the Wicked — Neutral Treachery, Signature Weakness (Zoey Samaras).
显现：从遭遇牌堆顶弃牌，直到弃掉1张敌人，将其生成在离你最远的地点上，
并将击退邪恶叠加到该敌人卡。
强制 - 游戏结束时，如果被叠加的敌人在场：佐伊·萨马拉斯受到1点精神创伤。

简化说明：
- "最远的地点"用 BFS 连接距离计算（无连接信息时取任一其他地点）。
- 叠加关系记录在 scenario.vars["smite_the_wicked_enemy"]。
- 游戏结束的精神创伤由 game_end_penalty() 提供给会话层结算。
"""

from collections import deque

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class SmiteTheWicked(CardImplementation):
    card_id = "smite_the_wicked_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "smite_the_wicked_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "smite_the_wicked_lv0" in inv.hand:
            inv.hand.remove("smite_the_wicked_lv0")

        scenario = ctx.game_state.scenario

        # 从遭遇牌堆顶弃牌直到弃掉1张敌人
        enemy_card_id = None
        deck = scenario.encounter_deck
        while deck:
            top = deck.pop(0)
            scenario.encounter_discard.append(top)
            data = ctx.game_state.get_card_data(top)
            if data is not None and data.type == CardType.ENEMY:
                enemy_card_id = top
                break

        if enemy_card_id is None:
            # 没有敌人：本卡效果结束，进弃牌堆
            inv.discard.append("smite_the_wicked_lv0")
            return

        # 生成在离你最远的地点
        target_loc = self._farthest_location(ctx.game_state, inv.location_id)

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        enemy = CardInstance(
            instance_id=inst_id,
            card_id=enemy_card_id,
            owner_id="scenario",
            controller_id="scenario",
            attached_to=target_loc,  # 所在地点
        )
        ctx.game_state.cards_in_play[inst_id] = enemy
        loc_state = ctx.game_state.get_location(target_loc)
        if loc_state is not None and inst_id not in loc_state.enemies:
            loc_state.enemies.append(inst_id)
        scenario.encounter_discard.remove(enemy_card_id)  # 敌人改为入场而非弃掉

        # 击退邪恶叠加到该敌人（留在威胁区域记录）
        ci = CardInstance(
            instance_id=ctx.game_state.next_instance_id(),
            card_id="smite_the_wicked_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[ci.instance_id] = ci
        inv.threat_area.append(ci.instance_id)
        scenario.vars["smite_the_wicked_enemy"] = inst_id

    def game_end_penalty(self, game_state, investigator_id) -> str | None:
        """游戏结束结算：被叠加的敌人在场则受1点精神创伤。"""
        scenario = game_state.scenario
        enemy_iid = scenario.vars.get("smite_the_wicked_enemy")
        if enemy_iid and enemy_iid in game_state.cards_in_play:
            inv = game_state.get_investigator(investigator_id)
            if inv is not None:
                inv.mental_trauma = getattr(inv, "mental_trauma", 0) + 1
            return "被击退邪恶叠加的敌人仍在场：受到1点精神创伤"
        return None

    @staticmethod
    def _farthest_location(game_state, start_location_id) -> str:
        """BFS 计算连接距离最远的地点；无连接信息时返回任一其他地点。"""
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
            # 无连接信息：取任一不同地点
            for loc_id in locations:
                if loc_id != start_location_id:
                    return loc_id
            return start_location_id
        return max(dist, key=lambda k: dist[k])
