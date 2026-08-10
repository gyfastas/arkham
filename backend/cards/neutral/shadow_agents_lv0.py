"""Shadow Agents (Level 0) — Neutral Enemy, Signature Weakness (Trish Scarborough). (07011)
猎物 - 仅限翠西·斯卡博勒。猎手。
暗影特工与你交战时，你不能通过调查以外的方式发现线索。
强制 - 在暗影特工被躲避后：丢弃它。

简化说明：
- 敌人生成/交战通道未接线（同 graveyard_ghouls_lv0 的说明），由会话层负责。
- "不能通过调查以外的方式发现线索"由 can_discover_clues() 供会话层查询
  （引擎的 CLUE_DISCOVERED 无来源区分的前置取消钩子）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ShadowAgents(CardImplementation):
    card_id = "shadow_agents_lv0"

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.WHEN)
    def discard_on_evaded(self, ctx):
        """强制 - 被躲避后：丢弃暗影特工。"""
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None or enemy.card_id != "shadow_agents_lv0":
            return
        # 躲避结算（威胁区→地点）已发生；直接从场上移除并放入持有者弃牌堆
        for inv in ctx.game_state.investigators.values():
            if ctx.enemy_id in inv.threat_area:
                inv.threat_area.remove(ctx.enemy_id)
        for loc in ctx.game_state.locations.values():
            if ctx.enemy_id in loc.enemies:
                loc.enemies.remove(ctx.enemy_id)
        ctx.game_state.cards_in_play.pop(ctx.enemy_id, None)
        owner = ctx.game_state.get_investigator(enemy.owner_id)
        if owner is not None:
            owner.discard.append("shadow_agents_lv0")
        ctx.extra["shadow_agents_discarded"] = True

    def can_discover_clues(self, game_state, investigator_id, by_investigating: bool = False) -> bool:
        """与你交战时：仅允许通过调查发现线索。"""
        if by_investigating:
            return True
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "shadow_agents_lv0":
                return False
        return True
