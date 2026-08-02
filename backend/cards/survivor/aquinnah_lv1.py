"""Aquinnah (Level 1) — Survivor Asset, Ally slot.
反应 - 当你受到敌人伤害时：弃置安奎娜。取消该伤害，改为对该敌人造成1点伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import CardType, GameEvent, TimingPriority


class AquinnahLv1(CardImplementation):
    card_id = "aquinnah_lv1"
    reflect_damage = 1

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def reflect(self, ctx):
        """受到敌人伤害时：弃置安奎娜，取消伤害并反弹。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if (ctx.amount or 0) < 1:
            return
        attacker = ctx.game_state.get_card_instance(ctx.source) if ctx.source else None
        if attacker is None:
            return
        attacker_data = ctx.game_state.get_card_data(attacker.card_id)
        if attacker_data is None or attacker_data.type != CardType.ENEMY:
            return

        # 取消伤害
        ctx.modify_amount(-ctx.amount, "aquinnah_cancel")
        # 弃置安奎娜
        vacate_asset_slots(ctx.game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
        # 反弹伤害
        attacker.damage += self.reflect_damage
        ctx.extra["aquinnah_reflected"] = self.reflect_damage
        ctx.game_state.log_effect(
            f"🛡️ 安奎娜：弃置并取消伤害，反弹{self.reflect_damage}点伤害")
