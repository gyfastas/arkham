"""Mob Goons (Level 0) — Neutral Enemy, Weakness (Daniela Reyes).
猎手。
猎物 - 仅限丹妮拉·雷耶斯。
本敌人的攻击不能被取消。
本敌人攻击造成的伤害/恐惧视为直接伤害/恐惧。

简化说明：
- 猎物/猎手与生成通道由会话层负责（同 graveyard_ghouls_lv0 说明；
  敌人数值不在玩家卡 JSON 加载通道内）。
- "视为直接"：ENEMY_ATTACKS(WHEN) 时直接对调查员施加伤害/恐惧并取消
  引擎的常规承伤分配流程（官方直接伤害不分配给支援卡）。
- "不能被取消"的局限：若有更早注册的取消攻击效果抢先 cancel，
  事件循环会中断、本 handler 不再执行（引擎缺口）；正常无取消效果时
  行为正确。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class MobGoons(CardImplementation):
    card_id = "mob_goons_lv0"

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def direct_attack(self, ctx):
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None or enemy.card_id != "mob_goons_lv0":
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if enemy_data is None or inv is None:
            return
        dmg = enemy_data.enemy_damage or 0
        hor = enemy_data.enemy_horror or 0
        inv.damage += dmg  # 直接伤害/恐惧（不分配）
        inv.horror += hor
        ctx.cancel()  # 跳过引擎的常规承伤分配
        ctx.game_state.log_effect(
            f"👊 帮派打手：攻击不能被取消，{dmg}伤害/{hor}恐惧视为直接"
        )
