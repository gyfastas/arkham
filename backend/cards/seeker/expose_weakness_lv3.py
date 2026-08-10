"""Expose Weakness (Level 3) — Seeker Event, Fast. (04195)
快速。选择一个在你地点的敌人。检定智力(X)，X为该敌人的战斗力。
如果你成功，本阶段下次对该敌人执行攻击时，将其战斗力视为0。抽取1张卡牌。

简化说明（继承 lv1 的机制，差异：视为0 + 成功后抽1张）：
- 目标默认为你所在地点的第一个敌人（交战优先），可用 ctx.extra["enemy_instance_id"] 指定；
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）；
- "战斗力视为0"以记录敌人当前战斗力、下次攻击按其全值降低难度实现，
  阶段结束（调查/敌人）时过期。
"""

from backend.cards.base import on_event
from backend.cards.seeker.expose_weakness_lv1 import ExposeWeakness as ExposeWeaknessLv1
from backend.models.enums import GameEvent, Skill, TimingPriority


class ExposeWeaknessLv3(ExposeWeaknessLv1):
    card_id = "expose_weakness_lv3"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def test_intellect_vs_fight(self, ctx):
        if ctx.extra.get("card_id") != "expose_weakness_lv3":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy = self._choose_target(ctx, inv)
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return

        fight = enemy_data.enemy_fight or 0
        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.INTELLECT,
            fight, source=self.instance_id,
        )
        if result is None:
            return
        success, _margin = result
        ctx.extra["expose_weakness_success"] = success
        if success:
            # 视为0：记录全额战斗力，下次攻击按其全值降低难度（下限0）
            self._fight_reductions[enemy.instance_id] = fight
            ctx.extra["expose_weakness_reduction"] = fight
            ctx.game_state.log_effect(
                f"🎯 暴露弱点(3级)：成功，本阶段下一次对其攻击其战斗力视为0"
            )
        # "Draw 1 card" 独立成句：无论成败均抽1张
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["expose_weakness_drew"] = True
