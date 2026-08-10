"""Butterfly Swords (Level 5) — Guardian Asset, Hand x2. (08030)
[行动]：攻击。本次攻击你获得+2战斗。本次攻击后，你可以再次攻击，
该次攻击你将敏捷加到技能值上。如果两次攻击都成功，你可以横置蝴蝶双刀
令第二次攻击造成+1伤害。

简化说明：
- 继承 lv2 流程；再次攻击不需预先横置。
- "两次都成功可横置令第二次+1伤害"：简化为第二次攻击成功且第一次也成功时
  自动横置（横置无其他代价）；已横置则无法获得该加值。
"""

from backend.cards.guardian.butterfly_swords_lv2 import ButterflySwordsLv2


class ButterflySwordsLv5(ButterflySwordsLv2):
    card_id = "butterfly_swords_lv5"
    combat_bonus_amount = 2
    followup_requires_exhaust = False
    followup_bonus_damage = 0  # +1 伤害改由 _on_followup_success 条件横置结算
    activations = [{
        "id": "fight_again",
        "label": "再次攻击（加敏捷；双成功可横置+1伤害）",
        "method": "activate_fight_again",
        "actions": 1,
        "target": "enemy",
    }]

    def _on_followup_success(self, ctx):
        """两次攻击都成功：自动横置，第二次攻击+1伤害。"""
        if not self._first_attack_success:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        inst.exhausted = True
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
        ctx.extra["butterfly_swords_followup_bonus"] = True
        ctx.game_state.log_effect("🦋 蝴蝶对剑(5)：两次攻击均成功，横置+1伤害")
