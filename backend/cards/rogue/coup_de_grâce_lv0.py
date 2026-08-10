"""Coup de Grâce (Level 0) — Rogue Event. (04269)
对你所在地点的1个敌人造成1点伤害。如果本效果击败该敌人，抽取1张卡牌。
如果此时是你的回合，则结束你的回合。此行动不会引起趁乱攻击。

简化说明：
- 目标自动选择：优先 ctx.extra["target_enemy_id"] 指定，否则你交战区的
  第一个敌人，再否则你所在地点的第一个未交战敌人（官方为玩家自选）。
- 伤害经 _shared.deal_damage_to_enemy 直接结算（可击败敌人并触发
  ENEMY_DEFEATED）。
- "如果是你的回合则结束回合"：本卡非快速，按官方时机只能在自己回合打出，
  故简化为打出即结束回合（actions_remaining 置0；回合完整结束流程由
  会话层负责）。
- "不引起趁乱攻击"：卡牌代码无法豁免会话层统一的 AoO 结算（引擎缺口，
  已在报告中列出）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import deal_damage_to_enemy
from backend.models.enums import GameEvent, TimingPriority


class CoupDeGrace(CardImplementation):
    card_id = "coup_de_grâce_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def deal_damage(self, ctx):
        """对你所在地点的1个敌人造成1点伤害；击败则抽1牌；结束你的回合。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 选择目标
        target_id = ctx.extra.get("target_enemy_id")
        if target_id is None:
            if inv.threat_area:
                target_id = inv.threat_area[0]
            else:
                loc = ctx.game_state.get_location(inv.location_id)
                if loc is not None and loc.enemies:
                    target_id = loc.enemies[0]
        if target_id is None:
            return
        enemy = ctx.game_state.get_card_instance(target_id)
        if enemy is None:
            return

        defeated = deal_damage_to_enemy(
            ctx.game_state, self._bus, target_id, 1,
            defeated_by=ctx.investigator_id,
        )
        ctx.extra["coup_de_grace_target"] = target_id
        ctx.game_state.log_effect(
            f"🔪 最后的枪击：对【{ctx.game_state.card_name(enemy.card_id)}】造成1点伤害")

        if defeated:
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
            ctx.extra["coup_de_grace_drew"] = True
            ctx.game_state.log_effect("🔪 最后的枪击：击败敌人，抽1张牌")

        inv.actions_remaining = 0
        ctx.extra["coup_de_grace_ended_turn"] = True
        ctx.game_state.log_effect("🔪 最后的枪击：结束你的回合")
