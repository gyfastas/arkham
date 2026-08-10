"""Improvised Weapon (Level 0) — Survivor Event. (02231 批次)
You may play Improvised Weapon from your discard pile. If you do, shuffle
it into your deck after resolving its effects.
Fight. The attacked enemy gets -1 fight for this attack. (If you played
Improvised Weapon from your discard pile, this attack deals +1 damage.)

简化说明：
- 战斗检定由卡牌自身回放（CardSelfTest，无投入窗口；同 waylay 模式），
  成功后经 _shared.deal_damage_to_enemy 结算伤害（含击败）。
- 目标选择自动化：默认与你交战的第一个敌人，其次你所在地点的敌人；
  可经 ctx.extra["enemy_instance_id"] 指定。
- "从弃牌堆打出"：引擎 _play 要求卡在手牌，弃牌堆直打需会话层支持
  （引擎缺口）；会话层经 ctx.extra["played_from_discard"]=True 标记，
  本实现据此 +1 伤害并在结算后洗回牌库
  （ACTION_PERFORMED/ROUND_ENDS 扫尾，同 nothing_left_to_lose 模式）。
"""

import random

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill, TimingPriority


class ImprovisedWeapon(CardSelfTest):
    card_id = "improvised_weapon_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._shuffle_pending: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def fight(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy_iid = ctx.extra.get("enemy_instance_id") or self._choose_enemy(
            ctx.game_state, inv)
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return

        # 被攻击敌人本次攻击 -1 战斗值
        difficulty = max(0, (enemy_data.enemy_fight or 0) - 1)
        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.COMBAT,
            difficulty, source=self.instance_id,
        )
        if result is None:
            return
        success, _margin = result
        ctx.extra["improvised_weapon_success"] = success
        if not success:
            return

        damage = 1 + (1 if ctx.extra.get("played_from_discard") else 0)
        defeated = deal_damage_to_enemy(
            ctx.game_state, getattr(self, "_selftest_bus", None),
            enemy_iid, damage, defeated_by=inv.investigator_id,
        )
        ctx.extra["improvised_weapon_damage"] = damage
        ctx.game_state.log_effect(
            f"🪑 即兴武器：对【{ctx.game_state.card_name(enemy.card_id)}】"
            f"造成{damage}点伤害" + ("，被击败" if defeated else ""))

        if ctx.extra.get("played_from_discard"):
            self._shuffle_pending = inv.investigator_id

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def sweep_after_action(self, ctx):
        self._sweep(ctx)

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def sweep_after_round(self, ctx):
        self._sweep(ctx)

    def _sweep(self, ctx) -> None:
        """弃牌堆打出的本卡结算后洗入牌库（而非弃置）。"""
        inv_id = self._shuffle_pending
        if inv_id is None:
            return
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is not None and self.card_id in inv.discard:
            inv.discard.remove(self.card_id)
            inv.deck.append(self.card_id)
            random.shuffle(inv.deck)
        self._shuffle_pending = None

    @staticmethod
    def _choose_enemy(game_state, inv) -> str | None:
        """目标：与你交战的第一个敌人优先，其次你所在地点的敌人。"""
        if inv.threat_area:
            return inv.threat_area[0]
        loc = game_state.get_location(inv.location_id)
        if loc is not None and loc.enemies:
            return loc.enemies[0]
        return None
