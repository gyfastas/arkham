"""Infighting (Level 3) — Survivor Event.
快速。敌军阶段开始时打出。取消本阶段所有非精英敌人对你的攻击。

简化说明：
- 从手牌中懒触发（同 dodge 的自动打出简化，官方为阶段开始时玩家自选
  时机）：本阶段首个非精英敌人攻击你时，若手牌中有内斗且资源足够，
  自动打出并取消本次攻击；此后本阶段非精英敌人对你的攻击均被取消。
  对"取消哪些攻击"而言与官方时机等价。
- 仅保护持有者本人（卡面"对你"的攻击）。
- 精英敌人（elite 关键词/精英特性）的攻击不取消。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.scenarios.official_core import is_elite_enemy

_EFFECT_KEY = "infighting_lv3"


class Infighting(CardImplementation):
    card_id = "infighting_lv3"
    persistent_in_hand = True  # 在手牌中持续监听敌人攻击窗口

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def cancel_non_elite_attack(self, ctx):
        """取消本阶段非精英敌人对你的攻击。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id) if ctx.enemy_id else None
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is None or is_elite_enemy(enemy_data):
            return

        if not getattr(inv, "active_effects", {}).get(_EFFECT_KEY):
            # 懒自动打出（简化：官方为敌军阶段开始时打出）
            if self.card_id not in inv.hand:
                return
            cd = ctx.game_state.get_card_data(self.card_id)
            cost = (getattr(cd, "cost", 1) or 1) if cd else 1
            if inv.resources < cost:
                return
            inv.resources -= cost
            inv.hand.remove(self.card_id)
            inv.discard.append(self.card_id)
            if not hasattr(inv, "active_effects"):
                inv.active_effects = {}
            inv.active_effects[_EFFECT_KEY] = True
            ctx.game_state.log_effect(
                "🥊 内斗：打出，本阶段非精英敌人对你的攻击均被取消")

        ctx.cancel()
        ctx.extra["infighting_cancelled"] = True

    @on_event(GameEvent.ENEMY_PHASE_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """本阶段结束：效果过期。"""
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None)
            if effects:
                effects.pop(_EFFECT_KEY, None)
